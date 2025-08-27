import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base

class AnnotationProject(Base):
    __tablename__ = "annotation_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=True)
    classes = Column(JSON, nullable=False)  # 类别列表
    image_directory = Column(String, nullable=False)  # 图片目录路径
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String, default="active")  # active, completed, archived

    # 关联关系
    dataset = relationship("Dataset", back_populates="annotation_projects")
    image_annotations = relationship("ImageAnnotation", back_populates="project", cascade="all, delete-orphan")

class ImageAnnotation(Base):
    __tablename__ = "image_annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("annotation_projects.id"), nullable=False)
    image_path = Column(String, nullable=False)  # 相对于项目目录的路径
    image_name = Column(String, nullable=False)  # 图片文件名
    annotations = Column(JSON, default=list)  # YOLO格式标注数据
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联关系
    project = relationship("AnnotationProject", back_populates="image_annotations")