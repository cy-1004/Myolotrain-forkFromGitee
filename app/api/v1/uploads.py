"""分片上传（大视频用）

1. POST /uploads {filename, size, sha256?} → upload_id、建议分片大小
2. PUT /uploads/{id}，请求体为分片原始字节，带 Content-Range: bytes <start>-<end>/<total>；
   分片必须按顺序，start 与服务端已接收字节数不一致时返回 409 和当前进度，客户端据此断点续传
3. POST /uploads/{id}/complete → 校验大小与 sha256、探测视频，状态变为 ready
4. 创建任务时在 videos[].upload_id 里引用；未使用的上传 UPLOAD_EXPIRE_HOURS 小时后过期
"""
import hashlib
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import require_scope
from app.core.config import settings
from app.core.paths import data_path, from_data_relative, to_data_relative
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.pipeline import PipelineUpload
from app.services.pipeline.events import isoformat
from app.services.pipeline.service import VIDEO_EXTS, ServiceError, check_disk
from app.services.pipeline.stages.ingest import probe_video

router = APIRouter()
_RANGE_RE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")


class UploadCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)
    sha256: Optional[str] = Field(None, pattern=r"^[0-9a-fA-F]{64}$")


def _serialize(u: PipelineUpload) -> dict:
    return {"upload_id": str(u.id), "filename": u.filename, "size": u.size_bytes, "received": u.received_bytes,
            "status": u.status, "chunk_size": settings.UPLOAD_CHUNK_BYTES, "expires_at": isoformat(u.expires_at),
            "video": u.video_info}


def _get_owned(db: Session, upload_id: str, api_key: ApiKey) -> PipelineUpload:
    try:
        uuid.UUID(upload_id)
    except ValueError:
        raise ServiceError("not_found", "上传不存在", http_status=404)
    u = db.query(PipelineUpload).filter(PipelineUpload.id == upload_id, PipelineUpload.api_key_id == api_key.id).first()
    if u is None:
        raise ServiceError("not_found", "上传不存在", http_status=404)
    if u.status == "uploading" and u.expires_at and u.expires_at < datetime.utcnow():
        u.status = "expired"
        db.commit()
    return u


@router.post("", status_code=201, summary="创建分片上传")
def create_upload(body: UploadCreate, db: Session = Depends(get_db), api_key: ApiKey = Depends(require_scope("pipeline:write"))):
    ext = Path(body.filename).suffix.lower()
    if ext not in VIDEO_EXTS:
        raise ServiceError("video_unreadable", f"不支持的视频格式 {ext or '(无扩展名)'}", http_status=422)
    if body.size > settings.PIPELINE_MAX_VIDEO_MB * 1024 * 1024:
        raise ServiceError("payload_too_large", f"视频大小超过上限 {settings.PIPELINE_MAX_VIDEO_MB} MB", http_status=413)
    check_disk()
    upload_id = uuid.uuid4()
    part = data_path("uploads", f"{upload_id}.part")
    part.parent.mkdir(parents=True, exist_ok=True)
    part.touch()
    u = PipelineUpload(id=upload_id, api_key_id=api_key.id, filename=Path(body.filename).name, size_bytes=body.size,
                       received_bytes=0, sha256_expected=(body.sha256 or "").lower() or None, status="uploading",
                       rel_path=to_data_relative(part),
                       expires_at=datetime.utcnow() + timedelta(hours=settings.UPLOAD_EXPIRE_HOURS))
    db.add(u)
    db.commit()
    return _serialize(u)


@router.put("/{upload_id}", summary="上传一个分片")
async def put_chunk(upload_id: str, request: Request, db: Session = Depends(get_db),
                    api_key: ApiKey = Depends(require_scope("pipeline:write"))):
    u = await run_in_threadpool(_get_owned, db, upload_id, api_key)
    if u.status != "uploading":
        raise ServiceError("invalid_state", f"上传状态为 {u.status}，不能继续上传", http_status=409)
    m = _RANGE_RE.match(request.headers.get("content-range", ""))
    if not m:
        raise ServiceError("invalid_spec", "缺少或格式错误的 Content-Range（应为 bytes <start>-<end>/<total>）", http_status=422)
    start, end, total = map(int, m.groups())
    if total != u.size_bytes or end < start or end >= total:
        raise ServiceError("invalid_spec", "Content-Range 与上传声明的大小不一致", http_status=422)
    if start != u.received_bytes:
        raise ServiceError("offset_mismatch", f"分片起点 {start} 与已接收字节数 {u.received_bytes} 不一致，请从该位置继续",
                           http_status=409, details={"received": u.received_bytes})
    expected_len = end - start + 1
    if expected_len > settings.UPLOAD_CHUNK_BYTES * 4:
        raise ServiceError("payload_too_large", "单个分片过大", http_status=413)

    part = from_data_relative(u.rel_path)
    written = 0
    with open(part, "r+b") as f:
        f.seek(start)
        async for block in request.stream():
            written += len(block)
            if written > expected_len:
                f.truncate(start)
                raise ServiceError("invalid_spec", "分片实际长度大于 Content-Range 声明的长度", http_status=422)
            f.write(block)
        if written != expected_len:
            f.truncate(start)
            raise ServiceError("invalid_spec", f"分片长度 {written} 与 Content-Range 声明的 {expected_len} 不一致", http_status=422)
    u.received_bytes = start + written
    db.commit()
    return _serialize(u)


@router.get("/{upload_id}", summary="查询上传进度（断点续传用）")
def get_upload(upload_id: str, db: Session = Depends(get_db), api_key: ApiKey = Depends(require_scope("pipeline:write"))):
    return _serialize(_get_owned(db, upload_id, api_key))


@router.post("/{upload_id}/complete", summary="完成上传：校验并探测视频")
def complete_upload(upload_id: str, db: Session = Depends(get_db), api_key: ApiKey = Depends(require_scope("pipeline:write"))):
    u = _get_owned(db, upload_id, api_key)
    if u.status == "ready":
        return _serialize(u)
    if u.status != "uploading":
        raise ServiceError("invalid_state", f"上传状态为 {u.status}", http_status=409)
    if u.received_bytes != u.size_bytes:
        raise ServiceError("invalid_state", f"还未上传完：已接收 {u.received_bytes}/{u.size_bytes} 字节", http_status=409,
                           details={"received": u.received_bytes})
    part = from_data_relative(u.rel_path)
    h = hashlib.sha256()
    with open(part, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    digest = h.hexdigest()
    if u.sha256_expected and digest != u.sha256_expected:
        u.status = "failed"
        db.commit()
        raise ServiceError("checksum_mismatch", "sha256 校验失败，文件在传输中损坏，请重新上传", http_status=422,
                           details={"expected": u.sha256_expected, "actual": digest})
    final = part.with_suffix(Path(u.filename).suffix.lower())
    os.replace(part, final)
    try:
        info = probe_video(final)
    except ValueError as e:
        u.status, u.rel_path = "failed", to_data_relative(final)
        db.commit()
        raise ServiceError("video_unreadable", f"视频无法读取: {e}", http_status=422)
    u.status, u.sha256, u.rel_path, u.video_info = "ready", digest, to_data_relative(final), info
    db.commit()
    return _serialize(u)
