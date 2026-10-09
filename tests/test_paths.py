"""路径存储与历史路径映射的测试：python -m pytest tests/test_paths.py"""
import os
import sys
from pathlib import Path

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import paths
from app.core.config import settings


@pytest.fixture
def env(tmp_path, monkeypatch):
    base = tmp_path / "app_root"
    data = tmp_path / "data"
    base.mkdir()
    data.mkdir()
    monkeypatch.setattr(settings, "BASE_DIR", base)
    monkeypatch.setattr(settings, "DATA_DIR", data)
    monkeypatch.setattr(settings, "LEGACY_PATH_PREFIXES", [r"C:\workspace\Myolotrain", "/app"])
    return base, data


def test_windows_legacy_path_maps_to_current_root(env):
    base, _ = env
    stored = r"C:\workspace\Myolotrain\app\static\datasets\abc"
    assert Path(paths.resolve_stored(stored)) == base / "app" / "static" / "datasets" / "abc"


def test_prefix_match_ignores_case_and_slashes(env):
    base, _ = env
    stored = "c:/WORKSPACE/myolotrain/app/static/models/best.pt"
    assert Path(paths.resolve_stored(stored)) == base / "app" / "static" / "models" / "best.pt"


def test_prefix_must_match_whole_directory_name(env):
    # /application 不能被当成 /app 前缀
    assert paths.resolve_stored("/application/data/x") == "/application/data/x"


def test_existing_and_unmatched_paths_unchanged(env, tmp_path):
    existing = tmp_path / "exists.txt"
    existing.write_text("x")
    assert paths.resolve_stored(str(existing)) == str(existing)
    assert paths.resolve_stored(r"D:\other\place") == r"D:\other\place"
    assert paths.resolve_stored("") == ""
    assert paths.resolve_stored(None) is None


def test_no_prefixes_configured_is_noop(env, monkeypatch):
    monkeypatch.setattr(settings, "LEGACY_PATH_PREFIXES", [])
    stored = r"C:\workspace\Myolotrain\app\static\datasets\abc"
    assert paths.resolve_stored(stored) == stored


def test_data_relative_roundtrip(env):
    _, data = env
    target = data / "runs" / "r1" / "delivery" / "model.tflite"
    stored = paths.to_data_relative(target)
    assert stored == "runs/r1/delivery/model.tflite"
    assert paths.from_data_relative(stored) == target.resolve()
    assert paths.data_path("runs", "r1") == data / "runs" / "r1"


def test_data_relative_rejects_outside_paths(env, tmp_path):
    with pytest.raises(ValueError):
        paths.to_data_relative(tmp_path / "elsewhere" / "x")
    with pytest.raises(ValueError):
        paths.from_data_relative("../../etc/passwd")
