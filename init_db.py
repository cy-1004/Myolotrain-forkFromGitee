import os
import sys
import subprocess
import psycopg2
from psycopg2 import sql
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def init_database():
    """初始化PostgreSQL数据库，在检测不到目标数据库时自动创建"""
    logger.info("正在初始化PostgreSQL数据库...")

    # 数据库连接参数
    db_params = {
        'user': 'postgres',
        'password': 'postgres',    # 使用你的本地数据库密码
        'host': 'localhost',     # 本地环境使用 localhost
        'port': '5432',
        'database': 'postgres'   # 连接到默认数据库
    }

    try:
        # 连接到默认数据库
        conn = psycopg2.connect(**db_params)
        conn.autocommit = True
        cursor = conn.cursor()

        # 检查数据库是否存在
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'yolov8_platform'")
        exists = cursor.fetchone()

        if exists:
            logger.info("yolov8_platform数据库已存在，跳过创建步骤")
        else:
            # 创建新数据库
            logger.info("创建yolov8_platform数据库...")
            cursor.execute(sql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8' LC_COLLATE='C' LC_CTYPE='C' TEMPLATE=template0").format(sql.Identifier('yolov8_platform')))

        # 关闭连接
        cursor.close()
        conn.close()

        # 初始化数据库表
        logger.info("初始化数据库表结构...")
        # 运行应用程序的数据库初始化
        try:
            # 导入应用程序的数据库初始化模块
            from app.db.init_db import init_db
            init_db()
            logger.info("数据库表创建成功")
        except Exception as e:
            logger.error(f"数据库表创建失败: {e}")
            return False

        logger.info("数据库初始化完成！")
        return True

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return False

if __name__ == "__main__":
    # 确保在虚拟环境中运行
    if sys.prefix == sys.base_prefix:
        logger.warning("警告: 当前不在Python虚拟环境中运行")
        response = input("是否继续? [y/n]: ")
        if response.lower() not in ['y', 'yes']:
            sys.exit(0)

    # 初始化数据库
    if init_database():
        logger.info("数据库初始化成功！")
    else:
        logger.error("数据库初始化失败！")

