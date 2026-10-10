"""流水线编排器：调度 Run、按顺序执行阶段、服务重启后恢复

- 调度线程每 2 秒从库里认领 queued 的 Run（FOR UPDATE SKIP LOCKED，多实例也不会重复认领），
  每个 Run 在独立线程中执行，同时执行数受 PIPELINE_MAX_PARALLEL_RUNS 限制；训练/评估另有全局 GPU 锁；
- 阶段幂等：每个阶段完成后记录状态，续跑时跳过已完成的阶段，阶段内部也跳过已完成的部分；
- 服务启动时，上次没跑完的 Run（running）自动重新排队续跑，超过 PIPELINE_MAX_ATTEMPTS 次判为失败；
  needs_review 的 Run 不受重启影响，继续等待人工处理。
"""
import logging
import os
import socket
import threading
import traceback
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.pipeline import PipelineRun
from app.services.pipeline import errors
from app.services.pipeline.context import STAGE_ORDER, RunContext, overall_progress
from app.services.pipeline.errors import PipelineError, RunCancelled, RunPaused
from app.services.pipeline.events import emit_event, utcnow
from app.services.pipeline.stages import (annotate, class_check, clean, dataset, evaluate, export_verify, extract,
                                          references,
                                          gate, ingest, package, train)
from app.services.pipeline.webhooks import webhook_sender

logger = logging.getLogger(__name__)

STAGES: List[Tuple[str, Callable]] = [
    ("ingest", ingest.run), ("extract", extract.run), ("clean", clean.run), ("references", references.run),
    ("class_check", class_check.run), ("annotate", annotate.run), ("gate", gate.run), ("dataset", dataset.run), ("train", train.run),
    ("evaluate", evaluate.run), ("export_verify", export_verify.run), ("package", package.run),
]
assert [s for s, _ in STAGES] == STAGE_ORDER

STAGE_LABELS = {
    "ingest": "接收视频", "extract": "切帧", "clean": "清洗", "class_check": "视频类别校验", "references": "参考图",
    "annotate": "自动标注",
    "gate": "质量闸门", "dataset": "构建数据集", "train": "训练", "evaluate": "测试集评估",
    "export_verify": "TFLite 导出与校验", "package": "打包交付",
}


def _set_stage(run: PipelineRun, stage: str, **fields):
    states = dict(run.stage_states or {})
    st = dict(states.get(stage, {}))
    st.update(fields)
    states[stage] = st
    run.stage_states = states
    run.progress = overall_progress(states)
    flag_modified(run, "stage_states")


class Orchestrator:
    def __init__(self):
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def start(self):
        if not settings.PIPELINE_WORKER_ENABLED:
            logger.info("流水线调度器未启用（PIPELINE_WORKER_ENABLED=false）")
            return
        if self._thread and self._thread.is_alive():
            return
        try:
            self.recover()
        except Exception:
            logger.exception("恢复未完成的流水线任务时出错")
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="pipeline-scheduler", daemon=True)
        self._thread.start()
        webhook_sender.start()
        logger.info(f"流水线调度器已启动（worker={self.worker_id}，并发 {settings.PIPELINE_MAX_PARALLEL_RUNS}）")

    def stop(self):
        self._stop.set()
        webhook_sender.stop()

    def recover(self):
        """服务启动时处理上次未结束的 Run（单 worker 部署：此刻不可能有其他进程在执行它们）"""
        db = SessionLocal()
        try:
            for run in db.query(PipelineRun).filter(PipelineRun.status.in_(["running", "cancelling"])).all():
                if run.status == "cancelling" or run.cancel_requested:
                    run.status, run.finished_at = "cancelled", utcnow()
                    emit_event(db, run, "job.cancelled", "任务已取消（服务重启时完成取消）", commit=False)
                elif run.attempt >= settings.PIPELINE_MAX_ATTEMPTS:
                    run.status, run.finished_at = "failed", utcnow()
                    run.error_code, run.error_message = errors.INTERRUPTED, f"服务重启导致中断，已自动续跑 {run.attempt} 次仍未完成"
                    emit_event(db, run, "job.failed", run.error_message, level="error", commit=False)
                else:
                    run.status = "queued"
                    emit_event(db, run, "run.requeued", f"服务重启，任务将从“{STAGE_LABELS.get(run.current_stage, run.current_stage)}”阶段自动续跑",
                               level="warning", stage=run.current_stage, commit=False)
            db.commit()
        finally:
            db.close()

    # ------------------------------------------------------------------
    def _loop(self):
        while not self._stop.is_set():
            try:
                self._reap()
                self._claim_and_start()
            except Exception:
                logger.exception("流水线调度循环出错")
            self._stop.wait(2)

    def _reap(self):
        with self._lock:
            for run_id in [k for k, t in self._running.items() if not t.is_alive()]:
                self._running.pop(run_id, None)

    def _claim_and_start(self):
        with self._lock:
            capacity = settings.PIPELINE_MAX_PARALLEL_RUNS - len(self._running)
        if capacity <= 0:
            return
        db = SessionLocal()
        try:
            rows = (db.query(PipelineRun).filter(PipelineRun.status == "queued")
                    .order_by(PipelineRun.created_at).with_for_update(skip_locked=True).limit(capacity).all())
            ids = []
            for run in rows:
                first = run.started_at is None   # 续跑、重启后恢复都不算"开始"
                run.status, run.worker_id, run.heartbeat_at = "running", self.worker_id, utcnow()
                run.attempt += 1
                run.started_at = run.started_at or utcnow()
                if first:
                    emit_event(db, run, "job.started", "任务开始执行", commit=False)
                ids.append(str(run.id))
            db.commit()
        finally:
            db.close()
        for run_id in ids:
            t = threading.Thread(target=self._execute, args=(run_id,), name=f"pipeline-run-{run_id[:8]}", daemon=True)
            with self._lock:
                self._running[run_id] = t
            t.start()

    def running_run_ids(self) -> List[str]:
        with self._lock:
            return [k for k, t in self._running.items() if t.is_alive()]

    # ------------------------------------------------------------------
    def _execute(self, run_id: str):
        ctx = None
        try:
            ctx = RunContext(run_id, self.worker_id)
            self._run_stages(ctx)
        except RunCancelled:
            self._finish(run_id, "cancelled", "job.cancelled", "任务已取消", stage_status="cancelled", ctx=ctx)
        except RunPaused as e:
            self._pause(run_id, ctx, e.reason, e.message)
        except PipelineError as e:
            logger.warning(f"[run {run_id}] 失败 {e.code}: {e.message}")
            self._finish(run_id, "failed", "job.failed", e.message, stage_status="failed", ctx=ctx,
                         error_code=e.code, details=e.details)
        except Exception as e:
            logger.exception(f"[run {run_id}] 未预期的错误")
            self._finish(run_id, "failed", "job.failed", f"内部错误：{type(e).__name__}: {e}", stage_status="failed",
                         ctx=ctx, error_code=errors.INTERNAL, details={"traceback": traceback.format_exc()[-3000:]})

    def _run_stages(self, ctx: RunContext):
        with ctx.session() as db:
            run = db.query(PipelineRun).filter(PipelineRun.id == ctx.run_id).one()
            states = dict(run.stage_states or {})
        for name, fn in STAGES:
            if (states.get(name) or {}).get("status") in ("completed", "skipped"):
                continue
            ctx.check_cancel(force=True)
            ctx.stage = name
            with ctx.session() as db:
                run = db.query(PipelineRun).filter(PipelineRun.id == ctx.run_id).one()
                attempts = int(((run.stage_states or {}).get(name) or {}).get("attempts") or 0) + 1
                _set_stage(run, name, status="running", progress=0.0, started_at=utcnow().isoformat() + "Z",
                           ended_at=None, error=None, attempts=attempts)
                run.current_stage, run.heartbeat_at = name, utcnow()
                emit_event(db, run, "stage.started", f"开始：{STAGE_LABELS[name]}", stage=name, commit=False)
            result = fn(ctx)
            if result == "pause":
                self._pause(ctx.run_id, ctx, "gate", None)
                return
            with ctx.session() as db:
                run = db.query(PipelineRun).filter(PipelineRun.id == ctx.run_id).one()
                status = "skipped" if result == "skip" else "completed"
                _set_stage(run, name, status=status, progress=1.0, ended_at=utcnow().isoformat() + "Z")
                emit_event(db, run, "stage.completed" if status == "completed" else "stage.skipped",
                           f"{'完成' if status == 'completed' else '跳过'}：{STAGE_LABELS[name]}", stage=name, commit=False)
        self._finish(ctx.run_id, "succeeded", "job.succeeded", "任务完成，交付包已生成", stage_status=None, ctx=ctx)

    def _pause(self, run_id, ctx, reason: str, message: Optional[str]):
        db = SessionLocal()
        try:
            run = db.query(PipelineRun).filter(PipelineRun.id == run_id).one()
            stage = ctx.stage if ctx else run.current_stage
            if stage:
                _set_stage(run, stage, status="paused", ended_at=utcnow().isoformat() + "Z")
            run.status = "needs_review"
            artifacts = dict(run.artifacts or {})
            review = dict(artifacts.get("review") or {})
            review.update({"paused": True, "reason": reason, "paused_at": utcnow().isoformat() + "Z"})
            if message:
                review["message"] = message
            review.pop("approved", None)
            artifacts["review"] = review
            run.artifacts = artifacts
            flag_modified(run, "artifacts")
            emit_event(db, run, "job.needs_review", message or "质量闸门触发，任务已暂停，等待人工处理", level="warning",
                       stage=stage, data={"reason": reason})
        finally:
            db.close()

    def _finish(self, run_id, status, event_type, message, *, stage_status, ctx=None, error_code=None, details=None):
        db = SessionLocal()
        try:
            run = db.query(PipelineRun).filter(PipelineRun.id == run_id).one()
            stage = (ctx.stage if ctx else None) or run.current_stage
            if stage_status and stage:
                fields = {"status": stage_status, "ended_at": utcnow().isoformat() + "Z"}
                if error_code:
                    fields["error"] = {"code": error_code, "message": message, "details": details}
                _set_stage(run, stage, **fields)
            run.status, run.finished_at = status, utcnow()
            if status == "succeeded":
                run.progress = 1.0
            if error_code:
                run.error_code, run.error_message = error_code, message
            emit_event(db, run, event_type, message, level="error" if status == "failed" else "info", stage=stage,
                       data={"code": error_code, "details": details} if error_code else None)
        finally:
            db.close()


orchestrator = Orchestrator()
