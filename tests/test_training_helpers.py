"""训练服务辅助函数的测试：python -m pytest tests/test_training_helpers.py

只测纯逻辑（日志分块、results.csv 解析、基础权重解析），不连数据库、不启动训练。
"""
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services import training_service as ts


def _task(tmp_path: Path, **params):
    task_id = uuid.uuid4()
    return SimpleNamespace(
        id=task_id,
        name="t",
        tensorboard_path=str(tmp_path / "tb"),
        parameters={"output_dir": str(tmp_path / "out"), **params},
        model_id=None,
        output_model_id=None,
    )


def _write_log(task, content: bytes):
    path = Path(task.tensorboard_path) / "training_log.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ---------------- 日志增量读取 ----------------

def test_log_chunk_missing_file(tmp_path):
    chunk = ts.read_training_log_chunk(_task(tmp_path))
    assert chunk == {"text": "", "offset": 0, "next_offset": 0, "size": 0, "exists": False}


def test_log_chunk_incremental_reads_reassemble_exactly(tmp_path):
    task = _task(tmp_path)
    content = ("Epoch 1/10 训练中…… 损失 0.123\n" * 50).encode("utf-8")
    _write_log(task, content)
    # 用很小的块逐段读，块边界必然落在中文字符中间
    pieces, offset = [], 0
    while True:
        chunk = ts.read_training_log_chunk(task, offset=offset, limit=7)
        if chunk["next_offset"] == offset:
            break
        pieces.append(chunk["text"])
        offset = chunk["next_offset"]
    assert "".join(pieces) == content.decode("utf-8")
    assert "�" not in "".join(pieces)


def test_log_chunk_tail_aligns_to_char_boundary(tmp_path):
    task = _task(tmp_path)
    content = "中文日志行\n".encode("utf-8") * 10
    _write_log(task, content)
    # 从末尾往前取 4 字节：起点必然落在某个 3 字节汉字中间
    chunk = ts.read_training_log_chunk(task, offset=-4)
    assert "�" not in chunk["text"]
    assert content[chunk["offset"]:].decode("utf-8") == chunk["text"]
    assert chunk["next_offset"] == chunk["size"] == len(content)


def test_log_chunk_offset_beyond_size_restarts(tmp_path):
    # 重新训练覆盖了日志，前端还拿着旧的大偏移量
    task = _task(tmp_path)
    _write_log(task, b"new log\n")
    chunk = ts.read_training_log_chunk(task, offset=10_000)
    assert chunk["offset"] == 0 and chunk["text"] == "new log\n"


def test_log_chunk_limit_is_capped(tmp_path):
    task = _task(tmp_path)
    _write_log(task, b"x" * (ts.LOG_CHUNK_MAX_BYTES + 100))
    chunk = ts.read_training_log_chunk(task, offset=0, limit=10 ** 9)
    assert len(chunk["text"]) == ts.LOG_CHUNK_MAX_BYTES


# ---------------- results.csv ----------------

def test_results_csv_strips_padded_headers(tmp_path):
    task = _task(tmp_path)
    exp = Path(task.parameters["output_dir"]) / "exp"
    exp.mkdir(parents=True)
    (exp / "results.csv").write_text(
        "                  epoch,      train/box_loss,   metrics/mAP50(B),metrics/mAP50-95(B)\n"
        "                      1,             1.2345,            0.5000,             0.3000\n"
        "                      2,             1.1000,            0.6000,             0.3500\n",
        encoding="utf-8",
    )
    rows = ts.read_results_csv(task)
    assert len(rows) == 2
    assert rows[1]["epoch"] == 2.0
    assert rows[1]["metrics/mAP50(B)"] == pytest.approx(0.6)
    assert set(rows[0]) == {"epoch", "train/box_loss", "metrics/mAP50(B)", "metrics/mAP50-95(B)"}


def test_results_csv_missing(tmp_path):
    assert ts.read_results_csv(_task(tmp_path)) == []


# ---------------- 基础权重解析 ----------------

@pytest.fixture
def weights_dir(tmp_path, monkeypatch):
    d = tmp_path / "weights"
    d.mkdir()
    monkeypatch.setattr(settings, "WEIGHTS_DIR", d)
    return d


@pytest.mark.parametrize("model_type, expected", [
    ("n", "yolov8n.pt"),          # 旧前端只传尺寸字母
    ("yolov8s", "yolov8s.pt"),
    ("yolo11n", "yolo11n.pt"),    # 原先会被拼成 yolov8yolo11n.pt
    ("yolo11n.pt", "yolo11n.pt"),
])
def test_resolve_base_weights_names(weights_dir, model_type, expected):
    (weights_dir / expected).write_bytes(b"pt")
    assert ts.resolve_base_weights(model_type) == weights_dir / expected


def test_resolve_base_weights_missing_points_to_weights_dir(weights_dir):
    path = ts.resolve_base_weights("yolo11x")
    assert path == weights_dir / "yolo11x.pt" and not path.exists()


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/b", "", "..\\x", "yolo 11n"])
def test_resolve_base_weights_rejects_paths(weights_dir, bad):
    with pytest.raises(ValueError):
        ts.resolve_base_weights(bad)
