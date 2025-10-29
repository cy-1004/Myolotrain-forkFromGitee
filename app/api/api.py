from fastapi import APIRouter

from app.api.endpoints import auth, datasets, models, training, detection, opencv, video, tracking, streaming, annotation, settings, tools, sync_detection, monitoring

api_router = APIRouter()
# 认证路由
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# 功能模块路由
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(detection.router, prefix="/detection", tags=["detection"])
api_router.include_router(sync_detection.router, prefix="/sync-detection", tags=["sync-detection"])
api_router.include_router(opencv.router, prefix="/opencv", tags=["opencv"])
api_router.include_router(video.router, prefix="/video", tags=["video"])
api_router.include_router(tracking.router, prefix="/tracking", tags=["tracking"])
api_router.include_router(streaming.router, prefix="/streaming", tags=["streaming"])
api_router.include_router(annotation.router, prefix="/annotation", tags=["annotation"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])