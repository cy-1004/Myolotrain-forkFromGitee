import logging
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger(__name__)

# 输出数据库连接信息
logger.info(f"Database URI: {settings.SQLALCHEMY_DATABASE_URI}")

# 创建引擎时添加详细的错误处理
try:
    engine = create_engine(
        str(settings.SQLALCHEMY_DATABASE_URI),
        pool_pre_ping=True,  # 测试连接是否有效
        echo=False  # 设置为 True 可以看到详细的 SQL 语句
    )
    logger.info("Database engine created successfully")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}", exc_info=True)
    raise

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()

# 依赖项
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        # 根据DEBUG模式决定是否输出完整错误堆栈
        # 在生产模式下只输出错误摘要，不输出完整堆栈
        logger.error(f"Database session error: {e}", exc_info=settings.DEBUG)
        raise
    finally:
        db.close()
