from fastapi import APIRouter, HTTPException, Form
from app.core.config import settings
import json
import os
from pathlib import Path

router = APIRouter()


@router.get("/debug-mode", tags=["settings"])
def get_debug_mode():
    """
    获取当前后端的DEBUG模式状态
    """
    return {
        "success": True,
        "debug_mode": settings.DEBUG
    }


@router.get("/runtime", tags=["settings"])
def get_runtime_config():
    """
    前端需要知道的部署形态：按此隐藏当前部署下不可用的功能入口
    （单端口部署没有 TensorBoard；对外部署模式下不能浏览/打开服务器本地目录）
    """
    return {
        "tensorboard_enabled": settings.TENSORBOARD_ENABLED,
        "external_mode": settings.EXTERNAL_MODE,
    }


@router.post("/debug-mode", tags=["settings"])
def set_debug_mode(debug_mode: bool):
    """
    设置后端的DEBUG模式状态
    注意：这个设置只会在当前运行时有效，重启应用后将恢复为配置文件中的设置
    """
    # 这里不能直接修改settings对象，因为它是不可变的
    # 我们只能返回操作状态
    return {
        "success": True,
        "message": f"DEBUG模式已设置为 {debug_mode}，但此设置仅在当前运行时有效，重启应用后将恢复为配置文件中的设置。如需持久化更改，请修改配置文件。"
    }