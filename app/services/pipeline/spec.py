"""流水线任务的请求契约：字段、默认值、校验

对外接口 POST /api/v1/pipeline/jobs 与控制台创建任务共用这一份定义。
创建 Run 时把补全默认值后的配置快照存进 PipelineRun.config，之后修改默认值不影响已有 Run。
"""
from typing import Annotated, Dict, List, Literal, Optional, Tuple
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings

# 类别名、视频 key：会写进 labels.txt、帧文件名，只允许安全字符
SAFE_NAME = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"

WEBHOOK_EVENTS = ("job.started", "job.needs_review", "job.succeeded", "job.failed", "job.cancelled")
DEFAULT_WEBHOOK_EVENTS = ["job.needs_review", "job.succeeded", "job.failed", "job.cancelled"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReferenceSpec(_Strict):
    """一张参考图：multipart 方式用 file 引用 references 字段里上传的文件；JSON 方式用 data_base64 内联"""
    file: Optional[str] = Field(None, max_length=255, description="multipart 方式：references 字段里上传文件的文件名")
    data_base64: Optional[str] = Field(None, max_length=8_000_000,
                                       description="JSON 方式：base64 编码的 JPEG/PNG（可带 data:image/...;base64, 前缀），不超过 5 MB")
    box: Optional[List[float]] = Field(None, min_length=4, max_length=4,
                                       description="可选：物品在图中的像素框 [x1, y1, x2, y2]，给了只用框内部分")

    @model_validator(mode="after")
    def _one_of(self):
        if (self.file is None) == (self.data_base64 is None):
            raise ValueError("参考图必须且只能填写 file 或 data_base64 之一")
        return self


class ClassSpec(_Strict):
    name: str = Field(pattern=SAFE_NAME, description="类别名（英文），顺序即 class_id，会写入 labels.txt")
    display_name: Optional[str] = Field(None, max_length=64, description="展示名，如 玉杯")
    prompt: Optional[str] = Field(None, max_length=300, description="给视觉模型的类别描述，如 玉杯（古代玉质饮器）")
    aliases: List[str] = Field(default_factory=list, max_length=10, description="视觉模型可能返回的其他叫法")
    references: List[ReferenceSpec] = Field(
        default_factory=list, max_length=3,
        description="可选：该文物的参考图（目录照片或清晰的裁剪图）。不提供时系统从视频里自动挑选；"
                    "提供了最可靠，对小件、外观相近的文物尤其有用")


class VideoSpec(_Strict):
    key: Optional[str] = Field(None, pattern=SAFE_NAME, description="视频标识，run 内唯一；不填自动生成 v1、v2……")
    upload_id: Optional[str] = Field(None, description="分片上传得到的 upload_id（JSON 方式创建任务时使用）")
    file: Optional[str] = Field(None, max_length=255, description="multipart 方式创建任务时，对应上传文件的文件名")
    class_name: Optional[str] = Field(None, alias="class", pattern=SAFE_NAME,
                                      description="该视频拍摄的文物类别（只拍了一类时用），必须在 classes 中")
    class_names: Optional[List[Annotated[str, Field(pattern=SAFE_NAME)]]] = Field(
        None, alias="classes", min_length=1, max_length=20,
        description="画面里会出现的多个文物类别（一段视频拍了几件不同文物时用，与 class 二选一）")
    expected_instances: int = Field(1, ge=1, le=10, description="每个声明的类别在同一画面里最多出现几件，通常为 1")
    skip_start: Optional[float] = Field(None, ge=0, le=600)
    skip_end: Optional[float] = Field(None, ge=0, le=600)

    @model_validator(mode="after")
    def _one_of(self):
        if (self.class_name is None) == (self.class_names is None):
            raise ValueError("每个视频必须填写 class（单类）或 classes（多类）之一，且只能填一个")
        if self.class_names is not None:
            self.class_names = list(dict.fromkeys(self.class_names))   # 去重并保持顺序
        return self

    @property
    def declared(self) -> List[str]:
        """该视频声明的类别（单类时只有一个）。标注时只问这些类别：实测比问全部类别精确率高约 15 个百分点"""
        return list(self.class_names) if self.class_names is not None else [self.class_name]


class ExtractConfig(_Strict):
    interval_seconds: float = Field(0.5, ge=0.05, le=30)
    skip_start: float = Field(1.0, ge=0, le=600)
    skip_end: float = Field(1.0, ge=0, le=600)
    max_long_edge: int = Field(1920, ge=320, le=4096, description="抽出的帧长边超过该值时等比缩小")


class CleanConfig(_Strict):
    blur_drop_ratio: float = Field(0.15, ge=0, le=0.9, description="每个视频内按清晰度剔除最模糊的比例")
    min_mean_brightness: float = Field(25, ge=0, le=128)
    max_mean_brightness: float = Field(235, ge=128, le=255)
    max_clipped_ratio: float = Field(0.5, ge=0.05, le=1.0, description="过曝/欠曝像素占比上限")
    dedup_hamming: int = Field(6, ge=0, le=32, description="pHash 汉明距离不超过该值视为近重复，0 关闭去重")
    max_frames_per_video: int = Field(200, ge=10, le=5000)
    min_frames_per_video: int = Field(10, ge=1, le=1000)


class SamGateConfig(_Strict):
    expand_ratio: float = Field(0.02, ge=0, le=0.2)
    min_area_ratio: float = Field(0.6, gt=0, le=1)
    max_area_ratio: float = Field(1.15, ge=1, le=3)
    max_center_shift_ratio: float = Field(0.15, gt=0, le=1)
    min_box_area: float = Field(16, ge=0)


class AnnotateConfig(_Strict):
    provider: Optional[Literal["openrouter", "openai_compatible", "mock"]] = None
    model: Optional[str] = Field(None, max_length=128)
    coord_mode: Literal["auto", "rel1000", "rel1", "abs"] = "auto"
    # recall：真实环境（文物小、杂物多）用，能辨认就标；strict：背景干净的展陈拍摄用，不确定就不标
    prompt_style: Literal["recall", "strict"] = "recall"
    max_long_edge: int = Field(1280, ge=256, le=2048, description="发给视觉模型的图片长边上限，超过时缩小")
    # 小分辨率画面里的小物件只占模型的几个图像块。实测 640x480 的帧放大到 1280 后，配合参考图召回率从 0.42 升到 0.74
    min_long_edge: int = Field(1280, ge=0, le=2048, description="图片长边小于该值时放大后再发给视觉模型，0 不放大")
    # auto：调用方给了参考图就用，没给的类别从视频里自动挑；provided：只用调用方给的；off：不用参考图
    references: Literal["auto", "provided", "off"] = "auto"
    references_per_class: int = Field(1, ge=1, le=3, description="每个类别随请求发送的参考图张数")
    reference_probe_frames: int = Field(48, ge=4, le=96, description="自动挑选参考图时每个类别最多探测的帧数（分轮探测，找到足够大的候选即停）")
    sam_enabled: bool = True
    sam_model: Optional[str] = Field(None, max_length=64)
    sam_gate: SamGateConfig = Field(default_factory=SamGateConfig)
    drop_risk_above: float = Field(0.6, ge=0, le=1, description="未复核时，风险分高于该值的帧不进训练集")
    class_check_frames: int = Field(8, ge=0, le=20, description="视频级类别校验抽查帧数，0 关闭")
    budget_usd: Optional[float] = Field(None, ge=0)


class GateThreshold(_Strict):
    warn: Optional[float] = None
    pause: Optional[float] = None


class GatesConfig(_Strict):
    thresholds: Dict[str, GateThreshold] = Field(default_factory=dict, description="覆盖默认的闸门阈值")


class DatasetConfig(_Strict):
    split: Literal["auto", "by_video", "hybrid", "by_segment"] = "auto"
    ratios: Tuple[float, float, float] = (0.7, 0.15, 0.15)
    min_videos_for_video_split: int = Field(3, ge=2, le=50)
    segment_buffer_seconds: float = Field(2.0, ge=0, le=60)
    seed: int = 0

    @field_validator("ratios")
    @classmethod
    def _ratios(cls, v):
        if any(r <= 0 for r in v) or abs(sum(v) - 1.0) > 1e-6:
            raise ValueError("ratios 必须是三个正数且和为 1，例如 [0.7, 0.15, 0.15]")
        return v


class TrainConfig(_Strict):
    model: str = Field("yolo11n", pattern=SAFE_NAME)
    epochs: int = Field(100, ge=1, le=300)
    imgsz: int = Field(640, ge=160, le=1280)
    batch: int = Field(16, ge=1, le=256)
    patience: int = Field(20, ge=0, le=300)
    # 测试集 mAP50 低于该值时发出质量警告（模型基本没学会）。TFLite 校验只保证"转换没掉精度"，
    # 不保证模型本身可用：训练不充分的模型 PT 和 TFLite 一样差，三道校验照样全部通过
    min_test_map50: float = Field(0.5, ge=0, le=1)
    fail_below_min_map: bool = Field(False, description="为 true 时低于 min_test_map50 直接判任务失败，而不只是警告")

    @field_validator("imgsz")
    @classmethod
    def _imgsz(cls, v):
        if v % 32:
            raise ValueError("imgsz 必须是 32 的倍数（TFLite 输入尺寸固定，训练与导出必须一致）")
        return v


class ExportConfig(_Strict):
    numeric_check_images: int = Field(20, ge=1, le=200)
    max_box_error_px: float = Field(1.0, gt=0)
    max_score_error: float = Field(1e-3, gt=0)
    max_map_drop: float = Field(0.01, ge=0, le=0.5, description="TFLite 相对 PT 的 mAP50-95 允许下降量")


class JobConfig(_Strict):
    extract: ExtractConfig = Field(default_factory=ExtractConfig)
    clean: CleanConfig = Field(default_factory=CleanConfig)
    annotate: AnnotateConfig = Field(default_factory=AnnotateConfig)
    gates: GatesConfig = Field(default_factory=GatesConfig)
    dataset: DatasetConfig = Field(default_factory=DatasetConfig)
    train: TrainConfig = Field(default_factory=TrainConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)


class JobSpec(_Strict):
    name: str = Field(min_length=1, max_length=128)
    external_ref: Optional[str] = Field(None, max_length=128)
    classes: List[ClassSpec] = Field(min_length=1, max_length=100)
    videos: List[VideoSpec] = Field(min_length=1)
    review_mode: Literal["auto", "on_anomaly", "full"] = "on_anomaly"
    callback_url: Optional[str] = Field(None, max_length=2048)
    callback_events: List[str] = Field(default_factory=lambda: list(DEFAULT_WEBHOOK_EVENTS))
    config: JobConfig = Field(default_factory=JobConfig)

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if any(ch in v for ch in '/\\:*?"<>|\0'):
            raise ValueError('name 不能包含 / \\ : * ? " < > | 等字符')
        return v.strip()

    @field_validator("callback_url")
    @classmethod
    def _callback(cls, v):
        if v is None:
            return v
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("callback_url 必须是 http(s) 地址")
        return v

    @field_validator("callback_events")
    @classmethod
    def _events(cls, v):
        unknown = sorted(set(v) - set(WEBHOOK_EVENTS))
        if unknown:
            raise ValueError(f"不支持的 callback_events: {unknown}，可选 {list(WEBHOOK_EVENTS)}")
        return v

    @model_validator(mode="after")
    def _cross_check(self):
        names = [c.name for c in self.classes]
        if len(set(names)) != len(names):
            raise ValueError("classes 中有重复的类别名")
        if self.config.annotate.min_long_edge > self.config.annotate.max_long_edge:
            raise ValueError("annotate.min_long_edge 不能大于 annotate.max_long_edge")
        if len(self.videos) > settings.PIPELINE_MAX_VIDEOS_PER_JOB:
            raise ValueError(f"单个任务最多 {settings.PIPELINE_MAX_VIDEOS_PER_JOB} 个视频")

        used = {v.key for v in self.videos if v.key}
        if len(used) != len([v for v in self.videos if v.key]):
            raise ValueError("videos 中有重复的 key")
        seq = 1
        for v in self.videos:
            if not v.key:
                while f"v{seq}" in used:
                    seq += 1
                v.key = f"v{seq}"
                used.add(v.key)
            unknown = [c for c in v.declared if c not in names]
            if unknown:
                raise ValueError(f"视频 {v.key} 的类别 {unknown} 不在 classes 中")
        missing = [n for n in names if not any(n in v.declared for v in self.videos)]
        if missing:
            raise ValueError(f"类别 {missing} 没有对应的视频，每个类别至少需要一个视频")
        return self


def effective_annotate_provider(cfg: AnnotateConfig) -> Tuple[str, str]:
    """解析实际使用的视觉模型提供方与模型名（请求未指定时取系统配置）"""
    provider = cfg.provider or settings.VLM_PROVIDER
    if provider == "mock":
        return provider, "mock-opencv"   # 不调用任何模型，记录真实的"模型名"，避免排查时误以为用了云端模型
    model = cfg.model or settings.VLM_MODEL
    return provider, model


def validate_runtime_constraints(spec: JobSpec) -> None:
    """依赖系统配置的校验（与请求本身的格式校验分开，错误信息更明确）

    Raises:
        ValueError
    """
    provider, model = effective_annotate_provider(spec.config.annotate)
    if provider == "openrouter":
        if not settings.ALLOW_CLOUD_VLM:
            raise ValueError("系统禁止把图片发送到云端视觉模型（ALLOW_CLOUD_VLM=false），请使用 openai_compatible（本地模型）")
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("未配置 OPENROUTER_API_KEY，无法使用 openrouter 自动标注")
    if provider in ("openrouter", "openai_compatible") and not model:
        raise ValueError("未指定视觉模型（annotate.model 或系统配置 VLM_MODEL）")
