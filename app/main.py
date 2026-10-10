import logging
import re
import socket
import threading
import uuid
from fastapi import FastAPI, Request, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordBearer

from app.api.api import api_router
from app.core.config import settings
from app.core.static_access import is_public_static, is_static_path
from app.services.process_monitor import process_monitor
from app.services.tensorboard_service import tensorboard_manager
from app.services.upload_service import start_cleanup
from app.services.monitoring_service import system_monitor
from app.patches.torch_load_patch import apply_patch

# 导入认证相关模块
from app.api.deps import extract_token, is_token_valid_for_static
from app.models.user import User
logging_level = logging.DEBUG if settings.DEBUG else logging.INFO
logging.basicConfig(
    level=logging_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.info(f"应用启动模式: {'DEBUG' if settings.DEBUG else 'PRODUCTION'}")

# 检查必要的目录
import os
for directory in [
    "app/static/uploads",
    "app/static/datasets",
    "app/static/models",
    "app/static/results",
    "logs/tensorboard",
]:
    os.makedirs(directory, exist_ok=True)
    logger.info(f"Ensured directory exists: {directory}")

# 对外部署模式下不暴露控制台内部接口的交互式文档（对外接口另有独立文档）
_docs_kwargs = {"docs_url": None, "redoc_url": None, "openapi_url": None} if settings.EXTERNAL_MODE else {}
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="YOLOv8 Training and Detection Web Platform",
    version="0.1.0",
    **_docs_kwargs,
)

def get_lan_ip_addresses() -> list:
    """探测本机可被局域网访问的 IPv4 地址，用于启动时打印可分享给同事的访问链接

    host=0.0.0.0 会监听所有网卡，但用户不知道该把哪个地址发给同事——
    尤其训练服务器常见双网卡（有线+无线/虚拟网卡）。这里把默认出口地址排在最前，
    其余网卡地址作为备选一并列出。
    """
    addresses = []

    # 不实际发送数据，只是借 UDP connect 让系统选出默认出口网卡的地址，
    # 这是获取"外部可达" IP 最可靠的写法，不依赖真实网络连通性
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            addresses.append(s.getsockname()[0])
    except OSError:
        pass

    # 补充其他网卡地址（多网卡场景下默认出口可能选错网段）
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in addresses and not ip.startswith("127."):
                addresses.append(ip)
    except OSError:
        pass

    return addresses

@app.on_event("startup")
async def startup_event():
    logger.info("Application startup")
    try:
        # 应用PyTorch加载补丁，确保使用weights_only=False
        apply_patch()
        logger.info("Applied PyTorch load patch: weights_only=False by default")

        # 检查数据库连接
        from app.db.session import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")

        # 添加PyTorch安全全局变量
        try:
            import torch
            from torch.nn.modules.container import Sequential
            from torch.nn import Module, ModuleList, ModuleDict

            # 导入Ultralytics模型类
            from ultralytics.nn.tasks import DetectionModel, SegmentationModel, ClassificationModel, PoseModel

            # 导入Ultralytics模块类
            from ultralytics.nn.modules import conv
            from ultralytics.nn.modules import block
            from ultralytics.nn.modules import head

            # 添加PyTorch核心类
            torch.serialization.add_safe_globals([
                Sequential,
                Module,
                ModuleList,
                ModuleDict
            ])

            # 添加Ultralytics模型类
            torch.serialization.add_safe_globals([
                DetectionModel,
                SegmentationModel,
                ClassificationModel,
                PoseModel
            ])

            # 添加Ultralytics模块类
            torch.serialization.add_safe_globals([conv.Conv])

            # 添加所有Ultralytics模块类
            # 直接添加常用的类
            try:
                # 添加常用的模块类
                from ultralytics.nn.modules.conv import Conv
                torch.serialization.add_safe_globals([Conv])
                logger.info("Successfully added common module classes to safe globals")
            except Exception as e:
                logger.warning(f"Could not add common module classes to safe globals: {e}")

            # 在PyTorch 2.6+中，使用weights_only=False参数代替添加安全全局变量
            logger.info("Using weights_only=False parameter to load models, avoiding safe globals issues")

            logger.info("PyTorch and Ultralytics safe globals added successfully")
        except ImportError as e:
            logger.warning(f"Could not add PyTorch safe globals: {e}")

        # 启动进程监控服务
        process_monitor.start()
        logger.info("Process monitor started")

        # 启动流水线调度器（放在进程监控之后：先把重启前遗留的训练任务收尾，流水线续跑时才能正确判断）
        from app.services.pipeline.orchestrator import orchestrator
        orchestrator.start()

        # 启动TensorBoard服务（需要额外占用一个端口，单端口部署时关闭）
        if not settings.TENSORBOARD_ENABLED:
            logger.info("TensorBoard 已关闭（TENSORBOARD_ENABLED=false），训练曲线请在训练详情中查看")
        elif tensorboard_manager.start():
            logger.info(f"TensorBoard started at {tensorboard_manager.get_url()}")
        else:
            logger.warning("Failed to start TensorBoard service")

        # 启动上传状态清理任务
        start_cleanup()
        logger.info("Upload status cleanup task started")

        log_access_addresses()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")


def _running_in_container() -> bool:
    return os.path.exists("/.dockerenv")


def log_access_addresses():
    """打印访问地址，方便直接复制发给同事。端口用的是实际监听端口（被占用时已自动顺延）"""
    logger.info("=" * 60)
    if settings.PUBLIC_BASE_URL:
        logger.info(f"平台已启动，对外访问地址: {settings.PUBLIC_BASE_URL}")
    elif _running_in_container():
        # 容器内的 IP 和端口对外没有意义，宿主机端口由启动脚本选定
        logger.info(f"平台已启动（容器内监听 {settings.SERVER_PORT}）。宿主机访问端口见 scripts/start.* 的输出或 .app_port")
    else:
        lan_ips = get_lan_ip_addresses()
        logger.info("平台已启动，可通过以下地址访问：")
        for ip in lan_ips:
            logger.info(f"  内网访问: http://{ip}:{settings.SERVER_PORT}")
        logger.info(f"  本机访问: http://localhost:{settings.SERVER_PORT}")
        if not lan_ips:
            logger.warning("未探测到内网 IP，无法打印局域网访问地址")
    logger.info("=" * 60)


# ---------------------------------------------------------------------
# 静态文件鉴权：数据文件必须登录才能访问（判定规则见 app/core/static_access.py）。
# <img>/<a> 加载这些文件时浏览器会自动带上登录 Cookie。
# ---------------------------------------------------------------------
@app.middleware("http")
async def static_auth_middleware(request: Request, call_next):
    path = request.url.path
    if is_static_path(path) and not is_public_static(path):
        token, _ = extract_token(request)
        if not token or not await run_in_threadpool(is_token_valid_for_static, token):
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    return await call_next(request)


# 每个请求一个 request_id：写进响应头 X-Request-ID 和 500 错误体，用户报错时凭它在日志里定位。
# 放在静态鉴权之后注册，Starlette 中后注册的中间件在外层，401 响应也能带上它
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    incoming = request.headers.get("x-request-id", "")
    request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# 跨域：控制台与 API 同源部署，默认不开放任何跨域。
# 原先的 allow_origins=["*"] + allow_credentials=True 会让任意网站带着用户的登录 Cookie 调接口
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

# Mount static files
# follow_symlink：Docker 中数据目录是指向 /data 卷的软链（见 docker/entrypoint.sh），
# Starlette 默认拒绝访问指向目录外的软链
app.mount("/static", StaticFiles(directory="app/static", follow_symlink=True), name="static")

# 添加调试日志
logger.info(f"Static files directory: {os.path.abspath('app/static')}")
logger.info(f"CSS files: {os.listdir('app/static/css')}")
logger.info(f"JS files: {os.listdir('app/static/js')}")

# 错误处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
    )

from app.services.pipeline.service import ServiceError


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    # 控制台接口沿用前端熟悉的 {"detail": ...} 格式，同时带上稳定的错误码
    return JSONResponse(status_code=exc.http_status,
                        content={"detail": exc.message, "code": exc.code, "details": exc.details})


# 记录日志时要去掉的请求头：里面是登录令牌，写进日志等于把账号交给能看日志的人
_SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex
    safe_headers = {k: v for k, v in request.headers.items() if k.lower() not in _SENSITIVE_HEADERS}
    logger.error(f"Unhandled exception [{request_id}]: {exc}", exc_info=True)
    logger.error(f"Request: {request.method} {request.url.path} headers={safe_headers}")

    content = {
        "detail": "Internal server error",
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method,
    }
    # 异常原文可能包含文件路径、SQL、配置等内部信息，只在内部使用时返回给前端便于排查；
    # 对外部署时凭 request_id 到日志里查
    if not settings.EXTERNAL_MODE:
        content["error"] = str(exc)
    return JSONResponse(status_code=500, content=content, headers={"X-Request-ID": request_id})

# 应用关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown")

    # 停止进程监控服务
    process_monitor.stop()

    from app.services.pipeline.orchestrator import orchestrator
    orchestrator.stop()
    logger.info("Process monitor stopped")

    # 停止TensorBoard服务
    if tensorboard_manager.stop():
        logger.info("TensorBoard service stopped")
    else:
        logger.warning("Failed to stop TensorBoard service")

# 对外接口（API Key 鉴权，独立文档 /api/v1/docs）。先于 /api 挂载，路径匹配时优先命中
from app.api.v1 import create_v1_app
app.mount("/api/v1", create_v1_app(), name="api_v1")

# Include API router
app.include_router(api_router, prefix="/api")

# 添加直接访问 CSS 和 JS 文件的路由
@app.get("/css/{file_path:path}", include_in_schema=False)
async def get_css(file_path: str):
    logger.info(f"Accessing CSS file: {file_path}")
    return RedirectResponse(url=f"/static/css/{file_path}")

@app.get("/js/{file_path:path}", include_in_schema=False)
async def get_js(file_path: str):
    logger.info(f"Accessing JS file: {file_path}")
    return RedirectResponse(url=f"/static/js/{file_path}")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    # 已登录（Authorization 头或登录 Cookie）则返回主页面，否则重定向到登录页
    token, _ = extract_token(request)
    if token and await run_in_threadpool(is_token_valid_for_static, token):
        with open("app/static/index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    # 返回登录页面
    try:
        with open("app/static/login.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Error loading login.html: {e}")
        return HTMLResponse(content="<h1>Error loading login page</h1><p>Please check server logs.</p>", status_code=500)


