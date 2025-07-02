import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import model
from app.models.model import Model
from app.schemas.model import ModelCreate, ModelUpdate

async def create_model(
    db: Session,
    name: str,
    description: Optional[str],
    type: str,
    task: str,
    file: UploadFile
) -> Model:
    """
    Create a new model from an uploaded PT file
    """
    # Check if model with the same name already exists
    db_model = model.get_by_name(db, name=name)
    if db_model:
        raise HTTPException(
            status_code=400,
            detail="名称已经存在",
        )

    # Validate model type
    if type not in settings.YOLO_MODEL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"模型类型无效，必须是： {', '.join(settings.YOLO_MODEL_TYPES)}",
        )

    # Validate task type
    if task not in settings.YOLO_TASK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"任务类型无效，必须是： {', '.join(settings.YOLO_TASK_TYPES)}",
        )

    # Generate unique ID for the model
    model_id = str(uuid.uuid4())
    model_path = settings.MODELS_DIR / f"{model_id}.pt"

    # Save the uploaded file
    with open(model_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Validate model file (basic check)
        if os.path.getsize(model_path) < 1000:  # Arbitrary small size check
            raise HTTPException(
                status_code=400,
                detail="模型文件无效",
            )

        # 创建模型对象
        obj_in_data = {
            "name": name,
            "description": description or "",
            "type": type,
            "task": task,
            "path": str(model_path),  # 设置path字段
            "source": "upload"
        }

        # 直接创建完整的数据库记录
        db_model = model.create_with_fields(db, obj_in=obj_in_data)

        return db_model

    except Exception as e:
        # Clean up in case of error
        if model_path.exists():
            os.remove(model_path)

        raise HTTPException(
            status_code=500,
            detail=f"Error processing model: {str(e)}",
        )

def get_model(db: Session, model_id: str) -> Model:
    """
    Get a model by ID
    """
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(
            status_code=404,
            detail="Model not found",
        )
    return db_model

def get_models(db: Session, skip: int = 0, limit: int = 100) -> List[Model]:
    """
    Get all models
    """
    return model.get_multi(db, skip=skip, limit=limit)

def delete_model(db: Session, model_id: str) -> Model:
    """
    Delete a model

    检查模型是否正在被训练任务使用，如果是，则不允许删除
    删除模型时，同时删除模型文件
    """
    from app.crud import training_task

    # 检查模型是否存在
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(
            status_code=404,
            detail="Model not found",
        )

    # 检查模型是否正在被训练任务使用
    # 检查作为输入模型
    tasks_using_model = training_task.get_by_model_id(db, model_id=model_id)
    if tasks_using_model:
        raise HTTPException(
            status_code=400,
            detail="无法删除模型，因为它正被训练任务使用",
        )

    # 检查作为输出模型
    from app.models.training_task import TrainingTask
    tasks_with_output = db.query(TrainingTask).filter(TrainingTask.output_model_id == model_id).all()
    if tasks_with_output:
        raise HTTPException(
            status_code=400,
            detail="无法删除模型，因为它是训练任务的输出",
        )

    # 检查模型是否正在被检测任务使用
    from app.crud import detection_task
    from app.models.detection_task import DetectionTask

    # 检查检测任务中的模型引用
    detection_tasks_using_model = db.query(DetectionTask).filter(DetectionTask.model_id == model_id).all()
    if detection_tasks_using_model:
        raise HTTPException(
            status_code=400,
            detail="无法删除模型，因为它正被检测任务使用",
        )

    # 删除模型文件
    model_path = Path(db_model.path)
    if model_path.exists():
        try:
            os.remove(model_path)
            print(f"已删除模型文件: {model_path}")
        except Exception as e:
            print(f"删除模型文件失败: {e}")

    # 从数据库中删除模型
    return model.remove(db, id=model_id)
