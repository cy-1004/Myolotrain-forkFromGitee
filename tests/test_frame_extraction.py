"""抽帧的测试：顺序读取与逐帧 seek 取到的是同一批帧、回调给出正确的帧号与时间戳

python -m pytest tests/test_frame_extraction.py
"""
import os
import sys

import cv2
import numpy as np
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.frame_extraction_service import FrameExtractionService

FPS = 10
N_FRAMES = 60


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    """每帧整体灰度 = 帧号 × 4，读出的帧可以反推出帧号"""
    path = tmp_path_factory.mktemp("vid") / "probe.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (64, 48))
    for i in range(N_FRAMES):
        writer.write(np.full((48, 64, 3), i * 4, np.uint8))
    writer.release()
    return path


def _extract(video, out_dir, interval, monkeypatch=None, max_step=None):
    if max_step is not None:
        monkeypatch.setattr(FrameExtractionService, "SEQUENTIAL_READ_MAX_STEP", max_step)
    records = []
    result = FrameExtractionService.extract_from_video(
        str(video), "probe.avi", out_dir, method="time", interval_seconds=interval,
        skip_start=0.5, skip_end=0.0, image_format="png",
        on_frame=lambda p, idx, ts: records.append((p, idx, ts)))
    decoded = [int(round(cv2.imread(str(p)).mean() / 4)) for p, _, _ in records]
    return result, records, decoded


def test_sequential_read_gets_exact_frames(video, tmp_path, monkeypatch):
    result, records, decoded = _extract(video, tmp_path, 0.5, monkeypatch, max_step=60)
    expected = list(range(5, N_FRAMES, 5))            # 跳过开头 0.5s = 5 帧，之后每 5 帧一张
    assert [idx for _, idx, _ in records] == expected
    assert decoded == expected                         # 读到的像素内容确实是那一帧
    assert [ts for _, _, ts in records] == pytest.approx([i / FPS for i in expected])
    assert result["status"] == "success" and result["extracted_frames"] == len(expected)


def test_seek_mode_matches_sequential(video, tmp_path, monkeypatch):
    _, seq_records, seq_decoded = _extract(video, tmp_path / "a", 0.5, monkeypatch, max_step=60)
    _, seek_records, seek_decoded = _extract(video, tmp_path / "b", 0.5, monkeypatch, max_step=0)
    assert [r[1] for r in seq_records] == [r[1] for r in seek_records]
    assert seq_decoded == seek_decoded


def test_should_stop(video, tmp_path):
    calls = []
    result = FrameExtractionService.extract_from_video(
        str(video), "probe.avi", tmp_path, interval_seconds=0.1, image_format="png",
        on_frame=lambda *a: calls.append(a), should_stop=lambda: len(calls) >= 3)
    assert result["status"] == "stopped" and len(calls) == 3
