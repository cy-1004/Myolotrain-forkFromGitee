"""等待数据库可连接（容器启动时由 entrypoint 调用）

compose 的 depends_on: service_healthy 只保证 Postgres 进程起来了，
首次初始化数据目录时它会重启一次，这里再兜底重试一段时间。
"""
import sys
import time

from sqlalchemy import create_engine, text

from app.core.config import settings

TIMEOUT_SECONDS = 120


def main() -> int:
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI), pool_pre_ping=True)
    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_error = None
    while time.monotonic() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"数据库已就绪: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
            return 0
        except Exception as e:  # 连接被拒、认证中、库还没建好等都在这里重试
            last_error = e
            time.sleep(2)
    print(f"等待数据库超时（{TIMEOUT_SECONDS}s）: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
