from typing import List, Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.model import Model
from app.schemas.model import ModelCreate, ModelUpdate

class CRUDModel(CRUDBase[Model, ModelCreate, ModelUpdate]):
    def get_by_name(self, db: Session, *, name: str) -> Optional[Model]:
        return db.query(Model).filter(Model.name == name).first()
    
    def get_by_type(self, db: Session, *, type: str, skip: int = 0, limit: int = 100) -> List[Model]:
        return db.query(Model).filter(Model.type == type).offset(skip).limit(limit).all()
    
    def get_by_task(self, db: Session, *, task: str, skip: int = 0, limit: int = 100) -> List[Model]:
        return db.query(Model).filter(Model.task == task).offset(skip).limit(limit).all()

model = CRUDModel(Model)
