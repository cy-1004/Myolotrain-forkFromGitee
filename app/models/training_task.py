import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base

class TrainingTask(Base):
    __tablename__ = "training_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=True)  # 允许为空，支持使用本地数据集路径
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"), nullable=True)
    output_model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"), nullable=True)
    parameters = Column(JSON, nullable=False)
    hardware_config = Column(JSON, nullable=True)  # 硬件配置，包括 CPU、GPU 和内存等
    status = Column(String, default="pending")  # pending, downloading_model, training, completed, failed, cancelled
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    log_path = Column(String, nullable=True)
    tensorboard_path = Column(String, nullable=True)
    process_id = Column(String, nullable=True)  # 训练进程的PID
    last_checkpoint = Column(String, nullable=True)  # 最后一次检查点的路径，用于继续训练

    # Relationships
    dataset = relationship("Dataset", foreign_keys=[dataset_id])
    model = relationship("Model", foreign_keys=[model_id])
    output_model = relationship("Model", foreign_keys=[output_model_id])
