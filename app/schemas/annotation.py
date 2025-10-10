from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel

# 标注框数据结构
class BoundingBox(BaseModel):
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float

# 标注项目基础模式
class AnnotationProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    classes: List[str]
    image_directory: Optional[str] = None

class AnnotationProjectCreate(AnnotationProjectBase):
    dataset_id: Optional[UUID] = None

class AnnotationProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    classes: Optional[List[str]] = None
    status: Optional[str] = None

class AnnotationProject(AnnotationProjectBase):
    id: UUID
    dataset_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    status: str
    
    class Config:
        from_attributes = True

# 响应模式
class AnnotationProjectResponse(AnnotationProject):
    pass

# 图片标注基础模式
class ImageAnnotationBase(BaseModel):
    image_path: str
    image_name: str
    annotations: List[BoundingBox] = []
    is_completed: bool = False

class ImageAnnotationCreate(ImageAnnotationBase):
    project_id: UUID

class ImageAnnotationUpdate(BaseModel):
    annotations: Optional[List[BoundingBox]] = None
    is_completed: Optional[bool] = None

class ImageAnnotation(ImageAnnotationBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 项目统计信息
class ProjectStats(BaseModel):
    total_images: int
    completed_images: int
    total_annotations: int
    progress_percentage: float

# 导出请求
class ExportRequest(BaseModel):
    format: str = "yolo"  # yolo, coco, pascal_voc
    include_images: bool = True
    split_data: bool = False
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15