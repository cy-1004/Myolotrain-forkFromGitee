"""流水线任务：创建 / 查询 / 事件 / 取消 / 续跑 / 下载交付物"""
import hashlib
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.api.v1.deps import get_owned_run, require_scope
from app.core.config import settings
from app.core.paths import data_path, from_data_relative
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.pipeline import PipelineEvent, PipelineRun, PipelineUpload
from app.services.pipeline import service
from app.services.pipeline.service import ServiceError, VideoSource
from app.services.pipeline.spec import JobSpec

router = APIRouter()

_FILE_COPY_BLOCK = 1024 * 1024


def _parse_spec(raw) -> JobSpec:
    try:
        return JobSpec.model_validate(raw)
    except ValidationError as e:
        details = [{"loc": list(err.get("loc", [])), "msg": err.get("msg")} for err in e.errors()]
        raise ServiceError("invalid_spec", "任务参数不合法", http_status=422, details=details)


def _spec_hash(spec_raw, file_hashes: Optional[List[str]] = None) -> str:
    h = hashlib.sha256(json.dumps(spec_raw, sort_keys=True, ensure_ascii=False).encode())
    for fh in file_hashes or []:
        h.update(fh.encode())
    return h.hexdigest()


async def _save_upload_file(upload, max_bytes: int) -> (Path, str, int):
    """把 multipart 中的文件流式写到数据目录（与 Run 目录在同一文件系统，之后可以直接移动），边写边算 sha256"""
    tmp = data_path("uploads", f"tmp_{uuid.uuid4().hex}{Path(upload.filename or '').suffix.lower()}")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    try:
        with open(tmp, "wb") as out:
            while True:
                block = await upload.read(_FILE_COPY_BLOCK)
                if not block:
                    break
                size += len(block)
                if size > max_bytes:
                    raise ServiceError("payload_too_large", f"视频 {upload.filename} 超过上限 {settings.PIPELINE_MAX_VIDEO_MB} MB",
                                       http_status=413)
                h.update(block)
                out.write(block)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp, h.hexdigest(), size


REFERENCE_FILE_MAX_BYTES = 5 * 1024 * 1024
REFERENCE_FILES_MAX = 300


async def parse_multipart_job(request: Request, temp_files: List[Path]):
    """解析 multipart 建任务请求：spec 字段（任务 JSON）+ videos 文件 + 可选的 references 参考图文件。
    对外接口与控制台共用

    写出的临时文件会追加到 temp_files，调用方负责在 finally 中清理（已被移入 Run 目录的文件自然不存在了）。
    填了 upload_id 的视频（大文件先分片上传、其余随请求上传的混合方式）不在这里处理，由调用方按 upload_id 解析。
    返回 (spec 原始 dict, JobSpec, {video_key: VideoSource}, {参考图文件名: 内容})
    """
    form = await request.form()
    raw_spec = form.get("spec")
    if not isinstance(raw_spec, str):
        raise ServiceError("invalid_spec", "multipart 请求缺少 spec 字段（任务 JSON 字符串）", http_status=422)
    try:
        spec_raw = json.loads(raw_spec)
    except ValueError:
        raise ServiceError("invalid_spec", "spec 不是合法的 JSON", http_status=422)
    spec = _parse_spec(spec_raw)
    files = [f for f in form.getlist("videos") if hasattr(f, "filename")]
    file_videos = [v for v in spec.videos if not v.upload_id]
    if file_videos and not files:
        raise ServiceError("invalid_spec", "multipart 请求中没有 videos 文件", http_status=422)
    saved = []
    for f in files:
        path, digest, _ = await _save_upload_file(f, settings.PIPELINE_MAX_VIDEO_MB * 1024 * 1024)
        temp_files.append(path)
        saved.append((f.filename, path, digest))
    by_name = {name: (name, path, digest) for name, path, digest in saved}
    sources = {}
    for i, v in enumerate(file_videos):
        if v.file:
            if v.file not in by_name:
                raise ServiceError("invalid_spec", f"视频 {v.key} 指定的文件 {v.file} 不在上传的文件中", http_status=422)
            name, path, digest = by_name[v.file]
        elif len(saved) == len(file_videos):
            name, path, digest = saved[i]
        else:
            raise ServiceError("invalid_spec", "上传文件数与 videos 数量不一致时，必须用 videos[].file 指定对应文件",
                               http_status=422)
        sources[v.key] = VideoSource(original_filename=name, path=path, sha256=digest)

    reference_files: Dict[str, bytes] = {}
    refs = [f for f in form.getlist("references") if hasattr(f, "filename")]
    if len(refs) > REFERENCE_FILES_MAX:
        raise ServiceError("invalid_spec", f"参考图最多 {REFERENCE_FILES_MAX} 张", http_status=422)
    for f in refs:
        data = await f.read(REFERENCE_FILE_MAX_BYTES + 1)
        if len(data) > REFERENCE_FILE_MAX_BYTES:
            raise ServiceError("payload_too_large", f"参考图 {f.filename} 超过 5 MB", http_status=413)
        reference_files[f.filename] = data
    return spec_raw, spec, sources, reference_files


def resolve_uploads(db: Session, api_key: ApiKey, videos, idempotency_key: Optional[str]) -> Dict[str, VideoSource]:
    """填了 upload_id 的视频 -> VideoSource（只能引用本 API Key 上传、已完成的文件）"""
    sources = {}
    for v in videos:
        try:
            uuid.UUID(v.upload_id)
        except ValueError:
            raise ServiceError("invalid_spec", f"视频 {v.key} 的 upload_id 格式不对", http_status=422)
        up = db.query(PipelineUpload).filter(PipelineUpload.id == v.upload_id,
                                             PipelineUpload.api_key_id == api_key.id).first()
        if up is None:
            raise ServiceError("invalid_spec", f"视频 {v.key} 的 upload_id 不存在", http_status=422)
        if up.status == "consumed" and idempotency_key:
            continue   # 幂等重放：文件已被原任务使用，交给 create_run 按幂等键返回原任务
        if up.status != "ready":
            raise ServiceError("invalid_spec", f"视频 {v.key} 的上传状态为 {up.status}，需要先完成上传", http_status=422)
        sources[v.key] = VideoSource(original_filename=up.filename, path=from_data_relative(up.rel_path),
                                     sha256=up.sha256, upload=up)
    return sources


@router.post("", status_code=202, summary="创建流水线任务",
             description="JSON：videos[].upload_id 引用分片上传的视频；"
                         "multipart：spec 字段为任务 JSON，videos 字段上传一个或多个视频文件（videos[].file 填文件名，或按顺序对应），"
                         "也可混用 upload_id（大文件先分片上传）；references 字段上传参考图（classes[].references[].file 引用）。"
                         "建议带 Idempotency-Key 请求头，网络重试时不会重复建任务。")
async def create_job(request: Request, db: Session = Depends(get_db),
                     api_key: ApiKey = Depends(require_scope("pipeline:write")),
                     idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", max_length=128)):
    content_type = request.headers.get("content-type", "")
    temp_files: List[Path] = []
    try:
        if content_type.startswith("multipart/form-data"):
            spec_raw, spec, sources, reference_files = await parse_multipart_job(request, temp_files)
            request_hash = _spec_hash(spec_raw, [s.sha256 for s in sources.values()]
                                      + [hashlib.sha256(reference_files[k]).hexdigest() for k in sorted(reference_files)])
            sources.update(resolve_uploads(db, api_key, [v for v in spec.videos if v.upload_id], idempotency_key))
        else:
            try:
                spec_raw = await request.json()
            except ValueError:
                raise ServiceError("invalid_spec", "请求体不是合法的 JSON", http_status=422)
            spec = _parse_spec(spec_raw)
            missing = [v.key for v in spec.videos if not v.upload_id]
            if missing:
                raise ServiceError("invalid_spec", f"视频 {missing} 缺少 upload_id（JSON 方式需先分片上传）", http_status=422)
            sources = resolve_uploads(db, api_key, spec.videos, idempotency_key)
            reference_files = {}
            request_hash = _spec_hash(spec_raw)

        run, created = await run_in_threadpool(service.create_run, db, spec, sources, api_key=api_key, source="api",
                                               idempotency_key=idempotency_key, request_hash=request_hash,
                                               reference_files=reference_files)
    finally:
        for p in temp_files:
            p.unlink(missing_ok=True)   # 已被移动进 Run 目录的文件这里不存在了，没移动的（出错时）清理掉
    body = service.serialize_run(run, detail=True, external=True)
    return JSONResponse(status_code=202 if created else 200, content=body,
                        headers={"Location": f"/api/v1/pipeline/jobs/{run.id}"})


@router.get("", summary="任务列表（只含当前 API Key 创建的任务）")
def list_jobs(db: Session = Depends(get_db), api_key: ApiKey = Depends(require_scope("pipeline:read")),
              status: Optional[str] = Query(None), external_ref: Optional[str] = Query(None),
              limit: int = Query(20, ge=1, le=100), before: Optional[str] = Query(None, description="分页游标")):
    q = db.query(PipelineRun).filter(PipelineRun.api_key_id == api_key.id)
    if status:
        q = q.filter(PipelineRun.status.in_(status.split(",")))
    if external_ref:
        q = q.filter(PipelineRun.external_ref == external_ref)
    if before:
        try:
            q = q.filter(PipelineRun.created_at < datetime.fromisoformat(before.rstrip("Z")))
        except ValueError:
            raise ServiceError("invalid_spec", "before 游标格式不对", http_status=422)
    rows = q.order_by(PipelineRun.created_at.desc()).limit(limit + 1).all()
    items = [service.serialize_run(r, external=True) for r in rows[:limit]]
    return {"items": items, "next_cursor": items[-1]["created_at"] if len(rows) > limit else None}


@router.get("/{job_id}", summary="任务详情")
def get_job(job_id: str, db: Session = Depends(get_db), api_key: ApiKey = Depends(require_scope("pipeline:read"))):
    return service.serialize_run(get_owned_run(db, job_id, api_key), detail=True, external=True)


@router.get("/{job_id}/events", summary="任务事件（增量：带上 after=上次最后一条的 id）")
def get_events(job_id: str, after: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000),
               db: Session = Depends(get_db), api_key: ApiKey = Depends(require_scope("pipeline:read"))):
    run = get_owned_run(db, job_id, api_key)
    rows = (db.query(PipelineEvent).filter(PipelineEvent.run_id == run.id, PipelineEvent.id > after)
            .order_by(PipelineEvent.id).limit(limit).all())
    items = [service.serialize_event(e, external=True) for e in rows]
    return {"items": items, "next_after": items[-1]["id"] if items else after}


class ResumeBody(BaseModel):
    from_stage: Optional[str] = None


@router.post("/{job_id}/cancel", summary="取消任务")
def cancel_job(job_id: str, db: Session = Depends(get_db), api_key: ApiKey = Depends(require_scope("pipeline:write"))):
    run = service.cancel_run(db, get_owned_run(db, job_id, api_key), api_key=api_key)
    return service.serialize_run(run, detail=True, external=True)


@router.post("/{job_id}/resume", summary="续跑失败/取消的任务")
def resume_job(job_id: str, body: ResumeBody = ResumeBody(), db: Session = Depends(get_db),
               api_key: ApiKey = Depends(require_scope("pipeline:write"))):
    run = service.resume_run(db, get_owned_run(db, job_id, api_key), body.from_stage, api_key=api_key)
    return service.serialize_run(run, detail=True, external=True)


@router.get("/{job_id}/artifacts", summary="交付物列表")
def list_artifacts(job_id: str, db: Session = Depends(get_db), api_key: ApiKey = Depends(require_scope("artifacts:read"))):
    run = get_owned_run(db, job_id, api_key)
    files = service.delivery_files(run)
    return {"job_id": str(run.id), "status": run.status, "items": [
        {"name": name, "size": f["size"], "sha256": f["sha256"],
         "url": f"/api/v1/pipeline/jobs/{run.id}/artifacts/{name}"} for name, f in files.items()]}


@router.get("/{job_id}/artifacts/{name}", summary="下载交付物（支持 Range 断点续传）")
def download_artifact(job_id: str, name: str, db: Session = Depends(get_db),
                      api_key: ApiKey = Depends(require_scope("artifacts:read"))):
    run = get_owned_run(db, job_id, api_key)
    files = service.delivery_files(run)
    if name not in files:
        raise ServiceError("not_found", f"交付物 {name} 不存在（任务完成后才会生成）", http_status=404)
    path = from_data_relative(files[name]["path"])
    if not path.exists():
        raise ServiceError("not_found", f"交付物 {name} 的文件已被清理", http_status=404)
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run.name)[:64] or "model"
    download_name = name if name != "delivery.zip" else f"{safe_name}_delivery.zip"
    return FileResponse(str(path), filename=download_name, headers={"X-Content-SHA256": files[name]["sha256"]})
