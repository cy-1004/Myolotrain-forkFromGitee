from fastapi import APIRouter

from app.api.endpoints import datasets, models, training, detection, opencv, video

api_router = APIRouter()
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(detection.router, prefix="/detection", tags=["detection"])
api_router.include_router(opencv.router, prefix="/opencv", tags=["opencv"])
api_router.include_router(video.router, prefix="/video", tags=["video"])
