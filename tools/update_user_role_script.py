from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.crud.user import get_user_by_username, update_user
from app.schemas.user import UserUpdate
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_admin_user_role(new_role: str):
    """更新管理员用户的角色"""
    db = SessionLocal()
    try:
        # 获取管理员用户
        admin_user = get_user_by_username(db, username="admin")
        if admin_user:
            logger.info(f"当前用户信息 - ID: {admin_user.id}, 用户名: {admin_user.username}, 当前角色: {admin_user.role}")
            
            # 创建用户更新对象
            user_update = UserUpdate(
                username=admin_user.username,
                role=new_role,
                password=None  # 不修改密码
            )
            
            # 更新用户角色
            updated_user = update_user(db=db, db_user=admin_user, user=user_update)
            logger.info(f"成功将用户 {updated_user.username} 的角色更新为 {updated_user.role}")
            print(f"成功将用户 {updated_user.username} 的角色从 {admin_user.role} 更新为 {updated_user.role}")
            return True
        else:
            logger.error("未找到用户名为admin的用户")
            print("未找到用户名为admin的用户")
            return False
    finally:
        db.close()

if __name__ == "__main__":
    # 设置新角色为admin
    new_role = "admin"
    success = update_admin_user_role(new_role)
    if not success:
        print("更新管理员角色失败")