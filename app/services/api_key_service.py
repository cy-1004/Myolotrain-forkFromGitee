"""对外接口 API Key：生成、校验、吊销；webhook 签名密钥的加解密

key 形如 myo_sk_<prefix 8 位>_<secret 32 位>，只在创建时返回一次。
库里存 prefix（查找用）和 HMAC-SHA256(服务端密钥, 完整 key)（校验用）——即使数据库泄露也拿不到可用的 key。
webhook 密钥需要原文才能签名，所以加密存储（Fernet，密钥由 SECRET_KEY 派生）：
更换 SECRET_KEY 后已有 key 的 webhook 签名密钥将无法解密，需要重新创建 key。
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime
from typing import List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.api.deps import SECRET_KEY
from app.models.api_key import ApiKey

KEY_PREFIX = "myo_sk_"
ALL_SCOPES = ("pipeline:write", "pipeline:read", "artifacts:read")
DEFAULT_SCOPES = list(ALL_SCOPES)


def _pepper(purpose: str) -> bytes:
    return hmac.new(SECRET_KEY.encode(), purpose.encode(), hashlib.sha256).digest()


def hash_key(full_key: str) -> str:
    return hmac.new(_pepper("api-key"), full_key.encode(), hashlib.sha256).hexdigest()


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_pepper("webhook-secret-encryption")))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def default_webhook_secret() -> str:
    """控制台创建的任务（没有 API Key）回调时使用的签名密钥"""
    return _pepper("console-webhook").hex()


def create_api_key(db: Session, name: str, scopes: Optional[List[str]] = None, created_by: Optional[int] = None,
                   expires_at: Optional[datetime] = None) -> Tuple[ApiKey, str, str]:
    """返回 (记录, 完整 key, webhook 密钥)。后两者只在这里出现一次"""
    scopes = list(scopes or DEFAULT_SCOPES)
    unknown = set(scopes) - set(ALL_SCOPES)
    if unknown:
        raise ValueError(f"未知的权限范围: {sorted(unknown)}")
    while True:
        prefix = secrets.token_hex(4)
        if not db.query(ApiKey).filter(ApiKey.prefix == prefix).first():
            break
    full_key = f"{KEY_PREFIX}{prefix}_{secrets.token_urlsafe(24)}"
    webhook_secret = "whsec_" + secrets.token_urlsafe(24)
    record = ApiKey(name=name, prefix=prefix, key_hash=hash_key(full_key), scopes=scopes,
                    webhook_secret_enc=encrypt_secret(webhook_secret), created_by=created_by, expires_at=expires_at)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, full_key, webhook_secret


def parse_prefix(full_key: str) -> Optional[str]:
    if not full_key or not full_key.startswith(KEY_PREFIX):
        return None
    rest = full_key[len(KEY_PREFIX):]
    prefix, sep, secret = rest.partition("_")
    if not sep or len(prefix) != 8 or not secret:
        return None
    return prefix


def verify_api_key(db: Session, full_key: str) -> Optional[ApiKey]:
    prefix = parse_prefix(full_key)
    if not prefix:
        return None
    record = db.query(ApiKey).filter(ApiKey.prefix == prefix).first()
    if record is None or not hmac.compare_digest(record.key_hash, hash_key(full_key)):
        return None
    now = datetime.utcnow()
    if record.revoked_at is not None or (record.expires_at is not None and record.expires_at <= now):
        return None
    # 最后使用时间精确到分钟就够了，避免每个请求都写库
    if record.last_used_at is None or (now - record.last_used_at).total_seconds() > 60:
        record.last_used_at = now
        db.commit()
    return record


def revoke_api_key(db: Session, key_id) -> Optional[ApiKey]:
    record = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if record and record.revoked_at is None:
        record.revoked_at = datetime.utcnow()
        db.commit()
    return record
