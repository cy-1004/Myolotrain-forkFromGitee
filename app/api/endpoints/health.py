"""存活 / 就绪检查。无需登录：供 Docker HEALTHCHECK、启动脚本和外部监控调用，不返回任何业务数据"""
import os
import shutil
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

router = APIRouter()

# 数据卷剩余空间低于该值时视为未就绪：抽帧、训练产物都很占空间，写满后各环节会以各种奇怪的方式失败
MIN_FREE_DISK_GB = 2.0


@router.get("/health")
def health():
    """存活检查：进程能处理请求即可"""
    return {"status": "ok"}


@router.get("/ready")
def ready():
    """就绪检查：数据库可连、数据目录可写、磁盘空间充足；GPU 只报告不作为判定条件"""
    checks = {}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as e:
        checks["database"] = {"ok": False, "error": type(e).__name__}

    data_dir = settings.DATA_DIR
    try:
        probe = data_dir / f".ready_probe_{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        free_gb = shutil.disk_usage(data_dir).free / 1024 ** 3
        checks["data_dir"] = {"ok": free_gb >= MIN_FREE_DISK_GB, "free_gb": round(free_gb, 1)}
    except Exception as e:
        checks["data_dir"] = {"ok": False, "error": type(e).__name__}

    try:
        import torch
        checks["gpu"] = {"available": torch.cuda.is_available(), "count": torch.cuda.device_count()}
    except Exception:
        checks["gpu"] = {"available": False, "count": 0}

    ok = all(v.get("ok", True) for k, v in checks.items() if k != "gpu")
    return JSONResponse(status_code=200 if ok else 503, content={"status": "ready" if ok else "not_ready", "checks": checks})
