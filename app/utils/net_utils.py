"""网络相关的小工具：启动时的端口探测与自动顺延"""
import errno
import logging
import socket
import sys

logger = logging.getLogger(__name__)


class NoAvailablePortError(RuntimeError):
    """在允许的范围内找不到可用端口"""


def _loopback_listening(port: int) -> bool:
    """本机回环地址上是否已有程序在监听该端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """尝试真实绑定一次来判断端口是否可用

    只做 connect 探测不可靠：Windows 上 Hyper-V/WSL 会保留一段端口（excludedportrange），
    这些端口没有进程在监听、connect 也连不上，但 bind 会报 WinError 10013。
    所以以 bind 为主判断，和 uvicorn 实际启动时的行为一致。

    但只做普通 bind 也不够：Windows 上别的程序只监听 127.0.0.1:8001（VS Code 端口转发就是这样）时，
    绑定 0.0.0.0:8001 照样成功，结果本机访问 localhost:8001 打到的是那个程序而不是本平台。
    因此 Windows 上用 SO_EXCLUSIVEADDRUSE 绑定（任何地址上有占用都会失败），
    再补一次回环地址的 connect 探测兜底。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sys.platform == "win32":
            # Windows 上不能设 SO_REUSEADDR：那里的语义是"允许抢占正在监听的端口"，会把占用中的端口误判为可用
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            # Linux 上 uvicorn 会设置 SO_REUSEADDR，这里保持一致，避免把 TIME_WAIT 状态的端口误判为被占用
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError as e:
            # EADDRINUSE：被占用；EACCES / WinError 10013：被系统保留或无权限，同样视为不可用
            if e.errno in (errno.EADDRINUSE, errno.EACCES) or getattr(e, "winerror", None) in (10013, 10048):
                return False
            raise
    return not _loopback_listening(port)


def find_available_port(start_port: int, max_tries: int = 20, host: str = "0.0.0.0", strict: bool = False) -> int:
    """从 start_port 开始找第一个可用端口，被占用就 +1 顺延

    Args:
        start_port: 首选端口
        max_tries: 最多尝试多少个端口（含首选端口）
        host: 监听地址，需与 uvicorn 的 host 一致
        strict: True 时不顺延，首选端口不可用直接报错（适合防火墙/网关已固定端口的环境）

    Raises:
        NoAvailablePortError: 范围内没有可用端口
    """
    tries = 1 if strict else max(1, max_tries)
    for port in range(start_port, min(start_port + tries, 65536)):
        if is_port_available(port, host):
            if port != start_port:
                logger.warning(f"端口 {start_port} 已被占用，自动顺延到 {port}")
            return port
        logger.info(f"端口 {port} 已被占用")

    if strict:
        raise NoAvailablePortError(
            f"端口 {start_port} 已被占用，且 APP_PORT_STRICT=true 不允许顺延。"
            f"请释放该端口，或修改 SERVER_PORT 后重试"
        )
    raise NoAvailablePortError(
        f"端口 {start_port}~{start_port + tries - 1} 全部被占用。"
        f"请释放端口，或调大 APP_PORT_MAX_TRIES / 修改 SERVER_PORT 后重试"
    )
