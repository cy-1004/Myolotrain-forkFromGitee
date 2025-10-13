import logging
from sqlalchemy import text, create_engine
from app.core.config import settings
from app.db.session import SessionLocal

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def remove_hashed_password_column():
    """检查并删除users表中的hashed_password列，解决添加用户失败问题"""
    try:
        # 转换数据库URI为字符串
        db_url = str(settings.SQLALCHEMY_DATABASE_URI)
        
        # 创建数据库引擎
        engine = create_engine(db_url)
        
        # 使用连接执行原始SQL
        with engine.connect() as connection:
            # 检查hashed_password列是否存在
            check_column_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'hashed_password'
            """)
            result = connection.execute(check_column_query)
            column_exists = result.fetchone() is not None
            
            if column_exists:
                # 删除hashed_password列
                remove_column_query = text("""
                    ALTER TABLE users 
                    DROP COLUMN IF EXISTS hashed_password
                """)
                connection.execute(remove_column_query)
                connection.commit()
                logger.info("成功从users表中删除hashed_password列")
            else:
                logger.info("users表中不存在hashed_password列，无需删除")
        
        logger.info("数据库修复完成，请尝试再次添加用户")
        
    except Exception as e:
        logger.error(f"删除hashed_password列时出错: {str(e)}")
        raise

if __name__ == "__main__":
    remove_hashed_password_column()