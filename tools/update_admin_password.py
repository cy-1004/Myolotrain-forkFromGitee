import psycopg2
from passlib.context import CryptContext
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 密码加密上下文
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__default_rounds=29000
)

def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)

def update_admin_password_directly(new_password: str):
    """直接连接数据库修改管理员密码"""
    try:
        # 数据库连接参数
        # 从app/core/config.py中获取的实际配置
        db_params = {
            'dbname': 'yolov8_platform',  # 从config.py中看到的数据库名
            'user': 'postgres',     # 从config.py中看到的用户名
            'password': 'postgres', # 从config.py中看到的密码
            'host': 'localhost',    # 从config.py中看到的主机
            'port': '5432'          # PostgreSQL默认端口
        }
        
        # 连接到数据库
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        
        # 生成新密码的哈希值
        hashed_password = get_password_hash(new_password)
        
        # 直接执行SQL更新语句
        # 使用id=1假设管理员用户是第一个创建的用户
        update_query = """UPDATE users SET password = %s WHERE username = 'admin'"""
        cursor.execute(update_query, (hashed_password,))
        
        # 提交事务
        conn.commit()
        
        # 检查是否有行被更新
        if cursor.rowcount > 0:
            logger.info(f"成功更新管理员密码")
            return True
        else:
            logger.error(f"未找到用户名'admin'的用户")
            return False
            
    except Exception as e:
        logger.error(f"更新密码时出错: {e}")
        return False
    finally:
        # 关闭游标和连接
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    # 设置新密码
    new_password = "bjt@2014-2024"
    success = update_admin_password_directly(new_password)
    if success:
        print(f"管理员密码已成功修改为：{new_password}")
    else:
        print("修改管理员密码失败，请查看日志获取详细信息")