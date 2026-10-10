"""⑫ 打包交付：model.pt / model.tflite / labels.txt / model_card.json / report.json / delivery.zip

model_card.json 是给端侧的机器可读接入参数，输入输出形状取导出校验时的实测值而不是理论值。
"""
import hashlib
import shutil
import zipfile
from datetime import datetime

from app.core.paths import to_data_relative
from app.services.pipeline.common import load_videos, write_json

DELIVERY_FILES = ("model.pt", "model.tflite", "labels.txt", "model_card.json", "report.json")


def sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(ctx):
    artifacts = ctx.get_artifacts()
    metrics = ctx.get_metrics()
    export = metrics.get("export") or {}
    structure = (export.get("gates") or {}).get("structure") or {}
    accuracy = (export.get("gates") or {}).get("accuracy") or {}
    evaluate = metrics.get("evaluate") or {}
    dataset = metrics.get("dataset") or {}
    review = artifacts.get("review") or {}

    out = ctx.path("delivery")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifacts["best_pt"], out / "model.pt")
    shutil.copy2(artifacts["tflite_path"], out / "model.tflite")
    (out / "labels.txt").write_text("\n".join(ctx.class_names) + "\n", encoding="utf-8")

    imgsz = ctx.config.train.imgsz
    label_source = "reviewed" if review.get("approved") and ctx.review_mode == "full" else (
        "auto_partially_reviewed" if review.get("approved") else "auto")
    card = {
        "model_name": ctx.name,
        "task": "detect",
        "classes": ctx.class_names,
        "display_names": {c["name"]: c.get("display_name") for c in ctx.classes if c.get("display_name")},
        "input": {"shape": structure.get("input_shape") or [1, imgsz, imgsz, 3], "dtype": "float32", "color": "RGB",
                  "normalize": "x/255", "resize": "letterbox", "pad_value": 114},
        "output": {"shape": structure.get("output_shape"), "layout": structure.get("output_layout"),
                   "values": "cx,cy,w,h（像素，相对 letterbox 后的输入图）+ 各类别分数（已 sigmoid）",
                   "nms_included": False},
        "recommended": {"conf": 0.25, "iou": 0.45},
        "metrics": {
            "eval_split": evaluate.get("split"),
            "pt_map50_95": evaluate.get("map50_95"), "pt_map50": evaluate.get("map50"),
            "per_class_ap50_95": {k: v.get("ap50_95") for k, v in (evaluate.get("per_class") or {}).items()},
            "cpu_latency_ms": (export.get("cpu_latency_ms") or {}).get("mean"),
        },
        # 转换前后对比：PT 与 TFLite 都按端侧方式（letterbox + 单标签 NMS）推理后计算，两者可直接比较；
        # 与上面 Ultralytics 评估的数值口径不同（后者用多标签 NMS 等），不要混着比
        "tflite_check": {
            "pt_map50_95": accuracy.get("pt_map50_95"),
            "tflite_map50_95": accuracy.get("tflite_map50_95"),
            "map50_95_drop": accuracy.get("map50_95_drop"),
            "max_box_error_px": ((export.get("gates") or {}).get("numeric") or {}).get("box_max_abs_error_px"),
        },
        # 评估可信度说明：测试集标签来自自动标注时，mAP 衡量的是"与自动标注的一致度"
        "label_source": label_source,
        "split_mode": dataset.get("split_mode"),
        "quality_ok": evaluate.get("quality_ok"),
        "evaluation_caveats": [c for c in [
            f"测试集 mAP50 = {evaluate.get('map50', 0):.3f}，低于质量要求 {ctx.config.train.min_test_map50:.2f}，模型可能不可用"
            if evaluate and evaluate.get("quality_ok") is False else None,
            "测试集标签来自自动标注，未经人工全量复核：自动标注漏标的物品被模型找到时会算作误报，mAP50 往往偏低；"
            "框的松紧与人工标注习惯不同，mAP50-95 与人工口径可能有出入" if label_source != "reviewed" else None,
            "按时间段划分：测试集与训练集来自同一批视频" if dataset.get("split_mode") == "by_segment" else None,
            f"类别 {dataset.get('segment_classes')} 视频不足，按时间段划分，这些类别的测试指标偏乐观"
            if dataset.get("split_mode") == "hybrid" else None,
        ] if c],
        "source": {"pipeline_run_id": str(ctx.run_id), "dataset_id": artifacts.get("dataset_id"),
                   "model_id": artifacts.get("model_id"), "base_model": ctx.config.train.model,
                   "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z"},
    }
    write_json(out / "model_card.json", card)

    videos = load_videos(ctx, include_inactive=True)
    report = {
        "run_id": str(ctx.run_id), "name": ctx.name, "review_mode": ctx.review_mode,
        "videos": [{"key": v["key"], "classes": v["class_names"], "status": v["status"], "stats": v["stats"]} for v in videos],
        "metrics": metrics,
        "llm_usage": None,
    }
    with ctx.session() as db:
        from app.models.pipeline import PipelineRun
        run_row = db.query(PipelineRun).filter(PipelineRun.id == ctx.run_id).one()
        report["llm_usage"] = run_row.llm_usage
        report["gate_results"] = run_row.gate_results
        report["stage_states"] = run_row.stage_states
    write_json(out / "report.json", report)

    zip_path = out / "delivery.zip"
    tmp_zip = out / "delivery.zip.tmp"
    with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in DELIVERY_FILES:
            zf.write(out / name, arcname=name)
    tmp_zip.replace(zip_path)

    files = {}
    for name in DELIVERY_FILES + ("delivery.zip",):
        path = out / name
        files[name] = {"path": to_data_relative(path), "size": path.stat().st_size, "sha256": sha256_of(path)}
    ctx.set_artifacts(delivery=files)
