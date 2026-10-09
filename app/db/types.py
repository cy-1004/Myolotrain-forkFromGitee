"""自定义列类型"""
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.paths import resolve_stored


class StoredPath(TypeDecorator):
    """存放文件系统路径的字符串列

    数据库里仍是普通 VARCHAR，不需要迁移表结构；读取时把历史绝对路径映射到当前环境
    （规则见 app/core/paths.resolve_stored），写入时原样保存。
    """

    impl = String
    cache_ok = True

    def process_result_value(self, value, dialect):
        return resolve_stored(value)
