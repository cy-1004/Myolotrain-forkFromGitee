from fastapi import APIRouter

from app.api.endpoints import datasets, models, training, detection

api_router = APIRouter()
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(detection.router, prefix="/detection", tags=["detection"])
