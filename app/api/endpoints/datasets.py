from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from pathlib import Path

from app.db.session import get_db
from app.schemas.dataset import Dataset
from app.services import dataset_service
from app.services.upload_service import upload_manager
from app.crud import dataset

router = APIRouter()

class UploadResponse(BaseModel):
    file_id: str
    message: str

class UploadStatusResponse(BaseModel):
    file_id: str
    filename: str
    total_size: int
    uploaded_size: int
    upload_speed: float
    status: str
    progress: int
    message: str
    error: Optional[str] = None
    elapsed_time: float
    estimated_time: float
    result_path: Optional[str] = None

@router.post("/upload-init", response_model=UploadResponse)
async def init_dataset_upload(
    name: str = Form(...),
    file: UploadFile = File(...)
):
    """
    初始化数据集上传，返回文件ID用于跟踪上传状态
    """
    # 创建上传任务
    file_id = upload_manager.create_upload(file.filename, file.size)

    return {
        "file_id": file_id,
        "message": "上传初始化成功，请开始上传文件"
    }

@router.get("/upload-status/{file_id}", response_model=UploadStatusResponse)
async def get_upload_status(file_id: str):
    """
    获取上传状态
    """
    status = upload_manager.get_status(file_id)
    if not status:
        raise HTTPException(status_code=404, detail="上传任务不存在")

    return status

@router.post("/", response_model=Dataset)
async def create_dataset(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    file_id: Optional[str] = Form(None),
    split_dataset_enabled: bool = Form(False),
    train_ratio: float = Form(0.7),
    val_ratio: float = Form(0.15),
    test_ratio: float = Form(0.15),
    random_seed: int = Form(42),
    db: Session = Depends(get_db)
):
    """
    Create a new dataset from a ZIP file
    """
    return await dataset_service.create_dataset(
        db=db,
        name=name,
        description=description,
        file=file,
        file_id=file_id,
        split_dataset_enabled=split_dataset_enabled,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        random_seed=random_seed
    )

@router.get("/", response_model=List[Dataset])
def read_datasets(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve datasets
    """
    datasets = dataset_service.get_datasets(db, skip=skip, limit=limit)
    return datasets

@router.get("/local-available", response_model=List[Dict[str, Any]])
def get_available_local_datasets():
    """
    获取可用的本地数据集目录列表
    """
    return dataset_service.get_available_local_datasets()

@router.get("/directory-info", response_model=Dict[str, Any])
def get_directory_info(name: str):
    """
    获取指定目录的信息
    """
    return dataset_service.get_directory_info(name)

@router.get("/browse-filesystem", response_model=Dict[str, Any])
def browse_filesystem(path: Optional[str] = None):
    """
    浏览本地文件系统
    """
    return dataset_service.browse_filesystem(path)

# 我们使用browse-filesystem API来浏览文件系统

@router.get("/validate-external-directory", response_model=Dict[str, Any])
def validate_external_directory(path: str):
    """
    验证外部数据集目录是否有效
    """
    return dataset_service.validate_external_directory(path)

@router.get("/validate-local-directory", response_model=Dict[str, Any])
def validate_local_directory(path: str):
    """
    验证本地数据集目录是否有效
    """
    return dataset_service.validate_external_directory(path)  # 复用现有的验证函数

@router.post("/register-external", response_model=Dataset)
def register_external_dataset(
    name: str = Body(...),
    description: Optional[str] = Body(None),
    external_path: str = Body(...),
    split_dataset_enabled: bool = Body(False),
    train_ratio: float = Body(0.7),
    val_ratio: float = Body(0.15),
    test_ratio: float = Body(0.15),
    random_seed: int = Body(42),
    db: Session = Depends(get_db)
):
    """
    注册外部数据集目录
    """
    return dataset_service.register_external_dataset(
        db=db,
        name=name,
        description=description,
        external_path=external_path,
        split_dataset_enabled=split_dataset_enabled,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        random_seed=random_seed
    )

@router.get("/{dataset_id}", response_model=Dataset)
def read_dataset(
    dataset_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific dataset by id
    """
    dataset = dataset_service.get_dataset(db, dataset_id=dataset_id)
    return dataset

@router.post("/import-local", response_model=Dataset)
def import_local_dataset(
    name: str = Body(...),
    description: Optional[str] = Body(None),
    directory_name: str = Body(...),
    split_dataset_enabled: bool = Body(False),
    train_ratio: float = Body(0.7),
    val_ratio: float = Body(0.15),
    test_ratio: float = Body(0.15),
    random_seed: int = Body(42),
    db: Session = Depends(get_db)
):
    """
    从本地目录导入数据集
    """
    return dataset_service.import_local_dataset(
        db=db,
        name=name,
        description=description,
        directory_name=directory_name,
        split_dataset_enabled=split_dataset_enabled,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        random_seed=random_seed
    )

@router.post("/import-external", response_model=Dataset)
def import_external_dataset(
    name: str = Body(...),
    description: Optional[str] = Body(None),
    directory_path: str = Body(...),
    split_dataset_enabled: bool = Body(False),
    train_ratio: float = Body(0.7),
    val_ratio: float = Body(0.15),
    test_ratio: float = Body(0.15),
    random_seed: int = Body(42),
    db: Session = Depends(get_db)
):
    """
    从外部目录导入数据集
    """
    return dataset_service.import_external_dataset(
        db=db,
        name=name,
        description=description,
        directory_path=directory_path,
        split_dataset_enabled=split_dataset_enabled,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        random_seed=random_seed
    )

@router.post("/{dataset_id}/split", response_model=Dict[str, Any])
def split_dataset_endpoint(
    dataset_id: str,
    train_ratio: float = Body(0.7),
    val_ratio: float = Body(0.15),
    test_ratio: float = Body(0.15),
    random_seed: int = Body(42),
    mode: str = Body("from_train"),
    db: Session = Depends(get_db)
):
    """
    分割数据集为训练集、验证集和测试集
    """
    # 检查比例总和是否为1
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.001:
        raise HTTPException(
            status_code=400,
            detail="分割比例总和必须为1.0",
        )

    # 获取数据集
    db_dataset = dataset_service.get_dataset(db, dataset_id=dataset_id)

    # 执行分割
    result = dataset_service.split_dataset(
        Path(db_dataset.path),
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        random_seed=random_seed,
        mode=mode
    )

    # 更新数据库中的图像数量
    db_dataset = dataset.update(db, db_obj=db_dataset, obj_in={
        "image_count": result["total"]
    })

    return {
        "success": True,
        "message": "数据集分割成功",
        "result": result
    }

@router.delete("/{dataset_id}", response_model=Dataset)
def delete_dataset(
    dataset_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a dataset
    """
    return dataset_service.delete_dataset(db, dataset_id=dataset_id)
