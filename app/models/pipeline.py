"""文物视频一键训练流水线的数据模型

一次"上传视频 → 切帧 → 清洗 → 自动标注 → 质量闸门 → [复核] → 构建数据集 → 训练 → 评估 → TFLite 导出校验 → 打包"
称为一个 Run。阶段状态、产物路径、指标都挂在 Run 上，文件产物放在 DATA_DIR/runs/<run_id>/ 下，
库里只存相对 DATA_DIR 的路径。
"""
import uuid
from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String,
                        Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    external_ref = Column(String(128), nullable=True, index=True)  # 调用方自己的业务单号，便于对账

    # queued / running / needs_review / succeeded / failed / cancelling / cancelled
    status = Column(String(20), nullable=False, default="queued", index=True)
    current_stage = Column(String(32), nullable=True)
    review_mode = Column(String(20), nullable=False, default="on_anomaly")  # auto / on_anomaly / full

    classes = Column(JSON, nullable=False)   # 冻结的类别列表（顺序即 class_id），一路带到 labels.txt
    config = Column(JSON, nullable=False)    # 创建时的配置快照（已补全默认值）
    stage_states = Column(JSON, nullable=False, default=dict)  # {stage: {status, progress, started_at, ended_at, error, ...}}
    artifacts = Column(JSON, nullable=False, default=dict)     # 产物：标注项目、数据集、训练任务、模型、交付文件（相对路径）
    metrics = Column(JSON, nullable=False, default=dict)       # 帧数漏斗、自动标注统计、模型指标、TFLite 校验结果
    gate_results = Column(JSON, nullable=False, default=list)  # 质量闸门逐项结果
    llm_usage = Column(JSON, nullable=False, default=dict)     # VLM 调用次数 / token / 费用
    progress = Column(Float, nullable=False, default=0.0)      # 0~1 的整体进度

    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    source = Column(String(16), nullable=False, default="api")  # api / console
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    idempotency_key = Column(String(128), nullable=True)
    request_hash = Column(String(64), nullable=True)
    callback_url = Column(String(2048), nullable=True)
    callback_events = Column(JSON, nullable=True)

    cancel_requested = Column(Boolean, nullable=False, default=False)
    attempt = Column(Integer, nullable=False, default=0)  # 被调度执行的次数（服务重启后自动续跑会 +1）
    worker_id = Column(String(128), nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    videos = relationship("PipelineVideo", back_populates="run", cascade="all, delete-orphan",
                          order_by="PipelineVideo.position")

    __table_args__ = (
        # 同一个 API Key 下幂等键唯一；控制台创建的 Run 没有 api_key_id，Postgres 中多个 NULL 互不冲突
        UniqueConstraint("api_key_id", "idempotency_key", name="uq_pipeline_runs_idempotency"),
    )


class PipelineVideo(Base):
    __tablename__ = "pipeline_videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False, default=0)
    key = Column(String(64), nullable=False)          # 调用方给的视频标识（帧文件名前缀），run 内唯一
    original_filename = Column(String, nullable=True)
    class_name = Column(String(64), nullable=False)   # 主类别（声明的第一个），兼容只看单类别的地方
    class_id = Column(Integer, nullable=False)
    class_names = Column(JSON, nullable=True)          # 声明的全部类别；为空时即 [class_name]
    expected_instances = Column(Integer, nullable=False, default=1)
    options = Column(JSON, nullable=False, default=dict)   # 单视频覆盖项（skip_start/skip_end 等）

    rel_path = Column(String, nullable=True)   # 相对 DATA_DIR
    sha256 = Column(String(64), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    fps = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # ok / excluded（人工排除）/ failed（抽帧失败等）
    status = Column(String(16), nullable=False, default="ok")
    stats = Column(JSON, nullable=False, default=dict)   # 各阶段的帧数漏斗、闸门指标
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("PipelineRun", back_populates="videos")

    __table_args__ = (UniqueConstraint("run_id", "key", name="uq_pipeline_videos_run_key"),)


class PipelineEvent(Base):
    """Run 的事件时间线。id 自增，外部接口用 ?after=<id> 增量拉取"""
    __tablename__ = "pipeline_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    level = Column(String(10), nullable=False, default="info")   # info / warning / error
    stage = Column(String(32), nullable=True)
    type = Column(String(64), nullable=False)                     # 如 stage.started / gate.paused / job.succeeded
    message = Column(Text, nullable=True)
    data = Column(JSON, nullable=True)
    actor = Column(String(64), nullable=True)                     # system / user:<id> / api_key:<prefix>

    __table_args__ = (Index("ix_pipeline_events_run_id_id", "run_id", "id"),)


class PipelineUpload(Base):
    """分片上传的视频。上传完成后被创建 Run 时引用（consumed），未使用的过期清理"""
    __tablename__ = "pipeline_uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    received_bytes = Column(BigInteger, nullable=False, default=0)
    sha256_expected = Column(String(64), nullable=True)
    sha256 = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, default="uploading")  # uploading / ready / consumed / expired
    rel_path = Column(String, nullable=False)
    video_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class WebhookDelivery(Base):
    """待投递 / 已投递的 webhook。由编排器循环投递，失败按退避重试（至少送达一次）"""
    __tablename__ = "webhook_deliveries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(BigInteger, nullable=True)
    event_type = Column(String(64), nullable=False)
    url = Column(String(2048), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(16), nullable=False, default="pending")  # pending / delivered / failed
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=True, index=True)
    last_status_code = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
