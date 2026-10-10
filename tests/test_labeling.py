"""自动标注纯逻辑的测试：python -m pytest tests/test_labeling.py"""
import os
import sys

import numpy as np
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.labeling import geometry, risk
from app.services.labeling.json_extract import ExtractError, parse_detections
from app.services.labeling.prompt import build_prompt, label_aliases
from app.services.labeling.vlm_client import VLMClient, VLMRequest, mock_localize, to_original_coords

CLASSES = [{"name": "JadeCup", "display_name": "玉杯", "prompt": "玉杯（古代玉质饮器）"}]


# ---------------- JSON 容错解析 ----------------

@pytest.mark.parametrize("text, n", [
    ('[{"label":"JadeCup","bbox":[100,200,300,400]}]', 1),
    ('好的，结果如下：\n```json\n[{"label":"JadeCup","bbox":[1,2,3,4]}]\n```\n以上。', 1),
    ('{"objects":[{"label":"JadeCup","bbox_2d":[1,2,3,4]},{"name":"x","box":[5,6,7,8]}]}', 2),
    ('[]', 0),
    ('图中没有文物。[]', 0),
    ('[{"label":"JadeCup","bbox":[[10,20],[30,40]]}]', 1),
    ('[{"label":"JadeCup","bbox":{"x1":1,"y1":2,"x2":3,"y2":4}}]', 1),
])
def test_parse_variants(text, n):
    assert len(parse_detections(text)) == n


def test_parse_skips_invalid_items_not_whole_reply():
    text = '[{"label":"a","bbox":[1,2]},{"label":"b","bbox":"oops"},{"label":"c","bbox":[0,0,10,10]}]'
    items = parse_detections(text)
    assert [i["label"] for i in items] == ["c"]


def test_parse_swaps_reversed_coords():
    assert parse_detections('[{"label":"a","bbox":[30,40,10,20]}]')[0]["bbox"] == (10, 20, 30, 40)


def test_truncated_reply_is_not_mistaken_for_empty():
    # 截断回复里扫到的 [100,200,300,400] 不能被当成"没有目标"；已完整给出的框应当救回来
    items = parse_detections('[{"label":"JadeCup","bbox":[100,200,300,400]')
    assert items == [{"label": "JadeCup", "bbox": (100, 200, 300, 400)}]


@pytest.mark.parametrize("text, labels", [
    ('[{"label":"Bodhisattva","bbox":[250,280,520,735}}]', ["Bodhisattva"]),          # 括号错配（实际出现过）
    ('[{"label": "A", "bbox": [1, 2, 3, 4]}, {"label": "B", "bbox_2d": [5,6,7,8}]', ["A", "B"]),
    ('[{"bbox_2d": [10, 20, 30, 40], "label": "C"}, {"bbox_2d": [5,5,9,9}, "label": "D"}]', ["C", "D"]),
])
def test_malformed_json_salvaged(text, labels):
    assert sorted(i["label"] for i in parse_detections(text)) == labels


def test_unparseable_raises():
    with pytest.raises(ExtractError):
        parse_detections("抱歉，我无法处理这张图片")


# ---------------- 坐标换算 ----------------

def test_rel1000_to_pixels():
    box, used = to_original_coords((100, 200, 500, 600), "auto", (1024, 768), (1920, 1440))
    assert used == "rel1000"
    assert box == pytest.approx((192, 288, 960, 864))


def test_auto_detects_rel1_and_abs():
    _, used = to_original_coords((0.1, 0.2, 0.5, 0.6), "auto", (1024, 768), (1920, 1440))
    assert used == "rel1"
    box, used = to_original_coords((100, 50, 1020, 700), "auto", (1024, 768), (2048, 1536))
    assert used == "abs" and box == pytest.approx((200, 100, 2040, 1400))


def test_qwen25_defaults_to_abs():
    client = VLMClient("mock", "qwen/qwen2.5-vl-72b-instruct")
    assert client.model_default_coord == "abs"
    assert VLMClient("mock", "qwen/qwen3-vl-30b-a3b-instruct").model_default_coord == "rel1000"


# ---------------- 标签匹配 ----------------

def test_label_aliases_accept_display_name():
    aliases = label_aliases(CLASSES)
    assert aliases["jadecup"] == "JadeCup" and aliases["玉杯"] == "JadeCup"


def test_single_class_mismatched_label_kept_and_flagged():
    client = VLMClient("mock", "m")
    req = VLMRequest(key="k", image_path=None, classes=CLASSES)
    res = client._interpret(req, '[{"label":"cup","bbox":[100,100,500,500]}]', (1000, 1000), (1000, 1000))
    assert len(res.boxes) == 1 and res.boxes[0]["label"] == "JadeCup" and res.boxes[0]["label_matched"] is False


def test_multi_class_unknown_label_dropped():
    classes = CLASSES + [{"name": "AncientBowl"}]
    client = VLMClient("mock", "m")
    req = VLMRequest(key="k", image_path=None, classes=classes)
    res = client._interpret(req, '[{"label":"cup","bbox":[1,1,5,5]},{"label":"AncientBowl","bbox":[100,100,500,500]}]',
                            (1000, 1000), (1000, 1000))
    assert [b["label"] for b in res.boxes] == ["AncientBowl"] and res.dropped_items == 1


def test_prompt_lists_class_with_description():
    prompt = build_prompt(CLASSES)
    assert "JadeCup：玉杯（古代玉质饮器）" in prompt and "0~1000" in prompt


# ---------------- mock 定位 ----------------

def test_mock_localize_finds_object():
    img = np.full((480, 640, 3), 200, np.uint8)
    img[100:300, 200:400] = (30, 60, 200)
    import json
    bbox = json.loads(mock_localize(img, CLASSES))[0]["bbox"]
    box, _ = to_original_coords(bbox, "rel1000", (640, 480), (640, 480))
    assert geometry.iou(box, (200, 100, 400, 300)) > 0.9


def test_mock_localize_empty_scene():
    assert mock_localize(np.full((100, 100, 3), 128, np.uint8), CLASSES) == "[]"


# ---------------- 时序与风险 ----------------

def test_temporal_outlier_detected():
    frames = [{"index": i, "ts": i * 0.5, "box": (100 + i, 100, 200 + i, 200)} for i in range(9)]
    frames[4]["box"] = (400, 400, 500, 500)    # 中间一帧框跳走
    out = risk.temporal_outliers(frames)
    assert list(out) == [4]


def test_temporal_ignores_large_time_gaps():
    # 清洗删帧后留下 1.5 秒的空档，物体在空档里移动了很远，不能因此报"框跳了"
    frames = [{"index": i, "ts": i * 0.25, "box": (100 + 40 * i, 100, 200 + 40 * i, 200)} for i in range(4)]
    frames += [{"index": 10 + i, "ts": 2.5 + i * 0.25, "box": (600 + 10 * i, 100, 700 + 10 * i, 200)} for i in range(4)]
    assert risk.temporal_outliers(frames) == {}


def test_temporal_tolerates_jitter_of_tiny_boxes():
    # 20 像素的小物件、手持拍摄抖动 6 像素：只按框大小算容差会判离群，按图像大小给下限后不判
    frames = [{"index": i, "ts": i * 0.5, "box": (300, 300, 320, 320), "image_diag": 800.0} for i in range(7)]
    frames[3]["box"] = (306, 304, 326, 324)
    assert risk.temporal_outliers(frames) == {}
    no_floor = [dict(f, image_diag=None) for f in frames]
    assert list(risk.temporal_outliers(no_floor)) == [3]
    frames[3]["box"] = (300, 300, 360, 360)          # 面积突然变成 9 倍：仍是离群
    assert list(risk.temporal_outliers(frames)) == [3]


def test_temporal_constant_motion_not_flagged():
    # 匀速移动的物体：插值预测与实际一致
    frames = [{"index": i, "ts": i * 0.5, "box": (10 * i, 0, 10 * i + 50, 50)} for i in range(10)]
    assert risk.temporal_outliers(frames) == {}


def test_near_duplicate_needs_pixel_similarity():
    from app.services.pipeline.stages.clean import is_near_duplicate
    base = np.full((48, 64), 128, np.uint8)
    moved = base.copy()
    moved[10:30, 40:60] = 30          # 背景不变、物体位置变了：pHash 可能相同，但像素差明显
    a = {"phash": 0, "thumb": base}
    assert is_near_duplicate(a, {"phash": 0, "thumb": base.copy()}, 6)
    assert not is_near_duplicate(a, {"phash": 0, "thumb": moved}, 6)
    assert not is_near_duplicate(a, {"phash": 0xFF, "thumb": base}, 6)


def test_risk_score_caps_and_dedups():
    assert risk.risk_score(["vlm_failed", "no_box"]) == 1.0
    assert risk.risk_score(["sam_fallback", "sam_fallback"]) == 0.3
    assert risk.risk_score([]) == 0.0


def test_geometry_flags():
    assert risk.geometry_flags((0, 10, 50, 60), 1000, 1000) == ["edge_truncated", "tiny_box"]
    assert risk.geometry_flags((100, 100, 600, 600), 1000, 1000) == []


def test_pick_primary_keeps_largest():
    boxes = [{"xyxy": (0, 0, 10, 10)}, {"xyxy": (0, 0, 100, 100)}, {"xyxy": (0, 0, 50, 50)}]
    assert risk.pick_primary_boxes(boxes, 1) == [{"xyxy": (0, 0, 100, 100)}]


def test_to_yolo_roundtrip():
    ann = geometry.to_yolo((100, 50, 300, 250), 400, 300, 2, source="sam")
    assert ann["class_id"] == 2 and ann["source"] == "sam"
    assert geometry.from_yolo(ann, 400, 300) == pytest.approx((100, 50, 300, 250), abs=0.01)  # 坐标保留 6 位小数
