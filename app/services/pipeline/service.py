"""流水线的业务操作：创建、取消、续跑、复核放行/驳回、视频级操作，以及对外序列化

对外接口（/api/v1，API Key）与控制台（/api/pipeline，登录用户）共用这里的逻辑，
权限与输入格式的差异留在各自的路由层处理。
"""
import base64
import binascii
import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.paths import data_path, to_data_relative
from app.models.annotation import ImageAnnotation
from app.models.pipeline import PipelineEvent, PipelineRun, PipelineUpload, PipelineVideo
from app.services.labeling import geometry
from app.services.labeling.references import crop_array, encode_reference, reference_from_upload
from app.services.pipeline import errors
from app.services.pipeline.common import read_json, video_class_names, write_json
from app.services.pipeline.context import STAGE_ORDER, overall_progress, run_dir
from app.services.pipeline.events import emit_event, isoformat, utcnow
from app.services.pipeline.spec import JobConfig, JobSpec, validate_runtime_constraints
from app.services.pipeline.stages.ingest import probe_video
from app.services.pipeline.stages.references import save_provided
from app.services.pipeline.webhooks import WebhookTargetError, check_target

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm", ".mpg", ".mpeg", ".wmv", ".flv", ".ts"}
TERMINAL = ("succeeded", "failed", "cancelled")


class ServiceError(Exception):
    """业务错误：code 对应对外接口的错误码，http_status 为建议的 HTTP 状态码"""

    def __init__(self, code: str, message: str, http_status: int = 400, details: Any = None):
        super().__init__(message)
        self.code, self.message, self.http_status, self.details = code, message, http_status, details


@dataclass
class VideoSource:
    """创建 Run 时的视频来源：分片上传记录，或 multipart 请求里的临时文件"""
    original_filename: str
    path: Path
    sha256: Optional[str] = None
    upload: Optional[PipelineUpload] = None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def free_disk_gb() -> float:
    root = Path(settings.DATA_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(root).free / 1024 ** 3


def check_disk():
    free = free_disk_gb()
    if free < settings.PIPELINE_MIN_FREE_DISK_GB:
        raise ServiceError("insufficient_storage", f"数据目录剩余空间 {free:.1f} GB，低于下限 {settings.PIPELINE_MIN_FREE_DISK_GB} GB，"
                           "请清理后重试", http_status=507)


REFERENCE_MAX_BYTES = 5 * 1024 * 1024


def prepare_references(spec: JobSpec, reference_files: Optional[Dict[str, bytes]] = None) -> Dict[str, List[bytes]]:
    """校验并标准化调用方提供的参考图 -> {类别: [JPEG 字节]}。不合法时抛 ServiceError（422/413）"""
    out: Dict[str, List[bytes]] = {}
    for c in spec.classes:
        for i, ref in enumerate(c.references):
            where = f"类别 {c.name} 的第 {i + 1} 张参考图"
            if ref.file is not None:
                data = (reference_files or {}).get(ref.file)
                if data is None:
                    raise ServiceError("invalid_spec", f"{where}（{ref.file}）不在上传的 references 文件中", http_status=422)
            else:
                text = ref.data_base64.split(",", 1)[1] if ref.data_base64.startswith("data:") else ref.data_base64
                try:
                    data = base64.b64decode(text, validate=True)
                except (binascii.Error, ValueError):
                    raise ServiceError("invalid_spec", f"{where}的 data_base64 不是合法的 base64", http_status=422)
            if len(data) > REFERENCE_MAX_BYTES:
                raise ServiceError("payload_too_large", f"{where}超过 {REFERENCE_MAX_BYTES // 1024 // 1024} MB", http_status=413)
            try:
                out.setdefault(c.name, []).append(reference_from_upload(data, ref.box))
            except ValueError as e:
                raise ServiceError("invalid_spec", f"{where}: {e}", http_status=422)
    return out


# ----------------------------------------------------------------------
# 创建
# ----------------------------------------------------------------------
def create_run(db: Session, spec: JobSpec, sources: Dict[str, VideoSource], *, api_key=None, user=None,
               source: str = "api", idempotency_key: Optional[str] = None,
               request_hash: Optional[str] = None,
               reference_files: Optional[Dict[str, bytes]] = None) -> (PipelineRun, bool):
    """创建 Run。返回 (run, 是否新建)；幂等键命中且请求一致时返回已有 Run

    reference_files：multipart 方式上传的参考图 {文件名: 内容}，由 classes[].references[].file 引用"""
    api_key_id = api_key.id if api_key is not None else None
    if idempotency_key:
        existing = db.query(PipelineRun).filter(PipelineRun.api_key_id == api_key_id,
                                                PipelineRun.idempotency_key == idempotency_key).first()
        if existing is not None:
            if request_hash and existing.request_hash and existing.request_hash != request_hash:
                raise ServiceError("idempotency_conflict", "同一个 Idempotency-Key 已用于内容不同的请求", http_status=409,
                                   details={"job_id": str(existing.id)})
            return existing, False

    try:
        validate_runtime_constraints(spec)
        if spec.callback_url:
            check_target(spec.callback_url)
    except (ValueError, WebhookTargetError) as e:
        raise ServiceError("invalid_spec", str(e), http_status=422)
    check_disk()
    prepared_refs = prepare_references(spec, reference_files)

    missing = [v.key for v in spec.videos if v.key not in sources]
    if missing:
        raise ServiceError("invalid_spec", f"视频 {missing} 没有对应的文件", http_status=422)
    for v in spec.videos:
        src = sources[v.key]
        ext = Path(src.original_filename).suffix.lower()
        if ext not in VIDEO_EXTS:
            raise ServiceError("video_unreadable", f"视频 {v.key} 的格式 {ext or '(无扩展名)'} 不受支持", http_status=422)
        size_mb = src.path.stat().st_size / 1024 ** 2
        if size_mb > settings.PIPELINE_MAX_VIDEO_MB:
            raise ServiceError("payload_too_large", f"视频 {v.key} 大小 {size_mb:.0f} MB 超过上限 {settings.PIPELINE_MAX_VIDEO_MB} MB",
                               http_status=413)
        try:
            info = probe_video(src.path)
        except ValueError as e:
            raise ServiceError("video_unreadable", f"视频 {v.key}（{src.original_filename}）无法读取: {e}", http_status=422)
        if info["duration"] > settings.PIPELINE_MAX_VIDEO_SECONDS:
            raise ServiceError("invalid_spec", f"视频 {v.key} 时长 {info['duration']:.0f}s 超过上限 "
                               f"{settings.PIPELINE_MAX_VIDEO_SECONDS}s", http_status=422)

    run_id = uuid.uuid4()
    # 参考图另存为文件（references/provided/），不写进数据库
    classes = [c.model_dump(exclude_none=True, exclude={"references"}) for c in spec.classes]
    class_index = {c["name"]: i for i, c in enumerate(classes)}
    run = PipelineRun(
        id=run_id, name=spec.name, external_ref=spec.external_ref, status="queued", review_mode=spec.review_mode,
        classes=classes, config=spec.config.model_dump(mode="json"), stage_states={}, artifacts={}, metrics={},
        gate_results=[], llm_usage={}, progress=0.0, source=source, api_key_id=api_key_id,
        created_by=getattr(user, "id", None), idempotency_key=idempotency_key, request_hash=request_hash,
        callback_url=spec.callback_url, callback_events=spec.callback_events if spec.callback_url else None,
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(PipelineRun).filter(PipelineRun.api_key_id == api_key_id,
                                                PipelineRun.idempotency_key == idempotency_key).first()
        if existing is not None:
            return existing, False
        raise

    input_dir = run_dir(run_id) / "input" / "videos"
    input_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    try:
        save_provided(run_dir(run_id), prepared_refs)
        for pos, v in enumerate(spec.videos):
            src = sources[v.key]
            target = input_dir / f"{v.key}{Path(src.original_filename).suffix.lower()}"
            shutil.move(str(src.path), str(target))
            moved.append((target, src))
            if src.upload is not None:
                src.upload.status = "consumed"
            db.add(PipelineVideo(
                run_id=run_id, position=pos, key=v.key, original_filename=src.original_filename,
                class_name=v.declared[0], class_id=class_index[v.declared[0]], class_names=v.declared,
                expected_instances=v.expected_instances,
                options={k: val for k, val in {"skip_start": v.skip_start, "skip_end": v.skip_end}.items() if val is not None},
                rel_path=to_data_relative(target), sha256=src.sha256 or sha256_file(target),
                size_bytes=target.stat().st_size, status="ok", stats={},
            ))
        emit_event(db, run, "job.created", f"任务已创建：{len(spec.videos)} 个视频、{len(classes)} 个类别、复核模式 {spec.review_mode}",
                   actor=_actor(api_key, user), commit=False)
        db.commit()
    except Exception:
        db.rollback()
        for target, src in moved:   # 失败时把文件还回去，调用方可以重试
            try:
                shutil.move(str(target), str(src.path))
            except OSError:
                pass
        shutil.rmtree(run_dir(run_id), ignore_errors=True)
        raise
    db.refresh(run)
    return run, True


def _actor(api_key=None, user=None) -> str:
    if api_key is not None:
        return f"api_key:{api_key.prefix}"
    if user is not None:
        return f"user:{user.username}"
    return "system"


# ----------------------------------------------------------------------
# 运行控制
# ----------------------------------------------------------------------
def cancel_run(db: Session, run: PipelineRun, *, api_key=None, user=None) -> PipelineRun:
    if run.status in TERMINAL:
        raise ServiceError("invalid_state", f"任务已结束（{run.status}），不能取消", http_status=409)
    if run.status in ("queued", "needs_review"):
        run.status, run.finished_at, run.cancel_requested = "cancelled", utcnow(), True
        emit_event(db, run, "job.cancelled", "任务已取消", actor=_actor(api_key, user))
    elif run.status in ("running", "cancelling"):
        run.cancel_requested, run.status = True, "cancelling"
        emit_event(db, run, "run.cancelling", "已请求取消，正在停止当前阶段", actor=_actor(api_key, user))
    db.refresh(run)
    return run


def resume_run(db: Session, run: PipelineRun, from_stage: Optional[str] = None, *, api_key=None, user=None) -> PipelineRun:
    """从失败（或取消）的阶段继续；from_stage 可以指定更早的阶段重新执行（已完成的部分会复用）"""
    if run.status not in ("failed", "cancelled"):
        raise ServiceError("invalid_state", f"只有失败或已取消的任务可以续跑（当前 {run.status}）", http_status=409)
    current = run.current_stage or STAGE_ORDER[0]
    stage = from_stage or current
    if stage not in STAGE_ORDER:
        raise ServiceError("invalid_spec", f"未知的阶段 {stage}，可选 {STAGE_ORDER}", http_status=422)
    if STAGE_ORDER.index(stage) > STAGE_ORDER.index(current):
        raise ServiceError("invalid_spec", f"不能跳过失败的阶段 {current} 直接从 {stage} 开始", http_status=422)
    _reset_stages_from(run, stage)
    if STAGE_ORDER.index(stage) <= STAGE_ORDER.index("gate"):
        _set_review(run, approved=None)   # 闸门会重新评估，之前的放行作废
    run.status, run.cancel_requested, run.finished_at = "queued", False, None
    run.error_code, run.error_message, run.attempt = None, None, 0
    emit_event(db, run, "run.resumed", f"从“{stage}”阶段继续执行", actor=_actor(api_key, user))
    db.refresh(run)
    return run


def _reset_stages_from(run: PipelineRun, stage: str):
    states = dict(run.stage_states or {})
    for name in STAGE_ORDER[STAGE_ORDER.index(stage):]:
        if name in states:
            states[name] = {"status": "pending", "attempts": (states[name] or {}).get("attempts", 0)}
    run.stage_states = states
    run.current_stage = stage
    run.progress = overall_progress(states)
    flag_modified(run, "stage_states")


def _set_review(run: PipelineRun, **fields):
    artifacts = dict(run.artifacts or {})
    review = dict(artifacts.get("review") or {})
    for k, v in fields.items():
        if v is None:
            review.pop(k, None)
        else:
            review[k] = v
    artifacts["review"] = review
    run.artifacts = artifacts
    flag_modified(run, "artifacts")


def review_counts(db: Session, run: PipelineRun) -> Dict[str, int]:
    project_id = (run.artifacts or {}).get("annotation_project_id")
    counts = {"auto_accepted": 0, "to_review": 0, "accepted": 0, "modified": 0, "discarded": 0, "total": 0}
    if not project_id:
        return counts
    for (status,) in db.query(ImageAnnotation.review_status).filter(ImageAnnotation.project_id == project_id).all():
        counts["total"] += 1
        if status in counts:
            counts[status] += 1
    return counts


def approve_run(db: Session, run: PipelineRun, user, *, include_unreviewed: str = "low_risk",
                override_gates: Optional[List[str]] = None, reason: Optional[str] = None,
                budget_usd: Optional[float] = None) -> PipelineRun:
    if run.status != "needs_review":
        raise ServiceError("invalid_state", f"任务不在等待复核状态（当前 {run.status}）", http_status=409)
    if include_unreviewed not in ("low_risk", "none", "all"):
        raise ServiceError("invalid_spec", "include_unreviewed 只能是 low_risk / none / all", http_status=422)
    review = (run.artifacts or {}).get("review") or {}
    if review.get("reason") == "full_review":
        pending = review_counts(db, run)["to_review"]
        if pending:
            raise ServiceError("invalid_state", f"全量复核模式下还有 {pending} 帧未处理（通过/修改/丢弃），不能放行", http_status=409)
    if review.get("reason") == "budget":
        if budget_usd is None:
            raise ServiceError("invalid_spec", "任务因 VLM 费用达到预算而暂停，放行时需提供新的预算 budget_usd", http_status=422)
        config = dict(run.config)
        config["annotate"] = {**config.get("annotate", {}), "budget_usd": float(budget_usd)}
        run.config = config
        flag_modified(run, "config")
    paused_stage = run.current_stage or "gate"
    _set_review(run, approved=True, approved_by=user.username, approved_at=utcnow().isoformat() + "Z",
                include_unreviewed=include_unreviewed, override_gates=list(override_gates or []), approve_reason=reason,
                paused=False)
    _reset_stages_from(run, paused_stage)
    run.status = "queued"
    emit_event(db, run, "review.approved", f"{user.username} 放行" + (f"：{reason}" if reason else ""),
               actor=_actor(user=user), data={"include_unreviewed": include_unreviewed, "override_gates": override_gates})
    db.refresh(run)
    return run


def reject_run(db: Session, run: PipelineRun, user, reason: Optional[str] = None) -> PipelineRun:
    if run.status != "needs_review":
        raise ServiceError("invalid_state", f"任务不在等待复核状态（当前 {run.status}）", http_status=409)
    run.status, run.finished_at = "failed", utcnow()
    run.error_code, run.error_message = errors.REJECTED_BY_OPERATOR, f"被 {user.username} 驳回" + (f"：{reason}" if reason else "")
    emit_event(db, run, "job.failed", run.error_message, level="error", actor=_actor(user=user),
               data={"code": run.error_code})
    db.refresh(run)
    return run


def video_action(db: Session, run: PipelineRun, video_key: str, action: str, user, class_name: Optional[str] = None,
                 class_names: Optional[List[str]] = None):
    """复核期间的视频级操作：exclude（排除）/ include（恢复）/ reassign_class（改类别并重新标注该视频）

    reassign_class 传 class_name（单类）或 class_names（视频里有多类文物）"""
    if run.status != "needs_review":
        raise ServiceError("invalid_state", "只有等待复核的任务可以调整视频", http_status=409)
    video = db.query(PipelineVideo).filter(PipelineVideo.run_id == run.id, PipelineVideo.key == video_key).first()
    if video is None:
        raise ServiceError("not_found", f"视频 {video_key} 不存在", http_status=404)
    if action == "exclude":
        video.status = "excluded"
        msg = f"排除视频 {video_key}"
    elif action == "include":
        if video.status != "excluded":
            raise ServiceError("invalid_state", "该视频未被排除", http_status=409)
        video.status = "ok"
        msg = f"恢复视频 {video_key}"
    elif action == "reassign_class":
        names = [c["name"] for c in run.classes]
        new = list(dict.fromkeys(class_names or ([class_name] if class_name else [])))
        unknown = [c for c in new if c not in names]
        if not new or unknown:
            raise ServiceError("invalid_spec", f"类别 {unknown or new!r} 不在任务的类别列表中", http_status=422)
        old = "+".join(video_class_names(video))
        video.class_name, video.class_id, video.class_names = new[0], names.index(new[0]), new
        stats = dict(video.stats or {})
        stats.pop("class_check", None)
        video.stats = stats
        flag_modified(video, "stats")
        project_id = (run.artifacts or {}).get("annotation_project_id")
        if project_id:   # 删掉该视频的自动标注结果，重新排队后只重标这个视频
            for row in db.query(ImageAnnotation).filter(ImageAnnotation.project_id == project_id).all():
                if (row.pipeline_meta or {}).get("video_key") == video_key:
                    db.delete(row)
        _reset_stages_from(run, "annotate")
        _set_review(run, approved=None)
        run.status = "queued"
        msg = f"视频 {video_key} 类别 {old} → {'+'.join(new)}，将重新标注该视频并重新评估质量闸门"
    else:
        raise ServiceError("invalid_spec", f"未知操作 {action}", http_status=422)
    emit_event(db, run, "video.updated", msg, actor=_actor(user=user), data={"video": video_key, "action": action})
    db.refresh(run)
    return run


def review_image(db: Session, run: PipelineRun, image_id, user, action: str,
                 annotations: Optional[List[Dict]] = None, expected_version: Optional[int] = None) -> ImageAnnotation:
    """逐帧复核：accept（原样通过）/ modify（修改后通过）/ discard（丢弃）。带版本号走乐观锁"""
    if action not in ("accept", "modify", "discard"):
        raise ServiceError("invalid_spec", "action 只能是 accept / modify / discard", http_status=422)
    project_id = (run.artifacts or {}).get("annotation_project_id")
    row = db.query(ImageAnnotation).filter(ImageAnnotation.id == image_id, ImageAnnotation.project_id == project_id).first()
    if row is None:
        raise ServiceError("not_found", "图片不存在或不属于该任务", http_status=404)
    if expected_version is not None and row.version != expected_version:
        raise ServiceError("version_conflict", "该图片已被他人修改，请刷新后重试", http_status=409,
                           details={"current_version": row.version})
    if action == "modify":
        if annotations is None:
            raise ServiceError("invalid_spec", "modify 需要提供 annotations", http_status=422)
        n_classes = len(run.classes)
        for a in annotations:
            if not isinstance(a, dict) or not 0 <= int(a.get("class_id", -1)) < n_classes:
                raise ServiceError("invalid_spec", "annotations 中的 class_id 超出类别范围", http_status=422)
        row.annotations = [{**a, "source": a.get("source", "manual"), "edited": True} for a in annotations]
    row.review_status = {"accept": "accepted", "modify": "modified", "discard": "discarded"}[action]
    row.reviewed_by, row.reviewed_at = user.id, datetime.utcnow()
    row.last_edited_by = user.id
    row.version = (row.version or 1) + 1
    db.commit()
    db.refresh(row)
    return row


# ----------------------------------------------------------------------
# 序列化
# ----------------------------------------------------------------------
HUMAN_REVIEWED = ("accepted", "modified", "discarded")


def replace_reference(db: Session, run: PipelineRun, class_name: str, image: bytes, source: Dict[str, Any], user) -> PipelineRun:
    """复核期间替换某个类别的参考图，并对含该类别的视频重做类别校验、重新标注（人工处理过的帧保留不动）

    自动挑选不出参考图、或挑错了的类别，召回会低一半；操作员在控制台从帧里框选或上传一张，比重新提交任务快得多。"""
    if run.status != "needs_review":
        raise ServiceError("invalid_state", "只有等待复核的任务可以更换参考图", http_status=409)
    names = [c["name"] for c in run.classes]
    if class_name not in names:
        raise ServiceError("invalid_spec", f"类别 {class_name!r} 不在任务的类别列表中", http_status=422)
    if JobConfig.model_validate(run.config).annotate.references == "off":
        raise ServiceError("invalid_state", "该任务关闭了参考图（annotate.references=off）", http_status=409)

    folder = run_dir(run.id) / "references"
    folder.mkdir(parents=True, exist_ok=True)
    index = read_json(folder / "references.json") or {"classes": {}, "missing": list(names), "report": None}
    for old in index["classes"].get(class_name, []):
        (folder / old["file"]).unlink(missing_ok=True)
    file = f"{class_name}_1.jpg"
    (folder / file).write_bytes(image)
    index["classes"][class_name] = [{"file": file, **source}]
    index["missing"] = [c for c in index.get("missing", []) if c != class_name]
    write_json(folder / "references.json", index)
    artifacts = dict(run.artifacts or {})
    artifacts["references"] = {"classes": index["classes"], "missing": index["missing"]}
    run.artifacts = artifacts
    flag_modified(run, "artifacts")

    keys = {v.key for v in run.videos if v.status == "ok" and class_name in video_class_names(v)}
    # 这些视频的类别校验也要重做：之前缺参考图时，模型常把小件认成别的类别（误报"选错类别"）
    for v in run.videos:
        if v.key in keys and "class_check" in (v.stats or {}):
            stats = dict(v.stats)
            stats.pop("class_check")
            v.stats = stats
            flag_modified(v, "stats")
    project_id = (run.artifacts or {}).get("annotation_project_id")
    removed = 0
    if project_id and keys:
        for row in db.query(ImageAnnotation).filter(ImageAnnotation.project_id == project_id).all():
            if (row.pipeline_meta or {}).get("video_key") in keys and row.review_status not in HUMAN_REVIEWED:
                db.delete(row)
                removed += 1
    _reset_stages_from(run, "class_check")
    _set_review(run, approved=None)
    run.status = "queued"
    emit_event(db, run, "references.updated",
               f"类别 {class_name} 的参考图已更换（{source.get('type')}），将重新标注 {len(keys)} 个视频的 {removed} 帧",
               actor=_actor(user=user), data={"class": class_name, "videos": sorted(keys), "frames": removed})
    db.refresh(run)
    return run


def reference_from_frame(db: Session, run: PipelineRun, image_id, box_index: int, user) -> PipelineRun:
    """用某一帧里的某个框（自动标注的或人工改过的）作为该框类别的参考图"""
    project_id = (run.artifacts or {}).get("annotation_project_id")
    row = db.query(ImageAnnotation).filter(ImageAnnotation.id == image_id, ImageAnnotation.project_id == project_id).first()
    if row is None:
        raise ServiceError("not_found", "图片不存在或不属于该任务", http_status=404)
    anns = row.annotations or []
    if not 0 <= box_index < len(anns):
        raise ServiceError("invalid_spec", f"该帧没有第 {box_index + 1} 个框", http_status=422)
    names = [c["name"] for c in run.classes]
    ann = anns[box_index]
    cid = int(ann.get("class_id", -1))
    if not 0 <= cid < len(names):
        raise ServiceError("invalid_spec", "框的类别不在任务的类别列表中", http_status=422)
    path = run_dir(run.id) / "images" / row.image_name
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR) if path.exists() else None
    if img is None:
        raise ServiceError("not_found", "帧图片文件不存在", http_status=404)
    box = geometry.from_yolo(ann, img.shape[1], img.shape[0])
    if box is None or geometry.area(box) < 16:
        raise ServiceError("invalid_spec", "框太小，无法作为参考图", http_status=422)
    data = encode_reference(crop_array(img, box))
    source = {"type": "operator", "frame": row.image_name, "box": [round(v, 1) for v in box],
              "by": getattr(user, "username", None)}
    return replace_reference(db, run, names[cid], data, source, user)


def reference_from_file(db: Session, run: PipelineRun, class_name: str, data: bytes, user,
                        box: Optional[List[float]] = None) -> PipelineRun:
    if len(data) > REFERENCE_MAX_BYTES:
        raise ServiceError("payload_too_large", f"参考图超过 {REFERENCE_MAX_BYTES // 1024 // 1024} MB", http_status=413)
    try:
        image = reference_from_upload(data, box)
    except ValueError as e:
        raise ServiceError("invalid_spec", str(e), http_status=422)
    return replace_reference(db, run, class_name, image, {"type": "provided", "by": getattr(user, "username", None)}, user)


def serialize_run(run: PipelineRun, *, detail: bool = False, external: bool = False) -> Dict[str, Any]:
    states = run.stage_states or {}
    data = {
        "job_id": str(run.id),
        "name": run.name,
        "external_ref": run.external_ref,
        "status": run.status,
        "stage": run.current_stage,
        "review_mode": run.review_mode,
        "progress": {
            "overall": round(run.progress or 0.0, 4),
            "stage": run.current_stage,
            "stage_progress": (states.get(run.current_stage) or {}).get("progress") if run.current_stage else None,
            "detail": (states.get(run.current_stage) or {}).get("detail") if run.current_stage else None,
        },
        "error": {"code": run.error_code, "message": run.error_message} if run.error_code else None,
        "created_at": isoformat(run.created_at),
        "started_at": isoformat(run.started_at),
        "finished_at": isoformat(run.finished_at),
        "links": {
            "self": f"/api/v1/pipeline/jobs/{run.id}",
            "events": f"/api/v1/pipeline/jobs/{run.id}/events",
            "artifacts": f"/api/v1/pipeline/jobs/{run.id}/artifacts",
        },
    }
    if detail:
        stages = []
        for name in STAGE_ORDER:
            st = dict(states.get(name) or {})
            err = st.get("error")
            if external and isinstance(err, dict):
                err = {"code": err.get("code"), "message": err.get("message")}   # 对外不返回日志与堆栈
            stages.append({"name": name, "status": st.get("status", "pending"), "progress": st.get("progress"),
                           "started_at": st.get("started_at"), "ended_at": st.get("ended_at"), "error": err})
        gate_results = run.gate_results or []
        data.update({
            "classes": run.classes,
            "videos": [{"key": v.key, "class": v.class_name, "classes": video_class_names(v), "status": v.status,
                        "original_filename": v.original_filename,
                        "duration": v.duration, "stats": v.stats, "error": v.error} for v in run.videos],
            "stages": stages,
            "gates": {
                "status": ("pause" if any(g["status"] in ("pause", "fail") and not g.get("overridden") for g in gate_results)
                           else "warn" if any(g["status"] == "warn" for g in gate_results) else
                           "ok" if gate_results else None),
                "failed": [g for g in gate_results if g["status"] in ("pause", "fail", "warn")],
            },
            "metrics": _public_metrics(run.metrics or {}),
            "llm_usage": run.llm_usage,
            "review": (run.artifacts or {}).get("review"),
        })
        if not external:
            data["artifacts"] = run.artifacts
            data["gate_results"] = gate_results
            data["config"] = run.config
            data["source"] = run.source
            data["attempt"] = run.attempt
    return data


def _public_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """对外只给结果性指标"""
    evaluate = metrics.get("evaluate") or {}
    export = metrics.get("export") or {}
    dataset = metrics.get("dataset") or {}
    return {
        "dataset": {"split_mode": dataset.get("split_mode"), "counts": dataset.get("counts"),
                    "segment_classes": dataset.get("segment_classes")} if dataset else None,
        "evaluate": {k: evaluate.get(k) for k in ("split", "map50_95", "map50", "precision", "recall", "per_class")} if evaluate else None,
        "tflite": {"passed": export.get("passed"), "gates": export.get("gates"), "cpu_latency_ms": export.get("cpu_latency_ms")} if export else None,
    }


def serialize_event(e: PipelineEvent, external: bool = False) -> Dict[str, Any]:
    data = e.data
    if external and isinstance(data, dict) and "details" in data:
        data = {k: v for k, v in data.items() if k != "details"}
    return {"id": e.id, "ts": isoformat(e.ts), "level": e.level, "stage": e.stage, "type": e.type,
            "message": e.message, "data": data}


def delivery_files(run: PipelineRun) -> Dict[str, Dict]:
    return dict((run.artifacts or {}).get("delivery") or {})
