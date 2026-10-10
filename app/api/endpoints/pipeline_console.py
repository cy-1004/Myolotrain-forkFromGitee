"""控制台的流水线接口（/api/pipeline，登录用户）：任务中心、复核、视频操作、API Key 管理

与对外接口 /api/v1 共用 services.pipeline.service 中的业务逻辑；
区别是控制台能看到所有任务、完整的内部信息（产物路径、日志、闸门明细），并能做复核放行等运维操作。
"""
import re
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_console_admin, require_console_user
from app.core.config import settings
from app.core.paths import from_data_relative
from app.db.session import get_db
from app.models.annotation import ImageAnnotation
from app.models.api_key import ApiKey
from app.models.pipeline import PipelineEvent, PipelineRun
from app.models.user import User
from app.services import api_key_service
from app.services.pipeline import service
from app.services.pipeline.orchestrator import STAGE_LABELS, orchestrator
from app.services.pipeline.service import ServiceError
from app.services.pipeline.spec import effective_annotate_provider, AnnotateConfig

router = APIRouter()


def _get_run(db: Session, run_id: str) -> PipelineRun:
    try:
        uuid.UUID(run_id)
    except ValueError:
        raise ServiceError("not_found", "任务不存在", http_status=404)
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if run is None:
        raise ServiceError("not_found", "任务不存在", http_status=404)
    return run


def _detail(db: Session, run: PipelineRun) -> Dict:
    data = service.serialize_run(run, detail=True, external=False)
    data["review_counts"] = service.review_counts(db, run)
    data["stage_labels"] = STAGE_LABELS
    data["running_here"] = str(run.id) in orchestrator.running_run_ids()
    if run.api_key_id:
        key = db.query(ApiKey).filter(ApiKey.id == run.api_key_id).first()
        data["api_key"] = {"name": key.name, "prefix": key.prefix} if key else None
    return data


# ----------------------------------------------------------------------
# 任务
# ----------------------------------------------------------------------
@router.get("/runs")
def list_runs(db: Session = Depends(get_db), status: Optional[str] = None, q: Optional[str] = None,
              skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    query = db.query(PipelineRun)
    if status:
        query = query.filter(PipelineRun.status.in_(status.split(",")))
    if q:
        like = f"%{q.strip()}%"
        conds = [PipelineRun.name.ilike(like), PipelineRun.external_ref.ilike(like)]
        try:
            conds.append(PipelineRun.id == uuid.UUID(q.strip()))
        except ValueError:
            pass
        query = query.filter(or_(*conds))
    total = query.count()
    rows = query.order_by(PipelineRun.created_at.desc()).offset(skip).limit(limit).all()
    keys = {k.id: k for k in db.query(ApiKey).filter(ApiKey.id.in_([r.api_key_id for r in rows if r.api_key_id])).all()}
    items = []
    for r in rows:
        item = service.serialize_run(r)
        item["source"] = r.source
        item["api_key_name"] = keys[r.api_key_id].name if r.api_key_id in keys else None
        item["video_count"] = len(r.videos)
        item["llm_cost_usd"] = (r.llm_usage or {}).get("cost_usd")
        items.append(item)
    return {"total": total, "items": items}


@router.post("/runs", status_code=202)
async def create_run_from_console(request: Request, db: Session = Depends(get_db),
                                  user: User = Depends(require_console_user)):
    """控制台创建任务：multipart，spec 字段为任务 JSON，videos 为视频文件（与对外接口格式相同）"""
    from app.api.v1.jobs import parse_multipart_job

    temp_files: List[Path] = []
    try:
        _, spec, sources, reference_files = await parse_multipart_job(request, temp_files)
        run, _ = await run_in_threadpool(service.create_run, db, spec, sources, user=user, source="console",
                                         reference_files=reference_files)
    finally:
        for p in temp_files:
            p.unlink(missing_ok=True)
    return _detail(db, run)


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    return _detail(db, _get_run(db, run_id))


@router.get("/runs/{run_id}/events")
def get_run_events(run_id: str, after: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=2000),
                   db: Session = Depends(get_db)):
    run = _get_run(db, run_id)
    rows = (db.query(PipelineEvent).filter(PipelineEvent.run_id == run.id, PipelineEvent.id > after)
            .order_by(PipelineEvent.id).limit(limit).all())
    items = [service.serialize_event(e) for e in rows]
    return {"items": items, "next_after": items[-1]["id"] if items else after}


class ResumeBody(BaseModel):
    from_stage: Optional[str] = None


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, db: Session = Depends(get_db), user: User = Depends(require_console_user)):
    return _detail(db, service.cancel_run(db, _get_run(db, run_id), user=user))


@router.post("/runs/{run_id}/resume")
def resume(run_id: str, body: ResumeBody = ResumeBody(), db: Session = Depends(get_db),
           user: User = Depends(require_console_user)):
    return _detail(db, service.resume_run(db, _get_run(db, run_id), body.from_stage, user=user))


class ApproveBody(BaseModel):
    include_unreviewed: str = "low_risk"
    override_gates: List[str] = Field(default_factory=list)
    reason: Optional[str] = Field(None, max_length=500)
    budget_usd: Optional[float] = Field(None, ge=0)


@router.post("/runs/{run_id}/review/approve")
def approve(run_id: str, body: ApproveBody, db: Session = Depends(get_db), user: User = Depends(require_console_user)):
    run = service.approve_run(db, _get_run(db, run_id), user, include_unreviewed=body.include_unreviewed,
                              override_gates=body.override_gates, reason=body.reason, budget_usd=body.budget_usd)
    return _detail(db, run)


class RejectBody(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


@router.post("/runs/{run_id}/review/reject")
def reject(run_id: str, body: RejectBody, db: Session = Depends(get_db), user: User = Depends(require_console_user)):
    return _detail(db, service.reject_run(db, _get_run(db, run_id), user, body.reason))


class VideoActionBody(BaseModel):
    action: str
    class_name: Optional[str] = None
    class_names: Optional[List[str]] = None   # 视频里有多类文物时用


@router.post("/runs/{run_id}/videos/{video_key}/action")
def video_action(run_id: str, video_key: str, body: VideoActionBody, db: Session = Depends(get_db),
                 user: User = Depends(require_console_user)):
    run = service.video_action(db, _get_run(db, run_id), video_key, body.action, user, body.class_name, body.class_names)
    return _detail(db, run)


# ----------------------------------------------------------------------
# 帧浏览与逐帧复核
# ----------------------------------------------------------------------
@router.get("/runs/{run_id}/frames")
def list_frames(run_id: str, db: Session = Depends(get_db), video: Optional[str] = None,
                review_status: Optional[str] = None, reason: Optional[str] = None, split: Optional[str] = None,
                has_boxes: Optional[bool] = None, min_risk: Optional[float] = None,
                order: str = Query("time", pattern="^(time|risk_desc)$"),
                skip: int = Query(0, ge=0), limit: int = Query(60, ge=1, le=500)):
    """按条件筛选帧（"只看问题帧"）。过滤在内存中做：单个任务的帧数有上限（每视频默认 200）"""
    run = _get_run(db, run_id)
    project_id = (run.artifacts or {}).get("annotation_project_id")
    if not project_id:
        return {"total": 0, "items": [], "project_id": None}
    rows = db.query(ImageAnnotation).filter(ImageAnnotation.project_id == project_id).all()

    def keep(r: ImageAnnotation) -> bool:
        meta = r.pipeline_meta or {}
        if video and meta.get("video_key") != video:
            return False
        if review_status and r.review_status not in review_status.split(","):
            return False
        if reason and reason not in (r.risk_reasons or []):
            return False
        if split and (meta.get("split") or "excluded") != split:
            return False
        if has_boxes is not None and bool(r.annotations) != has_boxes:
            return False
        if min_risk is not None and (r.risk_score or 0) < min_risk:
            return False
        return True

    rows = [r for r in rows if keep(r)]
    if order == "risk_desc":
        rows.sort(key=lambda r: (-(r.risk_score or 0), r.image_name))
    else:
        rows.sort(key=lambda r: ((r.pipeline_meta or {}).get("video_key", ""), (r.pipeline_meta or {}).get("ts", 0)))
    total = len(rows)
    items = [{
        "id": str(r.id), "image_name": r.image_name, "annotations": r.annotations,
        "auto_annotations": r.auto_annotations, "review_status": r.review_status, "risk_score": r.risk_score,
        "risk_reasons": r.risk_reasons, "pipeline_meta": r.pipeline_meta, "version": r.version,
        "image_url": f"/api/annotation/projects/{project_id}/images/{r.id}/file",
    } for r in rows[skip:skip + limit]]
    return {"total": total, "items": items, "project_id": project_id}


class ReviewBody(BaseModel):
    action: str
    annotations: Optional[List[Dict]] = None
    version: Optional[int] = None


@router.post("/runs/{run_id}/frames/{image_id}/review")
def review_frame(run_id: str, image_id: str, body: ReviewBody, db: Session = Depends(get_db),
                 user: User = Depends(require_console_user)):
    run = _get_run(db, run_id)
    row = service.review_image(db, run, image_id, user, body.action, body.annotations, body.version)
    return {"id": str(row.id), "review_status": row.review_status, "version": row.version,
            "review_counts": service.review_counts(db, run)}


class BatchReviewItem(BaseModel):
    image_id: str
    version: Optional[int] = None


class BatchReviewBody(BaseModel):
    action: str = "accept"
    items: List[BatchReviewItem] = Field(min_length=1, max_length=500)


@router.post("/runs/{run_id}/frames/batch-review")
def batch_review(run_id: str, body: BatchReviewBody, db: Session = Depends(get_db),
                 user: User = Depends(require_console_user)):
    """网格快审：一次通过/丢弃多帧，版本冲突的逐条返回，其余照常处理"""
    run = _get_run(db, run_id)
    results = []
    for item in body.items:
        try:
            row = service.review_image(db, run, item.image_id, user, body.action, None, item.version)
            results.append({"image_id": item.image_id, "ok": True, "version": row.version})
        except ServiceError as e:
            db.rollback()
            results.append({"image_id": item.image_id, "ok": False, "code": e.code, "message": e.message})
    return {"results": results, "review_counts": service.review_counts(db, run)}


# ----------------------------------------------------------------------
# 产物下载
# ----------------------------------------------------------------------
@router.get("/runs/{run_id}/artifacts/{name}")
def download(run_id: str, name: str, db: Session = Depends(get_db)):
    run = _get_run(db, run_id)
    files = service.delivery_files(run)
    if name not in files:
        raise ServiceError("not_found", f"交付物 {name} 不存在", http_status=404)
    path = from_data_relative(files[name]["path"])
    return FileResponse(str(path), filename=name)


class ReferenceFromFrameBody(BaseModel):
    image_id: str
    box_index: int = Field(0, ge=0)


@router.post("/runs/{run_id}/references/from-frame")
def set_reference_from_frame(run_id: str, body: ReferenceFromFrameBody, db: Session = Depends(get_db),
                             user: User = Depends(require_console_user)):
    """用某帧里的某个框作为该类别的参考图，并重新标注含该类别的视频"""
    try:
        uuid.UUID(body.image_id)
    except ValueError:
        raise ServiceError("invalid_spec", "image_id 格式不对", http_status=422)
    return _detail(db, service.reference_from_frame(db, _get_run(db, run_id), body.image_id, body.box_index, user))


@router.post("/runs/{run_id}/references/upload")
async def upload_reference(run_id: str, class_name: str = Form(...), image: UploadFile = File(...),
                           db: Session = Depends(get_db), user: User = Depends(require_console_user)):
    """上传某个类别的参考图（文物照片），并重新标注含该类别的视频"""
    data = await image.read(service.REFERENCE_MAX_BYTES + 1)
    run = await run_in_threadpool(service.reference_from_file, db, _get_run(db, run_id), class_name, data, user)
    return _detail(db, run)


@router.get("/runs/{run_id}/references/{name}")
def reference_image(run_id: str, name: str, db: Session = Depends(get_db)):
    """该任务每个类别用的参考图（自动挑选或调用方提供），控制台展示用"""
    from app.services.pipeline.context import run_dir
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.jpg", name):
        raise ServiceError("not_found", "参考图不存在", http_status=404)
    path = run_dir(_get_run(db, run_id).id) / "references" / name
    if not path.exists():
        raise ServiceError("not_found", "参考图不存在", http_status=404)
    return FileResponse(str(path), media_type="image/jpeg")


@router.get("/runs/{run_id}/logs/{name}")
def stage_log(run_id: str, name: str, db: Session = Depends(get_db)):
    """评估 / TFLite 导出子进程的日志（训练日志在训练任务里看）"""
    if name not in ("evaluate", "export_verify"):
        raise ServiceError("not_found", "日志不存在", http_status=404)
    from app.services.pipeline.context import run_dir
    path = run_dir(_get_run(db, run_id).id) / "logs" / f"{name}.log"
    if not path.exists():
        raise ServiceError("not_found", "日志尚未生成", http_status=404)
    return {"text": path.read_text(encoding="utf-8", errors="replace")[-200_000:]}


# ----------------------------------------------------------------------
# 视觉模型配置与连通性测试
# ----------------------------------------------------------------------
@router.get("/vlm")
def vlm_status():
    provider, model = effective_annotate_provider(AnnotateConfig())
    return {"provider": provider, "model": model, "allow_cloud": settings.ALLOW_CLOUD_VLM,
            "openrouter_configured": bool(settings.OPENROUTER_API_KEY),
            "local_base_url": settings.OPENAI_COMPATIBLE_BASE_URL, "sam_model": settings.SAM_MODEL}


@router.post("/vlm/test")
async def vlm_test(image: UploadFile = File(...), class_name: str = Form("object"), display_name: str = Form(""),
                   provider: Optional[str] = Form(None), model: Optional[str] = Form(None),
                   user: User = Depends(require_console_user)):
    """上传一张图测试视觉模型配置：返回模型原始回复与解析出的框"""
    from app.services.labeling.vlm_client import VLMAuthError, VLMClient

    cfg = AnnotateConfig(provider=provider or None, model=model or None)
    prov, mdl = effective_annotate_provider(cfg)
    if prov == "openrouter" and not settings.ALLOW_CLOUD_VLM:
        raise ServiceError("forbidden", "系统已禁止使用云端视觉模型", http_status=403)
    suffix = Path(image.filename or "x.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await image.read())
        tmp_path = Path(tmp.name)
    try:
        client = VLMClient(prov, mdl)
        classes = [{"name": class_name, "display_name": display_name or None}]
        res = await run_in_threadpool(client.test_connection, tmp_path, classes)
    except VLMAuthError as e:
        raise ServiceError("vlm_unavailable", str(e), http_status=502)
    finally:
        tmp_path.unlink(missing_ok=True)
    return {"provider": prov, "model": mdl, "ok": res.ok, "error": res.error, "boxes": res.boxes,
            "raw_text": res.raw_text, "usage": res.usage, "coord_mode": res.coord_mode, "image_size": res.image_size}


# ----------------------------------------------------------------------
# API Key 管理（管理员）
# ----------------------------------------------------------------------
class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    scopes: Optional[List[str]] = None
    expires_days: Optional[int] = Field(None, ge=1, le=3650)


def _key_out(k: ApiKey) -> Dict:
    return {"id": str(k.id), "name": k.name, "prefix": k.prefix, "scopes": k.scopes,
            "created_at": k.created_at.isoformat() + "Z" if k.created_at else None,
            "expires_at": k.expires_at.isoformat() + "Z" if k.expires_at else None,
            "revoked_at": k.revoked_at.isoformat() + "Z" if k.revoked_at else None,
            "last_used_at": k.last_used_at.isoformat() + "Z" if k.last_used_at else None}


@router.get("/api-keys", dependencies=[Depends(require_console_admin)])
def list_api_keys(db: Session = Depends(get_db)):
    return {"items": [_key_out(k) for k in db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()],
            "all_scopes": list(api_key_service.ALL_SCOPES)}


@router.post("/api-keys", status_code=201)
def create_api_key(body: ApiKeyCreate, db: Session = Depends(get_db), admin: User = Depends(require_console_admin)):
    expires_at = datetime.utcnow() + timedelta(days=body.expires_days) if body.expires_days else None
    try:
        record, full_key, webhook_secret = api_key_service.create_api_key(db, body.name, body.scopes, admin.id, expires_at)
    except ValueError as e:
        raise ServiceError("invalid_spec", str(e), http_status=422)
    # 完整 key 和 webhook 签名密钥只在这里返回一次
    return {**_key_out(record), "api_key": full_key, "webhook_secret": webhook_secret}


@router.delete("/api-keys/{key_id}", dependencies=[Depends(require_console_admin)])
def revoke_api_key(key_id: str, db: Session = Depends(get_db)):
    try:
        uuid.UUID(key_id)
    except ValueError:
        raise ServiceError("not_found", "API Key 不存在", http_status=404)
    record = api_key_service.revoke_api_key(db, key_id)
    if record is None:
        raise ServiceError("not_found", "API Key 不存在", http_status=404)
    return _key_out(record)
