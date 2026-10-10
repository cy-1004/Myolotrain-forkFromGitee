"""全局 GPU 锁：同一时刻只允许一个流水线 Run 占用 GPU 训练/评估

用 Postgres 会话级 advisory lock 实现，跨进程有效（以后拆出多个 worker 也不用改）。
拿锁前还要等待控制台里手动发起的训练结束：两路训练同时跑会互相挤爆显存。
"""
import logging
import time
from contextlib import contextmanager

from sqlalchemy import text

from app.db.session import engine
from app.models.training_task import TrainingTask

logger = logging.getLogger(__name__)

GPU_LOCK_KEY = 7_316_002_001   # 任意固定的 64 位整数，只要全库唯一
POLL_SECONDS = 10

_ACTIVE_TRAINING = ("training", "downloading_model", "running")


def _foreign_training_running(db, own_task_id=None) -> bool:
    """是否有不属于流水线的训练正在运行"""
    for task in db.query(TrainingTask).filter(TrainingTask.status.in_(_ACTIVE_TRAINING)).all():
        params = task.parameters if isinstance(task.parameters, dict) else {}
        if own_task_id and str(task.id) == str(own_task_id):
            continue
        if not params.get("pipeline_run_id"):
            return True
    return False


@contextmanager
def gpu_lock(ctx, purpose: str):
    """阻塞直到拿到 GPU；等待期间每 10 秒检查一次取消并刷新心跳"""
    conn = engine.connect()
    waited_since = time.monotonic()
    announced = False
    try:
        while True:
            ctx.check_cancel(force=True)
            with ctx.session() as db:
                busy = _foreign_training_running(db)
            if not busy and conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": GPU_LOCK_KEY}).scalar():
                conn.commit()
                break
            conn.commit()
            if not announced:
                ctx.event("gpu.waiting", f"等待 GPU 空闲后开始{purpose}（其他任务正在训练）")
                announced = True
            ctx.progress(0.0, detail={"waiting_gpu": True, "waited_seconds": int(time.monotonic() - waited_since)},
                         force=True)
            time.sleep(POLL_SECONDS)
        if announced:
            ctx.event("gpu.acquired", f"已获得 GPU，开始{purpose}")
        yield
    finally:
        try:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": GPU_LOCK_KEY})
            conn.commit()
        except Exception:
            pass
        conn.close()   # 连接关闭时 Postgres 也会自动释放会话级锁
