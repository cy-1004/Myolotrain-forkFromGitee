import os
from pathlib import Path
from typing import Any, List, Optional

from pydantic import AnyHttpUrl, PostgresDsn, field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "YOLOv8 Training Platform"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False  # 全局DEBUG模式开关

    # 服务监听端口（首选值）。run.py/start.py 启动时若该端口被占用会自动顺延到下一个，
    # 实际使用的端口会回写到本字段，启动日志打印访问地址时用的就是实际端口
    SERVER_PORT: int = 8000
    # 端口被占用时最多顺延尝试多少个端口（含首选端口），8000 被占就试 8001、8002……
    APP_PORT_MAX_TRIES: int = 20
    # 为 True 时不顺延，首选端口被占用直接报错退出。防火墙/网关已固定端口的环境应打开
    APP_PORT_STRICT: bool = False
    # 开发时的代码热重载。默认关闭：训练任务会在项目目录下生成 .py 脚本，
    # 热重载监听到后会重启服务，把正在跑的训练监控线程一并杀掉
    RELOAD: bool = False

    # 对外部署模式（Docker 镜像默认开启）。开启后：禁用服务器文件系统浏览类接口、
    # 用户传入的路径只能落在数据目录内、SECRET_KEY 必须显式配置、异常信息不回显给客户端
    EXTERNAL_MODE: bool = False
    # 允许跨域访问的来源列表。控制台与 API 同源部署，默认不需要任何跨域；
    # 只有前端单独部署在其他域名时才需要配置，例如 '["https://console.example.com"]'
    CORS_ORIGINS: List[str] = []
    # 对外访问的基础地址，例如 http://10.0.0.5:8001。webhook 等没有请求上下文的地方
    # 需要它来拼绝对链接；留空时只返回相对路径。端口可能因冲突顺延，部署脚本会提示实际端口
    PUBLIC_BASE_URL: str = ""
    # 首次初始化数据库时创建的 admin 账号密码。留空时：对外部署模式随机生成并在日志里打印一次，
    # 本地开发沿用默认密码 admin@123
    ADMIN_INITIAL_PASSWORD: str = ""

    # Security
    # JWT 签名密钥，必须在 .env 中设置。留空时启动会临时随机生成一个，后果是
    # 服务每重启一次全体用户就被登出；多 worker 部署时各 worker 密钥不同，
    # 还会导致令牌在 worker 之间互不认、随机返回 401。
    SECRET_KEY: str = ""
    # 访问令牌有效期。标注员常常整天开着标注页，设太短会被反复弹回登录页，
    # 且平台没有令牌自动续期机制，因此按一个工作日设置。
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "123456"
    POSTGRES_DB: str = "yolov8_platform"
    POSTGRES_PORT: int = 5432
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        if isinstance(v, str):
            return v

        # 从模型中获取值
        values = {}
        for field_name in ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_SERVER", "POSTGRES_DB", "POSTGRES_PORT"]:
            try:
                values[field_name] = info.data.get(field_name)
            except (KeyError, AttributeError):
                values[field_name] = None

        return PostgresDsn.build(
            scheme="postgresql",
            username=values["POSTGRES_USER"],
            password=values["POSTGRES_PASSWORD"],
            host=values["POSTGRES_SERVER"],
            port=values["POSTGRES_PORT"] or 5432,
            path=f"{values['POSTGRES_DB'] or ''}",
            query="client_encoding=utf8"
        )

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STATIC_DIR: Path = BASE_DIR / "app" / "static"
    UPLOADS_DIR: Path = STATIC_DIR / "uploads"
    DATASETS_DIR: Path = STATIC_DIR / "datasets"
    MODELS_DIR: Path = STATIC_DIR / "models"
    RESULTS_DIR: Path = STATIC_DIR / "results"
    TEMP_DIR: Path = STATIC_DIR / "temp"

    # 流水线等新功能的数据根目录。数据库里只存相对它的路径，换机器/进容器时整体搬迁即可。
    # Docker 中为 /data（挂载卷）；本地开发默认是项目下的 data/
    DATA_DIR: Path = BASE_DIR / "data"
    # 预置的基础权重目录（yolo11n.pt、sam2.1_b.pt 等）。训练按模型名到这里找权重，
    # 找不到才会联网下载；离线部署时必须提前放好
    WEIGHTS_DIR: Path = BASE_DIR / "models"
    # 历史数据迁移用：旧环境的项目根目录。数据库里以这些前缀开头的绝对路径，读取时会替换为当前项目根目录。
    # 例：从 Windows 开发机迁到 Docker 时设为 '["C:\\\\workspace\\\\Myolotrain"]'（JSON 数组，反斜杠要转义）
    LEGACY_PATH_PREFIXES: List[str] = []

    # TensorBoard
    # 是否启动 TensorBoard 子进程。它要单独占一个端口（TENSORBOARD_PORT），
    # 与"只开放一个端口"的部署方式冲突，Docker 中默认关闭，训练曲线改由 results.csv 绘制
    TENSORBOARD_ENABLED: bool = True
    TENSORBOARD_LOGS_DIR: Path = BASE_DIR / "logs" / "tensorboard"
    TENSORBOARD_PORT: int = 6006

    # YOLOv8 Settings
    YOLO_MODEL_TYPES: List[str] = ["yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x"]
    YOLO_TASK_TYPES: List[str] = ["detect", "segment", "pose", "obb", "detection", "segmentation", "keypoints"]

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "allow"  # 允许额外的配置项

settings = Settings()

# Create directories if they don't exist
for directory in [
    settings.UPLOADS_DIR,
    settings.DATASETS_DIR,
    settings.MODELS_DIR,
    settings.RESULTS_DIR,
    settings.TENSORBOARD_LOGS_DIR,
    settings.TEMP_DIR,
    settings.DATA_DIR,
]:
    os.makedirs(directory, exist_ok=True)

