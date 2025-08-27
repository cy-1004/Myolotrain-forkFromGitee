from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.model import Model
from app.services import model_service

router = APIRouter()

@router.post("/", response_model=Model)
async def create_model(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    type: str = Form(...),
    task: str = Form("detect"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Create a new model from a PT file
    """
    return await model_service.create_model(
        db=db, 
        name=name, 
        description=description, 
        type=type,
        task=task,
        file=file
    )

@router.get("/", response_model=List[Model])
def read_models(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve models
    """
    models = model_service.get_models(db, skip=skip, limit=limit)
    return models

@router.get("/{model_id}", response_model=Model)
def read_model(
    model_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific model by id
    """
    model = model_service.get_model(db, model_id=model_id)
    return model

@router.delete("/{model_id}", response_model=Model)
def delete_model(
    model_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a model
    """
    return model_service.delete_model(db, model_id=model_id)

@router.get("/{model_id}/classes")
def get_model_classes(
    model_id: str,
    db: Session = Depends(get_db)
):
    """
    Get model classes
    """
    from ultralytics import YOLO
    from app.crud.crud_model import model
    
    # 获取模型信息
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    
    try:
        # 加载模型获取类别
        yolo_model = YOLO(db_model.path)
        classes = list(yolo_model.names.values())
        
        return {
            "success": True,
            "classes": classes,
            "class_count": len(classes)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型类别失败: {str(e)}")
