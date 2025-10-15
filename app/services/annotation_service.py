import os
import shutil
import zipfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID
import tempfile

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from PIL import Image

from app.core.config import settings
from app.crud import annotation_project, image_annotation, dataset
from app.models.annotation import AnnotationProject, ImageAnnotation
from app.schemas.annotation import (
    AnnotationProjectCreate, ImageAnnotationCreate, 
    BoundingBox, ExportRequest
)
from app.schemas.dataset import DatasetCreate

class AnnotationService:
    def __init__(self):
        self.annotation_dir = settings.STATIC_DIR / "annotations"
        os.makedirs(self.annotation_dir, exist_ok=True)

    def create_project(
        self, 
        db: Session, 
        project_data: AnnotationProjectCreate
    ) -> AnnotationProject:
        """创建标注项目"""
        # 检查项目名称是否已存在
        existing_project = annotation_project.get_by_name(db, name=project_data.name)
        if existing_project:
            raise HTTPException(
                status_code=400,
                detail="Project with this name already exists"
            )
        
        # 如果关联了数据集，验证数据集是否存在
        if project_data.dataset_id:
            db_dataset = dataset.get(db, id=project_data.dataset_id)
            if not db_dataset:
                raise HTTPException(
                    status_code=404,
                    detail="Dataset not found"
                )
            
            # 使用数据集的图片目录
            dataset_path = Path(db_dataset.path)
            image_directory = str(dataset_path / "train" / "images")
            
            # 创建包含image_directory的新对象
            project_data_dict = project_data.model_dump()
            project_data_dict['image_directory'] = image_directory
            
            # 如果没有指定类别，使用数据集的类别
            if not project_data.classes:
                project_data_dict['classes'] = db_dataset.classes
                
            # 创建项目数据对象
            project_data_for_create = AnnotationProjectCreate(**project_data_dict)
        else:
            # 检查是否提供了图片目录
            if not project_data.image_directory:
                raise HTTPException(
                    status_code=400,
                    detail="Image directory is required when not associating with a dataset"
                )
            
            # 验证图片目录是否存在
            if not os.path.exists(project_data.image_directory):
                raise HTTPException(
                    status_code=404,
                    detail="Image directory not found"
                )
            image_directory = project_data.image_directory
            project_data_for_create = project_data

        # 创建项目
        project = annotation_project.create(db, obj_in=project_data_for_create)
        
        # 扫描图片目录，创建图片记录
        self._scan_images(db, project, image_directory)
        
        return project

    def scan_images(self, db: Session, project_id: UUID, image_directory: str) -> int:
        """扫描图片目录，更新图片标注记录，保留已有标注信息"""
        project = annotation_project.get(db, id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        image_dir = Path(image_directory)
        if not image_dir.exists():
            raise HTTPException(status_code=404, detail="Image directory not found")
        
        # 支持的图片格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        
        # 获取当前目录中的所有图片文件
        current_image_files = []
        for image_file in image_dir.iterdir():
            if image_file.is_file() and image_file.suffix.lower() in image_extensions:
                try:
                    # 尝试获取相对于static目录的路径
                    static_dir = Path("app/static")
                    if static_dir.exists():
                        relative_path = str(image_file.relative_to(static_dir.resolve()))
                    else:
                        # 如果static目录不存在，使用绝对路径
                        relative_path = str(image_file)
                except ValueError:
                    # 如果无法计算相对路径，使用绝对路径
                    relative_path = str(image_file)
                
                current_image_files.append({
                    'path': relative_path,
                    'name': image_file.name
                })
        
        # 获取数据库中已有的图片记录
        existing_images = image_annotation.get_by_project_id(db, project_id=project_id, skip=0, limit=10000)
        existing_image_paths = {img.image_path: img for img in existing_images}
        
        # 处理新增的图片
        for image_info in current_image_files:
            if image_info['path'] not in existing_image_paths:
                # 创建新的图片标注记录
                image_annotation_data = ImageAnnotationCreate(
                    project_id=project.id,
                    image_path=image_info['path'],
                    image_name=image_info['name'],
                    annotations=[],
                    is_completed=False
                )
                image_annotation.create(db, obj_in=image_annotation_data)
        
        # 处理删除的图片
        current_paths = {img['path'] for img in current_image_files}
        for path, img in existing_image_paths.items():
            if path not in current_paths:
                image_annotation.remove(db, id=img.id)
        
        # 提交数据库事务
        db.commit()
        
        return len(current_image_files)
    
    def _scan_images(self, db: Session, project: AnnotationProject, image_directory: str):
        """初始扫描图片目录（内部使用）"""
        try:
            self.scan_images(db, project.id, image_directory)
        except HTTPException:
            # 如果扫描失败，不抛出异常，只是记录日志
            pass

    def get_project_images(self, db: Session, project_id: UUID) -> List[ImageAnnotation]:
        """获取项目的所有图片"""
        return image_annotation.get_by_project_id(db, project_id=project_id)

    def save_annotations(
        self, 
        db: Session, 
        image_id: UUID, 
        annotations: List[BoundingBox]
    ) -> ImageAnnotation:
        """保存图片标注"""
        db_image = image_annotation.get(db, id=image_id)
        if not db_image:
            raise HTTPException(
                status_code=404,
                detail="Image annotation not found"
            )
        
        # 转换为字典格式存储
        annotation_data = [
            {
                "class_id": ann.class_id,
                "x_center": ann.x_center,
                "y_center": ann.y_center,
                "width": ann.width,
                "height": ann.height
            }
            for ann in annotations
        ]
        
        # 更新标注数据
        update_data = {
            "annotations": annotation_data,
            "is_completed": len(annotation_data) > 0
        }
        
        return image_annotation.update(db, db_obj=db_image, obj_in=update_data)

    def export_annotations(
        self, 
        db: Session, 
        project_id: UUID, 
        export_request: ExportRequest
    ) -> str:
        """导出项目标注数据"""
        project = annotation_project.get(db, id=project_id)
        if not project:
            raise HTTPException(
                status_code=404,
                detail="Project not found"
            )
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        export_dir = Path(temp_dir) / f"export_{project_id}"
        os.makedirs(export_dir, exist_ok=True)
        
        try:
            if export_request.format == "yolo":
                return self._export_yolo_format(db, project, export_dir, export_request)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Export format '{export_request.format}' not supported yet"
                )
        except Exception as e:
            # 清理临时目录
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise e

    def _export_yolo_format(
        self, 
        db: Session, 
        project: AnnotationProject, 
        export_dir: Path, 
        export_request: ExportRequest
    ) -> str:
        """导出YOLO格式"""
        # 获取所有图片标注
        images = image_annotation.get_by_project_id(db, project_id=project.id)
        
        # 创建目录结构
        if export_request.split_data:
            train_dir = export_dir / "train"
            val_dir = export_dir / "val"
            test_dir = export_dir / "test"
            
            os.makedirs(train_dir / "images", exist_ok=True)
            os.makedirs(train_dir / "labels", exist_ok=True)
            os.makedirs(val_dir / "images", exist_ok=True)
            os.makedirs(val_dir / "labels", exist_ok=True)
            os.makedirs(test_dir / "images", exist_ok=True)
            os.makedirs(test_dir / "labels", exist_ok=True)
        else:
            os.makedirs(export_dir / "images", exist_ok=True)
            os.makedirs(export_dir / "labels", exist_ok=True)
        
        # 处理每张图片
        for img in images:
            if not img.annotations:
                continue
                
            # 创建标签文件
            label_content = []
            for ann in img.annotations:
                label_content.append(
                    f"{ann['class_id']} {ann['x_center']:.6f} {ann['y_center']:.6f} "
                    f"{ann['width']:.6f} {ann['height']:.6f}"
                )
            
            # 确定目标目录
            if export_request.split_data:
                # 简单分割逻辑（可以改进）
                import random
                rand = random.random()
                if rand < export_request.train_ratio:
                    target_dir = export_dir / "train"
                elif rand < export_request.train_ratio + export_request.val_ratio:
                    target_dir = export_dir / "val"
                else:
                    target_dir = export_dir / "test"
            else:
                target_dir = export_dir
            
            # 写入标签文件
            label_file = target_dir / "labels" / f"{Path(img.image_name).stem}.txt"
            with open(label_file, 'w') as f:
                f.write('\n'.join(label_content))
        
        # 创建classes.txt文件
        classes_file = export_dir / "classes.txt"
        with open(classes_file, 'w', encoding='utf-8') as f:
            for class_name in project.classes:
                f.write(f"{class_name}\n")
        
        # 创建dataset.yaml文件
        yaml_file = export_dir / "dataset.yaml"
        yaml_content = f"""# YOLO dataset configuration
path: {export_dir.name}
train: train/images
val: val/images
test: test/images

nc: {len(project.classes)}
names: {project.classes}
"""
        with open(yaml_file, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        # 创建ZIP文件
        zip_path = export_dir.parent / f"{project.name}_export.zip"
        shutil.make_archive(str(zip_path.with_suffix('')), 'zip', export_dir)
        return str(zip_path)      
    
        # 复制图片文件（如果需要）
        if export_request.include_images:
            source_image = Path(project.image_directory) / img.image_name
        if source_image.exists():
            target_image = target_dir / "images" / img.image_name
            shutil.copy2(source_image, target_image)
        
        # 创建classes.txt
        classes_file = export_dir / "classes.txt"
        with open(classes_file, 'w', encoding='utf-8') as f:
            for cls in project.classes:
                f.write(f"{cls}\n")
        
        # 创建dataset.yaml
        yaml_content = f"""path: {export_dir}
train: {'train/images' if export_request.split_data else 'images'}
val: {'val/images' if export_request.split_data else 'images'}
test: {'test/images' if export_request.split_data else 'images'}
nc: {len(project.classes)}
names: {project.classes}"""
        
        yaml_file = export_dir / "dataset.yaml"
        with open(yaml_file, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        # 创建临时ZIP文件用于下载
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(export_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, export_dir)
                    zipf.write(file_path, arcname)
        
        return temp_zip.name
    
    def create_project_with_zip(
        self,
        db: Session,
        name: str,
        description: str,
        classes: List[str],
        zip_file: UploadFile
    ) -> AnnotationProject:
        """创建标注项目并上传ZIP图片"""
        # 检查项目名称是否已存在
        existing_project = annotation_project.get_by_name(db, name=name)
        if existing_project:
            raise HTTPException(status_code=400, detail="项目名称已存在")
        
        # 创建项目目录
        project_dir = self.annotation_dir / f"project_{name}"
        images_dir = project_dir / "images"
        os.makedirs(images_dir, exist_ok=True)
        
        # 保存并解压ZIP文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            content = zip_file.file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                # 支持的图片格式
                image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
                extracted_count = 0
                
                for file_info in zip_ref.filelist:
                    if not file_info.is_dir():
                        file_path = Path(file_info.filename)
                        if file_path.suffix.lower() in image_extensions:
                            # 提取图片文件
                            zip_ref.extract(file_info, images_dir)
                            # 重命名为简单的文件名
                            old_path = images_dir / file_info.filename
                            new_path = images_dir / file_path.name
                            if old_path != new_path and old_path.exists():
                                os.makedirs(new_path.parent, exist_ok=True)
                                shutil.move(str(old_path), str(new_path))
                                # 清理空目录
                                try:
                                    old_path.parent.rmdir()
                                except OSError:
                                    pass  # 目录不为空或其他错误，忽略
                            extracted_count += 1
                
                if extracted_count == 0:
                    raise HTTPException(status_code=400, detail="ZIP文件中没有找到支持的图片文件")
        
        finally:
            os.unlink(temp_file_path)
        
        # 创建数据库记录
        project_data = AnnotationProjectCreate(
            name=name,
            description=description,
            classes=classes,
            image_directory=str(images_dir)
        )
        
        project = annotation_project.create(db, obj_in=project_data)
        
        # 扫描图片目录
        self._scan_images(db, project, str(images_dir))
        
        return project
    
    def export_to_dataset(
        self,
        db: Session,
        project_id: UUID,
        dataset_name: str,
        dataset_description: str
    ):
        """将标注项目导出为数据集"""
        project = annotation_project.get(db, id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 检查数据集名称是否已存在（只检查数据库记录）
        existing_dataset = dataset.get_by_name(db, name=dataset_name)
        if existing_dataset:
            raise HTTPException(status_code=400, detail="数据集名称已存在")
        
        # 创建数据集目录
        dataset_dir = settings.STATIC_DIR / "datasets" / dataset_name
        # 如果目录存在，先删除
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir)
        
        # 创建目录结构
        train_images_dir = dataset_dir / "train" / "images"
        train_labels_dir = dataset_dir / "train" / "labels"
        os.makedirs(train_images_dir, exist_ok=True)
        os.makedirs(train_labels_dir, exist_ok=True)
        
        # 获取所有已完成的标注
        images = image_annotation.get_by_project_id(db, project_id=project_id)
        completed_images = [img for img in images if img.is_completed and img.annotations]
        
        if not completed_images:
            raise HTTPException(status_code=400, detail="没有已完成的标注数据")
        
        # 复制图片和创建标签
        for img in completed_images:
            # 复制图片
            source_image = Path(project.image_directory) / img.image_name
            if source_image.exists():
                target_image = train_images_dir / img.image_name
                shutil.copy2(source_image, target_image)
                
                # 创建标签文件
                label_content = []
                for ann in img.annotations:
                    label_content.append(
                        f"{ann['class_id']} {ann['x_center']:.6f} {ann['y_center']:.6f} "
                        f"{ann['width']:.6f} {ann['height']:.6f}"
                    )
                
                label_file = train_labels_dir / f"{Path(img.image_name).stem}.txt"
                with open(label_file, 'w') as f:
                    f.write('\n'.join(label_content))
        
        # 创建 classes.txt
        classes_file = dataset_dir / "classes.txt"
        with open(classes_file, 'w', encoding='utf-8') as f:
            for cls in project.classes:
                f.write(f"{cls}\n")
        
        # 创建 dataset.yaml
        yaml_content = f"""path: {dataset_dir}
train: train/images
val: train/images
test: train/images
nc: {len(project.classes)}
names: {project.classes}"""
        
        yaml_file = dataset_dir / "dataset.yaml"
        with open(yaml_file, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        # 创建数据集记录
        dataset_data = {
            "name": dataset_name,
            "description": dataset_description,
            "classes": project.classes,
            "path": str(dataset_dir),
            "image_count": len(completed_images),
            "status": "available"
        }
        
        return dataset.create_with_fields(db, obj_in=dataset_data)
    
    def auto_annotate_image(
        self,
        db: Session,
        image_id: UUID,
        model_path: str,
        project_classes: List[str],
        confidence: float = 0.25,
        iou: float = 0.45,
        overwrite: bool = True
    ) -> List[Dict[str, Any]]:
        """使用AI模型自动标注图片"""
        from ultralytics import YOLO
        import torch
        
        # 获取图片信息
        db_image = image_annotation.get(db, id=image_id)
        if not db_image:
            raise HTTPException(status_code=404, detail="图片未找到")
        
        # 获取项目信息
        project = annotation_project.get(db, id=db_image.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 构建图片文件路径
        if db_image.image_path.startswith('datasets/'):
            image_file_path = Path("app/static") / db_image.image_path
        elif Path(db_image.image_path).is_absolute():
            image_file_path = Path(db_image.image_path)
        else:
            image_file_path = Path(project.image_directory) / db_image.image_name
        
        if not image_file_path.exists():
            raise HTTPException(status_code=404, detail="图片文件不存在")
        
        try:
            # 加载模型
            model = YOLO(model_path)
            
            # 进行推理
            results = model.predict(
                source=str(image_file_path),
                conf=confidence,
                iou=iou,
                verbose=False
            )
            
            # 解析结果
            annotations = []
            if results and len(results) > 0:
                result = results[0]
                if result.boxes is not None:
                    boxes = result.boxes
                    
                    # 获取图片尺寸
                    img_height, img_width = result.orig_shape
                    
                    for i in range(len(boxes)):
                        # 获取边界框坐标 (xyxy 格式)
                        box = boxes.xyxy[i].cpu().numpy()
                        x1, y1, x2, y2 = box
                        
                        # 转换为YOLO格式 (中心点 + 宽高，归一化)
                        x_center = (x1 + x2) / 2 / img_width
                        y_center = (y1 + y2) / 2 / img_height
                        width = (x2 - x1) / img_width
                        height = (y2 - y1) / img_height
                        
                        # 获取类别 ID
                        class_id = int(boxes.cls[i].cpu().numpy())
                        
                        # 检查类别 ID 是否在项目类别范围内
                        if class_id < len(project_classes):
                            annotations.append({
                                "class_id": class_id,
                                "x_center": float(x_center),
                                "y_center": float(y_center),
                                "width": float(width),
                                "height": float(height)
                            })
            
            # 更新数据库
            if overwrite or not db_image.annotations:
                update_data = {
                    "annotations": annotations,
                    "is_completed": len(annotations) > 0
                }
                image_annotation.update(db, db_obj=db_image, obj_in=update_data)
            
            return annotations
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"自动标注失败: {str(e)}"
            )

annotation_service = AnnotationService()