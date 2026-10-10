"""⑪ TFLite 导出与三道校验（子进程，只用 CPU）。校验不通过 = Run 失败：TFLite 是交付物，不是附件"""
from app.services.pipeline import errors
from app.services.pipeline.errors import PipelineError
from app.services.pipeline.subprocess_runner import run_worker


def run(ctx):
    artifacts = ctx.get_artifacts()
    cfg = ctx.config.export
    report = run_worker(
        ctx, "app.services.pipeline.workers.export_verify",
        ["--weights", artifacts["best_pt"], "--dataset-dir", str(ctx.path("dataset")),
         "--imgsz", str(ctx.config.train.imgsz), "--nc", str(len(ctx.classes)), "--out-dir", str(ctx.path("export")),
         "--numeric-images", str(cfg.numeric_check_images), "--max-box-error-px", str(cfg.max_box_error_px),
         "--max-score-error", str(cfg.max_score_error), "--max-map-drop", str(cfg.max_map_drop)],
        out_json=ctx.path("export", "report.json"), log_path=ctx.path("logs", "export_verify.log"),
        error_code=errors.TFLITE_EXPORT_FAILED, timeout_seconds=3600, cpu_only=True, progress_hint="TFLite 导出与校验")
    ctx.set_metrics(export=report)
    ctx.set_artifacts(tflite_path=report.get("tflite_path"))
    if not report.get("passed"):
        raise PipelineError(errors.TFLITE_VERIFY_FAILED, report.get("error") or "TFLite 校验未通过",
                            details={"gates": report.get("gates")})
    acc = report["gates"]["accuracy"]
    ctx.event("export.verified", f"TFLite 三道校验通过：mAP50-95 PT {acc['pt_map50_95']:.4f} / TFLite {acc['tflite_map50_95']:.4f}",
              data={"gates": {k: v["passed"] for k, v in report["gates"].items()}})
