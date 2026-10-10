"""框的几何工具。框统一用原图像素坐标的 xyxy 元组 (x1, y1, x2, y2)"""
import math
from typing import Dict, Optional, Sequence, Tuple

Box = Tuple[float, float, float, float]


def clamp_box(box: Sequence[float], width: float, height: float) -> Box:
    x1, y1, x2, y2 = box
    return (min(max(x1, 0.0), width), min(max(y1, 0.0), height),
            min(max(x2, 0.0), width), min(max(y2, 0.0), height))


def area(box: Sequence[float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def center(box: Sequence[float]) -> Tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def diag(box: Sequence[float]) -> float:
    return math.hypot(box[2] - box[0], box[3] - box[1])


def iou(a: Sequence[float], b: Sequence[float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def expand(box: Sequence[float], ratio: float, width: float, height: float) -> Box:
    w, h = box[2] - box[0], box[3] - box[1]
    dx, dy = w * ratio, h * ratio
    return clamp_box((box[0] - dx, box[1] - dy, box[2] + dx, box[3] + dy), width, height)


def edges_touched(box: Sequence[float], width: float, height: float, margin_ratio: float = 0.01) -> int:
    """框贴住了几条图像边（容差为图像尺寸的 1%）"""
    mx, my = width * margin_ratio, height * margin_ratio
    return sum([box[0] <= mx, box[1] <= my, box[2] >= width - mx, box[3] >= height - my])


def to_yolo(box: Sequence[float], width: float, height: float, class_id: int, **extra) -> Dict:
    """xyxy 像素坐标 -> 平台标注格式（YOLO 归一化中心点宽高）"""
    x1, y1, x2, y2 = clamp_box(box, width, height)
    return {
        "class_id": int(class_id),
        "x_center": round((x1 + x2) / 2.0 / width, 6),
        "y_center": round((y1 + y2) / 2.0 / height, 6),
        "width": round((x2 - x1) / width, 6),
        "height": round((y2 - y1) / height, 6),
        **extra,
    }


def from_yolo(ann: Dict, width: float, height: float) -> Optional[Box]:
    try:
        cx, cy = float(ann["x_center"]) * width, float(ann["y_center"]) * height
        w, h = float(ann["width"]) * width, float(ann["height"]) * height
    except (KeyError, TypeError, ValueError):
        return None
    return (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
