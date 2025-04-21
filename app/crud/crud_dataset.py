from typing import List, Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.dataset import Dataset
from app.schemas.dataset import DatasetCreate, DatasetUpdate

class CRUDDataset(CRUDBase[Dataset, DatasetCreate, DatasetUpdate]):
    def get_by_name(self, db: Session, *, name: str) -> Optional[Dataset]:
        return db.query(Dataset).filter(Dataset.name == name).first()
    
    def get_available(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Dataset]:
        return db.query(Dataset).filter(Dataset.status == "available").offset(skip).limit(limit).all()

dataset = CRUDDataset(Dataset)
