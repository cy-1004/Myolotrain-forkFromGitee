import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.types import StoredPath

# 待审核（pending）候选的数量上限。
# 拼图是随机批量生成的，不设上限的话待定区会无限堆积、把磁盘吃光。
MOSAIC_PENDING_LIMIT = 50


class MosaicCandidate(Base):
    """Mosaic 拼图候选

    拼图产物不直接进训练集，先落在待定区由人工审核：
    采纳（写入目标数据集）/ 丢弃（删文件）/ 暂留（保持 pending）。
    因为"暂留"是第三态，状态必须持久化，刷新页面或换台机器都不能丢。
    """
    __tablename__ = "mosaic_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 来源数据集（四张子图都取自同一个数据集，否则 class_id 对不上会静默产出错标数据）
    source_dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=True)
    # 采纳时写入的目标数据集，默认是单独新建的 xxx_mosaic
    target_dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=True)

    source_images = Column(JSON, default=list)   # 参与拼图的四个源文件相对路径，便于溯源
    image_path = Column(StoredPath, nullable=False)  # 待定区里的拼图文件路径
    preview_path = Column(StoredPath, nullable=True) # 叠加了标注框的预览图，用于人工校验标签
    labels = Column(JSON, default=list)          # 变换后的 YOLO 标签

    status = Column(String, default="pending", index=True)  # pending / accepted / discarded
    seed = Column(Integer, nullable=True)        # 该次随机采样的种子，可复现
    batch_id = Column(String, nullable=True, index=True)  # 同一次生成的归为一批

    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    creator = relationship("User", foreign_keys=[created_by])

    # 审核界面按 (来源数据集, 状态) 拉列表，走该索引
    __table_args__ = (
        Index("ix_mosaic_candidates_review", "source_dataset_id", "status", "created_at"),
    )
