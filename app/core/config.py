import os
from pathlib import Path
from typing import Any, List, Optional

from pydantic import AnyHttpUrl, PostgresDsn, field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "YOLOv8 Training Platform"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False  # 全局DEBUG模式开关

    # Database
    POSTGRES_SERVER: str = "localhost"  # 本地环境使用 localhost
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"   # 使用你设置的密码
    POSTGRES_DB: str = "yolov8_platform"
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        if isinstance(v, str):
            return v

        # 从模型中获取值
        values = {}
        for field_name in ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_SERVER", "POSTGRES_DB"]:
            try:
                values[field_name] = info.data.get(field_name)
            except (KeyError, AttributeError):
                values[field_name] = None

        return PostgresDsn.build(
            scheme="postgresql",
            username=values["POSTGRES_USER"],
            password=values["POSTGRES_PASSWORD"],
            host=values["POSTGRES_SERVER"],
            path=f"{values['POSTGRES_DB'] or ''}",
            query="client_encoding=utf8"
        )

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STATIC_DIR: Path = BASE_DIR / "app" / "static"
    UPLOADS_DIR: Path = STATIC_DIR / "uploads"
    DATASETS_DIR: Path = STATIC_DIR / "datasets"
    MODELS_DIR: Path = STATIC_DIR / "models"
    RESULTS_DIR: Path = STATIC_DIR / "results"
    TEMP_DIR: Path = STATIC_DIR / "temp"

    # TensorBoard
    TENSORBOARD_LOGS_DIR: Path = BASE_DIR / "logs" / "tensorboard"
    TENSORBOARD_PORT: int = 6006

    # YOLOv8 Settings
    YOLO_MODEL_TYPES: List[str] = ["yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x"]
    YOLO_TASK_TYPES: List[str] = ["detect", "segment", "pose", "obb", "detection", "segmentation", "keypoints"]

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "allow"  # 允许额外的配置项

settings = Settings()

# Create directories if they don't exist
for directory in [
    settings.UPLOADS_DIR,
    settings.DATASETS_DIR,
    settings.MODELS_DIR,
    settings.RESULTS_DIR,
    settings.TENSORBOARD_LOGS_DIR,
    settings.TEMP_DIR,
]:
    os.makedirs(directory, exist_ok=True)

