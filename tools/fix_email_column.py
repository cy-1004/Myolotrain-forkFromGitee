import logging
from sqlalchemy import create_engine, text
from app.core.config import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    try:
        # 创建数据库连接
        logger.info("正在连接到数据库...")
        # 将PostgresDsn对象转换为字符串
        db_url = str(settings.SQLALCHEMY_DATABASE_URI)
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # 检查email列是否存在
            logger.info("检查email列是否存在...")
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'email'
            """))
            
            column_exists = result.fetchone()
            
            if column_exists:
                # 检查email列是否有非空约束
                logger.info("检查email列的非空约束...")
                null_constraint_result = conn.execute(text("""
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'email'
                """))
                
                is_nullable = null_constraint_result.scalar()
                
                if is_nullable.lower() == 'no':
                    # 修改email列为可为空
                    logger.info("正在修改email列为可为空...")
                    conn.execute(text("""
                        ALTER TABLE users
                        ALTER COLUMN email DROP NOT NULL
                    """))
                    conn.commit()
                    logger.info("成功将email列修改为可为空")
                else:
                    logger.info("email列已经是可为空的，无需修改")
            else:
                logger.info("users表中不存在email列，无需修改")
    except Exception as e:
        logger.error(f"修改数据库表结构时出错: {e}")
        raise

if __name__ == "__main__":
    main()