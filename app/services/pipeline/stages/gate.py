"""⑦ 质量闸门：统计自动标注质量，决定继续训练、暂停等人，还是直接失败

review_mode：
- auto：只记录，不暂停（只有"某类别没有任何可用帧"这种无法继续的情况才失败）；
- on_anomaly（默认）：任一指标到"暂停"档就暂停到 needs_review；
- full：总是暂停，所有帧都要人工处理。
暂停后由控制台处理（排除视频、改类别、逐帧复核），然后"放行"继续；放行时可以覆盖指定的闸门。
"""
from typing import Dict, List, Optional

from app.models.annotation import ImageAnnotation
from app.services.labeling import geometry
from app.services.pipeline import errors
from app.services.pipeline.common import load_videos
from app.services.pipeline.errors import PipelineError

# 指标定义：scope 为统计范围；direction=max 表示越大越差，min 表示越小越差
GATES = {
    "class_check_agreement": {"scope": "video", "direction": "min", "warn": 0.8, "pause": 0.6,
                              "label": "视频类别校验一致率"},
    "zero_box_rate": {"scope": "video", "direction": "max", "warn": 0.10, "pause": 0.25, "label": "未检出比例"},
    "multi_box_rate": {"scope": "video", "direction": "max", "warn": 0.05, "pause": 0.15, "label": "多框比例"},
    "vlm_fail_rate": {"scope": "video", "direction": "max", "warn": 0.02, "pause": 0.05, "label": "视觉模型失败比例"},
    "sam_fallback_rate": {"scope": "video", "direction": "max", "warn": 0.15, "pause": 0.35, "label": "SAM 收框回退比例"},
    "temporal_jump_rate": {"scope": "video", "direction": "max", "warn": 0.05, "pause": 0.15, "label": "框跳变比例"},
    # 只警告不暂停：真实素材里文物本来就常常很小（桌面远景），实测按它暂停的视频标注都是对的
    "tiny_or_truncated_rate": {"scope": "video", "direction": "max", "warn": 0.4, "pause": None, "label": "过小/截断框比例"},
    "kept_ratio_after_clean": {"scope": "video", "direction": "min", "warn": 0.5, "pause": 0.2, "label": "清洗保留比例"},
    "usable_frames_per_class": {"scope": "class", "direction": "min", "warn": 100, "pause": 40, "label": "每类可用帧数"},
    "videos_per_class": {"scope": "class", "direction": "min", "warn": 3, "pause": None,
                         "label": "每类视频数（少于 3 个时只能按时间段划分，评估指标会偏高）"},
    "class_balance": {"scope": "run", "direction": "min", "warn": 0.3, "pause": None, "label": "类别均衡度（最少类/最多类）"},
}

TRAINABLE_REVIEWED = ("accepted", "modified")


def thresholds(ctx) -> Dict[str, Dict]:
    merged = {k: dict(v) for k, v in GATES.items()}
    for name, override in (ctx.config.gates.thresholds or {}).items():
        if name in merged:
            for k in ("warn", "pause"):
                val = getattr(override, k)
                if val is not None:
                    merged[name][k] = val
    return merged


def frame_is_trainable(row: ImageAnnotation, drop_risk_above: float, include_unreviewed: str = "low_risk") -> bool:
    """这一帧会不会进训练集（数据集阶段与闸门统计共用同一判定）"""
    status = row.review_status
    if status == "discarded":
        return False
    if status in TRAINABLE_REVIEWED:
        return True   # 人工确认过的帧，包括确认"无目标"的负样本
    if not row.annotations:
        return False  # 自动标注没检出：可能是漏检，不能当负样本
    if status == "to_review":
        if include_unreviewed == "all":
            return True
        if include_unreviewed == "none":
            return False
    return (row.risk_score or 0.0) <= drop_risk_above


def _status(value, rule) -> str:
    if value is None:
        return "skipped"
    bad = (lambda t: value > t) if rule["direction"] == "max" else (lambda t: value < t)
    if rule.get("fail") is not None and bad(rule["fail"]):
        return "fail"
    if rule.get("pause") is not None and bad(rule["pause"]):
        return "pause"
    if rule.get("warn") is not None and bad(rule["warn"]):
        return "warn"
    return "ok"


def compute(ctx, include_unreviewed: str = "low_risk") -> Dict:
    """统计闸门指标。返回 {"results": [...], "video_stats": {...}, "class_stats": {...}}"""
    rules = thresholds(ctx)
    drop = ctx.config.annotate.drop_risk_above
    project_id = ctx.get_artifacts().get("annotation_project_id")
    videos = load_videos(ctx)
    names = ctx.class_names
    class_frames = {c: 0 for c in names}   # 每类：含该类框、且会进训练集的帧数
    with ctx.session() as db:
        rows = db.query(ImageAnnotation).filter(ImageAnnotation.project_id == project_id).all() if project_id else []
        per_video: Dict[str, Dict] = {v["key"]: {"frames": 0, "no_box": 0, "multi_box": 0, "vlm_failed": 0, "with_box": 0,
                                                  "sam_fallback": 0, "sam_tried": 0, "temporal": 0, "tiny_trunc": 0,
                                                  "trainable": 0, "to_review": 0, "reviewed": 0, "discarded": 0}
                                      for v in videos}
        for r in rows:
            key = (r.pipeline_meta or {}).get("video_key")
            s = per_video.get(key)
            if s is None:
                continue   # 被排除的视频
            reasons = set(r.risk_reasons or [])
            s["frames"] += 1
            s["no_box"] += "no_box" in reasons
            s["multi_box"] += "multi_box" in reasons
            s["vlm_failed"] += "vlm_failed" in reasons
            s["temporal"] += "temporal_outlier" in reasons
            if r.annotations:
                s["with_box"] += 1
                size = ((r.auto_annotations or {}).get("meta") or {}).get("image_size") or [1, 1]
                boxes = [geometry.from_yolo(a, size[0], size[1]) for a in r.annotations]
                if "tiny_box" in reasons or any(b and geometry.edges_touched(b, size[0], size[1]) >= 2 for b in boxes):
                    s["tiny_trunc"] += 1
            sam = (r.auto_annotations or {}).get("sam") or []
            if sam:
                s["sam_tried"] += 1
                s["sam_fallback"] += any(o.get("status") in ("fallback", "error") for o in sam)
            trainable = frame_is_trainable(r, drop, include_unreviewed)
            s["trainable"] += trainable
            if trainable:
                for cid in {int(a.get("class_id", -1)) for a in (r.annotations or [])}:
                    if 0 <= cid < len(names):
                        class_frames[names[cid]] += 1
            s["to_review"] += r.review_status == "to_review"
            s["reviewed"] += r.review_status in TRAINABLE_REVIEWED
            s["discarded"] += r.review_status == "discarded"

    def rate(n, d):
        return round(n / d, 4) if d else None

    results: List[Dict] = []

    def add(metric, scope, key, value, extra=None):
        rule = rules[metric]
        results.append({"metric": metric, "label": rule["label"], "scope": scope, "key": key,
                        "value": value, "warn": rule.get("warn"), "pause": rule.get("pause"),
                        "direction": rule["direction"], "status": _status(value, rule), **(extra or {})})

    class_videos = {c: 0 for c in names}
    for v in videos:
        s = per_video[v["key"]]
        attempted = s["frames"] - s["vlm_failed"]
        add("class_check_agreement", "video", v["key"], (v["stats"].get("class_check") or {}).get("agreement"))
        add("zero_box_rate", "video", v["key"], rate(s["no_box"], attempted))
        add("multi_box_rate", "video", v["key"], rate(s["multi_box"], attempted))
        add("vlm_fail_rate", "video", v["key"], rate(s["vlm_failed"], s["frames"]))
        add("sam_fallback_rate", "video", v["key"], rate(s["sam_fallback"], s["sam_tried"]))
        add("temporal_jump_rate", "video", v["key"], rate(s["temporal"], s["with_box"]))
        add("tiny_or_truncated_rate", "video", v["key"], rate(s["tiny_trunc"], s["with_box"]))
        add("kept_ratio_after_clean", "video", v["key"], (v["stats"].get("clean") or {}).get("kept_ratio"))
        for c in v["class_names"]:
            class_videos[c] += 1

    for c in names:
        add("usable_frames_per_class", "class", c, class_frames[c])
        results[-1]["status"] = "fail" if class_frames[c] == 0 else results[-1]["status"]
        add("videos_per_class", "class", c, class_videos[c])
    counts = [n for n in class_frames.values()]
    add("class_balance", "run", None, round(min(counts) / max(counts), 4) if counts and max(counts) else None)
    return {"results": results, "video_stats": per_video, "class_frames": class_frames}


def mark_for_review(ctx, full: bool) -> int:
    """暂停时给需要人看的帧标 to_review：full 模式全部，on_anomaly 只标风险高于阈值的"""
    project_id = ctx.get_artifacts().get("annotation_project_id")
    drop = ctx.config.annotate.drop_risk_above
    n = 0
    with ctx.session() as db:
        for r in db.query(ImageAnnotation).filter(ImageAnnotation.project_id == project_id,
                                                  ImageAnnotation.review_status == "auto_accepted").all():
            if full or (r.risk_score or 0.0) > drop or not r.annotations:
                r.review_status = "to_review"
                n += 1
    return n


def run(ctx):
    review = ctx.get_artifacts().get("review") or {}
    approved = bool(review.get("approved"))
    include_unreviewed = review.get("include_unreviewed", "low_risk")
    overrides = set(review.get("override_gates") or [])

    stats = compute(ctx, include_unreviewed)
    results = stats["results"]
    for r in results:
        if r["metric"] in overrides and r["status"] in ("warn", "pause"):
            r["overridden"] = True
    with ctx.session() as db:
        from app.models.pipeline import PipelineRun
        run_row = db.query(PipelineRun).filter(PipelineRun.id == ctx.run_id).one()
        run_row.gate_results = results
    ctx.set_metrics(gate={"video_stats": stats["video_stats"], "class_frames": stats["class_frames"]})

    failing = [r for r in results if r["status"] == "fail"]
    pausing = [r for r in results if r["status"] == "pause" and not r.get("overridden")]
    warnings = [r for r in results if r["status"] == "warn"]
    summary = {"pause": len(pausing), "fail": len(failing), "warn": len(warnings)}
    ctx.update_stage_state(summary=summary)

    if ctx.review_mode == "auto" or approved:
        if failing:
            names = ", ".join(r["key"] for r in failing)
            if ctx.review_mode == "auto":
                raise PipelineError(errors.GATE_FAILED_HARD,
                                    f"类别 {names} 没有任何可用于训练的帧，无法继续。请检查该类视频，或改用 on_anomaly 模式人工处理",
                                    details={"failed": failing})
            raise PipelineError(errors.NO_USABLE_FRAMES, f"放行后类别 {names} 仍没有可用于训练的帧，无法训练",
                                details={"failed": failing})
        if warnings:
            ctx.warn(f"质量闸门有 {len(warnings)} 项警告", data={"warnings": [_brief(r) for r in warnings]})
        return None

    if ctx.review_mode == "full" or pausing or failing:
        n = mark_for_review(ctx, full=ctx.review_mode == "full")
        reason = "full_review" if ctx.review_mode == "full" else "anomaly"
        ctx.set_artifacts(review={"paused": True, "reason": reason, "to_review": n})
        msg = ("全量复核模式：所有帧需要人工处理后放行" if reason == "full_review"
               else f"质量闸门暂停：{', '.join(_brief(r) for r in (failing + pausing)[:5])}")
        ctx.event("gate.paused", msg, level="warning",
                  data={"reason": reason, "to_review": n, "failed": [_brief(r) for r in failing + pausing]})
        return "pause"
    return None


def _brief(r: Dict) -> str:
    where = f"{r['scope']} {r['key']}" if r["key"] else r["scope"]
    value = r["value"]
    shown = f"{value:.2%}" if isinstance(value, float) and value <= 1 and r["metric"].endswith(("rate", "agreement", "ratio")) else value
    return f"{r['label']}（{where}）= {shown}"
