"""⑥ 自动标注：VLM 定位 → SAM 收框 → 质量闸门 → 时序一致性 → 风险评分，写入标注项目

每个视频只问该视频声明的类别（通常一个视频一类文物，也可声明多类），不问全部类别：
VLM 主要负责定位而不是分类，实测精确率比问全部类别高约 15 个百分点。
按 32 帧一批处理并立即入库：中途中断后续跑只处理还没有结果的帧，VLM 结果另有缓存，不会重复计费。
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

import cv2
import numpy as np

from app.core.config import settings
from app.models.annotation import AnnotationProject, ImageAnnotation
from app.services.labeling import geometry, risk
from app.services.labeling.sam_refiner import SamRefiner
from app.services.labeling.vlm_client import VLMAuthError, VLMClient, VLMRequest
from app.services.pipeline import errors
from app.services.pipeline.common import load_videos, read_json
from app.services.pipeline.errors import PipelineError, RunPaused
from app.services.pipeline.spec import effective_annotate_provider
from app.services.pipeline.stages import references as reference_store

logger = logging.getLogger(__name__)

CHUNK = 32
# 前这么多次请求全部因网络/接口原因失败，判定为服务不可用，直接终止而不是把每一帧都标成失败
FAIL_FAST_AFTER = 16


def ensure_project(ctx) -> str:
    artifacts = ctx.get_artifacts()
    if artifacts.get("annotation_project_id"):
        return artifacts["annotation_project_id"]
    images_dir = ctx.path("images")
    images_dir.mkdir(parents=True, exist_ok=True)
    with ctx.session() as db:
        project = AnnotationProject(
            name=f"[流水线] {ctx.name}",
            description=f"由流水线任务 {ctx.run_id} 自动创建，类别顺序已冻结",
            classes=ctx.class_names,
            image_directory=str(images_dir),
            project_type="detection",
            review_required=True,
            pipeline_run_id=ctx.run_id,
            status="active",
        )
        db.add(project)
        db.flush()
        project_id = str(project.id)
    ctx.set_artifacts(annotation_project_id=project_id)
    return project_id


def _read(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def build_record(frame: Dict, video: Dict, class_ids: Dict[str, int], vlm, sam: Optional[SamRefiner],
                 img: Optional[np.ndarray], provider: str, model: str, prompt_version: str = "",
                 n_references: int = 0) -> Dict:
    """一帧的标注结果 -> ImageAnnotation 字段

    class_ids：该视频声明的类别名 -> 全局 class_id。VLM 返回的标签已归一到声明的类别名
    （只声明一类时，标签不符的框也归到该类并标 label_mismatch；多类时认不出的标签已被丢弃）。
    """
    reasons: List[str] = []
    W, H = (img.shape[1], img.shape[0]) if img is not None else vlm.image_size
    if not vlm.ok:
        reasons.append("vlm_failed")
    boxes = [b for b in (vlm.boxes if vlm.ok else []) if b["label"] in class_ids]
    expected = video["expected_instances"]
    if vlm.ok and not boxes:
        reasons.append("no_box")
    by_class: Dict[str, List[Dict]] = {}
    for b in boxes:
        by_class.setdefault(b["label"], []).append(b)
    if any(len(items) > expected for items in by_class.values()):
        reasons.append("multi_box")
    if any(not b["label_matched"] for b in boxes):
        reasons.append("label_mismatch")
    # 件数按类别计：每类最多保留 expected 个（面积最大的），类别之间互不挤占
    primary = [b for name in class_ids for b in risk.pick_primary_boxes(by_class.get(name, []), expected)]

    sam_info = []
    if primary and sam is not None and img is not None:
        sam_info = sam.refine(img, [b["xyxy"] for b in primary])
    finals = []
    for i, b in enumerate(primary):
        outcome = sam_info[i] if i < len(sam_info) else {"xyxy": b["xyxy"], "status": "disabled"}
        if outcome["status"] in ("fallback", "error"):
            reasons.append("sam_fallback")
        source = "sam" if outcome["status"] == "refined" else "vlm"
        finals.append((outcome["xyxy"], source, class_ids[b["label"]]))
        reasons += risk.geometry_flags(outcome["xyxy"], W, H)

    annotations = [geometry.to_yolo(box, W, H, cid, source=source, edited=False) for box, source, cid in finals]
    base_reasons = sorted(set(reasons))
    return {
        "image_name": frame["image"],
        "annotations": annotations,
        "auto_annotations": {
            "vlm": boxes,
            "sam": sam_info,
            "meta": {
                "provider": provider, "model": model, "prompt_version": prompt_version, "references": n_references,
                "coord_mode": vlm.coord_mode, "cached": vlm.cached, "error": vlm.error, "error_kind": vlm.error_kind,
                "dropped_items": vlm.dropped_items, "image_size": [W, H], "base_reasons": base_reasons,
            },
        },
        "risk_reasons": base_reasons,
        "risk_score": risk.risk_score(base_reasons),
        "pipeline_meta": {
            "video_key": video["key"], "class_name": video["class_names"][0], "classes": list(video["class_names"]),
            "frame_index": frame["frame_index"], "ts": frame["ts"],
            "blur": round(frame.get("blur", 0.0), 2), "brightness": round(frame.get("brightness", 0.0), 2),
        },
    }


def _insert(ctx, project_id: str, records: List[Dict]):
    with ctx.session() as db:
        for r in records:
            db.add(ImageAnnotation(
                project_id=project_id, image_path=r["image_name"], image_name=r["image_name"],
                annotations=r["annotations"], is_completed=False, auto_annotations=r["auto_annotations"],
                review_status="auto_accepted", risk_score=r["risk_score"], risk_reasons=r["risk_reasons"],
                pipeline_meta=r["pipeline_meta"],
            ))


def apply_temporal_check(ctx, project_id: str, video_keys: Optional[List[str]] = None) -> Dict[str, int]:
    """按视频做时序一致性检查，重算风险分（可重复执行：每次都从 base_reasons 开始）"""
    counts = {}
    with ctx.session() as db:
        rows = db.query(ImageAnnotation).filter(ImageAnnotation.project_id == project_id).all()
        by_video: Dict[str, List[ImageAnnotation]] = {}
        for r in rows:
            key = (r.pipeline_meta or {}).get("video_key")
            if key and (video_keys is None or key in video_keys):
                by_video.setdefault(key, []).append(r)
        for key, items in by_video.items():
            # 每个类别单独成一条轨迹：取该帧里这一类的第一个框（多类视频里各件文物各自连续运动）
            outliers: Dict[str, Dict] = {}
            for cid in sorted({int(a.get("class_id", -1)) for r in items for a in (r.annotations or [])}):
                frames = []
                for r in items:
                    size = ((r.auto_annotations or {}).get("meta") or {}).get("image_size") or [1, 1]
                    ann = next((a for a in (r.annotations or []) if int(a.get("class_id", -1)) == cid), None)
                    box = geometry.from_yolo(ann, size[0], size[1]) if ann else None
                    frames.append({"index": str(r.id), "ts": (r.pipeline_meta or {}).get("ts", 0), "box": box,
                                   "image_diag": (size[0] ** 2 + size[1] ** 2) ** 0.5})
                outliers.update(risk.temporal_outliers(frames))
            counts[key] = len(outliers)
            for r in items:
                if r.review_status in ("accepted", "modified", "discarded"):
                    continue   # 人工处理过的帧不再改动
                base = list(((r.auto_annotations or {}).get("meta") or {}).get("base_reasons") or [])
                if str(r.id) in outliers:
                    base.append("temporal_outlier")
                reasons = sorted(set(base))
                r.risk_reasons = reasons
                r.risk_score = risk.risk_score(reasons)
    return counts


def make_client(ctx) -> VLMClient:
    cfg = ctx.config.annotate
    provider, model = effective_annotate_provider(cfg)
    if provider == "openrouter" and not settings.ALLOW_CLOUD_VLM:
        raise PipelineError(errors.VLM_UNAVAILABLE, "系统已禁止使用云端视觉模型（ALLOW_CLOUD_VLM=false）")
    if provider == "openrouter" and not settings.OPENROUTER_API_KEY:
        raise PipelineError(errors.VLM_UNAVAILABLE, "未配置 OPENROUTER_API_KEY")
    return VLMClient(provider, model, coord_mode=cfg.coord_mode, max_long_edge=cfg.max_long_edge,
                     min_long_edge=cfg.min_long_edge, cache_dir=ctx.path("vlm_cache"), prompt_style=cfg.prompt_style)


def check_budget(ctx, usage: Dict):
    budget = ctx.config.annotate.budget_usd
    if budget is None:
        budget = settings.VLM_BUDGET_PER_RUN_USD
    if budget and usage.get("cost_usd", 0.0) >= budget:
        raise RunPaused("budget", f"视觉模型费用已达到本任务预算 ${budget:.2f}，已暂停。调高预算或改用本地模型后继续")


def run(ctx, video_keys: Optional[List[str]] = None):
    """video_keys 不为空时只处理这些视频（人工修改类别后重标）"""
    cfg = ctx.config.annotate
    provider, model = effective_annotate_provider(cfg)
    project_id = ensure_project(ctx)
    client = make_client(ctx)
    sam = SamRefiner(cfg.sam_model or settings.SAM_MODEL, cfg.sam_gate.model_dump()) if cfg.sam_enabled else None
    if sam is not None and not sam.available:
        ctx.warn(f"{sam.load_error}；本次只用视觉模型的框，不做收框", data={"sam_model": sam.model_name})
        sam = None

    videos = [v for v in load_videos(ctx) if video_keys is None or v["key"] in video_keys]
    classes = {c["name"]: c for c in ctx.classes}
    global_ids = {name: i for i, name in enumerate(ctx.class_names)}
    refs = reference_store.load(ctx)
    with ctx.session() as db:
        done = {name for (name,) in db.query(ImageAnnotation.image_name).filter(
            ImageAnnotation.project_id == project_id, ImageAnnotation.auto_annotations.isnot(None)).all()}

    plan = []
    for v in videos:
        kept = [f for f in (read_json(ctx.path("manifest", f"{v['key']}.json"), {}) or {}).get("frames", []) if f.get("keep")]
        plan.append((v, [f for f in kept if f["image"] not in done]))
    total = sum(len(todo) for _, todo in plan) or 1
    processed = 0
    api_ok = api_failed = 0

    for v, todo in plan:
        declared = [classes[name] for name in v["class_names"]]
        class_ids = {c["name"]: global_ids[c["name"]] for c in declared}
        video_refs = [r for c in declared for r in refs.get(c["name"], [])]
        for start in range(0, len(todo), CHUNK):
            ctx.check_cancel()
            chunk = todo[start:start + CHUNK]
            requests = [VLMRequest(key=f["image"], image_path=ctx.path("images", f["image"]), classes=declared,
                                   references=video_refs) for f in chunk]
            try:
                results = client.detect_batch(requests, should_stop=ctx.is_cancel_requested)
            except VLMAuthError as e:
                raise PipelineError(errors.VLM_UNAVAILABLE, str(e))
            ctx.check_cancel(force=True)

            usage = {"calls": 0, "cached": 0, "failures": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
            records = []
            for f in chunk:
                res = results.get(f["image"])
                if res is None:
                    continue   # 被取消打断，未处理的帧下次续跑
                if res.cached:
                    usage["cached"] += 1
                else:
                    usage["calls"] += 1
                if not res.ok:
                    usage["failures"] += 1
                if not res.cached and provider != "mock":
                    if res.ok:
                        api_ok += 1
                    elif res.error_kind in ("timeout", "http"):
                        api_failed += 1
                u = res.usage or {}
                usage["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
                usage["completion_tokens"] += int(u.get("completion_tokens") or 0)
                usage["cost"] += float(u.get("cost") or 0.0)
                img = _read(ctx.path("images", f["image"])) if (sam is not None and res.ok and res.boxes) else None
                records.append(build_record(f, v, class_ids, res, sam, img, provider, model, client.prompt_version,
                                            len(video_refs)))

            if api_ok == 0 and api_failed >= FAIL_FAST_AFTER:
                first_error = next((r.error for r in results.values() if not r.ok), "")
                raise PipelineError(errors.VLM_UNAVAILABLE, f"视觉模型接口连续 {api_failed} 次请求失败，判定为不可用: {first_error}",
                                    retryable=True)
            _insert(ctx, project_id, records)
            total_usage = ctx.add_llm_usage(**usage)
            processed += len(records)
            ctx.progress(processed / total, detail={"video": v["key"], "annotated": processed, "total": total,
                                                    "cost_usd": total_usage.get("cost_usd", 0.0)})
            check_budget(ctx, total_usage)

    outliers = apply_temporal_check(ctx, project_id, video_keys)
    ctx.set_metrics(annotate={"temporal_outliers": outliers, "finished_at": datetime.utcnow().isoformat() + "Z"})
