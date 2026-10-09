"""数据路径的存储与解析

两类路径：
1. 历史数据：数据库里存的是写入时机器上的绝对路径（如 C:\\workspace\\Myolotrain\\app\\static\\datasets\\xx）。
   换机器或进容器后这些路径不存在。resolve_stored() 把配置在 LEGACY_PATH_PREFIXES 里的旧项目根目录
   替换为当前项目根目录（BASE_DIR）。Docker 中 app/static 下的数据目录是指向数据卷的软链
   （见 docker/entrypoint.sh），所以替换后的路径能直接读到迁移进数据卷的数据。
   这一步在 ORM 读取时自动完成（app/db/types.StoredPath），业务代码不用改。
2. 新功能（流水线等）：只存相对 DATA_DIR 的路径，用 to_data_relative() / data_path() 互转。
"""
import os
from pathlib import Path
from typing import Optional, Union

from app.core.config import settings

PathLike = Union[str, os.PathLike]


def _normalize(value: str) -> str:
    return value.replace("\\", "/")


def resolve_stored(value: Optional[str]) -> Optional[str]:
    """把数据库里的历史绝对路径映射到当前环境

    - 路径在当前环境存在，或不匹配任何旧前缀：原样返回；
    - 匹配 LEGACY_PATH_PREFIXES 中的某个旧项目根目录：替换为 BASE_DIR。
      前缀比较不区分大小写、不区分正反斜杠（Windows 路径大小写不敏感）。
    """
    if not value or not settings.LEGACY_PATH_PREFIXES:
        return value
    if os.path.exists(value):
        return value
    normalized = _normalize(value)
    lowered = normalized.lower()
    for prefix in settings.LEGACY_PATH_PREFIXES:
        prefix_norm = _normalize(prefix).rstrip("/") + "/"
        if lowered.startswith(prefix_norm.lower()):
            return str(Path(settings.BASE_DIR) / normalized[len(prefix_norm):])
    return value


def data_path(*parts: PathLike) -> Path:
    """DATA_DIR 下的路径"""
    return Path(settings.DATA_DIR).joinpath(*parts)


def to_data_relative(path: PathLike) -> str:
    """转为相对 DATA_DIR 的 posix 路径（用于入库）

    Raises:
        ValueError: 路径不在 DATA_DIR 内——新功能的数据必须放在数据目录里，否则换环境就丢
    """
    resolved = Path(path).resolve()
    root = Path(settings.DATA_DIR).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        raise ValueError(f"路径不在数据目录 {root} 内: {resolved}")


def from_data_relative(stored: str) -> Path:
    """to_data_relative 的逆操作；拒绝跳出 DATA_DIR 的路径（如 ../../etc/passwd）"""
    root = Path(settings.DATA_DIR).resolve()
    candidate = (root / stored).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"非法的数据路径: {stored}")
    return candidate
