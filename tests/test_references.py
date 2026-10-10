"""参考图与多类别标注的纯逻辑测试（不调用视觉模型、不连数据库）：python -m pytest tests/test_references.py"""
import base64
import os
import sys

import cv2
import numpy as np
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.labeling import references as refs
from app.services.labeling.vlm_client import VLMClient, VLMRequest, VLMResult, _encode_for_model


def _jpeg(w=200, h=100, color=(0, 128, 255)) -> bytes:
    img = np.full((h, w, 3), color, np.uint8)
    return cv2.imencode(".jpg", img)[1].tobytes()


# ---------------- 发给模型的图片 ----------------

def test_small_frames_are_upscaled_large_ones_capped():
    _, size = _encode_for_model(np.zeros((640, 480, 3), np.uint8), max_long_edge=1280, min_long_edge=1280)
    assert size == (960, 1280)
    _, size = _encode_for_model(np.zeros((1080, 1920, 3), np.uint8), max_long_edge=1280, min_long_edge=1280)
    assert size == (1280, 720)
    _, size = _encode_for_model(np.zeros((640, 480, 3), np.uint8), max_long_edge=1024, min_long_edge=0)
    assert size == (480, 640)


def test_payload_puts_references_before_target_image():
    client = VLMClient("mock", "m")
    payload = client._payload("提示词", b"target", [{"label": "JadeCup", "image": b"ref"}])
    content = payload["messages"][0]["content"]
    kinds = [c["type"] for c in content]
    assert kinds[0] == "text" and kinds[-1] == "image_url"          # 待标注的图在最后
    assert any(c.get("text") == "参考图：JadeCup" for c in content)
    assert content[-1]["image_url"]["url"].endswith(base64.b64encode(b"target").decode())


def test_cache_key_depends_on_references():
    client = VLMClient("mock", "m")
    classes = [{"name": "A"}]
    assert client._cache_key(b"x", classes) != client._cache_key(b"x", classes, [{"label": "A", "image": b"r"}])


# ---------------- 调用方提供的参考图 ----------------

def test_reference_from_upload_crops_and_limits_size():
    out = refs.reference_from_upload(_jpeg(1000, 500), box=[100, 100, 300, 200])
    img = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[:2] == (100, 200)
    big = cv2.imdecode(np.frombuffer(refs.reference_from_upload(_jpeg(1000, 500)), np.uint8), cv2.IMREAD_COLOR)
    assert max(big.shape[:2]) == refs.REFERENCE_MAX_EDGE


@pytest.mark.parametrize("data, box, msg", [
    (b"not an image", None, "无法解码"),
    (_jpeg(), [0, 0, 500, 50], "超出图片范围"),
])
def test_reference_from_upload_rejects_bad_input(data, box, msg):
    with pytest.raises(ValueError, match=msg):
        refs.reference_from_upload(data, box)


def test_prepare_references_resolves_files_and_base64():
    from app.services.pipeline.service import ServiceError, prepare_references
    from app.services.pipeline.spec import JobSpec

    b64 = "data:image/jpeg;base64," + base64.b64encode(_jpeg()).decode()
    spec = JobSpec.model_validate({"name": "t", "videos": [{"class": "A"}, {"class": "B"}], "classes": [
        {"name": "A", "references": [{"file": "a.jpg"}, {"data_base64": b64}]}, {"name": "B"}]})
    out = prepare_references(spec, {"a.jpg": _jpeg()})
    assert list(out) == ["A"] and len(out["A"]) == 2
    with pytest.raises(ServiceError, match="不在上传的 references"):
        prepare_references(spec, {})
    bad = JobSpec.model_validate({"name": "t", "videos": [{"class": "A"}], "classes": [
        {"name": "A", "references": [{"data_base64": "@@@"}]}]})
    with pytest.raises(ServiceError, match="base64"):
        prepare_references(bad)


# ---------------- 自动挑选 ----------------

def test_pick_probes_rotates_videos_single_class_first_and_spreads_in_time():
    frames = {v: [{"video": v, "i": i} for i in range(100)] for v in ("m1", "s1", "s2")}
    out = refs.pick_probes(frames, ["m1", "s1", "s2"], ["s1", "s2"], 6)
    assert [f["video"] for f in out] == ["s1", "s2", "m1", "s1", "s2", "m1"]   # 每轮单类视频在前，多类视频也轮得到
    assert [f["i"] for f in out if f["video"] == "s1"] == [50, 25]           # 任意前缀都是分散的：先中间、再四分之一……
    few = {"s1": [{"video": "s1", "i": 0}], "m1": [{"video": "m1", "i": i} for i in range(10)]}
    assert [f["video"] for f in refs.pick_probes(few, ["s1", "m1"], ["s1"], 3)] == ["s1", "m1", "m1"]


def test_context_crop_keeps_object_position():
    img = np.zeros((480, 640, 3), np.uint8)
    crop, box = refs.context_crop(img, (600, 10, 630, 40))          # 贴近右上角的小物件
    assert crop.shape[:2] == (192, 192)
    x1, y1, x2, y2 = box
    assert 0 <= x1 < x2 <= 192 and 0 <= y1 < y2 <= 192 and (x2 - x1, y2 - y1) == (30, 30)


@pytest.mark.parametrize("boxes, verdict", [
    ([{"label": "A", "xyxy": [10, 10, 50, 50]}], "confirmed"),
    ([{"label": "B", "xyxy": [12, 12, 48, 48]}], "contradicted"),
    ([{"label": "A", "xyxy": [150, 150, 190, 190]}], "unconfirmed"),   # 认出的 A 不在候选的位置
    ([], "unconfirmed"),
])
def test_verify_verdicts(boxes, verdict):
    res = VLMResult(key="k", ok=True, boxes=boxes)
    assert refs.verify_result(res, "A", (10, 10, 50, 50))[0] == verdict


class FakeClient:
    """按图片的 key 返回预设的检测结果；核对请求（image 不为空）按 key 前缀返回。
    verdicts_with_refs：带了参考图的二次核对时改用的结果"""

    def __init__(self, detections, verdicts, verdicts_with_refs=None):
        self.detections, self.verdicts, self.calls = detections, verdicts, []
        self.verdicts_with_refs = verdicts_with_refs or {}

    def detect_batch(self, requests, on_result=None, should_stop=None):
        out = {}
        for r in requests:
            self.calls.append(r.key)
            if r.image is not None:
                label = r.key.split("#")[0]
                h, w = r.image.shape[:2]
                verdict = self.verdicts.get(label, "nothing")
                if r.references:
                    verdict = self.verdicts_with_refs.get(label, verdict)
                boxes = {"confirm": [{"label": label, "xyxy": [w * 0.3, h * 0.3, w * 0.7, h * 0.7]}],
                         "nothing": []}[verdict]
                out[r.key] = VLMResult(key=r.key, ok=True, boxes=boxes, image_size=(w, h))
            else:
                out[r.key] = VLMResult(key=r.key, ok=True, boxes=self.detections.get(r.key, []), image_size=(640, 480))
        return out


def _probes(tmp_path, n, classes, prefix):
    img = np.full((480, 640, 3), 90, np.uint8)
    out = []
    for i in range(n):
        p = tmp_path / f"{prefix}{i}.jpg"
        cv2.imwrite(str(p), img)
        out.append(refs.Probe(key=p.name, image_path=p, video=prefix, classes=classes))
    return out


def test_bootstrap_picks_confirmed_and_falls_back_for_single_class(tmp_path):
    A, B = {"name": "A"}, {"name": "B"}
    probes = {"A": _probes(tmp_path, 8, [A], "a"), "B": _probes(tmp_path, 8, [B], "b")}
    big = {"label": "A", "label_matched": True, "xyxy": [100, 100, 200, 200]}     # 面积 3.3%，够大
    small = {"label": "B", "label_matched": True, "xyxy": [300, 300, 330, 330]}   # 面积 0.3%
    detections = {"a0.jpg": [big], "a1.jpg": [dict(big, xyxy=[100, 100, 180, 180])], "b2.jpg": [small]}
    client = FakeClient(detections, {"A": "confirm", "B": "nothing"})
    chosen, report = refs.bootstrap(client, probes, [A, B], round_size=8)
    assert chosen["A"][0]["source"]["verdict"] == "confirmed"
    assert chosen["B"][0]["source"]["verdict"] == "unconfirmed"     # 单类视频里没认出也没认错：兜底采用
    assert report["classes"]["A"]["probes"] == 8 and report["rounds"] == 1


def test_bootstrap_rejects_single_unconfirmed_from_multi_class_video(tmp_path):
    A, B = {"name": "A"}, {"name": "B"}
    probes = {"A": _probes(tmp_path, 4, [A, B], "m")}
    detections = {"m0.jpg": [{"label": "A", "label_matched": True, "xyxy": [100, 100, 200, 200]}]}
    chosen, report = refs.bootstrap(FakeClient(detections, {}), probes, [A, B])
    assert "A" not in chosen and report["classes"]["A"]["candidates"] == 1


def test_appearance_medoid_excludes_the_odd_one_out():
    red = np.zeros((40, 40, 3), np.uint8); red[:] = (30, 30, 200)
    red2 = red.copy(); red2[:5] = (40, 40, 190)
    blue = np.zeros((40, 40, 3), np.uint8); blue[:] = (200, 60, 20)
    assert refs.appearance_medoid([blue, red, red2]) in (1, 2)


def test_bootstrap_consensus_for_multi_class_only_class(tmp_path):
    # B 只在多类视频里出现、核对都没认出：多个候选时取外观最一致的，标为 consensus
    A, B = {"name": "A"}, {"name": "B"}
    probes = {"B": _probes(tmp_path, 4, [A, B], "m")}
    box = {"label": "B", "label_matched": True, "xyxy": [100, 100, 200, 200]}
    detections = {"m0.jpg": [box], "m1.jpg": [dict(box, xyxy=[110, 100, 200, 190])]}
    chosen, _ = refs.bootstrap(FakeClient(detections, {}), probes, [A, B])
    assert chosen["B"][0]["source"]["verdict"] == "consensus"


def test_bootstrap_second_pass_uses_confirmed_references_of_other_classes(tmp_path):
    # B 只出现在多类视频里、首次核对没认出；带上 A 已确认的参考图再核对一次，认出了就采用
    A, B = {"name": "A"}, {"name": "B"}
    probes = {"A": _probes(tmp_path, 4, [A], "a"), "B": _probes(tmp_path, 4, [A, B], "m")}
    detections = {"a0.jpg": [{"label": "A", "label_matched": True, "xyxy": [100, 100, 200, 200]}],
                  "m0.jpg": [{"label": "B", "label_matched": True, "xyxy": [300, 100, 400, 200]}]}
    client = FakeClient(detections, {"A": "confirm"}, verdicts_with_refs={"B": "confirm"})
    chosen, report = refs.bootstrap(client, probes, [A, B])
    assert chosen["B"][0]["source"]["verdict"] == "confirmed"
    assert report["second_pass"] and report["second_pass"][0]["label"] == "B"
    assert any(k.endswith("#2") for k in client.calls)


def test_bootstrap_probes_more_rounds_when_candidates_are_small(tmp_path):
    A = {"name": "A"}
    probes = {"A": _probes(tmp_path, 24, [A], "a")}
    small = [{"label": "A", "label_matched": True, "xyxy": [300, 300, 330, 330]}]
    client = FakeClient({"a0.jpg": small, "a1.jpg": small}, {"A": "confirm"})
    _, report = refs.bootstrap(client, probes, [A], round_size=8)
    assert report["rounds"] == 3 and report["classes"]["A"]["probes"] == 24


# ---------------- 多类别视频的标注记录 ----------------

def test_build_record_maps_labels_to_class_ids_per_class():
    from app.services.pipeline.stages.annotate import build_record

    video = {"key": "v1", "class_names": ["A", "B"], "expected_instances": 1}
    frame = {"image": "v1_000001.jpg", "frame_index": 1, "ts": 0.5}
    boxes = [{"label": "B", "label_matched": True, "xyxy": [10, 10, 60, 60]},
             {"label": "A", "label_matched": True, "xyxy": [100, 100, 300, 300]},
             {"label": "A", "label_matched": True, "xyxy": [400, 100, 420, 120]}]   # A 多出一个小框
    vlm = VLMResult(key="k", ok=True, boxes=boxes, image_size=(640, 480))
    rec = build_record(frame, video, {"A": 0, "B": 3}, vlm, None, None, "mock", "m")
    assert sorted(a["class_id"] for a in rec["annotations"]) == [0, 3]          # 每类各留一个，互不挤占
    assert "multi_box" in rec["risk_reasons"]
    assert rec["pipeline_meta"]["classes"] == ["A", "B"]
