from typing import List, Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.training_task import TrainingTask
from app.schemas.training_task import TrainingTaskCreate, TrainingTaskUpdate

class CRUDTrainingTask(CRUDBase[TrainingTask, TrainingTaskCreate, TrainingTaskUpdate]):
    def get_by_dataset_id(self, db: Session, *, dataset_id: str, skip: int = 0, limit: int = 100) -> List[TrainingTask]:
        return db.query(TrainingTask).filter(TrainingTask.dataset_id == dataset_id).offset(skip).limit(limit).all()
    
    def get_by_model_id(self, db: Session, *, model_id: str, skip: int = 0, limit: int = 100) -> List[TrainingTask]:
        return db.query(TrainingTask).filter(TrainingTask.model_id == model_id).offset(skip).limit(limit).all()
    
    def get_by_status(self, db: Session, *, status: str, skip: int = 0, limit: int = 100) -> List[TrainingTask]:
        return db.query(TrainingTask).filter(TrainingTask.status == status).offset(skip).limit(limit).all()
    
    def get_with_relations(self, db: Session, *, id: str) -> Optional[TrainingTask]:
        return db.query(TrainingTask).filter(TrainingTask.id == id).first()

training_task = CRUDTrainingTask(TrainingTask)
