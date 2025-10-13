from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.crud.user import get_user_by_username, update_user
from app.schemas.user import UserUpdate
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def change_admin_password(new_password: str):
    """修改管理员用户的密码"""
    db = SessionLocal()
    try:
        # 获取管理员用户
        admin_user = get_user_by_username(db, username="admin")
        if admin_user:
            # 创建用户更新对象，提供所有必需字段
            user_update = UserUpdate(
                username=admin_user.username,
                role=admin_user.role,
                password=new_password
            )
            # 更新用户密码
            updated_user = update_user(db=db, db_user=admin_user, user=user_update)
            logger.info("Admin user password updated successfully")
            return True
        else:
            logger.error("Admin user not found")
            return False
    finally:
        db.close()

if __name__ == "__main__":
    # 设置新密码
    new_password = "bjt@2014-2024"
    success = change_admin_password(new_password)
    if success:
        print("管理员密码已成功修改为：", new_password)
    else:
        print("修改管理员密码失败")