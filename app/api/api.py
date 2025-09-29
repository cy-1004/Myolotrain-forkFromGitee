from fastapi import APIRouter

from app.api.endpoints import datasets, models, training, detection, opencv, video, tracking, streaming, annotation, settings, tools

api_router = APIRouter()
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(detection.router, prefix="/detection", tags=["detection"])
api_router.include_router(opencv.router, prefix="/opencv", tags=["opencv"])
api_router.include_router(video.router, prefix="/video", tags=["video"])
api_router.include_router(tracking.router, prefix="/tracking", tags=["tracking"])
api_router.include_router(streaming.router, prefix="/streaming", tags=["streaming"])
api_router.include_router(annotation.router, prefix="/annotation", tags=["annotation"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
