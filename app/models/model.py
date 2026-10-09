import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base
from app.db.types import StoredPath

class Model(Base):
    __tablename__ = "models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    path = Column(StoredPath, nullable=False)
    type = Column(String, nullable=False)  # yolov8n, yolov8s, yolov8m, yolov8l, yolov8x
    task = Column(String, nullable=False, default="detect")  # detect, segment, classify, pose
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    source = Column(String, default="upload")  # upload, training
