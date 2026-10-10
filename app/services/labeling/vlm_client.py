"""视觉大模型（VLM）客户端：OpenAI 兼容的 chat/completions 接口

提供方：
- openrouter：云端（OpenRouter），按量计费，请求时要求 data_collection=deny；
- openai_compatible：本地部署的 llama.cpp / vLLM 等（图片不出网）；
- mock：不调任何模型，用 OpenCV 找画面中与背景差异最大的主体，离线测试与演示用。

稳定性设计：
- httpx 异步 + 信号量限制并发；429/5xx/超时按指数退避重试（尊重 Retry-After）；
- 401/403 视为配置错误立即终止（VLMAuthError），不做无意义的重试；
- 单张图失败只影响这一张（结果标记失败，后续进入复核/剔除），不拖垮整个阶段；
- 结果按"发送的图片内容 + 模型 + 提示词版本 + 类别"缓存，服务重启后续跑不重复计费。
"""
import asyncio
import base64
import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.core.config import settings
from app.services.labeling.json_extract import ExtractError, parse_detections
from app.services.labeling.prompt import DEFAULT_STYLE, build_prompt, label_aliases, prompt_version

logger = logging.getLogger(__name__)


class VLMAuthError(Exception):
    """鉴权/配置错误（密钥无效、无权限、模型不存在），重试没有意义"""


@dataclass
class VLMRequest:
    key: str
    image_path: Path
    classes: List[Dict]
    # 参考图：[{"label": 类别名, "image": JPEG 字节}]。只给文字描述时，模型往往认不出特定的小物件；
    # 附上该类物品的裁剪图（"它长这样"）能明显提高识别率
    references: List[Dict] = field(default_factory=list)
    image: Optional[np.ndarray] = None   # 直接给图像（如参考图候选的裁剪），此时不读 image_path


@dataclass
class VLMResult:
    key: str
    ok: bool
    boxes: List[Dict] = field(default_factory=list)   # [{"label", "raw_label", "label_matched", "xyxy"}]，原图像素坐标
    raw_text: Optional[str] = None
    error: Optional[str] = None
    error_kind: Optional[str] = None                  # timeout / http / parse / image
    usage: Dict = field(default_factory=dict)
    cached: bool = False
    coord_mode: Optional[str] = None
    image_size: Tuple[int, int] = (0, 0)
    dropped_items: int = 0                             # 标签不在类别列表或坐标非法而被丢弃的项


def default_coord_mode(model: str) -> str:
    """不同模型的坐标约定：Qwen2.5-VL 输出输入图上的绝对像素，Qwen3-VL 及之后输出 0~1000 相对坐标"""
    m = (model or "").lower()
    if "qwen2.5" in m or "qwen2_5" in m:
        return "abs"
    return "rel1000"


def to_original_coords(bbox, mode: str, sent_size: Tuple[int, int], orig_size: Tuple[int, int],
                       model_default: str = "rel1000") -> Tuple[Tuple[float, float, float, float], str]:
    """模型坐标 -> 原图像素坐标，返回 (框, 实际采用的坐标约定)"""
    x1, y1, x2, y2 = bbox
    used = mode
    if mode == "auto":
        top = max(bbox)
        if top <= 1.0 + 1e-6:
            used = "rel1"
        elif top > 1000.0 + 1e-6:
            used = "abs"       # 超过 1000 只可能是像素坐标
        else:
            used = model_default
    W, H = orig_size
    if used == "rel1":
        sx, sy = W, H
    elif used == "rel1000":
        sx, sy = W / 1000.0, H / 1000.0
    else:  # abs：模型看到的是缩放后的图
        sx, sy = W / max(sent_size[0], 1), H / max(sent_size[1], 1)
    box = (x1 * sx, y1 * sy, x2 * sx, y2 * sy)
    box = (min(max(box[0], 0.0), W), min(max(box[1], 0.0), H), min(max(box[2], 0.0), W), min(max(box[3], 0.0), H))
    return box, used


def _read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)   # 兼容中文路径
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"无法读取图片: {path}")
    return img


def _encode_for_model(img: np.ndarray, max_long_edge: int, min_long_edge: int = 0) -> Tuple[bytes, Tuple[int, int]]:
    """缩放后编码为 JPEG：长边超过 max_long_edge 时缩小（图片 token 数和费用随分辨率增长）；
    低于 min_long_edge 时放大——小分辨率画面里的小物件只占模型的寥寥几个图像块，放大后更容易被认出。
    坐标是相对值（或按发送尺寸换算），缩放不影响精度换算"""
    h, w = img.shape[:2]
    long_edge = float(max(h, w))
    scale = min(1.0, max_long_edge / long_edge)
    if min_long_edge and long_edge < min_long_edge:
        scale = min(min_long_edge, max_long_edge) / long_edge
    if scale != 1.0:
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        img = cv2.resize(img, (max(1, int(round(w * scale))), max(1, int(round(h * scale)))), interpolation=interp)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise ValueError("图片编码失败")
    return buf.tobytes(), (img.shape[1], img.shape[0])


def mock_localize(img: np.ndarray, classes: List[Dict]) -> str:
    """mock 提供方：找出与背景（取图像边缘一圈的中位色）差异最大的连通区域，返回 0~1000 坐标的 JSON

    只适合"单件文物 + 相对干净的背景"，用于离线跑通流程，不是真正的识别。
    """
    h, w = img.shape[:2]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    bg = np.median(border, axis=0)
    dist = np.linalg.norm(lab - bg, axis=2)
    _, mask = cv2.threshold(dist.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return "[]"
    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < 0.002 * w * h:
        return "[]"
    x, y, bw, bh = cv2.boundingRect(c)
    bbox = [round(x / w * 1000), round(y / h * 1000), round((x + bw) / w * 1000), round((y + bh) / h * 1000)]
    return json.dumps([{"label": classes[0]["name"], "bbox": bbox}])


class VLMClient:
    def __init__(self, provider: str, model: str, *, coord_mode: str = "auto", max_long_edge: int = 1024,
                 cache_dir: Optional[Path] = None, timeout: Optional[float] = None,
                 max_retries: Optional[int] = None, concurrency: Optional[int] = None,
                 prompt_style: str = DEFAULT_STYLE, min_long_edge: int = 0):
        self.provider = provider
        self.model = model
        self.prompt_style = prompt_style
        self.prompt_version = prompt_version(prompt_style)
        self.coord_mode = coord_mode
        self.model_default_coord = default_coord_mode(model)
        self.max_long_edge = max_long_edge
        self.min_long_edge = min_long_edge
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.timeout = timeout or settings.VLM_TIMEOUT_SECONDS
        self.max_retries = settings.VLM_MAX_RETRIES if max_retries is None else max_retries
        self.concurrency = max(1, concurrency or settings.VLM_MAX_CONCURRENCY)
        if provider == "openrouter":
            self.base_url, self.api_key = settings.OPENROUTER_BASE_URL, settings.OPENROUTER_API_KEY
        elif provider == "openai_compatible":
            self.base_url, self.api_key = settings.OPENAI_COMPATIBLE_BASE_URL, settings.OPENAI_COMPATIBLE_API_KEY
        elif provider == "mock":
            self.base_url, self.api_key = "", ""
        else:
            raise ValueError(f"不支持的视觉模型提供方: {provider}")

    # ------------------------------------------------------------------
    def _cache_key(self, image_bytes: bytes, classes: List[Dict], references: Optional[List[Dict]] = None) -> str:
        h = hashlib.sha1(image_bytes)
        for ref in references or []:
            h.update(ref["label"].encode() + hashlib.sha1(ref["image"]).digest())
        h.update(f"|{self.provider}|{self.model}|{self.prompt_version}|".encode())
        h.update(json.dumps([[c["name"], c.get("prompt"), c.get("display_name")] for c in classes], ensure_ascii=False).encode())
        return h.hexdigest()

    def _cache_get(self, key: str) -> Optional[Dict]:
        if not self.cache_dir:
            return None
        path = self.cache_dir / key[:2] / f"{key}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _cache_put(self, key: str, value: Dict):
        if not self.cache_dir:
            return
        path = self.cache_dir / key[:2] / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    # ------------------------------------------------------------------
    def _payload(self, prompt: str, image_bytes: bytes, references: Optional[List[Dict]] = None) -> Dict:
        def image_part(data: bytes) -> Dict:
            return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(data).decode()}}

        content = [{"type": "text", "text": prompt}]
        if references:
            content.append({"type": "text", "text": "下面是各类物品的参考图，只用来认识它们的外观，不要对参考图作答："})
            for ref in references:
                content.append({"type": "text", "text": f"参考图：{ref['label']}"})
                content.append(image_part(ref["image"]))
            content.append({"type": "text", "text": "需要标注的图片（坐标只针对这一张）："})
        content.append(image_part(image_bytes))
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 512,
            "messages": [{"role": "user", "content": content}],
        }
        if self.provider == "openrouter":
            payload["usage"] = {"include": True}                 # 让 OpenRouter 返回本次费用
            payload["provider"] = {"data_collection": "deny"}     # 只路由到承诺不留存/不训练数据的服务商
        return payload

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.provider == "openrouter":
            headers["X-Title"] = "Myolotrain"
            if settings.PUBLIC_BASE_URL:
                headers["HTTP-Referer"] = settings.PUBLIC_BASE_URL
        return headers

    @staticmethod
    def _content_text(data: Dict) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ExtractError("返回结构不符合 OpenAI 兼容格式")
        if isinstance(content, list):
            return "\n".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in content)
        return str(content or "")

    async def _call_api(self, client, prompt: str, image_bytes: bytes,
                        references: Optional[List[Dict]] = None) -> Tuple[str, Dict]:
        import httpx

        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = self._payload(prompt, image_bytes, references)
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await client.post(url, json=payload, headers=self._headers())
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_error = f"{type(e).__name__}: {e}"
                kind = "timeout" if isinstance(e, httpx.TimeoutException) else "http"
            else:
                if resp.status_code in (401, 403):
                    raise VLMAuthError(f"视觉模型接口鉴权失败（HTTP {resp.status_code}），请检查 API Key 和权限: {resp.text[:200]}")
                if resp.status_code == 404:
                    raise VLMAuthError(f"视觉模型或接口地址不存在（HTTP 404）: {resp.text[:200]}")
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError:
                        data = {"error": f"返回内容不是 JSON: {resp.text[:200]}"}
                    if isinstance(data, dict) and data.get("error"):
                        last_error, kind = f"接口返回错误: {str(data['error'])[:200]}", "http"
                    else:
                        return self._content_text(data), dict(data.get("usage") or {})
                elif resp.status_code == 429 or resp.status_code >= 500:
                    last_error, kind = f"HTTP {resp.status_code}: {resp.text[:200]}", "http"
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit() and attempt < self.max_retries:
                        await asyncio.sleep(min(60, int(retry_after)))
                        continue
                else:
                    # 其他 4xx 多半是这张图或参数有问题，重试也一样
                    raise _PermanentRequestError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            if attempt < self.max_retries:
                await asyncio.sleep(min(30.0, 2 ** attempt + random.random()))
        raise _RetryExhausted(last_error or "未知错误", kind)

    # ------------------------------------------------------------------
    def _interpret(self, req: VLMRequest, text: str, sent_size, orig_size) -> VLMResult:
        result = VLMResult(key=req.key, ok=True, raw_text=text, image_size=orig_size)
        aliases = label_aliases(req.classes)
        single = len(req.classes) == 1
        try:
            items = parse_detections(text)
        except ExtractError as e:
            result.ok, result.error, result.error_kind = False, f"无法解析模型回复: {e}", "parse"
            return result
        modes = set()
        for item in items:
            raw_label = item["label"]
            label = aliases.get(raw_label.lower())
            matched = label is not None
            if not matched:
                if not single:
                    result.dropped_items += 1
                    continue
                label = req.classes[0]["name"]   # 只问了一个类别：标签写法不一致也认，但记下来
            box, used = to_original_coords(item["bbox"], self.coord_mode, sent_size, orig_size, self.model_default_coord)
            modes.add(used)
            if box[2] - box[0] < 1 or box[3] - box[1] < 1:
                result.dropped_items += 1
                continue
            result.boxes.append({"label": label, "raw_label": raw_label, "label_matched": matched,
                                 "xyxy": [round(v, 2) for v in box]})
        result.coord_mode = ",".join(sorted(modes)) if modes else None
        return result

    async def _detect_one(self, client, sem, req: VLMRequest) -> VLMResult:
        """保证每张图都返回一个结果（失败也是结果），只有鉴权类错误向上抛出"""
        try:
            return await self._detect_one_inner(client, sem, req)
        except VLMAuthError:
            raise
        except ExtractError as e:
            return VLMResult(key=req.key, ok=False, error=f"无法解析模型回复: {e}", error_kind="parse")
        except Exception as e:
            logger.exception(f"VLM 处理 {req.image_path} 时出现未预期的错误")
            return VLMResult(key=req.key, ok=False, error=f"{type(e).__name__}: {e}", error_kind="internal")

    async def _detect_one_inner(self, client, sem, req: VLMRequest) -> VLMResult:
        try:
            img = req.image if req.image is not None else _read_image(req.image_path)
            image_bytes, sent_size = _encode_for_model(img, self.max_long_edge, self.min_long_edge)
        except Exception as e:
            return VLMResult(key=req.key, ok=False, error=str(e), error_kind="image")
        orig_size = (img.shape[1], img.shape[0])

        cache_key = self._cache_key(image_bytes, req.classes, req.references)
        cached = self._cache_get(cache_key)
        if cached is not None:
            res = self._interpret(req, cached["raw_text"], tuple(cached.get("sent_size") or sent_size), orig_size)
            res.cached = True
            return res

        if self.provider == "mock":
            text, usage = mock_localize(img, req.classes), {}
        else:
            prompt = build_prompt(req.classes, self.prompt_style)
            async with sem:
                try:
                    text, usage = await self._call_api(client, prompt, image_bytes, req.references)
                except _PermanentRequestError as e:
                    return VLMResult(key=req.key, ok=False, error=str(e), error_kind="http", image_size=orig_size)
                except _RetryExhausted as e:
                    return VLMResult(key=req.key, ok=False, error=f"重试 {self.max_retries} 次后仍失败: {e}",
                                     error_kind=e.kind, image_size=orig_size)
        self._cache_put(cache_key, {"raw_text": text, "usage": usage, "sent_size": list(sent_size),
                                    "model": self.model, "prompt_version": self.prompt_version, "ts": int(time.time())})
        res = self._interpret(req, text, sent_size, orig_size)
        res.usage = usage
        return res

    def detect_batch(self, requests: List[VLMRequest],
                     on_result: Optional[Callable[[VLMResult], None]] = None,
                     should_stop: Optional[Callable[[], bool]] = None) -> Dict[str, VLMResult]:
        """批量检测。在独立的事件循环里运行（流水线工作线程中调用，不占用 Web 服务的事件循环）

        on_result 每完成一张调用一次；should_stop 返回 True 时尽快停止（未开始的请求不再发出）。
        VLMAuthError 会直接抛出给调用方。
        """
        return asyncio.run(self._detect_batch(requests, on_result, should_stop))

    async def _detect_batch(self, requests, on_result, should_stop) -> Dict[str, VLMResult]:
        import httpx

        results: Dict[str, VLMResult] = {}
        sem = asyncio.Semaphore(self.concurrency)
        limits = httpx.Limits(max_connections=self.concurrency * 2, max_keepalive_connections=self.concurrency)
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=15.0), limits=limits) as client:
            pending = list(requests)
            running = set()
            while pending or running:
                while pending and len(running) < self.concurrency * 2:
                    if should_stop and should_stop():
                        pending.clear()
                        break
                    running.add(asyncio.create_task(self._detect_one(client, sem, pending.pop(0))))
                if not running:
                    break
                done, running = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    exc = task.exception()
                    if isinstance(exc, VLMAuthError):
                        for t in running:
                            t.cancel()
                        raise exc
                    if exc is not None:
                        logger.exception("VLM 请求出现未预期的异常", exc_info=exc)
                        continue
                    res = task.result()
                    results[res.key] = res
                    if on_result:
                        on_result(res)
        return results

    def test_connection(self, image_path: Path, classes: List[Dict]) -> VLMResult:
        """用一张图测试配置与连通性（控制台"测试视觉模型"按钮用）"""
        self.cache_dir = None
        return self.detect_batch([VLMRequest(key="test", image_path=image_path, classes=classes)])["test"]


class _PermanentRequestError(Exception):
    pass


class _RetryExhausted(Exception):
    def __init__(self, message, kind):
        super().__init__(message)
        self.kind = kind
