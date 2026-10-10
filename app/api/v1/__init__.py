"""对外接口 /api/v1：独立的 FastAPI 子应用（独立的 OpenAPI 文档 /api/v1/docs 与统一错误格式）

错误统一为：{"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}
"""
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.services.pipeline.service import ServiceError

logger = logging.getLogger(__name__)

_HTTP_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
               409: "conflict", 413: "payload_too_large", 415: "unsupported_media_type", 422: "invalid_spec",
               429: "rate_limited", 507: "insufficient_storage"}


def _error(request: Request, status: int, code: str, message: str, details=None) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex
    return JSONResponse(status_code=status, headers={"X-Request-ID": request_id},
                        content={"error": {"code": code, "message": message, "details": details, "request_id": request_id}})


def create_v1_app() -> FastAPI:
    app = FastAPI(
        title="Myolotrain 对外接口",
        version="1.0",
        description=(
            "文物视频一键训练：上传视频 → 自动切帧、标注、训练 → 获取已校验的 TFLite 交付包。\n\n"
            "鉴权：请求头 `X-API-Key: myo_sk_...`（在控制台“API Key 管理”中创建）。\n\n"
            "所有错误返回 `{\"error\": {\"code\", \"message\", \"details\", \"request_id\"}}`。"
        ),
        docs_url="/docs", redoc_url=None, openapi_url="/openapi.json",
    )

    @app.exception_handler(ServiceError)
    async def _service_error(request: Request, exc: ServiceError):
        return _error(request, exc.http_status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return _error(request, 422, "invalid_spec", "请求参数不合法", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return _error(request, exc.status_code, _HTTP_CODES.get(exc.status_code, "error"), str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception(f"对外接口未处理的异常: {request.method} {request.url.path}")
        message = "服务内部错误" if settings.EXTERNAL_MODE else f"服务内部错误: {exc}"
        return _error(request, 500, "internal", message)

    from app.api.v1 import jobs, uploads
    app.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
    app.include_router(jobs.router, prefix="/pipeline/jobs", tags=["pipeline"])

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    return app
