from datetime import datetime
from typing import Dict, Optional, Any, List
from uuid import UUID
from pydantic import BaseModel

from app.schemas.dataset import Dataset
from app.schemas.model import Model

# 硬件配置模型
class HardwareConfig(BaseModel):
    device_type: str = "cpu"  # "cpu", "gpu" 或 "ascend"
    cpu_cores: Optional[int] = None  # CPU 核心数
    gpu_memory: Optional[int] = None  # GPU 显存（MB）
    gpu_index: Optional[int] = None  # 单个GPU索引
    gpu_indices: Optional[List[int]] = None  # 多个GPU索引
    auto_select_gpu: Optional[bool] = None  # 是否自动选择GPU
    ascend_memory: Optional[int] = None  # 昇腾NPU内存（MB）
    ascend_index: Optional[int] = None  # 昇腾NPU索引
    memory: Optional[int] = None  # 内存（MB）

    model_config = {
        'protected_namespaces': ()
    }

class TrainingTaskBase(BaseModel):
    name: str
    dataset_id: Optional[UUID] = None  # 可选，支持使用本地数据集路径
    model_id: Optional[UUID] = None
    parameters: Dict[str, Any]
    hardware_config: Optional[HardwareConfig] = None

    model_config = {
        'protected_namespaces': ()
    }

class TrainingTaskCreate(TrainingTaskBase):
    pass

class TrainingTaskUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    output_model_id: Optional[UUID] = None
    hardware_config: Optional[HardwareConfig] = None
    last_checkpoint: Optional[str] = None

class TrainingTaskInDBBase(TrainingTaskBase):
    id: UUID
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    log_path: Optional[str] = None
    tensorboard_path: Optional[str] = None
    output_model_id: Optional[UUID] = None
    process_id: Optional[str] = None
    last_checkpoint: Optional[str] = None

    class Config:
        from_attributes = True

class TrainingTask(TrainingTaskInDBBase):
    pass

class TrainingTaskWithRelations(TrainingTask):
    dataset: Optional[Dataset] = None
    model: Optional[Model] = None
    output_model: Optional[Model] = None

class TrainingTaskInDB(TrainingTaskInDBBase):
    pass
