import uuid
from datetime import datetime, timedelta
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.types import StoredPath

# 标注租约有效期：持有者每 60 秒续期一次，超时未续期则视为已释放，
# 避免标注员浏览器崩溃或直接关页面后图片被永久锁死
ANNOTATION_LEASE_TTL = timedelta(minutes=5)

class AnnotationProject(Base):
    __tablename__ = "annotation_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=True)
    classes = Column(JSON, nullable=False)  # 类别列表
    class_keypoints = Column(JSON, nullable=True)  # 类别和关键点的映射关系
    image_directory = Column(StoredPath, nullable=False)  # 图片目录路径
    project_type = Column(String, default="detection")  # detection, segmentation, obb, keypoints
    import_original_annotations = Column(Boolean, default=False)  # 是否导入原标注
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

    # 多人协作字段
    version = Column(Integer, nullable=False, default=1, server_default="1")  # 乐观锁版本号，每次保存自增
    locked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # 租约持有者
    locked_at = Column(DateTime, nullable=True)  # 租约最后续期时间，配合 ANNOTATION_LEASE_TTL 判断是否过期
    last_edited_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # 最后修改者

    # 关联关系
    project = relationship("AnnotationProject", back_populates="image_annotations")
    locker = relationship("User", foreign_keys=[locked_by])
    last_editor = relationship("User", foreign_keys=[last_edited_by])

    # 认领接口按 (项目, 未完成, 租约) 过滤，走该索引避免全表扫描
    __table_args__ = (
        Index("ix_image_annotations_claim", "project_id", "is_completed", "locked_at"),
    )