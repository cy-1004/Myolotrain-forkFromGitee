"""端口自动顺延的测试：python -m pytest tests/test_net_utils.py"""
import os
import socket
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.net_utils import NoAvailablePortError, find_available_port, is_port_available


def _listen_on_free_port() -> socket.socket:
    """让系统分配一个空闲端口并监听，模拟"端口被其他程序占用" """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("0.0.0.0", 0))
    sock.listen(1)
    return sock



def test_occupied_port_is_detected():
    sock = _listen_on_free_port()
    try:
        assert is_port_available(sock.getsockname()[1]) is False
    finally:
        sock.close()


def test_loopback_only_listener_is_detected():
    # 别的程序只监听 127.0.0.1（如 VS Code 端口转发）：Windows 上普通的 0.0.0.0 bind 会成功，
    # 但本机访问 localhost 会被那个程序截走，必须判为被占用
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    try:
        assert is_port_available(sock.getsockname()[1]) is False
    finally:
        sock.close()


def _adjacent_free_ports() -> int:
    """找一对相邻且都空闲的端口，返回较小的那个"""
    for port in range(20000, 30000, 7):
        if is_port_available(port) and is_port_available(port + 1):
            return port
    pytest.skip("找不到相邻的空闲端口")


def test_falls_through_to_next_port():
    port = _adjacent_free_ports()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("0.0.0.0", port))
    sock.listen(1)
    try:
        assert find_available_port(port, max_tries=5) == port + 1
    finally:
        sock.close()


def test_free_start_port_is_kept():
    sock = _listen_on_free_port()
    port = sock.getsockname()[1]
    sock.close()
    assert find_available_port(port, max_tries=5) == port


def test_strict_mode_refuses_to_move():
    sock = _listen_on_free_port()
    try:
        with pytest.raises(NoAvailablePortError):
            find_available_port(sock.getsockname()[1], strict=True)
    finally:
        sock.close()


def test_all_ports_in_range_taken():
    sock = _listen_on_free_port()
    try:
        with pytest.raises(NoAvailablePortError):
            find_available_port(sock.getsockname()[1], max_tries=1)
    finally:
        sock.close()
