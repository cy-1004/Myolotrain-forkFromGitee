"""静态文件公开/鉴权判定的测试：python -m pytest tests/test_static_access.py"""
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.static_access import is_public_static, is_static_path


@pytest.mark.parametrize("path", [
    "/static/js/main.js",
    "/static/css/style.css",
    "/static/libs/bootstrap/bootstrap.min.css",
    "/static/fonts/Arial.Unicode.ttf",
    "/static/templates/user_management.html",
    "/static/login.html",
    "/static/annotation.html",
])
def test_frontend_assets_are_public(path):
    assert is_public_static(path)


@pytest.mark.parametrize("path", [
    "/static/datasets/abc/images/1.jpg",
    "/static/models/training_x/exp/weights/best.pt",
    "/static/extracted_frames/task/frame.jpg",
    "/static/uploads/video.mp4",
    "/static",
    "/static/",
    # 数据目录里的 html 不能因为后缀是 .html 就放行
    "/static/datasets/report.html",
])
def test_data_files_require_login(path):
    assert not is_public_static(path)


@pytest.mark.parametrize("path", [
    "/static/js/../datasets/x.jpg",
    "/static/js/..\\datasets\\x.jpg",
    "/static/libs/../../static/models/m.pt",
    "/static/./models/m.pt",
    "/static/css/../../static/uploads/a.mp4",
    "/static/js/../login.html/../datasets/x.jpg",
])
def test_traversal_out_of_public_dirs_is_not_public(path):
    assert not is_public_static(path)


def test_traversal_into_public_dir_stays_public():
    # 规范化后确实落在前端代码目录里，放行没有风险
    assert is_public_static("/static/datasets/../js/main.js")


def test_static_path_detection():
    assert is_static_path("/static")
    assert is_static_path("/static/js/a.js")
    assert not is_static_path("/staticx/a.js")
    assert not is_static_path("/api/datasets/")
