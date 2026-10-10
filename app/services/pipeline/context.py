"""阶段执行上下文

每个阶段函数拿到一个 RunContext：
- 用 ctx.session() 取短生命周期的数据库会话——耗时的 GPU/网络调用期间不持有会话；
- ctx.progress() 汇报进度（节流写库，同时刷新心跳）；
- ctx.check_cancel() 在循环中检查取消请求；
- ctx.event() 写时间线事件。
"""
import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.paths import data_path
from app.db.session import SessionLocal
from app.models.pipeline import PipelineRun
from app.services.pipeline.errors import RunCancelled
from app.services.pipeline.events import emit_event, utcnow
from app.services.pipeline.spec import JobConfig

logger = logging.getLogger(__name__)

PROGRESS_WRITE_INTERVAL = 2.0     # 进度最多每 2 秒写一次库
CANCEL_CHECK_INTERVAL = 1.0

# 各阶段在整体进度中的权重（训练最久）
STAGE_WEIGHTS = {
    "ingest": 2, "extract": 8, "clean": 4, "references": 2, "class_check": 2, "annotate": 20, "gate": 1,
    "dataset": 3, "train": 45, "evaluate": 5, "export_verify": 8, "package": 2,
}
STAGE_ORDER = list(STAGE_WEIGHTS)


def run_dir(run_id) -> Path:
    return data_path("runs", str(run_id))


class RunContext:
    def __init__(self, run_id, worker_id: str):
        self.run_id = run_id
        self.worker_id = worker_id
        self.dir = run_dir(run_id)
        self.stage: Optional[str] = None
        self._last_progress_write = 0.0
        self._last_cancel_check = 0.0
        self._cancelled = False
        self._lock = threading.Lock()
        with self.session() as db:
            run = self._get(db)
            self.config = JobConfig.model_validate(run.config)
            self.classes: List[Dict[str, Any]] = list(run.classes)
            self.review_mode = run.review_mode
            self.name = run.name

    # ------------------------------------------------------------------
    @contextmanager
    def session(self) -> Iterator[Session]:
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _get(self, db: Session) -> PipelineRun:
        return db.query(PipelineRun).filter(PipelineRun.id == self.run_id).one()

    def path(self, *parts) -> Path:
        return self.dir.joinpath(*parts)

    @property
    def class_names(self) -> List[str]:
        return [c["name"] for c in self.classes]

    # ------------------------------------------------------------------
    def event(self, type: str, message: str = None, *, level: str = "info", data: Dict[str, Any] = None,
              stage: Optional[str] = "__current__"):
        with self.session() as db:
            run = self._get(db)
            emit_event(db, run, type, message, level=level, data=data,
                       stage=self.stage if stage == "__current__" else stage, commit=False)
        log = logger.warning if level in ("warning", "error") else logger.info
        log(f"[run {self.run_id}] {type}: {message or ''}")

    def warn(self, message: str, data: Dict[str, Any] = None):
        self.event("stage.warning", message, level="warning", data=data)

    def progress(self, fraction: float, detail: Optional[Dict[str, Any]] = None, force: bool = False):
        """汇报当前阶段进度（0~1）。节流写库，同时作为心跳"""
        now = time.monotonic()
        if not force and now - self._last_progress_write < PROGRESS_WRITE_INTERVAL:
            return
        self._last_progress_write = now
        fraction = max(0.0, min(1.0, float(fraction)))
        with self.session() as db:
            run = self._get(db)
            states = dict(run.stage_states or {})
            st = dict(states.get(self.stage, {}))
            st["progress"] = round(fraction, 4)
            if detail is not None:
                st["detail"] = detail
            states[self.stage] = st
            run.stage_states = states
            run.progress = overall_progress(states)
            run.heartbeat_at = utcnow()
            flag_modified(run, "stage_states")

    def heartbeat(self):
        with self.session() as db:
            self._get(db).heartbeat_at = utcnow()

    def check_cancel(self, force: bool = False):
        now = time.monotonic()
        if self._cancelled:
            raise RunCancelled()
        if not force and now - self._last_cancel_check < CANCEL_CHECK_INTERVAL:
            return
        self._last_cancel_check = now
        with self.session() as db:
            requested = db.query(PipelineRun.cancel_requested).filter(PipelineRun.id == self.run_id).scalar()
        if requested:
            self._cancelled = True
            raise RunCancelled()

    def is_cancel_requested(self) -> bool:
        """不抛异常的取消检查（节流，可以在逐帧循环里放心调用）"""
        try:
            self.check_cancel()
            return False
        except RunCancelled:
            return True

    # ------------------------------------------------------------------
    def stage_state(self, stage: Optional[str] = None) -> Dict[str, Any]:
        with self.session() as db:
            return dict((self._get(db).stage_states or {}).get(stage or self.stage, {}))

    def update_stage_state(self, stage: Optional[str] = None, **fields):
        stage = stage or self.stage
        with self.session() as db:
            run = self._get(db)
            states = dict(run.stage_states or {})
            st = dict(states.get(stage, {}))
            st.update(fields)
            states[stage] = st
            run.stage_states = states
            run.progress = overall_progress(states)
            flag_modified(run, "stage_states")

    def get_artifacts(self) -> Dict[str, Any]:
        with self.session() as db:
            return dict(self._get(db).artifacts or {})

    def set_artifacts(self, **items):
        with self.session() as db:
            run = self._get(db)
            artifacts = dict(run.artifacts or {})
            artifacts.update(items)
            run.artifacts = artifacts
            flag_modified(run, "artifacts")

    def get_metrics(self) -> Dict[str, Any]:
        with self.session() as db:
            return dict(self._get(db).metrics or {})

    def set_metrics(self, **items):
        with self.session() as db:
            run = self._get(db)
            metrics = dict(run.metrics or {})
            metrics.update(items)
            run.metrics = metrics
            flag_modified(run, "metrics")

    def add_llm_usage(self, calls: int = 0, cached: int = 0, prompt_tokens: int = 0,
                      completion_tokens: int = 0, cost: float = 0.0, failures: int = 0):
        with self._lock, self.session() as db:
            run = self._get(db)
            usage = dict(run.llm_usage or {})
            usage["calls"] = usage.get("calls", 0) + calls
            usage["cached"] = usage.get("cached", 0) + cached
            usage["failures"] = usage.get("failures", 0) + failures
            usage["prompt_tokens"] = usage.get("prompt_tokens", 0) + prompt_tokens
            usage["completion_tokens"] = usage.get("completion_tokens", 0) + completion_tokens
            usage["cost_usd"] = round(usage.get("cost_usd", 0.0) + cost, 6)
            run.llm_usage = usage
            flag_modified(run, "llm_usage")
            return usage


def overall_progress(states: Dict[str, Any]) -> float:
    total = sum(STAGE_WEIGHTS.values())
    done = 0.0
    for stage, weight in STAGE_WEIGHTS.items():
        st = states.get(stage) or {}
        if st.get("status") in ("completed", "skipped"):
            done += weight
        elif st.get("status") == "running":
            done += weight * float(st.get("progress") or 0.0)
    return round(done / total, 4)
