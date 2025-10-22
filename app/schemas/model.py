from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class ModelBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: str
    task: str = "detect"

class ModelCreate(ModelBase):
    path: str
    source: str = "upload"

class ModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    task: Optional[str] = None

class ModelInDBBase(ModelBase):
    id: UUID
    path: str
    created_at: datetime
    updated_at: datetime
    source: str

    class Config:
        from_attributes = True

class Model(ModelInDBBase):
    pass

class ModelInDB(ModelInDBBase):
    pass