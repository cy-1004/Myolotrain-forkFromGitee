"""本地启动入口（run.py / start.py 共用）：选端口 → 启动 uvicorn

Docker 中不走这里：容器内端口固定为 8000，宿主机端口的冲突顺延由 scripts/start.sh 处理。
"""
import logging
import os

import uvicorn

from app.core.config import settings
from app.utils.net_utils import find_available_port

logger = logging.getLogger(__name__)

HOST = "0.0.0.0"


def run_server() -> None:
    port = find_available_port(
        settings.SERVER_PORT,
        max_tries=settings.APP_PORT_MAX_TRIES,
        host=HOST,
        strict=settings.APP_PORT_STRICT,
    )
    if port != settings.SERVER_PORT:
        logger.warning("=" * 60)
        logger.warning(f"首选端口 {settings.SERVER_PORT} 被占用，本次使用端口 {port}")
        logger.warning("=" * 60)

    # 回写实际端口：本进程内的 settings 用于打印访问地址；
    # 环境变量供热重载模式下的子进程重新加载配置时读取
    settings.SERVER_PORT = port
    os.environ["SERVER_PORT"] = str(port)

    if settings.RELOAD:
        # 只监听 app/ 下的代码；数据目录（app/static）和训练日志目录里会不断生成文件，
        # 其中训练脚本 train_script.py 一旦被监听到就会触发重启、打断正在进行的训练
        uvicorn.run(
            "app.main:app",
            host=HOST,
            port=port,
            reload=True,
            reload_dirs=[str(settings.BASE_DIR / "app")],
            # 必须传目录的绝对路径：uvicorn 对目录会递归排除，而 "static/*" 这类通配只匹配直接子文件
            reload_excludes=[str(settings.STATIC_DIR)],
        )
    else:
        uvicorn.run("app.main:app", host=HOST, port=port)
