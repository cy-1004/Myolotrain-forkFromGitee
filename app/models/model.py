import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base

class Model(Base):
    __tablename__ = "models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    path = Column(String, nullable=False)
    type = Column(String, nullable=False)  # yolov8n, yolov8s, yolov8m, yolov8l, yolov8x
    task = Column(String, nullable=False, default="detect")  # detect, segment, classify, pose
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source = Column(String, default="upload")  # upload, training
