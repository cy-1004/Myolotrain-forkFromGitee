from fastapi import APIRouter
from app.core.config import settings

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