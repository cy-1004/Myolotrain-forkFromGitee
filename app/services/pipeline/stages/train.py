"""⑨ 训练：复用平台现有的训练服务（子进程训练 + 监控线程），在全局 GPU 锁内执行

- 训练任务登记在 training_tasks 表里，控制台"训练管理"页能看到它的日志和曲线；
- 服务重启后续跑：训练进程若还活着就继续等；已中断且有 last.pt 就续训；否则重新训练；
- 取消 Run 会停止训练进程。
"""
import time
from pathlib import Path

from fastapi import HTTPException

from app.crud import training_task as training_task_crud
from app.services import training_service
from app.services.pipeline import errors
from app.services.pipeline.errors import PipelineError, RunCancelled
from app.services.pipeline.gpu_lock import gpu_lock

POLL_SECONDS = 5
FINAL_STATUSES = ("completed", "failed", "cancelled", "interrupted")


def _hardware_config():
    try:
        import torch
        if torch.cuda.is_available():
            return {"device_type": "gpu", "gpu_index": 0}
    except Exception:
        pass
    return {"device_type": "cpu"}


def _log_tail(task, n_bytes=3000) -> str:
    chunk = training_service.read_training_log_chunk(task, offset=-n_bytes, limit=n_bytes)
    return chunk.get("text", "")


def _create_task(ctx, db, attempt: int):
    cfg = ctx.config.train
    artifacts = ctx.get_artifacts()
    params = {
        "model_type": cfg.model,
        "epochs": cfg.epochs,
        "batch_size": cfg.batch,
        "img_size": cfg.imgsz,
        "task_type": "detect",
        "pipeline_run_id": str(ctx.run_id),
        "extra_train_args": {"patience": cfg.patience},
    }
    try:
        task = training_service.create_training_task(
            db, name=f"[流水线] {ctx.name}" + (f" #{attempt}" if attempt > 1 else ""),
            dataset_id=artifacts["dataset_id"], parameters=params, hardware_config=_hardware_config())
    except HTTPException as e:
        raise PipelineError(errors.TRAIN_FAILED, f"创建训练任务失败: {e.detail}")
    return task


def run(ctx):
    artifacts = ctx.get_artifacts()
    total_epochs = ctx.config.train.epochs
    with gpu_lock(ctx, "训练"):
        with ctx.session() as db:
            task_id = artifacts.get("training_task_id")
            task = training_task_crud.get(db, id=task_id) if task_id else None
            attempts = int(artifacts.get("training_attempts") or 0)

            if task is not None and task.status == "completed":
                pass   # 已完成（续跑时直接复用）
            elif task is not None and task.status in ("training", "downloading_model", "running") and \
                    (training_service.is_task_watched(task.id) or _process_alive(task)):
                pass   # 训练进程还在跑，继续等
            elif task is not None and task.status in ("interrupted", "cancelled") and \
                    (training_service.get_training_output_dir(task) / "exp" / "weights" / "last.pt").exists():
                ctx.event("train.resumed", "检测到上次中断的训练，从 last.pt 继续")
                try:
                    training_service.resume_training(db, str(task.id))
                except HTTPException as e:
                    raise PipelineError(errors.TRAIN_FAILED, f"续训失败: {e.detail}")
            else:
                attempts += 1
                task = _create_task(ctx, db, attempts)
                ctx.set_artifacts(training_task_id=str(task.id), training_attempts=attempts)
                try:
                    training_service.start_training(db, str(task.id))
                except HTTPException as e:
                    raise PipelineError(errors.TRAIN_FAILED, f"启动训练失败: {e.detail}")
                except Exception as e:
                    raise PipelineError(errors.TRAIN_FAILED, f"启动训练失败: {e}")
                ctx.event("train.started", f"训练已开始（{ctx.config.train.model}，{total_epochs} 轮，imgsz={ctx.config.train.imgsz}）",
                          data={"training_task_id": str(task.id)})
            task_id = str(task.id)

        # 轮询直到训练结束
        while True:
            try:
                ctx.check_cancel()
            except RunCancelled:
                with ctx.session() as db:
                    try:
                        training_service.stop_training(db, task_id)
                    except Exception:
                        pass
                raise
            with ctx.session() as db:
                task = training_task_crud.get(db, id=task_id)
                status = task.status
                rows = training_service.read_results_csv(task)
            done = len(rows)
            last = rows[-1] if rows else {}
            ctx.progress(min(1.0, done / max(1, total_epochs)), detail={
                "training_task_id": task_id, "epoch": done, "epochs": total_epochs,
                "map50_95": last.get("metrics/mAP50-95(B)"), "map50": last.get("metrics/mAP50(B)")})
            if status in FINAL_STATUSES:
                break
            time.sleep(POLL_SECONDS)

        with ctx.session() as db:
            task = training_task_crud.get(db, id=task_id)
            if task.status != "completed":
                tail = _log_tail(task)
                raise PipelineError(errors.TRAIN_FAILED, f"训练未成功结束（状态 {task.status}），日志末尾见 details",
                                    details={"training_task_id": task_id, "log_tail": tail[-2000:]})
            if not task.output_model_id:
                training_service.register_trained_model(db, task, "best")
            best = training_service.get_training_output_dir(task) / "exp" / "weights" / "best.pt"
            model_id = str(task.output_model_id)
            # 必须在会话内读：会话关闭后 task 已脱离会话，再访问属性会触发 DetachedInstanceError
            rows = training_service.read_results_csv(task)
        ctx.set_artifacts(model_id=model_id, best_pt=str(best))
        ctx.set_metrics(train={"epochs_run": len(rows), "last": rows[-1] if rows else {},
                               "best_map50_95": max((r.get("metrics/mAP50-95(B)") or 0) for r in rows) if rows else None})


def _process_alive(task) -> bool:
    from app.services.process_monitor import is_training_process_alive
    try:
        return bool(task.process_id) and is_training_process_alive(int(task.process_id), task.id)
    except (TypeError, ValueError):
        return False
