from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import uuid

from app.api.deps import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_active_user,
    get_current_admin_user,
)
from app.crud.user import (
    authenticate_user,
    create_user,
    delete_user,
    get_user,
    get_users,
    update_user,
    get_user_by_username,
    verify_password
)
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import User, UserCreate, UserUpdate, Token
from pydantic import BaseModel

router = APIRouter()

# 密码更新请求模型
class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """用户登录，获取访问令牌"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 更新用户最后登录时间
    user.last_login = datetime.utcnow()
    db.commit()
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/validate-token")
async def validate_token(
    current_user: User = Depends(get_current_active_user)
):
    """验证访问令牌的有效性"""
    return {"valid": True, "username": current_user.username, "role": current_user.role}

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user)
):
    """用户退出登录
    注意：由于JWT令牌是无状态的，此端点主要用于前端清除令牌
    实际的令牌过期由JWT的expire时间控制
    """
    # 在实际应用中，你可能希望将令牌添加到黑名单中
    # 这里仅返回成功信息
    return {"message": "Successfully logged out"}

@router.post("/users", response_model=User)
async def create_new_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """创建新用户（管理员权限）"""
    # 检查用户名是否已存在
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    return create_user(db=db, user=user)

@router.get("/users/me", response_model=User)
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户信息"""
    return current_user

@router.put("/users/me/password")
async def update_current_user_password(
    password_update: PasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新当前用户密码
    用户需要提供当前密码进行验证，验证通过后可以设置新密码
    """
    # 验证当前密码是否正确
    if not verify_password(password_update.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # 创建UserUpdate对象，包含当前用户的username、role和新密码
    user_update = UserUpdate(
        username=current_user.username,
        role=current_user.role,
        password=password_update.new_password
    )
    
    # 更新用户密码
    updated_user = update_user(db=db, db_user=current_user, user=user_update)
    
    return {"message": "Password updated successfully"}

@router.get("/users", response_model=List[User])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """获取用户列表（仅管理员可访问）"""
    users = get_users(db, skip=skip, limit=limit)
    return users

@router.get("/users/{user_id}", response_model=User)
async def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取单个用户信息
    - 管理员可以查看所有用户
    - 普通用户只能查看自己
    """
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 检查权限
    if current_user.role != UserRole.ADMIN and db_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return db_user

@router.put("/users/{user_id}", response_model=User)
async def update_existing_user(
    user_id: int,
    user: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """更新用户信息（管理员权限）"""
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 如果更新了用户名，检查新用户名是否已存在
    if user.username and user.username != db_user.username:
        existing_user = get_user_by_username(db, username=user.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
    
    return update_user(db=db, db_user=db_user, user=user)

@router.delete("/users/{user_id}")
async def delete_existing_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """删除用户（管理员权限）"""
    # 不允许删除当前登录的管理员用户
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete current admin user"
        )
    
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    delete_user(db=db, db_user=db_user)
    return {"message": "User deleted successfully"}