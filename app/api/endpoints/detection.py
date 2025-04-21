from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.detection_task import DetectionTask
from app.services import detection_service

router = APIRouter()

@router.post("/", response_model=DetectionTask)
async def create_detection_task(
    model_id: str = Form(...),
    file: UploadFile = File(...),
    conf_thres: float = Form(0.25),
    iou_thres: float = Form(0.45),
    db: Session = Depends(get_db)
):
    """
    Create a new detection task
    """
    parameters = {
        "conf_thres": conf_thres,
        "iou_thres": iou_thres
    }

    return await detection_service.create_detection_task(
        db=db,
        model_id=model_id,
        file=file,
        parameters=parameters
    )

@router.get("/", response_model=List[DetectionTask])
def read_detection_tasks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve detection tasks
    """
    tasks = detection_service.get_detection_tasks(db, skip=skip, limit=limit)
    return tasks

@router.get("/{task_id}", response_model=DetectionTask)
def read_detection_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific detection task by id
    """
    task = detection_service.get_detection_task(db, task_id=task_id)
    return task

@router.get("/{task_id}/result")
def get_detection_result(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the detection result for a task
    """
    # 直接从模块中导入函数，避免使用缓存的导入
    from app.services.detection_service import get_detection_result
    return get_detection_result(db, task_id=task_id)
