from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from pathlib import Path
import os
import shutil
import uuid
import json
import zipfile
import subprocess
import platform
import tempfile

from app.db.session import get_db
from app.schemas.dataset import Dataset
from app.services import dataset_service
from app.services.upload_service import upload_manager
from app.crud import dataset
from app.core.config import settings

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

@router.post("/import-coco", response_model=Dataset)
async def import_coco_dataset(
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
    从COCO格式的JSON文件导入数据集
    """
    # 验证文件类型
    if not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=400,
            detail="只接受JSON格式的COCO数据集文件"
        )

    # 调用服务函数处理导入
    return await dataset_service.import_coco_dataset(
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

@router.post("/convert-coco", response_model=Dict[str, Any])
async def convert_coco_json(
    file: UploadFile = File(...),
    split_enabled: bool = Form(True),
    train_ratio: float = Form(0.7),
    val_ratio: float = Form(0.15),
    test_ratio: float = Form(0.15),
    random_seed: int = Form(42)
):
    """
    将COCO格式的JSON文件转换为YOLO格式的标签文件
    """
    # 验证文件类型
    if not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=400,
            detail="只接受JSON格式的COCO数据集文件"
        )

    # 创建临时目录
    temp_dir = Path(settings.TEMP_DIR) / "coco_convert" / str(uuid.uuid4())
    os.makedirs(temp_dir, exist_ok=True)

    # 保存上传的JSON文件
    json_path = temp_dir / "annotations.json"
    with open(json_path, "wb") as f:
        f.write(await file.read())

    try:
        # 创建输出目录结构
        output_dir = temp_dir / "yolo_labels"
        os.makedirs(output_dir, exist_ok=True)

        if split_enabled:
            train_dir = output_dir / "train" / "labels"
            val_dir = output_dir / "val" / "labels"
            test_dir = output_dir / "test" / "labels"
            os.makedirs(train_dir, exist_ok=True)
            os.makedirs(val_dir, exist_ok=True)
            os.makedirs(test_dir, exist_ok=True)

            # 创建图像目录（仅用于说明）
            os.makedirs(output_dir / "train" / "images", exist_ok=True)
            os.makedirs(output_dir / "val" / "images", exist_ok=True)
            os.makedirs(output_dir / "test" / "images", exist_ok=True)
        else:
            labels_dir = output_dir / "labels"
            os.makedirs(labels_dir, exist_ok=True)
            # 创建图像目录（仅用于说明）
            os.makedirs(output_dir / "images", exist_ok=True)

        # 调用转换函数
        result = dataset_service.convert_coco_to_yolo(
            json_path=json_path,
            output_dir=output_dir,
            split_enabled=split_enabled,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            random_seed=random_seed
        )

        # 创建一个README文件，说明如何使用转换后的标签文件
        with open(output_dir / "README.txt", "w", encoding="utf-8") as f:
            f.write("COCO格式转YOLO格式标签文件\n")
            f.write("=======================\n\n")
            f.write("目录结构说明：\n")
            if split_enabled:
                f.write("- train/labels: 训练集标签文件\n")
                f.write("- val/labels: 验证集标签文件\n")
                f.write("- test/labels: 测试集标签文件\n")
                f.write("- train/images: 训练集图像目录（需要手动添加图像）\n")
                f.write("- val/images: 验证集图像目录（需要手动添加图像）\n")
                f.write("- test/images: 测试集图像目录（需要手动添加图像）\n")
            else:
                f.write("- labels: 标签文件\n")
                f.write("- images: 图像目录（需要手动添加图像）\n")
            f.write("\n图像文件名要求：\n")
            f.write("- 图像文件名必须与标签文件名一致（不包括扩展名）\n")
            f.write("- 如果COCO JSON中的文件名包含路径（如'data/image.jpg'），只需使用文件名部分（'image.jpg'）\n")
            f.write("\n类别信息：\n")
            for idx, cls in enumerate(result["classes"]):
                f.write(f"- {idx}: {cls}\n")

        # 创建一个classes.txt文件
        with open(output_dir / "classes.txt", "w", encoding="utf-8") as f:
            for cls in result["classes"]:
                f.write(f"{cls}\n")

        # 创建一个dataset.yaml文件
        with open(output_dir / "dataset.yaml", "w", encoding="utf-8") as f:
            f.write(f"path: {output_dir.absolute()}\n")
            if split_enabled:
                f.write("train: train/images\n")
                f.write("val: val/images\n")
                f.write("test: test/images\n")
            else:
                f.write("train: images\n")
                f.write("val: images\n")
            f.write(f"nc: {len(result['classes'])}\n")
            f.write(f"names: {json.dumps(result['classes'], ensure_ascii=False)}\n")

        # 返回结果
        return {
            "success": True,
            "message": "COCO格式JSON文件已成功转换为YOLO格式标签文件",
            "output_dir": str(output_dir),
            "file_count": result["file_count"],
            "classes": result["classes"],
            "class_count": len(result["classes"]),
            "annotation_count": result["annotation_count"]
        }
    except Exception as e:
        # 发生错误时，删除临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail=f"转换失败: {str(e)}"
        )

@router.post("/open-folder", response_model=Dict[str, Any])
async def open_folder(data: Dict[str, str]):
    """
    打开本地文件夹
    """
    path = data.get("path")
    if not path or not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail="指定的路径不存在"
        )

    try:
        # 根据操作系统打开文件夹
        system = platform.system()
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", path])
        else:  # Linux
            subprocess.Popen(["xdg-open", path])

        return {"success": True, "message": "文件夹已打开"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"打开文件夹失败: {str(e)}"
        )

@router.get("/download-labels-zip")
async def download_labels_zip(path: str):
    """
    将标签文件打包成ZIP文件并提供下载
    """
    if not path or not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail="指定的路径不存在"
        )

    try:
        # 创建临时ZIP文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        temp_file.close()

        # 创建ZIP文件
        with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 遍历目录并添加文件
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 计算相对路径
                    rel_path = os.path.relpath(file_path, path)
                    # 添加到ZIP文件
                    zipf.write(file_path, rel_path)

        # 返回ZIP文件
        response = FileResponse(
            path=temp_file.name,
            filename="yolo_labels.zip",
            media_type="application/zip"
        )

        # 设置一个回调函数，在响应发送后删除临时文件
        async def remove_file():
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                print(f"删除临时文件失败: {str(e)}")

        response.background = remove_file
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"创建ZIP文件失败: {str(e)}"
        )
