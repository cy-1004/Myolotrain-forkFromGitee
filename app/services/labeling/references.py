"""参考图：每个类别一张"它长这样"的裁剪图，随标注请求一起发给视觉模型

只给文字描述（"玉杯（古代玉质饮器）"）时，模型常常认不出画面里特定的那件小文物。
实测（真实文物视频 100 帧，qwen3-vl-235b，只问声明的类别）：

    基线 召回 0.34 / 精确 0.73；只放大到 1280 0.41 / 0.89；只加参考图 0.42 / 0.52；放大 + 参考图 0.74 / 0.85

两者要一起用：小图上参考图反而让模型乱框，放大后才能对照参考图找到目标。

参考图来源：
- 调用方提供（目录照片或裁剪图，可带框）：最可靠；
- 自动挑选（bootstrap）：先不带参考图、只放大，在该类别的若干帧上检测（这种设置下精确率最高），
  从检出框里按面积挑候选，再把候选周围的区域单独发给模型、用全部类别提问核对一次。

核对有三种结果：confirmed（认出是该类别）直接采用；contradicted（在同一位置认成了别的类别）丢弃；
unconfirmed（什么都没认出）只作兜底。之所以不把"没认出"当否定：没有参考图时模型本来就认不出小碗、小杯
这类物件（核对和检测一样难），实测这类候选与人工框比对全部正确，丢掉它们就等于这些最需要参考图的类别永远拿不到。
兜底只接受只声明了一个类别的视频里的候选（标签无歧义）；多类视频里唯一一次挑错就是把布料标成了碗。
只出现在多类视频里的类别（如总是和布料、杯子摆在一起的碗）：先对未确认的候选再核对一次，这次带上其他类别
已确认的参考图；仍未确认时，若有 ≥ 2 个候选，取外观（颜色直方图）与其他候选最相近的那个（consensus）——
挑错的候选（布料被标成碗）与真正的碗长得不像，会被排除。这类参考图在控制台标为"未经核对"，并发警告请人确认。
"""
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from app.services.labeling import geometry
from app.services.labeling.vlm_client import VLMClient, VLMRequest, VLMResult

logger = logging.getLogger(__name__)

REFERENCE_MAX_EDGE = 256      # 参考图长边：再大也只是多花 token，模型认的是外观特征
CROP_MARGIN = 0.15            # 裁剪时框外多留的比例，带一点周围环境更好认
MIN_AREA_RATIO = 0.002        # 候选框占画面的比例范围：太小看不清细节，太大往往是框错了（框住了整张桌子）
MAX_AREA_RATIO = 0.5
GOOD_AREA_RATIO = 0.015       # 候选框占画面这么大（640x480 上约 68x68 像素）时细节已经够用，可以停止探测
PROBE_ROUND = 8               # 每轮每个类别探测的帧数
VERIFY_CONTEXT_FACTOR = 3.0   # 核对时裁剪的区域约为框的 3 倍大小
VERIFY_MIN_SIDE = 192
VERIFY_MIN_IOU = 0.3


@dataclass
class Probe:
    """用于自动挑选参考图的一帧"""
    key: str
    image_path: object
    video: str
    classes: List[Dict]          # 该帧所在视频声明的类别（检测时只问这些）


@dataclass
class Candidate:
    label: str
    probe: Probe
    xyxy: Tuple[float, float, float, float]
    image_size: Tuple[int, int]
    area_ratio: float
    verdict: Optional[str] = None        # confirmed / contradicted / unconfirmed；未核对为 None
    verify_labels: List[str] = field(default_factory=list)

    @property
    def single_class(self) -> bool:
        return len(self.probe.classes) == 1


def _read(path) -> Optional[np.ndarray]:
    try:
        return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    except (OSError, ValueError):
        return None


def crop_array(img: np.ndarray, xyxy: Sequence[float], margin: float = CROP_MARGIN) -> np.ndarray:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = xyxy
    mx, my = (x2 - x1) * margin, (y2 - y1) * margin
    x1, y1 = int(max(0, x1 - mx)), int(max(0, y1 - my))
    x2, y2 = int(min(w, x2 + mx)), int(min(h, y2 + my))
    return img[y1:max(y2, y1 + 1), x1:max(x2, x1 + 1)]


def encode_reference(img: np.ndarray, max_edge: int = REFERENCE_MAX_EDGE) -> bytes:
    scale = max_edge / float(max(img.shape[:2]))
    if scale < 1:
        img = cv2.resize(img, (max(1, int(img.shape[1] * scale)), max(1, int(img.shape[0] * scale))),
                         interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise ValueError("参考图编码失败")
    return buf.tobytes()


def reference_from_upload(data: bytes, box: Optional[Sequence[float]] = None) -> bytes:
    """调用方上传的参考图 -> 标准化的 JPEG（可选按像素框裁剪）。无法解码时抛 ValueError"""
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("无法解码参考图（支持 JPEG/PNG/WebP/BMP）")
    if box is not None:
        x1, y1, x2, y2 = [float(v) for v in box]
        h, w = img.shape[:2]
        if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
            raise ValueError(f"参考图的框 {list(box)} 超出图片范围 {w}x{h}")
        img = crop_array(img, (x1, y1, x2, y2), margin=0.0)
    return encode_reference(img)


def is_good_candidate(xyxy, width: int, height: int) -> bool:
    ratio = geometry.area(xyxy) / float(max(1, width * height))
    return MIN_AREA_RATIO <= ratio <= MAX_AREA_RATIO and geometry.edges_touched(xyxy, width, height) <= 1


def collect_candidates(results: Dict[str, VLMResult], probes: List[Probe], label: str) -> List[Candidate]:
    """某类别在探测帧上的候选框，按面积从大到小，同一视频的候选排在其他视频之后（分散来源）"""
    found = []
    for p in probes:
        res = results.get(p.key)
        if res is None or not res.ok:
            continue
        W, H = res.image_size
        for b in res.boxes:
            if b["label"] != label or not b.get("label_matched", True):
                continue
            if is_good_candidate(b["xyxy"], W, H):
                found.append(Candidate(label=label, probe=p, xyxy=tuple(b["xyxy"]), image_size=(W, H),
                                       area_ratio=geometry.area(b["xyxy"]) / float(W * H)))
    found.sort(key=lambda c: -c.area_ratio)
    first, rest, seen = [], [], set()
    for c in found:
        (rest if c.probe.video in seen else first).append(c)
        seen.add(c.probe.video)
    return first + rest


def context_crop(img: np.ndarray, xyxy: Sequence[float], factor: float = VERIFY_CONTEXT_FACTOR,
                 min_side: int = VERIFY_MIN_SIDE) -> Tuple[np.ndarray, Tuple[float, float, float, float]]:
    """核对用的裁剪：以框为中心取约 factor 倍大小（至少 min_side 像素）的区域，返回 (裁剪图, 框在裁剪图里的坐标)。
    小物件只裁框本身只剩几十个像素，模型认不出来，要带上周围环境"""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = xyxy
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    cw = min(w, max((x2 - x1) * factor, min_side))
    ch = min(h, max((y2 - y1) * factor, min_side))
    X1 = int(round(min(max(0.0, cx - cw / 2), w - cw)))
    Y1 = int(round(min(max(0.0, cy - ch / 2), h - ch)))
    X2, Y2 = int(round(X1 + cw)), int(round(Y1 + ch))
    return img[Y1:Y2, X1:X2], (x1 - X1, y1 - Y1, x2 - X1, y2 - Y1)


def _at_location(xyxy: Sequence[float], box: Sequence[float]) -> bool:
    """模型给出的框是否指向候选所在的位置"""
    if geometry.iou(xyxy, box) >= VERIFY_MIN_IOU:
        return True
    cx, cy = geometry.center(box)
    x1, y1, x2, y2 = xyxy
    return x1 <= cx <= x2 and y1 <= cy <= y2 and geometry.area(xyxy) <= 4 * geometry.area(box)


def verify_result(res: VLMResult, label: str, box: Sequence[float]) -> Tuple[str, List[str]]:
    """核对：单独看候选周围的区域、问全部类别 -> (confirmed / contradicted / unconfirmed, 认出的类别)"""
    if not res.ok:
        return "unconfirmed", []
    labels = [b["label"] for b in res.boxes]
    here = [b["label"] for b in res.boxes if _at_location(b["xyxy"], box)]
    if label in here:
        return "confirmed", labels
    if here:
        return "contradicted", labels
    return "unconfirmed", labels


def _color_signature(img: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [30, 32], [0, 180, 0, 256])
    return cv2.normalize(hist, hist).astype(np.float32)


def appearance_medoid(crops: List[np.ndarray]) -> int:
    """外观与其余候选平均最相近的那个的下标（颜色直方图相关系数）"""
    sigs = [_color_signature(c) for c in crops]
    scores = [np.mean([cv2.compareHist(a, b, cv2.HISTCMP_CORREL) for j, b in enumerate(sigs) if j != i])
              for i, a in enumerate(sigs)]
    return int(np.argmax(scores))


def bootstrap(client: VLMClient, probes_by_class: Dict[str, List[Probe]], all_classes: List[Dict], *,
              per_class: int = 1, verify: bool = True, verify_top: int = 3, round_size: int = PROBE_ROUND,
              should_stop: Optional[Callable[[], bool]] = None,
              on_result: Optional[Callable[[VLMResult], None]] = None) -> Tuple[Dict[str, List[Dict]], Dict]:
    """自动挑选参考图

    probes_by_class：每个类别按优先顺序排好的探测帧（见 pick_probes，任意前缀在时间上都是分散的）。
    分轮探测，每轮每个类别取 round_size 帧；某类别已有 ≥ 2 个候选且最大的足够大（面积 ≥ GOOD_AREA_RATIO）
    就不再探测——小物件多数帧里只有几十个像素，要多看几帧才能碰到拍得近、看得清的。
    返回 ({类别: [{"label", "image": JPEG 字节, "source": {...}}]}, 报告)。挑不出的类别不在结果里（该类别不带参考图标注）。
    """
    results: Dict[str, VLMResult] = {}
    used = {label: 0 for label in probes_by_class}
    pending = {label for label, probes in probes_by_class.items() if probes}
    rounds = 0
    while pending:
        batch: Dict[str, Probe] = {}
        for label in sorted(pending):
            take = probes_by_class[label][used[label]:used[label] + round_size]
            used[label] += len(take)
            for p in take:
                if p.key not in results:
                    batch.setdefault(p.key, p)
        if batch:
            results.update(client.detect_batch([VLMRequest(key=p.key, image_path=p.image_path, classes=p.classes)
                                                for p in batch.values()], on_result=on_result, should_stop=should_stop))
            rounds += 1
        if should_stop is not None and should_stop():
            break
        for label in list(pending):
            cands = collect_candidates(results, probes_by_class[label][:used[label]], label)
            enough = len(cands) >= 2 and max(c.area_ratio for c in cands) >= GOOD_AREA_RATIO
            if enough or used[label] >= len(probes_by_class[label]):
                pending.discard(label)
    usage = list(results.values())

    candidates = {label: collect_candidates(results, probes[:used[label]], label)
                  for label, probes in probes_by_class.items()}
    images: Dict[str, Optional[np.ndarray]] = {}

    def image_of(p: Probe):
        if p.key not in images:
            images[p.key] = _read(p.image_path)
        return images[p.key]

    limit = verify_top if verify else per_class
    contexts: Dict[str, Tuple] = {}
    to_verify: List[VLMRequest] = []
    for label, cands in candidates.items():
        for i, c in enumerate(cands[:limit]):
            img = image_of(c.probe)
            if img is None or not verify:
                continue
            crop, box_in_crop = context_crop(img, c.xyxy)
            contexts[f"{label}#{i}"] = box_in_crop
            to_verify.append(VLMRequest(key=f"{label}#{i}", image_path=None, classes=all_classes, image=crop))
    checked = client.detect_batch(to_verify, on_result=on_result, should_stop=should_stop) if to_verify else {}
    usage += list(checked.values())

    usable: Dict[str, List[Tuple[int, Candidate]]] = {}
    for label, cands in candidates.items():
        usable[label] = []
        for i, c in enumerate(cands[:limit]):
            if image_of(c.probe) is None:
                continue
            if verify:
                key = f"{label}#{i}"
                c.verdict, c.verify_labels = verify_result(checked.get(key) or VLMResult(key=key, ok=False),
                                                           label, contexts[key])
            usable[label].append((i, c))

    # 二次核对：还没有确认候选的类别，带上其他类别已确认的参考图再问一次
    second_pass = []
    if verify:
        confirmed_refs = {}
        for label, items in usable.items():
            first = next((c for _, c in items if c.verdict == "confirmed"), None)
            if first is not None:
                confirmed_refs[label] = {"label": label, "image": encode_reference(crop_array(image_of(first.probe), first.xyxy))}
        retry = [(label, i, c) for label, items in usable.items() if label not in confirmed_refs
                 for i, c in items if c.verdict == "unconfirmed"]
        if retry and confirmed_refs:
            requests = []
            for label, i, c in retry:
                crop, _ = context_crop(image_of(c.probe), c.xyxy)
                requests.append(VLMRequest(key=f"{label}#{i}#2", image_path=None, classes=all_classes, image=crop,
                                           references=list(confirmed_refs.values())))
            rechecked = client.detect_batch(requests, on_result=on_result, should_stop=should_stop)
            usage += list(rechecked.values())
            for label, i, c in retry:
                key = f"{label}#{i}#2"
                verdict, labels = verify_result(rechecked.get(key) or VLMResult(key=key, ok=False), label, contexts[f"{label}#{i}"])
                if verdict != "unconfirmed":
                    c.verdict, c.verify_labels = verdict, labels
                second_pass.append({"label": label, "frame": _frame_name(c), "verdict": verdict, "labels": labels})

    chosen: Dict[str, List[Dict]] = {}
    report = {"probes": len(results), "rounds": rounds, "second_pass": second_pass, "classes": {}}
    for label, cands in candidates.items():
        tried = [{"frame": _frame_name(c), "video": c.probe.video, "box": [round(v, 1) for v in c.xyxy],
                  "area_ratio": round(c.area_ratio, 4), "single_class_video": c.single_class,
                  "verdict": c.verdict, "verify_labels": c.verify_labels} for _, c in usable[label]]
        usable_c = [c for _, c in usable[label]]
        if verify:
            # 先用核对通过的；一个都没有时，才用单类视频里"没认出、也没认成别的"的候选兜底；
            # 再没有，多个未确认候选里取外观最一致的那个
            ordered = [c for c in usable_c if c.verdict == "confirmed"]
            ordered += [c for c in usable_c if c.verdict == "unconfirmed" and c.single_class]
            unconfirmed = [c for c in usable_c if c.verdict == "unconfirmed"]
            if not ordered and len(unconfirmed) >= 2:
                best = unconfirmed[appearance_medoid([crop_array(image_of(c.probe), c.xyxy) for c in unconfirmed])]
                best.verdict = "consensus"
                ordered = [best]
        else:
            ordered = usable_c
        picked = [{"label": label, "image": encode_reference(crop_array(image_of(c.probe), c.xyxy)),
                   "source": {"type": "auto", "video": c.probe.video, "frame": _frame_name(c),
                              "box": [round(v, 1) for v in c.xyxy], "verdict": c.verdict}}
                  for c in ordered[:per_class]]
        if picked:
            chosen[label] = picked
        report["classes"][label] = {"probes": used[label], "candidates": len(cands), "picked": len(picked),
                                    "verdicts": [p["source"]["verdict"] for p in picked], "tried": tried}
    report["usage"] = {
        "calls": sum(1 for r in usage if not r.cached), "cached": sum(1 for r in usage if r.cached),
        "failures": sum(1 for r in usage if not r.ok),
        "prompt_tokens": sum(int((r.usage or {}).get("prompt_tokens") or 0) for r in usage),
        "completion_tokens": sum(int((r.usage or {}).get("completion_tokens") or 0) for r in usage),
        "cost": sum(float((r.usage or {}).get("cost") or 0.0) for r in usage),
    }
    return chosen, report


def _frame_name(c: Candidate) -> str:
    return str(getattr(c.probe.image_path, "name", c.probe.image_path))


def _spread(n_frames: int, k: int) -> List[int]:
    """从 n_frames 帧里取 k 个下标，任意前缀在时间上都分散（van der Corput 序列）"""
    out, seen, i = [], set(), 1
    k = min(k, n_frames)
    while len(out) < k and i < 1 << 16:
        f, denom, x = 0.0, 1.0, i
        while x:
            denom *= 2
            f += (x & 1) / denom
            x >>= 1
        idx = int(round(f * (n_frames - 1)))
        if idx not in seen:
            seen.add(idx)
            out.append(idx)
        i += 1
    return out


def pick_probes(frames_by_video: Dict[str, List], videos_for_class: List[str], single_class_videos: Sequence[str],
                n: int) -> List:
    """给一个类别排出至多 n 帧探测帧：该类别的所有视频轮流取（每轮里只声明了这一类的视频排在前面），
    视频内按时间分散取，排在前面的任意一段都覆盖不同视频、不同时间。

    不能先把单类视频取完再取多类视频：实测唯一的单类视频里文物特别小（只占画面 0.2%），24 帧探测全花在它身上，
    一个候选都没找到，而多类视频里同一件文物拍得大得多。多类视频的标签歧义由核对环节把关。"""
    videos = sorted((v for v in videos_for_class if frames_by_video.get(v)),
                    key=lambda v: v not in single_class_videos)
    if not videos or n <= 0:
        return []
    pools = {v: [frames_by_video[v][i] for i in _spread(len(frames_by_video[v]), n)] for v in videos}
    picked: List = []
    while len(picked) < n and any(pools.values()):
        for v in videos:
            if pools[v] and len(picked) < n:
                picked.append(pools[v].pop(0))
    return picked
