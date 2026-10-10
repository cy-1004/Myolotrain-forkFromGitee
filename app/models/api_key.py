import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class ApiKey(Base):
    """对外接口的调用凭据（机器对机器），与控制台的用户登录相互独立

    完整的 key 形如 myo_sk_<prefix>_<secret>，只在创建时展示一次；
    库里只存 prefix（用于查找）和整串 key 的 HMAC 摘要（用于校验）。
    """
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    prefix = Column(String(16), nullable=False, unique=True, index=True)
    key_hash = Column(String(64), nullable=False)
    scopes = Column(JSON, nullable=False, default=list)  # ["pipeline:write", "pipeline:read", "artifacts:read"]
    # webhook 签名密钥（加密存储；创建时与 key 一起展示一次）
    webhook_secret_enc = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
