import psycopg2
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_users_table_structure():
    """检查数据库中users表的结构"""
    try:
        # 数据库连接参数
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
        
        # 检查users表的结构
        cursor.execute("""\
            SELECT column_name, data_type \
            FROM information_schema.columns \
            WHERE table_name = 'users' \
            ORDER BY ordinal_position
        """)
        
        print("Users表的列结构:")
        print("=" * 50)
        print(f"{'列名':<20}{'数据类型':<30}")
        print("=" * 50)
        
        for row in cursor.fetchall():
            print(f"{row[0]:<20}{row[1]:<30}")
        
        # 检查是否有用户记录
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        print(f"\nUsers表中的记录数: {count}")
        
        # 如果有记录，查看第一条记录的id类型
        if count > 0:
            cursor.execute("SELECT id, username FROM users LIMIT 1")
            user = cursor.fetchone()
            print(f"\n第一条用户记录的ID: {user[0]}")
            print(f"第一条用户记录的用户名: {user[1]}")
            print(f"ID的数据类型: {type(user[0])}")
        
    except Exception as e:
        logger.error(f"检查数据库结构时出错: {e}")
        print(f"检查数据库结构时出错: {e}")
    finally:
        # 关闭游标和连接
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    check_users_table_structure()