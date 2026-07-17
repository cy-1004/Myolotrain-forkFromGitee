from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel

# 标注框数据结构
class BoundingBox(BaseModel):
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float

# 旋转框数据结构
class OBBAnnotation(BaseModel):
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float
    angle: float

# 关键点数据结构
class Keypoint(BaseModel):
    x: float
    y: float
    v: int  # 可见性: 0=不可见, 1=模糊, 2=可见

class KeypointsAnnotation(BaseModel):
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float
    keypoints: List[Keypoint]

# 实例分割数据结构
class SegmentationAnnotation(BaseModel):
    class_id: int
    points: List[List[float]]  # [x1, y1, x2, y2, ...] 或 [[x1, y1], [x2, y2], ...]
    x_center: Optional[float] = None
    y_center: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None

# 通用标注数据结构
class Annotation(BaseModel):
    # 共同字段
    class_id: int
    
    # 通用边界框字段
    x_center: Optional[float] = None
    y_center: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    
    # 实例分割字段
    points: Optional[List[Union[List[float], float]]] = None
    
    # 旋转框字段
    angle: Optional[float] = None
    
    # 关键点字段
    keypoints: Optional[List[Keypoint]] = None

# 类别关键点配置
class ClassKeypointConfig(BaseModel):
    class_name: str
    keypoints_count: Optional[int] = None  # 新增关键点数量字段
    keypoints: List[str]

# 标注项目基础模式
class AnnotationProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    classes: List[str]
    class_keypoints: Optional[List[ClassKeypointConfig]] = None  # 类别和关键点的映射关系
    image_directory: Optional[str] = None
    project_type: Optional[str] = "detection"  # detection, segmentation, obb, keypoints

class AnnotationProjectCreate(AnnotationProjectBase):
    dataset_id: Optional[UUID] = None
    import_original_annotations: Optional[bool] = False

class AnnotationProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    classes: Optional[List[str]] = None
    class_keypoints: Optional[List[ClassKeypointConfig]] = None
    project_type: Optional[str] = None
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
    annotations: List[Annotation] = []
    is_completed: bool = False

class ImageAnnotationCreate(ImageAnnotationBase):
    project_id: UUID

class ImageAnnotationUpdate(BaseModel):
    annotations: Optional[List[Annotation]] = None
    is_completed: Optional[bool] = None
    # 乐观锁：带上客户端读到的版本号，与库中不一致说明期间有他人改过，返回 409。
    # 省略则跳过版本校验，此时仅由租约保证互斥（供服务端内部调用）
    expected_version: Optional[int] = None

class ImageAnnotation(ImageAnnotationBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
    version: int = 1
    locked_by: Optional[int] = None
    locked_at: Optional[datetime] = None
    last_edited_by: Optional[int] = None

    class Config:
        from_attributes = True

# 租约持有者信息
class LeaseHolder(BaseModel):
    user_id: int
    username: str
    locked_at: datetime

# 获取/续期租约的响应
class LeaseResponse(BaseModel):
    image_id: UUID
    version: int
    holder: LeaseHolder
    expires_at: datetime

# 认领下一张待标注图片的响应
class NextImageResponse(BaseModel):
    image: Optional[ImageAnnotation] = None
    expires_at: Optional[datetime] = None
    message: Optional[str] = None

# 项目内当前在线标注情况（谁正在标哪张图）
class PresenceEntry(BaseModel):
    image_id: UUID
    image_name: str
    user_id: int
    username: str
    locked_at: datetime

class PresenceResponse(BaseModel):
    entries: List[PresenceEntry] = []

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


class MergeProjectsRequest(BaseModel):
    target_project_name: str
    source_project_ids: List[UUID]
    delete_source_projects: bool = False
    duplicate_handling: str = 'rename'  # rename, overwrite, skip