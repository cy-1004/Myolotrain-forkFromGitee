import logging
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

from app.db.session import Base, engine
from app.core.config import settings

# 导入所有模型以确保它们被注册
from app.models import Dataset, Model, TrainingTask, DetectionTask

logger = logging.getLogger(__name__)

def init_db():
    try:
        # 测试数据库连接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")

        # 检查模型是否注册
        logger.info(f"Registered models: {Base.metadata.tables.keys()}")

        # 创建表
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # 检查表是否存在
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"Tables in database: {tables}")

        # 检查每个表的列
        for table in tables:
            columns = [col['name'] for col in inspector.get_columns(table)]
            logger.info(f"Columns in {table}: {columns}")

        # 检查并添加缺失的列
        if 'training_tasks' in tables:
            columns = [col['name'] for col in inspector.get_columns('training_tasks')]
            if 'process_id' not in columns:
                logger.info("Adding process_id column to training_tasks table")
                with engine.connect() as conn:
                    conn.execute(text("""
                        ALTER TABLE training_tasks
                        ADD COLUMN process_id VARCHAR(255)
                    """))
                    conn.commit()
                logger.info("Added process_id column to training_tasks table")

        # 检查并修改 detection_tasks 表的 input_path 列
        if 'detection_tasks' in tables:
            # 检查 input_path 列是否为非空
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT column_name, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'detection_tasks' AND column_name = 'input_path'
                """))
                column_info = result.fetchone()
                if column_info and column_info[1] == 'NO':  # 'NO' 表示不可为空
                    logger.info("Modifying input_path column in detection_tasks table to allow NULL values")
                    conn.execute(text("""
                        ALTER TABLE detection_tasks
                        ALTER COLUMN input_path DROP NOT NULL
                    """))
                    conn.commit()
                    logger.info("Modified input_path column in detection_tasks table to allow NULL values")

        # 检查并添加 datasets 表的 is_external 列
        if 'datasets' in tables:
            # 检查 is_external 列是否存在
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'datasets' AND column_name = 'is_external'
                """))
                column_exists = result.fetchone()
                if not column_exists:
                    logger.info("Adding is_external column to datasets table")
                    conn.execute(text("""
                        ALTER TABLE datasets
                        ADD COLUMN is_external BOOLEAN DEFAULT FALSE
                    """))
                    conn.commit()
                    logger.info("Added is_external column to datasets table")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        raise
