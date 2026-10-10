"""视觉模型提示词

两种风格：
- recall（默认）：真实拍摄环境里文物常常很小、在画面边缘、被部分遮挡，周围还有书本、绿植、台灯等杂物。
  严格风格在这种画面上大量返回 []（实测 Qwen3-VL-30B 召回率仅 0.17），所以明确要求"能辨认就标"，
  同时点名常见杂物让模型排除，并使用 Qwen-VL 原生的 bbox_2d 输出格式；
- strict：借鉴 AutoLabelimage-pro-max 的强约束写法（不确定就不输出），适合背景干净、文物占画面主体的展陈拍摄。
两种风格都要求：只输出 JSON、label 使用给定类别名、0~1000 相对坐标、框贴紧物体本身。

模板内容变化时 prompt_version 随之变化，自动让 VLM 结果缓存失效。
"""
import hashlib
from typing import Dict, Iterable, List

TEMPLATES = {
    "recall": """请在图中找出下列物品，并为每一件给出边界框：
{class_bullets}

要求：
- 物品可能很小、位于画面边缘或被部分遮挡，只要能辨认出是上述物品就要标注
- 画面中常有书本、绿植、台灯、乐器、摆件等无关物品，不要标注它们
- 同一类物品出现多件时，每件单独一个框；同一件物品只标一次
- 框紧贴物品本身，不包含底座、支架、展柜、手、阴影和倒影
- 坐标为 0~1000 的相对坐标 [x1, y1, x2, y2]，原点在图像左上角
- label 使用冒号前的英文类别名
- 只输出 JSON 数组，不要任何解释，例如 [{{"label": "类别名", "bbox_2d": [x1, y1, x2, y2]}}]；图中确实没有上述物品时输出 []""",

    "strict": """你是一个严格的视觉标注器。
任务：只检测图中清晰可见的以下文物：
{class_bullets}

只返回 JSON 数组，不要任何解释。格式：[{{"label":"类别名","bbox":[x1,y1,x2,y2]}}]
规则：
- label 必须严格使用上面列表中冒号前的英文类别名
- bbox 使用 0~1000 的相对坐标，原点在图像左上角，x1<x2，y1<y2
- bbox 紧贴文物本体边界，不包含底座、支架、展柜、手、阴影和倒影
- 文物可见部分不足一半时不要输出
- 不确定就不要输出；没有目标时返回 []
- 同一件文物只输出一次""",
}
DEFAULT_STYLE = "recall"


def prompt_version(style: str = DEFAULT_STYLE) -> str:
    return hashlib.sha1(TEMPLATES[style].encode("utf-8")).hexdigest()[:8]


# 兼容旧引用：默认风格的版本号
PROMPT_VERSION = prompt_version(DEFAULT_STYLE)


def class_bullets(classes: Iterable[Dict]) -> str:
    lines = []
    for c in classes:
        desc = c.get("prompt") or c.get("display_name")
        lines.append(f"- {c['name']}：{desc}" if desc else f"- {c['name']}")
    return "\n".join(lines) or "- （无）"


def build_prompt(classes: List[Dict], style: str = DEFAULT_STYLE) -> str:
    return TEMPLATES[style].format(class_bullets=class_bullets(classes))


def label_aliases(classes: List[Dict]) -> Dict[str, str]:
    """模型返回的 label -> 类别名。模型常返回展示名或描述而不是英文类别名，这里都认"""
    mapping = {}
    for c in classes:
        for alias in [c["name"], c.get("display_name"), c.get("prompt"), *(c.get("aliases") or [])]:
            if alias:
                mapping[str(alias).strip().lower()] = c["name"]
    return mapping
