from typing import List, Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.detection_task import DetectionTask
from app.schemas.detection_task import DetectionTaskCreate, DetectionTaskUpdate

class CRUDDetectionTask(CRUDBase[DetectionTask, DetectionTaskCreate, DetectionTaskUpdate]):
    def get_by_model_id(self, db: Session, *, model_id: str, skip: int = 0, limit: int = 100) -> List[DetectionTask]:
        return db.query(DetectionTask).filter(DetectionTask.model_id == model_id).offset(skip).limit(limit).all()
    
    def get_by_status(self, db: Session, *, status: str, skip: int = 0, limit: int = 100) -> List[DetectionTask]:
        return db.query(DetectionTask).filter(DetectionTask.status == status).offset(skip).limit(limit).all()
    
    def get_with_model(self, db: Session, *, id: str) -> Optional[DetectionTask]:
        return db.query(DetectionTask).filter(DetectionTask.id == id).first()

detection_task = CRUDDetectionTask(DetectionTask)
