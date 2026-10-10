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

    # ---------------- 文物视频一键训练流水线 ----------------
    # 是否在本进程内运行流水线调度器。以后拆出独立 worker 容器时，Web 容器设为 false
    PIPELINE_WORKER_ENABLED: bool = True
    # 同时执行的 Run 数（训练阶段另有全局 GPU 锁，同一时刻只有一个 Run 在训练）
    PIPELINE_MAX_PARALLEL_RUNS: int = 2
    # 服务重启导致中断后自动续跑的最多次数，超过则判为失败
    PIPELINE_MAX_ATTEMPTS: int = 3
    PIPELINE_MAX_VIDEOS_PER_JOB: int = 50
    PIPELINE_MAX_VIDEO_MB: int = 4096
    PIPELINE_MAX_VIDEO_SECONDS: int = 1800
    # 数据目录剩余空间低于该值时拒绝新任务（返回 507）
    PIPELINE_MIN_FREE_DISK_GB: float = 10.0
    # 分片上传：单片大小、未完成上传的保留时长
    UPLOAD_CHUNK_BYTES: int = 8 * 1024 * 1024
    UPLOAD_EXPIRE_HOURS: int = 24

    # 自动标注用的视觉大模型（OpenAI 兼容接口）
    # openrouter：云端；openai_compatible：本地 llama.cpp / vLLM 等；mock：本地轮廓检测（离线测试用）
    VLM_PROVIDER: str = "openrouter"
    # 在真实文物视频上校准过（tools/calibrate_vlm.py）：235b 配合放大 + 参考图召回 0.72、精确 0.84，约 $0.0004/帧；
    # 30b 同样设置下召回只有约 0.53
    VLM_MODEL: str = "qwen/qwen3-vl-235b-a22b-instruct"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENAI_COMPATIBLE_BASE_URL: str = "http://127.0.0.1:8887/v1"
    OPENAI_COMPATIBLE_API_KEY: str = ""
    VLM_MAX_CONCURRENCY: int = 8   # 235b + 1280 + 参考图单次约 10~15 秒，并发 4 时每分钟只能标约 20 帧
    VLM_TIMEOUT_SECONDS: int = 60
    VLM_MAX_RETRIES: int = 3
    # 管理员总开关：false 时禁止把图片发到云端，只能用 openai_compatible（本地）或 mock
    ALLOW_CLOUD_VLM: bool = True
    # 单个 Run 的 VLM 费用上限（美元），0 表示不限；达到上限时 Run 暂停等待处理
    VLM_BUDGET_PER_RUN_USD: float = 0.0

    # SAM 收框：权重文件名（在 WEIGHTS_DIR 下查找，找不到时自动下载）
    SAM_MODEL: str = "sam2.1_b.pt"

    # webhook：默认禁止回调到内网/本机地址（防 SSRF）。本地化部署回调内网系统时，
    # 把目标主机名或 IP 加进来，例如 '["10.0.0.8", "erp.internal"]'；"*" 表示放行全部内网地址
    WEBHOOK_ALLOWED_HOSTS: List[str] = []
    WEBHOOK_TIMEOUT_SECONDS: int = 10

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

