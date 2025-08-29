from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.crud.base import CRUDBase
from app.models.annotation import AnnotationProject, ImageAnnotation
from app.schemas.annotation import (
    AnnotationProjectCreate, AnnotationProjectUpdate,
    ImageAnnotationCreate, ImageAnnotationUpdate, ProjectStats
)

class CRUDAnnotationProject(CRUDBase[AnnotationProject, AnnotationProjectCreate, AnnotationProjectUpdate]):
    def get_by_name(self, db: Session, *, name: str) -> Optional[AnnotationProject]:
        return db.query(AnnotationProject).filter(AnnotationProject.name == name).first()
    
    def get_by_dataset_id(self, db: Session, *, dataset_id: UUID) -> List[AnnotationProject]:
        return db.query(AnnotationProject).filter(AnnotationProject.dataset_id == dataset_id).all()
    
    def get_project_stats(self, db: Session, *, project_id: UUID) -> ProjectStats:
        """获取项目统计信息"""
        # 获取总图片数
        total_images = db.query(func.count(ImageAnnotation.id)).filter(
            ImageAnnotation.project_id == project_id
        ).scalar() or 0
        
        # 获取已完成图片数
        completed_images = db.query(func.count(ImageAnnotation.id)).filter(
            ImageAnnotation.project_id == project_id,
            ImageAnnotation.is_completed == True
        ).scalar() or 0
        
        # 获取总标注数
        images_with_annotations = db.query(ImageAnnotation).filter(
            ImageAnnotation.project_id == project_id,
            ImageAnnotation.annotations.isnot(None)
        ).all()
        
        total_annotations = 0
        for img in images_with_annotations:
            if img.annotations:
                total_annotations += len(img.annotations)
        
        # 计算进度百分比
        progress_percentage = (completed_images / total_images * 100) if total_images > 0 else 0
        
        return ProjectStats(
            total_images=total_images,
            completed_images=completed_images,
            total_annotations=total_annotations,
            progress_percentage=round(progress_percentage, 2)
        )

class CRUDImageAnnotation(CRUDBase[ImageAnnotation, ImageAnnotationCreate, ImageAnnotationUpdate]):
    def get_by_project_id(self, db: Session, *, project_id: UUID, skip: int = 0, limit: Optional[int] = None) -> List[ImageAnnotation]:
        query = db.query(ImageAnnotation).filter(
            ImageAnnotation.project_id == project_id
        ).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()
    
    def get_by_image_path(self, db: Session, *, project_id: UUID, image_path: str) -> Optional[ImageAnnotation]:
        return db.query(ImageAnnotation).filter(
            ImageAnnotation.project_id == project_id,
            ImageAnnotation.image_path == image_path
        ).first()

annotation_project = CRUDAnnotationProject(AnnotationProject)
image_annotation = CRUDImageAnnotation(ImageAnnotation)