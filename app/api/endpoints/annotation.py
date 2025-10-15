from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from uuid import UUID
from app.db.session import get_db
from app.crud import annotation_project, image_annotation
from app.crud.crud_model import model
from app.schemas.annotation import (
    AnnotationProjectCreate, AnnotationProjectResponse, AnnotationProjectUpdate,
    ImageAnnotationCreate, ImageAnnotation, ImageAnnotationUpdate,
    ProjectStats, ExportRequest
)
from app.services.annotation_service import AnnotationService

router = APIRouter()

@router.get("/test")
def test_annotation():
    """测试标注API"""
    return {"message": "Annotation API is working"}

@router.post("/projects/", response_model=AnnotationProjectResponse)
def create_annotation_project(
    project: AnnotationProjectCreate,
    db: Session = Depends(get_db)
):
    """创建标注项目"""
    service = AnnotationService()
    return service.create_project(db=db, project_data=project)

@router.post("/projects/from-directory", response_model=AnnotationProjectResponse)
def create_project_from_directory(
    name: str = Body(...),
    description: str = Body(""),
    classes: List[str] = Body(...),
    image_directory: str = Body(...),
    db: Session = Depends(get_db)
):
    """从目录创建标注项目"""
    project_data = AnnotationProjectCreate(
        name=name,
        description=description,
        classes=classes,
        image_directory=image_directory
    )
    
    service = AnnotationService()
    return service.create_project(db=db, project_data=project_data)

@router.get("/projects/")
def get_annotation_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取标注项目列表"""
    return annotation_project.get_multi(db, skip=skip, limit=limit)

@router.get("/projects/{project_id}", response_model=AnnotationProjectResponse)
def get_annotation_project(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """获取单个标注项目"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    return project

@router.put("/projects/{project_id}", response_model=AnnotationProjectResponse)
def update_annotation_project(
    project_id: UUID,
    project_update: AnnotationProjectUpdate,
    db: Session = Depends(get_db)
):
    """更新标注项目"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    return annotation_project.update(db, db_obj=project, obj_in=project_update)

@router.delete("/projects/{project_id}")
def delete_annotation_project(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """删除标注项目"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    annotation_project.remove(db, id=project_id)
    return {"message": "项目删除成功"}

@router.get("/projects/{project_id}/stats", response_model=ProjectStats)
def get_project_stats(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """获取项目统计信息"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    return annotation_project.get_project_stats(db, project_id=project_id)

@router.post("/projects/{project_id}/scan")
def scan_project_images(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """扫描项目图片"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    service = AnnotationService()
    count = service.scan_images(db, project_id, project.image_directory)
    return {"message": f"扫描完成，发现 {count} 张图片"}

@router.get("/projects/{project_id}/images")
def get_project_images(
    project_id: UUID,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取项目图片列表"""
    return image_annotation.get_by_project_id(db, project_id=project_id, skip=skip, limit=limit)

@router.get("/images/{image_id}", response_model=ImageAnnotation)
def get_image_annotation(
    image_id: UUID,
    db: Session = Depends(get_db)
):
    """获取图片标注"""
    image = image_annotation.get(db, id=image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片未找到")
    return image

@router.put("/images/{image_id}", response_model=ImageAnnotation)
def update_image_annotation(
    image_id: UUID,
    annotation_update: ImageAnnotationUpdate,
    db: Session = Depends(get_db)
):
    """更新图片标注"""
    image = image_annotation.get(db, id=image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片未找到")
    return image_annotation.update(db, db_obj=image, obj_in=annotation_update)

@router.delete("/images/{image_id}")
def delete_image_annotation(
    image_id: UUID,
    db: Session = Depends(get_db)
):
    """删除图片"""
    image = image_annotation.get(db, id=image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片未找到")
    image_annotation.remove(db, id=image_id)
    return {"message": "图片删除成功"}

@router.post("/projects/{project_id}/export")
def export_annotations(
    project_id: UUID,
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """导出标注数据"""
    from fastapi.responses import FileResponse
    import os
    
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    service = AnnotationService()
    temp_zip_path = service.export_annotations(db, project_id, export_request)
    
    # 返回文件下载响应
    filename = f"{project.name}_export.zip"
    
    # 添加清理任务
    def cleanup_file(file_path: str):
        try:
            os.unlink(file_path)
        except:
            pass
    
    background_tasks.add_task(cleanup_file, temp_zip_path)
    
    return FileResponse(
        path=temp_zip_path,
        filename=filename,
        media_type='application/zip'
    )

@router.post("/projects/upload")
def create_project_with_images(
    name: str = Form(...),
    description: str = Form(""),
    classes: str = Form(...),
    images_zip: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """创建标注项目并上传图片ZIP"""
    import json
    
    try:
        classes_list = json.loads(classes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="类别数据格式错误")
    
    if not images_zip.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="只支持ZIP文件")
    
    service = AnnotationService()
    project = service.create_project_with_zip(
        db=db,
        name=name,
        description=description,
        classes=classes_list,
        zip_file=images_zip
    )
    
    return project

@router.post("/projects/{project_id}/export-to-dataset")
def export_to_dataset(
    project_id: UUID,
    dataset_name: str = Form(...),
    dataset_description: str = Form(""),
    db: Session = Depends(get_db)
):
    """将标注项目导出为数据集"""
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    service = AnnotationService()
    new_dataset = service.export_to_dataset(db, project_id, dataset_name, dataset_description)
    return {"message": "导出为数据集成功", "dataset_id": new_dataset.id}

@router.post("/projects/upload-folder")
def create_project_with_folder(
    name: str = Form(...),
    description: str = Form(""),
    classes: str = Form(...),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """从本地文件夹创建标注项目"""
    import json
    import tempfile
    import zipfile
    
    try:
        classes_list = json.loads(classes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="类别数据格式错误")
    
    # 创建临时ZIP文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for image_file in images:
                # 读取文件内容
                content = image_file.file.read()
                # 将文件添加到ZIP中
                zipf.writestr(image_file.filename, content)
                # 重置文件指针
                image_file.file.seek(0)
        
        temp_zip_path = temp_zip.name
    
    # 使用临时ZIP文件创建项目
    try:
        with open(temp_zip_path, 'rb') as f:
            # 创建UploadFile对象
            zip_upload = UploadFile(filename=f"{name}.zip", file=f)
            
            service = AnnotationService()
            project = service.create_project_with_zip(
                db=db,
                name=name,
                description=description,
                classes=classes_list,
                zip_file=zip_upload
            )
            
            return project
    
    finally:
        # 清理临时文件
        import os
        try:
            os.unlink(temp_zip_path)
        except:
            pass

@router.get("/browse-directories")
def browse_directories(path: str = None):
    """浏览本地目录"""
    import os
    import platform
    from pathlib import Path
    
    # 如果没有提供路径，返回根目录列表
    if not path:
        if platform.system() == "Windows":
            # Windows: 返回所有驱动器
            drives = []
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive_path = f"{letter}:\\"
                if os.path.exists(drive_path):
                    drives.append({
                        "name": f"{letter}:",
                        "path": drive_path,
                        "type": "drive",
                        "is_directory": True
                    })
            return {"items": drives, "current_path": ""}
        else:
            # Linux/Mac: 从根目录开始
            path = "/"
    
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            raise HTTPException(status_code=404, detail="路径不存在")
        
        if not path_obj.is_dir():
            raise HTTPException(status_code=400, detail="不是有效的目录")
        
        items = []
        
        # 添加上级目录（除非是根目录）
        if path_obj.parent != path_obj:
            items.append({
                "name": "..",
                "path": str(path_obj.parent),
                "type": "parent",
                "is_directory": True
            })
        
        # 列出目录内容
        try:
            for item in sorted(path_obj.iterdir()):
                if item.is_dir():
                    items.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory",
                        "is_directory": True
                    })
        except PermissionError:
            raise HTTPException(status_code=403, detail="没有权限访问此目录")
        
        return {
            "items": items,
            "current_path": str(path_obj)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"浏览目录失败: {str(e)}")

@router.get("/scan-directory-images")
def scan_directory_images(directory_path: str):
    """扫描目录中的图片数量"""
    from pathlib import Path
    
    try:
        path_obj = Path(directory_path)
        if not path_obj.exists():
            raise HTTPException(status_code=404, detail="目录不存在")
        
        if not path_obj.is_dir():
            raise HTTPException(status_code=400, detail="不是有效的目录")
        
        # 支持的图片格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.tif'}
        
        image_count = 0
        image_files = []
        
        try:
            for item in path_obj.iterdir():
                if item.is_file() and item.suffix.lower() in image_extensions:
                    image_count += 1
                    image_files.append({
                        "name": item.name,
                        "path": str(item),
                        "size": item.stat().st_size
                    })
                    
                    # 只返回前10个文件作为预览
                    if len(image_files) >= 10:
                        break
        
        except PermissionError:
            raise HTTPException(status_code=403, detail="没有权限访问此目录")
        
        return {
            "directory_path": directory_path,
            "image_count": image_count,
            "sample_images": image_files,
            "is_valid": image_count > 0
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描目录失败: {str(e)}")

@router.get("/projects/{project_id}/images/{image_id}/file")
def get_image_file(
    project_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db)
):
    """获取图片文件"""
    from fastapi.responses import FileResponse
    from pathlib import Path
    
    # 获取项目信息
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    # 获取图片信息
    image = image_annotation.get(db, id=image_id)
    if not image or image.project_id != project_id:
        raise HTTPException(status_code=404, detail="图片未找到")
    
    # 构建图片文件路径
    if image.image_path.startswith('datasets/'):
        # 如果路径已经包含datasets，直接使用
        image_file_path = Path("app/static") / image.image_path
    elif Path(image.image_path).is_absolute():
        # 如果是绝对路径，直接使用
        image_file_path = Path(image.image_path)
    else:
        # 否则使用项目的image_directory
        image_file_path = Path(project.image_directory) / image.image_name
    
    if not image_file_path.exists():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    
    return FileResponse(image_file_path)

@router.post("/images/{image_id}/auto-annotate")
def auto_annotate_image(
    image_id: UUID,
    model_id: str = Body(...),
    confidence: float = Body(0.25),
    iou: float = Body(0.45),
    overwrite: bool = Body(True),
    db: Session = Depends(get_db)
):
    """使用AI模型自动标注图片"""
    from app.services.annotation_service import AnnotationService

    
    # 获取图片信息
    image = image_annotation.get(db, id=image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片未找到")
    
    # 获取模型信息
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    
    # 获取项目信息
    project = annotation_project.get(db, id=image.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    try:
        service = AnnotationService()
        annotations = service.auto_annotate_image(
            db=db,
            image_id=image_id,
            model_path=db_model.path,
            project_classes=project.classes,
            confidence=confidence,
            iou=iou,
            overwrite=overwrite
        )
        
        return {
            "success": True,
            "message": "自动标注完成",
            "annotations": annotations,
            "annotation_count": len(annotations)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自动标注失败: {str(e)}")



@router.post("/projects/{project_id}/mark-all-completed")
def mark_all_completed(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """一键标记所有图片为已完成"""
    # 获取项目信息
    project = annotation_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目未找到")
    
    try:
        # 获取所有图片
        images = image_annotation.get_by_project_id(db, project_id=project_id, skip=0, limit=10000)
        
        # 批量更新
        updated_count = 0
        for img in images:
            if not img.is_completed:
                image_annotation.update(db, db_obj=img, obj_in={"is_completed": True})
                updated_count += 1
        
        return {
            "success": True,
            "message": f"已标记 {updated_count} 张图片为完成",
            "updated_count": updated_count,
            "total_count": len(images)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标记失败: {str(e)}")

