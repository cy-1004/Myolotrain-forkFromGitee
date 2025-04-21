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
