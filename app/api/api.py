from fastapi import APIRouter, Depends



from app.api.deps import require_console_user
from app.api.endpoints import auth, datasets, models, training, detection, opencv, video, tracking, streaming, annotation, settings, tools, sync_detection, monitoring, comparison, sam3, frame_extraction, health

api_router = APIRouter()
# 无需登录的路由：健康检查；认证路由内部各接口自行鉴权（/token 登录接口本身必须开放）
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# 功能模块路由：统一要求登录（Bearer 头或登录 Cookie），见 deps.require_console_user。
# 个别接口在此基础上还要求管理员或资源归属，由接口自身的依赖声明。
_console = [Depends(require_console_user)]
api_router.include_router(sam3.router, prefix="/sam3", tags=["sam3"], dependencies=_console)
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"], dependencies=_console)
api_router.include_router(models.router, prefix="/models", tags=["models"], dependencies=_console)
api_router.include_router(training.router, prefix="/training", tags=["training"], dependencies=_console)
api_router.include_router(detection.router, prefix="/detection", tags=["detection"], dependencies=_console)
api_router.include_router(sync_detection.router, prefix="/sync-detection", tags=["sync-detection"], dependencies=_console)
api_router.include_router(opencv.router, prefix="/opencv", tags=["opencv"], dependencies=_console)
api_router.include_router(video.router, prefix="/video", tags=["video"], dependencies=_console)
api_router.include_router(frame_extraction.router, prefix="/frame-extraction", tags=["frame-extraction"], dependencies=_console)
api_router.include_router(tracking.router, prefix="/tracking", tags=["tracking"], dependencies=_console)
api_router.include_router(streaming.router, prefix="/streaming", tags=["streaming"], dependencies=_console)
api_router.include_router(annotation.router, prefix="/annotation", tags=["annotation"], dependencies=_console)
api_router.include_router(settings.router, prefix="/settings", tags=["settings"], dependencies=_console)
api_router.include_router(tools.router, prefix="/tools", tags=["tools"], dependencies=_console)
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"], dependencies=_console)
api_router.include_router(comparison.router, prefix="/comparison", tags=["comparison"], dependencies=_console)
