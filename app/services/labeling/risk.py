"""帧级风险评分与时序一致性检查

风险分决定两件事：
1. 没有人工复核时，风险分高于阈值（默认 0.6）的帧不进训练集——不用人也有一道质量过滤；
2. 需要复核时，风险高的帧排在前面、进入逐张精审。
权重是初始值（v2 设计 §5.4.3），后续可用复核数据回归调整。
"""
import math
from typing import Dict, List, Optional, Sequence

from app.services.labeling import geometry

RISK_WEIGHTS = {
    "vlm_failed": 1.0,         # 超时 / 解析失败 / 接口错误
    "no_box": 0.5,             # 视频声明有文物但没检出
    "multi_box": 0.5,          # 检出的框多于声明的件数
    "sam_fallback": 0.3,       # SAM 收框没过质量闸门，用的是 VLM 的粗框
    "temporal_outlier": 0.3,   # 与相邻帧的框不连续
    "label_mismatch": 0.2,     # 模型返回的类别名与给定的不一致
    "edge_truncated": 0.15,    # 框贴图像边缘，文物可能被截断
    "tiny_box": 0.15,          # 框面积占比过小
}

TINY_BOX_AREA_RATIO = 0.005
TEMPORAL_WINDOW = 2             # 前后各看 2 帧
TEMPORAL_CENTER_SHIFT = 0.2     # 中心偏离 > 0.2 × 预测框对角线
# 偏离容差的下限：图像对角线的 2%。小物件的框只有二三十个像素，手持拍摄稍一晃就超过"框对角线 × 0.2"；
# 在真实文物视频上，加了下限后被判离群的帧从 35 降到 24，抓到的错框数不变（10 个）
TEMPORAL_MIN_SHIFT_RATIO = 0.02
TEMPORAL_MAX_AREA_CHANGE = 2.5  # 面积相对预测框变大或缩小超过 2.5 倍（小框用 IoU 判断太敏感，改用面积比）
# 只和时间上足够近的帧比较：清洗会删掉一部分帧，留下的帧之间可能隔了一两秒，
# 物体本来就移动了很远，拿它们比会大量误报
TEMPORAL_MAX_GAP_FACTOR = 2.5   # 最大间隔 = 2.5 × 相邻保留帧间隔的中位数
TEMPORAL_MIN_GAP_SECONDS = 0.6


def risk_score(reasons: Sequence[str]) -> float:
    return round(min(1.0, sum(RISK_WEIGHTS.get(r, 0.0) for r in set(reasons))), 4)


def geometry_flags(box: Sequence[float], width: float, height: float) -> List[str]:
    flags = []
    if geometry.edges_touched(box, width, height) >= 1:
        flags.append("edge_truncated")
    if geometry.area(box) < TINY_BOX_AREA_RATIO * width * height:
        flags.append("tiny_box")
    return flags


def _interp(a: Sequence[float], b: Sequence[float], t: float) -> List[float]:
    return [a[k] + (b[k] - a[k]) * t for k in range(4)]


def temporal_outliers(frames: List[Dict]) -> Dict[int, Dict]:
    """同一视频内按时间排序的帧，检查主框（第一个框）是否与前后帧连续

    frames: [{"index": 任意标识, "ts": 秒, "box": xyxy 或 None, "image_diag": 图像对角线像素（可选）}]
    返回 {index: {"center_shift": .., "area_change": .., "iou": ..}}，只包含被判为离群的帧。

    文物拍摄是连续运动，相邻帧的框应当平滑变化。做法：用前后各至多 2 个邻近帧两两线性插值出
    "此刻应有的框"，与实际框比较中心偏移（容差为 0.2 × 框对角线，且不小于图像对角线的 2%）和面积变化。
    只要有一组邻居能"解释"当前框就不算离群；只和时间上足够近的帧比较，前后都没有近邻的帧不做判断。
    这个检查几乎零成本，能抓住"框跳了"的帧。
    """
    ordered = sorted((f for f in frames if f.get("box") is not None), key=lambda f: f["ts"])
    if len(ordered) < 3:
        return {}
    gaps = sorted(ordered[i + 1]["ts"] - ordered[i]["ts"] for i in range(len(ordered) - 1))
    max_gap = max(TEMPORAL_MIN_GAP_SECONDS, TEMPORAL_MAX_GAP_FACTOR * gaps[len(gaps) // 2])

    outliers = {}
    for i, f in enumerate(ordered):
        t = f["ts"]
        prev = [g for g in ordered[max(0, i - TEMPORAL_WINDOW):i] if t - g["ts"] <= max_gap]
        nxt = [g for g in ordered[i + 1:i + 1 + TEMPORAL_WINDOW] if g["ts"] - t <= max_gap]
        if not prev or not nxt:
            continue
        box = f["box"]
        floor = TEMPORAL_MIN_SHIFT_RATIO * float(f.get("image_diag") or 0.0)
        best = None   # (偏离程度, 偏移/容差, 面积变化倍数, iou)：与当前框最吻合的那组插值
        for p in prev:
            for n in nxt:
                span = n["ts"] - p["ts"]
                ref = _interp(p["box"], n["box"], (t - p["ts"]) / span if span > 0 else 0.5)
                (bx, by), (rx, ry) = geometry.center(box), geometry.center(ref)
                tolerance = max(TEMPORAL_CENTER_SHIFT * geometry.diag(ref), floor, 1.0)
                shift = math.hypot(bx - rx, by - ry) / tolerance
                ratio = geometry.area(box) / max(geometry.area(ref), 1e-6)
                change = max(ratio, 1.0 / max(ratio, 1e-6))
                badness = max(shift, math.log(change) / math.log(TEMPORAL_MAX_AREA_CHANGE))
                if best is None or badness < best[0]:
                    best = (badness, shift, change, geometry.iou(box, ref))
        # 只要有一组前后邻居能"解释"当前框就不算离群：邻居里混进一个离群帧时，不会连累它旁边的正常帧
        badness, shift, change, overlap = best
        if badness > 1.0:
            outliers[f["index"]] = {"center_shift": round(shift, 4), "area_change": round(change, 3), "iou": round(overlap, 4)}
    return outliers


def pick_primary_boxes(boxes: List[Dict], expected: int) -> List[Dict]:
    """检出框多于声明件数时，按面积保留最大的 expected 个（VLM 不给置信度，主体文物通常最大）"""
    if len(boxes) <= expected:
        return boxes
    return sorted(boxes, key=lambda b: geometry.area(b["xyxy"]), reverse=True)[:expected]


def summarize(values: List[Optional[float]]) -> Dict:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"count": 0}
    vals.sort()
    return {"count": len(vals), "min": vals[0], "median": vals[len(vals) // 2], "max": vals[-1]}
