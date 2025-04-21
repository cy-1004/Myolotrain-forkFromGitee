from datetime import datetime
from typing import Dict, Optional, Any
from uuid import UUID
from pydantic import BaseModel

from app.schemas.model import Model

class DetectionTaskBase(BaseModel):
    model_id: UUID
    parameters: Dict[str, Any]

    model_config = {
        'protected_namespaces': ()
    }

class DetectionTaskCreate(DetectionTaskBase):
    pass

class DetectionTaskUpdate(BaseModel):
    status: Optional[str] = None
    output_path: Optional[str] = None

class DetectionTaskInDBBase(DetectionTaskBase):
    id: UUID
    input_path: str
    output_path: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class DetectionTask(DetectionTaskInDBBase):
    pass

class DetectionTaskWithModel(DetectionTask):
    model: Model

class DetectionTaskInDB(DetectionTaskInDBBase):
    pass
