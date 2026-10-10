"""SAM 收框：以 VLM 的粗框为提示，取分割 mask 的外接矩形作为更贴合的框

质量闸门（阈值默认值来自 AutoLabelimage-pro-max）：
  粗框外扩 2% 作为提示 → mask 外接矩形 → 新框面积 / 粗框面积 ∈ [0.6, 1.15]，
  中心偏移 ≤ 15% 粗框长边，面积 ≥ 16 像素；任一不满足就回退到粗框。
与参考实现不同的是：回退不是静默的，回退原因会作为风险信号进入复核优先级和质量闸门统计。
文物场景最典型的回退：SAM 把底座/展台一起分了进来（面积比过大），或只分出器盖等局部（面积比过小）。
"""
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from app.core.config import settings
from app.services.labeling import geometry

logger = logging.getLogger(__name__)

_model_cache: Dict[str, object] = {}
_model_lock = threading.Lock()


def resolve_sam_weights(name: str) -> Path:
    """在 WEIGHTS_DIR、项目 models/ 下找 SAM 权重，都没有则下载到 WEIGHTS_DIR"""
    if not name or "/" in name or "\\" in name or ".." in name:
        raise ValueError(f"不合法的 SAM 权重名: {name!r}")
    for candidate in (Path(settings.WEIGHTS_DIR) / name, Path(settings.BASE_DIR) / "models" / name):
        if candidate.exists():
            return candidate
    target = Path(settings.WEIGHTS_DIR) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    from ultralytics.utils.downloads import attempt_download_asset
    attempt_download_asset(str(target))
    if not target.exists():
        raise FileNotFoundError(f"SAM 权重 {name} 不存在且下载失败（离线环境需预先放到 {settings.WEIGHTS_DIR}）")
    return target


class SamRefiner:
    def __init__(self, model_name: str, gate: Dict, device: Optional[str] = None):
        self.model_name = model_name
        self.gate = gate
        self._model = None
        self._load_error: Optional[str] = None
        if device:
            self.device = device
        else:
            try:
                import torch
                self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
            except Exception:
                self.device = "cpu"

    @property
    def available(self) -> bool:
        return self._ensure_model()

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        if self._load_error:
            return False
        try:
            path = resolve_sam_weights(self.model_name)
            with _model_lock:
                key = str(path.resolve())
                if key not in _model_cache:
                    from ultralytics import SAM
                    _model_cache[key] = SAM(str(path))
                self._model = _model_cache[key]
            return True
        except Exception as e:
            self._load_error = f"SAM 模型不可用（{self.model_name}）: {e}"
            logger.warning(self._load_error)
            return False

    def _predict_masks(self, img: np.ndarray, prompts: List[Sequence[float]]):
        try:
            results = self._model(img, bboxes=[list(map(float, b)) for b in prompts], verbose=False, device=self.device)
        except RuntimeError as e:
            # 显存不足（训练占着 GPU 时常见）：本 Run 后续都改用 CPU，慢一些但不会失败
            if "out of memory" in str(e).lower() and self.device != "cpu":
                logger.warning("SAM 显存不足，改用 CPU")
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass
                self.device = "cpu"
                results = self._model(img, bboxes=[list(map(float, b)) for b in prompts], verbose=False, device="cpu")
            else:
                raise
        if not results or results[0].masks is None:
            return None
        masks = results[0].masks.data
        return masks.cpu().numpy() if hasattr(masks, "cpu") else np.asarray(masks)

    def _check(self, coarse: Sequence[float], refined: Sequence[float]) -> Optional[str]:
        """返回不通过的原因；通过返回 None"""
        refined_area = geometry.area(refined)
        if refined_area < self.gate["min_box_area"]:
            return "too_small"
        coarse_area = geometry.area(coarse)
        if coarse_area > 0:
            ratio = refined_area / coarse_area
            if ratio < self.gate["min_area_ratio"]:
                return "area_ratio_low"
            if ratio > self.gate["max_area_ratio"]:
                return "area_ratio_high"
        (cx, cy), (rx, ry) = geometry.center(coarse), geometry.center(refined)
        long_side = max(coarse[2] - coarse[0], coarse[3] - coarse[1], 1.0)
        if np.hypot(rx - cx, ry - cy) / long_side > self.gate["max_center_shift_ratio"]:
            return "center_shift"
        return None

    def refine(self, img: np.ndarray, boxes: List[Sequence[float]]) -> List[Dict]:
        """对一张图上的多个粗框收框。返回与 boxes 一一对应的结果：
        {"xyxy": 最终框, "status": refined/fallback/unavailable/error, "reason", "area_ratio", "center_shift"}
        """
        if not boxes:
            return []
        if not self._ensure_model():
            return [{"xyxy": list(b), "status": "unavailable", "reason": "sam_unavailable"} for b in boxes]

        h, w = img.shape[:2]
        prompts = [geometry.expand(b, self.gate["expand_ratio"], w, h) for b in boxes]
        try:
            masks = self._predict_masks(img, prompts)
        except Exception as e:
            logger.warning(f"SAM 推理失败: {e}")
            return [{"xyxy": list(b), "status": "error", "reason": "sam_error"} for b in boxes]

        outcomes = []
        for i, coarse in enumerate(boxes):
            if masks is None or i >= len(masks):
                outcomes.append({"xyxy": list(coarse), "status": "fallback", "reason": "no_mask"})
                continue
            mask = masks[i] > 0.5
            ys, xs = np.nonzero(mask)
            if len(xs) == 0:
                outcomes.append({"xyxy": list(coarse), "status": "fallback", "reason": "empty_mask"})
                continue
            # mask 尺寸与原图一致；保险起见按比例换算
            mh, mw = mask.shape[:2]
            sx, sy = w / float(mw), h / float(mh)
            refined = geometry.clamp_box((xs.min() * sx, ys.min() * sy, (xs.max() + 1) * sx, (ys.max() + 1) * sy), w, h)
            coarse_area = geometry.area(coarse)
            info = {
                "area_ratio": round(geometry.area(refined) / coarse_area, 4) if coarse_area > 0 else None,
                "center_shift": round(float(np.hypot(*(np.subtract(geometry.center(refined), geometry.center(coarse))))) /
                                      max(coarse[2] - coarse[0], coarse[3] - coarse[1], 1.0), 4),
                "sam_box": [round(v, 2) for v in refined],
            }
            reason = self._check(coarse, refined)
            if reason:
                outcomes.append({"xyxy": list(coarse), "status": "fallback", "reason": reason, **info})
            else:
                outcomes.append({"xyxy": [round(v, 2) for v in refined], "status": "refined", "reason": None, **info})
        return outcomes
