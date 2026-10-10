"""对外接口的鉴权：API Key（X-API-Key 头，或 Authorization: Bearer myo_sk_...）"""
from fastapi import Depends, Request
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.pipeline import PipelineRun
from app.services.api_key_service import verify_api_key
from app.services.pipeline.service import ServiceError


def _extract_key(request: Request) -> str:
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()
    scheme, param = get_authorization_scheme_param(request.headers.get("authorization"))
    return param.strip() if scheme.lower() == "bearer" else ""


def require_scope(scope: str):
    def dependency(request: Request, db: Session = Depends(get_db)) -> ApiKey:
        key = _extract_key(request)
        if not key:
            raise ServiceError("unauthorized", "缺少 API Key（请求头 X-API-Key）", http_status=401)
        record = verify_api_key(db, key)
        if record is None:
            raise ServiceError("unauthorized", "API Key 无效、已过期或已吊销", http_status=401)
        if scope not in (record.scopes or []):
            raise ServiceError("forbidden_scope", f"该 API Key 没有 {scope} 权限", http_status=403)
        request.state.api_key_prefix = record.prefix
        return record
    return dependency


def get_owned_run(db: Session, job_id: str, api_key: ApiKey) -> PipelineRun:
    """取当前 Key 自己的任务；不存在和不属于它都返回 404（不泄露别人的任务是否存在）"""
    try:
        import uuid
        uuid.UUID(str(job_id))
    except ValueError:
        raise ServiceError("not_found", "任务不存在", http_status=404)
    run = db.query(PipelineRun).filter(PipelineRun.id == job_id, PipelineRun.api_key_id == api_key.id).first()
    if run is None:
        raise ServiceError("not_found", "任务不存在", http_status=404)
    return run
