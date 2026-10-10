"""流水线纯逻辑的测试（不连数据库）：python -m pytest tests/test_pipeline_logic.py

覆盖：任务参数校验（含多类别视频、参考图）、数据集划分、清洗选帧、类别校验、闸门判定、webhook 签名与防 SSRF、API Key 格式。
"""
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.pipeline.spec import JobSpec
from app.services.pipeline.stages import dataset as ds
from app.services.pipeline.stages.class_check import summarize as class_check_summary
from app.services.pipeline.stages.clean import select_frames
from app.services.pipeline.stages.gate import _status
from app.services.pipeline import webhooks
from app.services import api_key_service


def _spec(**over):
    base = {"name": "t", "classes": [{"name": "A"}, {"name": "B"}],
            "videos": [{"class": "A"}, {"class": "B"}]}
    base.update(over)
    return base


# ---------------- 任务参数 ----------------

def test_spec_assigns_video_keys_and_defaults():
    spec = JobSpec.model_validate(_spec())
    assert [v.key for v in spec.videos] == ["v1", "v2"]
    assert spec.review_mode == "on_anomaly" and spec.config.train.imgsz == 640


@pytest.mark.parametrize("bad, msg", [
    (_spec(videos=[{"class": "A"}]), "没有对应的视频"),
    (_spec(videos=[{"class": "A"}, {"class": "C"}]), "不在 classes 中"),
    (_spec(classes=[{"name": "A"}, {"name": "A"}]), "重复的类别名"),
    (_spec(classes=[{"name": "玉杯"}, {"name": "B"}]), "pattern"),
    (_spec(config={"train": {"imgsz": 650}}), "32 的倍数"),
    (_spec(config={"dataset": {"ratios": [0.5, 0.5, 0.5]}}), "和为 1"),
    (_spec(callback_url="ftp://x"), "http(s)"),
    (_spec(config={"unknown": 1}), "Extra inputs"),
    (_spec(videos=[{"class": "A", "classes": ["A", "B"]}]), "只能填一个"),
    (_spec(videos=[{"key": "x"}]), "class（单类）或 classes（多类）"),
    (_spec(videos=[{"classes": ["A", "C"]}, {"class": "B"}]), "不在 classes 中"),
    (_spec(config={"annotate": {"min_long_edge": 1600, "max_long_edge": 1280}}), "min_long_edge"),
    (_spec(classes=[{"name": "A", "references": [{"file": "a.jpg", "data_base64": "eA=="}]}, {"name": "B"}]),
     "file 或 data_base64"),
])
def test_spec_rejects_invalid(bad, msg):
    with pytest.raises(Exception) as e:
        JobSpec.model_validate(bad)
    assert msg in str(e.value)


def test_multi_class_video_declares_all_and_satisfies_coverage():
    spec = JobSpec.model_validate(_spec(videos=[{"classes": ["A", "B", "A"]}]))
    assert spec.videos[0].declared == ["A", "B"]           # 去重保序
    single = JobSpec.model_validate(_spec())
    assert single.videos[1].declared == ["B"]


# ---------------- 数据集划分 ----------------

def _split(video_classes, ratios=(0.7, 0.15, 0.15), seed=0):
    assignment, segment_val = ds.plan_video_split(video_classes, ratios, seed)
    by = {s: [k for k, v in assignment.items() if v == s] for s in ("train", "val", "test")}
    return by, segment_val


def test_split_small_class_keeps_test_video_and_segments_rest():
    by, segment_val = _split({"a": ["X"], "b": ["X"], "c": ["X"]})
    assert len(by["test"]) == 1 and by["val"] == [] and len(by["train"]) == 2 and segment_val == {"X"}


def test_split_large_class_all_by_video():
    by, segment_val = _split({f"v{i}": ["X"] for i in range(10)})
    assert segment_val == set() and len(by["test"]) == 2 and len(by["val"]) == 2 and len(by["train"]) == 6


def test_split_per_class_quotas_with_single_class_videos():
    videos = {f"x{i}": ["X"] for i in range(5)}
    videos.update({f"y{i}": ["Y"] for i in range(3)})
    by, segment_val = _split(videos)
    assert sum(k.startswith("x") for k in by["test"]) == 1 and sum(k.startswith("y") for k in by["test"]) == 1
    assert segment_val == {"Y"}                              # Y 只有 3 个视频，验证集只能按时间段切
    assert sum(k.startswith("x") for k in by["val"]) == 1


def test_split_multi_class_videos_cover_each_class_and_keep_train():
    # 多类视频：每类都要有测试视频，同时每类在训练集里至少留 1 个视频
    videos = {"ab1": ["A", "B"], "ab2": ["A", "B"], "a1": ["A"], "b1": ["B"], "c1": ["C"], "c2": ["C"], "c3": ["C"]}
    by, _ = _split(videos)
    for c in "ABC":
        assert any(c in videos[k] for k in by["test"]), c
        assert any(c in videos[k] for k in by["train"]), c
    # 同等条件下优先用只含一类的视频做测试集，少占用别的类别
    assert not any(len(videos[k]) > 1 for k in by["test"])


def test_split_never_empties_train_for_a_class():
    videos = {"ab": ["A", "B"], "a": ["A"], "b": ["B"]}
    by, _ = _split(videos)
    for c in "AB":
        assert any(c in videos[k] for k in by["train"]), c


@pytest.mark.parametrize("videos, mode, few, segment", [
    ({"x1": ["X"], "x2": ["X"], "x3": ["X"]}, "by_video", [], set()),
    ({"x1": ["X"], "x2": ["X"]}, "by_segment", ["X"], set()),
    # 只有 Y 视频不足：含 Y 的视频按时间段，其余照常按视频
    ({"x1": ["X"], "x2": ["X"], "x3": ["X"], "y1": ["Y"], "xy": ["X", "Y"]}, "hybrid", ["Y"], {"y1", "xy"}),
    # 视频不足的 Y 与 A 同框：含 Y 的视频按时间段，只有 a3 能整段留出
    ({"a1": ["A", "Y"], "a2": ["A", "Y"], "a3": ["A"]}, "hybrid", ["Y"], {"a1", "a2"}),
    ({"a1": ["A", "Y"], "a2": ["A", "Y"]}, "by_segment", ["A", "Y"], set()),
    # 视频不足的 Y、Z 合起来覆盖了每一个视频：没有可以整段留出的视频，退回 by_segment
    ({"a1": ["A", "Y"], "a2": ["A", "Y"], "a3": ["A", "Z"]}, "by_segment", ["Y", "Z"], set()),
])
def test_choose_split(videos, mode, few, segment):
    got_mode, got_few, got_segment = ds.choose_split(videos, "auto", 3)
    assert (got_mode, got_few, got_segment) == (mode, few, segment)


def test_choose_split_respects_explicit_request():
    videos = {"x1": ["X"], "x2": ["X"], "x3": ["X"], "y1": ["Y"], "y2": ["Y"]}
    assert ds.choose_split(videos, "by_segment", 3)[0] == "by_segment"
    assert ds.choose_split(videos, "by_video", 3)[0] == "by_video"                     # 每类 ≥2 个视频时照办
    assert ds.choose_split({"x1": ["X"], "y1": ["Y"]}, "by_video", 3)[0] == "by_segment"  # 只有 1 个视频，做不到


def test_split_deterministic_by_seed():
    videos = {f"v{i}": ["X"] for i in range(10)}
    assert ds.plan_video_split(videos, (0.7, 0.15, 0.15), 3) == ds.plan_video_split(videos, (0.7, 0.15, 0.15), 3)


# ---------------- 类别校验 ----------------

def test_class_check_ignores_frames_with_nothing_detected():
    # 8 帧里 5 帧什么都没认出（漏检），认出的 3 帧都是声明的类别：一致率 100%，不应报警
    out = class_check_summary([set()] * 5 + [{"A"}] * 3, ["A"])
    assert out["agreement"] == 1.0 and out["detected"] == 3 and out["answered"] == 8


def test_class_check_flags_wrong_declaration():
    out = class_check_summary([{"B"}] * 4 + [{"A", "B"}], ["A"])
    assert out["agreement"] == 0.2 and out["top"] == "B" and out["top_undeclared"] == "B"


def test_class_check_multi_class_hit_on_any_declared():
    out = class_check_summary([{"A"}, {"B"}, {"A", "C"}, {"C"}], ["A", "B"])
    assert out["agreement"] == 0.75


def test_class_check_needs_enough_evidence():
    assert class_check_summary([{"B"}, {"B"}, set(), None], ["A"])["agreement"] is None


def test_segment_split_interleaves_and_buffers():
    frames = [{"id": str(i), "ts": i * 0.5} for i in range(400)]   # 200 秒
    out = ds.assign_by_segment(frames, (0.7, 0.15, 0.15), buffer_seconds=2.0)
    counts = {s: sum(1 for v in out.values() if v == s) for s in ("train", "val", "test")}
    assert counts["val"] > 0 and counts["test"] > 0 and counts["train"] > counts["val"]
    assert len(out) < len(frames)   # 交界缓冲带里的帧被丢弃
    # 每个被丢弃的帧都在"两个不同划分的分界线"的缓冲距离之内
    pattern = ds._segment_pattern((0.7, 0.15, 0.15))
    span, seg_len = 399 * 0.5, 399 * 0.5 / ds.SEGMENTS
    boundaries = [k * seg_len for k in range(1, ds.SEGMENTS) if pattern[k - 1] != pattern[k]]
    for f in frames:
        if f["id"] not in out:
            assert min(abs(f["ts"] - b) for b in boundaries) <= 2.0 + 1e-6


def test_short_video_segments_keep_val_frames():
    # 7 秒的视频、2 秒缓冲带：原先切 20 段（每段 0.35s），验证段的帧全被缓冲带吃掉，训练直接报错
    frames = [{"id": str(i), "ts": 0.5 + i * 0.25} for i in range(28)]
    out = ds.assign_by_segment(frames, (0.82, 0.18, 0.0), buffer_seconds=2.0)
    assert sum(1 for v in out.values() if v == "val") >= 2
    assert sum(1 for v in out.values() if v == "train") >= 10


def test_segment_plan_scales_with_duration():
    assert ds.segment_plan(200, 2.0) == (20, 2.0)
    segments, buffer = ds.segment_plan(7, 2.0)
    assert segments == ds.MIN_SEGMENTS and buffer == pytest.approx(7 / 5 / 4)


def test_segment_pattern_zero_ratio_split_gets_nothing():
    pattern = ds._segment_pattern((0.82, 0.18, 0.0))
    assert "test" not in pattern and "val" in pattern


# ---------------- 清洗选帧 ----------------

class _CleanCfg:
    min_mean_brightness, max_mean_brightness, max_clipped_ratio = 25, 235, 0.5
    blur_drop_ratio, dedup_hamming, max_frames_per_video = 0.0, 6, 5


def test_select_frames_reasons():
    import numpy as np
    frames = []
    for i in range(10):
        thumb = np.full((48, 64), 100 + i * 10, np.uint8)
        frames.append({"ts": i, "blur": 100.0 + i, "brightness": 120.0, "clipped": 0.0, "phash": i * 0xFFFF, "thumb": thumb})
    frames[0]["brightness"] = 5.0                                 # 过暗
    frames[3]["phash"], frames[3]["thumb"] = frames[2]["phash"], frames[2]["thumb"].copy()   # 与上一帧重复
    frames[2]["blur"] = 500.0                                     # 帧 2 更清晰，应保留帧 2、丢帧 3
    select_frames(frames, _CleanCfg())
    reasons = {i: f["drop_reason"] for i, f in enumerate(frames)}
    assert reasons[0] == "exposure"
    assert reasons[3] == "duplicate" and reasons[2] in (None, "cap")
    assert sum(1 for f in frames if f["keep"]) == 5                # 数量上限
    assert all(f["drop_reason"] == "cap" for f in frames if not f["keep"] and f["drop_reason"] not in ("exposure", "duplicate"))


# ---------------- 闸门判定 ----------------

def test_gate_status_directions():
    assert _status(0.3, {"direction": "max", "warn": 0.1, "pause": 0.25}) == "pause"
    assert _status(0.15, {"direction": "max", "warn": 0.1, "pause": 0.25}) == "warn"
    assert _status(0.05, {"direction": "max", "warn": 0.1, "pause": 0.25}) == "ok"
    assert _status(30, {"direction": "min", "warn": 100, "pause": 40}) == "pause"
    assert _status(None, {"direction": "min", "warn": 100, "pause": 40}) == "skipped"


# ---------------- webhook ----------------

def test_webhook_signature_verifiable():
    import hashlib
    import hmac
    sig = webhooks.sign("whsec_x", b'{"a":1}', timestamp=1700000000)
    t, v1 = (p.split("=", 1)[1] for p in sig.split(","))
    assert t == "1700000000"
    assert v1 == hmac.new(b"whsec_x", b'1700000000.{"a":1}', hashlib.sha256).hexdigest()


@pytest.mark.parametrize("url", ["http://127.0.0.1:9/x", "http://10.0.0.8/x", "http://localhost/x", "http://[::1]/x"])
def test_webhook_blocks_private_targets(url, monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_ALLOWED_HOSTS", [])
    with pytest.raises(webhooks.WebhookTargetError):
        webhooks.check_target(url)


def test_webhook_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_ALLOWED_HOSTS", ["10.0.0.8"])
    webhooks.check_target("http://10.0.0.8/hook")
    monkeypatch.setattr(settings, "WEBHOOK_ALLOWED_HOSTS", ["*"])
    webhooks.check_target("http://127.0.0.1/hook")


# ---------------- API Key ----------------

def test_api_key_prefix_parsing_and_hash():
    assert api_key_service.parse_prefix("myo_sk_ab12cd34_secretpart") == "ab12cd34"
    assert api_key_service.parse_prefix("myo_sk_short_x") is None
    assert api_key_service.parse_prefix("sk_ab12cd34_x") is None
    h1 = api_key_service.hash_key("myo_sk_ab12cd34_a")
    assert h1 != api_key_service.hash_key("myo_sk_ab12cd34_b") and len(h1) == 64


def test_webhook_secret_encryption_roundtrip():
    token = api_key_service.encrypt_secret("whsec_abc")
    assert token != "whsec_abc" and api_key_service.decrypt_secret(token) == "whsec_abc"
    assert api_key_service.decrypt_secret("garbage") is None
