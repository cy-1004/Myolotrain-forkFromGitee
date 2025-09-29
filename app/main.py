import logging
import threading
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError

from app.api.api import api_router
from app.core.config import settings
from app.services.process_monitor import process_monitor
from app.services.tensorboard_service import tensorboard_manager
from app.services.upload_service import start_cleanup
from app.patches.torch_load_patch import apply_patch

# 配置日志
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

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="YOLOv8 Training and Detection Web Platform",
    version="0.1.0",
)

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

        # 启动TensorBoard服务
        if tensorboard_manager.start():
            logger.info(f"TensorBoard started at {tensorboard_manager.get_url()}")
        else:
            logger.warning("Failed to start TensorBoard service")

        # 启动上传状态清理任务
        start_cleanup()
        logger.info("Upload status cleanup task started")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

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

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    logger.error(f"Request path: {request.url.path}")
    logger.error(f"Request method: {request.method}")
    logger.error(f"Request headers: {request.headers}")

    # 返回更详细的错误信息（仅在开发环境中）
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
            "path": request.url.path,
            "method": request.method
        },
    )

# 应用关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown")

    # 停止进程监控服务
    process_monitor.stop()
    logger.info("Process monitor stopped")

    # 停止TensorBoard服务
    if tensorboard_manager.stop():
        logger.info("TensorBoard service stopped")
    else:
        logger.warning("Failed to stop TensorBoard service")

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
async def root():
    # 返回静态HTML文件
    try:
        with open("app/static/index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Error loading index.html: {e}")
        return HTMLResponse(content="<h1>Error loading page</h1><p>Please check server logs.</p>", status_code=500)


