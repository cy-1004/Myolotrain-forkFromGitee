"""⑩ 测试集评估：用训练出的 best.pt 在 test 集上评估（子进程，持 GPU 锁）"""
from app.services.pipeline import errors
from app.services.pipeline.errors import PipelineError
from app.services.pipeline.common import read_json
from app.services.pipeline.gpu_lock import gpu_lock
from app.services.pipeline.subprocess_runner import run_worker


def run(ctx):
    artifacts = ctx.get_artifacts()
    dataset_dir = ctx.path("dataset")
    counts = (read_json(dataset_dir / "split.json", {}) or {}).get("counts", {})
    split = "test" if counts.get("test") else ("val" if counts.get("val") else None)
    if split is None:
        ctx.warn("测试集和验证集都为空，跳过评估")
        ctx.update_stage_state(skipped_reason="没有测试数据")
        return "skip"
    if split == "val":
        ctx.warn("测试集为空，改用验证集评估（指标会偏乐观）")
    with gpu_lock(ctx, "评估"):
        result = run_worker(
            ctx, "app.services.pipeline.workers.evaluate",
            ["--weights", artifacts["best_pt"], "--data", str(dataset_dir / "dataset.yaml"), "--split", split,
             "--imgsz", str(ctx.config.train.imgsz), "--batch", str(min(ctx.config.train.batch, 16)),
             "--project", str(ctx.path("eval"))],
            out_json=ctx.path("eval", "metrics.json"), log_path=ctx.path("logs", "evaluate.log"),
            error_code=errors.EVALUATE_FAILED, timeout_seconds=3600, progress_hint="测试集评估")
    cfg = ctx.config.train
    result["quality_ok"] = result["map50"] >= cfg.min_test_map50
    ctx.set_metrics(evaluate=result)
    ctx.event("evaluate.done", f"{split} 集 mAP50-95 = {result['map50_95']:.4f}，mAP50 = {result['map50']:.4f}",
              data={"split": split, "map50_95": result["map50_95"], "map50": result["map50"]})
    if not result["quality_ok"]:
        message = (f"模型在 {split} 集上 mAP50 = {result['map50']:.3f}，低于要求的 {cfg.min_test_map50:.2f}，基本不可用。"
                   f"常见原因：训练轮数太少、每类帧数太少或标注质量差。可增加 epochs、补充视频，或在控制台检查标注")
        if cfg.fail_below_min_map:
            raise PipelineError(errors.EVALUATE_FAILED, message, details={"map50": result["map50"]})
        ctx.warn(message, data={"map50": result["map50"], "min_test_map50": cfg.min_test_map50})
