"""从视觉模型的回复里容错地提取检测结果

模型即使被要求"只返回 JSON 数组"，也常常会：包一层 ```json 代码块、前后加解释文字、
返回 {"objects": [...]} 这样的对象、用 bbox_2d / box 等不同字段名。
这里先整体解析，失败再按括号配对扫描所有 [...] / {...} 片段逐个尝试（思路来自 AutoLabelimage-pro-max），
最后逐项校验：不合法的项丢弃，而不是让整张图失败。
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

_LABEL_KEYS = ("label", "name", "class", "category", "class_name")
_BBOX_KEYS = ("bbox", "bbox_2d", "box", "bbox_xyxy", "coordinates", "xyxy")
_LIST_KEYS = ("objects", "detections", "boxes", "results", "items", "annotations")
_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.S)
# 最后的兜底：模型偶尔输出括号错配的 JSON，如 "bbox":[250,280,520,735}，整体解析失败。
# 按 "label":"…" … "bbox":[四个数] 的模式逐项提取
_ITEM_RE = re.compile(
    r'"(?:label|name|class|category)"\s*:\s*"(?P<label>[^"]*)"[^{}\[\]]*?'
    r'"(?:bbox_2d|bbox|box|bbox_xyxy|coordinates|xyxy)"\s*:\s*[\[\(]\s*'
    r'(?P<nums>-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?)', re.S)
_ITEM_RE_REVERSED = re.compile(
    r'"(?:bbox_2d|bbox|box|bbox_xyxy|coordinates|xyxy)"\s*:\s*[\[\(]\s*'
    r'(?P<nums>-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?)'
    r'\s*[\]\)\}][^{}\[\]]*?"(?:label|name|class|category)"\s*:\s*"(?P<label>[^"]*)"', re.S)


class ExtractError(ValueError):
    """回复里找不到可解析的 JSON"""


def _balanced_fragments(text: str, open_ch: str, close_ch: str) -> List[str]:
    """按括号配对找出所有顶层片段，跳过字符串内部的括号"""
    results = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != open_ch:
            i += 1
            continue
        depth, in_str, esc = 0, False, False
        for j in range(i, n):
            ch = text[j]
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1
                    if depth == 0:
                        results.append(text[i:j + 1])
                        i = j
                        break
        i += 1
    return results


def _as_item_list(data: Any) -> Optional[List[Dict]]:
    if isinstance(data, list):
        items = [x for x in data if isinstance(x, dict)]
        # 非空却不含对象的数组（如截断回复里扫到的坐标 [1,2,3,4]）不是检测结果列表，
        # 返回 None 让调用方继续尝试其他片段，而不是误判为"没有目标"
        if data and not items:
            return None
        return items
    if isinstance(data, dict):
        for key in _LIST_KEYS:
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
        if any(k in data for k in _BBOX_KEYS):
            return [data]
        if not data:
            return []
    return None


def extract_items(text: str) -> List[Dict]:
    """返回模型回复中的检测项列表（未校验）。完全找不到 JSON 时抛 ExtractError"""
    if text is None:
        raise ExtractError("回复为空")
    stripped = text.strip()

    def parse(cand):
        try:
            return _as_item_list(json.loads(cand))
        except (json.JSONDecodeError, ValueError):
            return None

    # 整段（或代码块里的整段）是合法 JSON：以它为准
    for cand in [stripped] + [m.strip() for m in _FENCE_RE.findall(stripped)]:
        items = parse(cand) if cand else None
        if items is not None:
            return items
    # 整段不合法：括号配对扫描出的第一个可解析片段，与正则逐项提取，取找到项更多的那个——
    # 数组里只有一项写坏时，片段扫描只能拿到前面那个合法对象，正则能把坏的那项也救回来
    fragment_items = None
    for cand in _balanced_fragments(stripped, "[", "]") + _balanced_fragments(stripped, "{", "}"):
        fragment_items = parse(cand)
        if fragment_items is not None:
            break
    salvaged = [{"label": m.group("label"), "bbox": [float(x) for x in m.group("nums").split(",")]}
                for m in list(_ITEM_RE.finditer(stripped)) + list(_ITEM_RE_REVERSED.finditer(stripped))]
    if fragment_items is not None and len(fragment_items) >= len(salvaged):
        return fragment_items
    if salvaged:
        return salvaged
    if fragment_items is not None:
        return fragment_items
    raise ExtractError("无法从回复中提取 JSON")


def _parse_bbox(value: Any) -> Optional[Tuple[float, float, float, float]]:
    try:
        if isinstance(value, dict):
            nums = [value.get(k) for k in ("x1", "y1", "x2", "y2")]
            if any(v is None for v in nums):
                nums = [value.get(k) for k in ("xmin", "ymin", "xmax", "ymax")]
        elif isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(p, (list, tuple)) for p in value):
            nums = [value[0][0], value[0][1], value[1][0], value[1][1]]   # [[x1,y1],[x2,y2]]
        elif isinstance(value, (list, tuple)) and len(value) == 4:
            nums = list(value)
        elif isinstance(value, str):
            nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", value)][:4]
        else:
            return None
        x1, y1, x2, y2 = (float(v) for v in nums)
    except (TypeError, ValueError, IndexError):
        return None
    if not all(v == v and abs(v) < 1e7 for v in (x1, y1, x2, y2)):  # NaN / 离谱值
        return None
    # 有的模型给反了顺序，交换而不是丢弃
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1
    if x2 - x1 <= 0 or y2 - y1 <= 0:
        return None
    return x1, y1, x2, y2


def parse_detections(text: str) -> List[Dict]:
    """解析为 [{"label": str, "bbox": (x1, y1, x2, y2)}]，坐标保持模型原始的坐标系，由调用方换算"""
    result = []
    for item in extract_items(text):
        label = next((str(item[k]).strip() for k in _LABEL_KEYS if item.get(k) not in (None, "")), "")
        bbox = next((_parse_bbox(item[k]) for k in _BBOX_KEYS if k in item), None)
        if bbox is None:
            continue
        result.append({"label": label, "bbox": bbox})
    return result
