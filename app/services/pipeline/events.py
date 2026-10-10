"""Run 事件与 webhook 入队

事件写入 pipeline_events，是控制台时间线和对外接口 /events 的数据来源。
job.* 事件如果命中 Run 订阅的 callback_events，会同时生成一条待投递的 webhook（由编排器循环发送）。
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.pipeline import PipelineEvent, PipelineRun, WebhookDelivery


def utcnow() -> datetime:
    return datetime.utcnow()


def isoformat(dt: Optional[datetime]) -> Optional[str]:
    """库里统一存 UTC 的 naive datetime，对外输出带 Z 后缀的 ISO 格式"""
    return dt.replace(microsecond=0).isoformat() + "Z" if dt else None


def job_summary(run: PipelineRun) -> Dict[str, Any]:
    """webhook 载荷里的任务摘要：只放调用方做决策需要的字段，详情让对方再调 GET 接口"""
    return {
        "job_id": str(run.id),
        "name": run.name,
        "external_ref": run.external_ref,
        "status": run.status,
        "stage": run.current_stage,
        "progress": round(run.progress or 0.0, 4),
        "error": {"code": run.error_code, "message": run.error_message} if run.error_code else None,
        "links": {
            "self": f"/api/v1/pipeline/jobs/{run.id}",
            "events": f"/api/v1/pipeline/jobs/{run.id}/events",
            "artifacts": f"/api/v1/pipeline/jobs/{run.id}/artifacts",
        },
    }


def emit_event(
    db: Session,
    run: PipelineRun,
    type: str,
    message: Optional[str] = None,
    *,
    level: str = "info",
    stage: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    actor: str = "system",
    commit: bool = True,
) -> PipelineEvent:
    event = PipelineEvent(
        run_id=run.id, ts=utcnow(), level=level, stage=stage, type=type,
        message=message, data=data, actor=actor,
    )
    db.add(event)
    db.flush()  # 拿到自增 id，webhook 载荷里要用

    if type.startswith("job.") and run.callback_url and type in (run.callback_events or []):
        from app.core.config import settings
        payload = {
            "event_id": event.id,
            "delivery_id": uuid.uuid4().hex,
            "event": type,
            "created_at": isoformat(event.ts),
            "job": job_summary(run),
        }
        if settings.PUBLIC_BASE_URL:
            base = settings.PUBLIC_BASE_URL.rstrip("/")
            payload["job"]["links"] = {k: base + v for k, v in payload["job"]["links"].items()}
        db.add(WebhookDelivery(
            run_id=run.id, event_id=event.id, event_type=type, url=run.callback_url,
            payload=payload, status="pending", attempts=0, next_attempt_at=utcnow(),
        ))
    if commit:
        db.commit()
    return event
