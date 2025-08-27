from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

class DatasetBase(BaseModel):
    name: str
    description: Optional[str] = None

class DatasetCreate(DatasetBase):
    path: str
    classes: List[str]
    image_count: int = 0

class DatasetUpdate(DatasetBase):
    name: Optional[str] = None

class DatasetInDBBase(DatasetBase):
    id: UUID
    path: str
    classes: List[str]
    image_count: int
    train_count: Optional[int] = None
    val_count: Optional[int] = None
    test_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    status: str

    class Config:
        from_attributes = True

class Dataset(DatasetInDBBase):
    pass

class DatasetInDB(DatasetInDBBase):
    pass
