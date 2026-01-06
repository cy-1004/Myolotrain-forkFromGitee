import os
import shutil
import zipfile
import math
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID
import tempfile
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from PIL import Image

from app.core.config import settings
from app.crud import annotation_project, image_annotation, dataset
from app.models.annotation import AnnotationProject as AnnotationProjectModel, ImageAnnotation as ImageAnnotationModel
from app.schemas.annotation import (
    AnnotationProjectCreate, AnnotationProjectUpdate, ImageAnnotationCreate, 
    BoundingBox, ExportRequest, Annotation, ClassKeypointConfig, ImageAnnotation
)
from app.schemas.dataset import DatasetCreate

class AnnotationService:
    def __init__(self):
        self.annotation_dir = settings.STATIC_DIR / "annotations"
        os.makedirs(self.annotation_dir, exist_ok=True)

    def update_annotation_project(self, db: Session, project_id: UUID, project_update: AnnotationProjectUpdate):
        """更新标注项目"""
        # 获取项目
        project = annotation_project.get(db, id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 保存更新前的类别和数据集ID
        old_classes = project.classes if project.classes is not None else []
        old_dataset_id = project.dataset_id
        
        # 执行更新
        updated_project = annotation_project.update(db, db_obj=project, obj_in=project_update)
        
        # 数据集一旦生成就应保持独立，与在线标注项目解耦
        
        return updated_project

    def create_project(
        self, 
        db: Session, 
        project_data: AnnotationProjectCreate
    ) -> AnnotationProjectModel:
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
            dataset_path = Path(str(db_dataset.path))
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
                    project_id=project_id,
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
    
    def _scan_images(self, db: Session, project: AnnotationProjectModel, image_directory: str):
        """初始扫描图片目录（内部使用）"""
        try:
            # 通过查询获取实际的project数据
            actual_project = db.query(AnnotationProjectModel).filter(AnnotationProjectModel.id == project.id).first()
            if actual_project:
                # 确保获取实际的UUID值
                project_id_value = UUID(str(actual_project.id)) if actual_project.id is not None else UUID(str(project.id))
                self.scan_images(db, project_id_value, image_directory)
        except HTTPException:
            # 如果扫描失败，不抛出异常，只是记录日志
            pass

    def get_project_images(self, db: Session, project_id: UUID) -> List[ImageAnnotationModel]:
        """获取项目的所有图片"""
        return image_annotation.get_by_project_id(db, project_id=project_id)

    def save_annotations(
        self, 
        db: Session, 
        image_id: UUID, 
        annotations: List[Dict[str, Any]]
    ) -> ImageAnnotationModel:
        """保存图片标注"""
        db_image = image_annotation.get(db, id=image_id)
        if not db_image:
            raise HTTPException(
                status_code=404,
                detail="Image annotation not found"
            )
        
        # 直接使用传入的字典格式数据
        annotation_data = annotations
        
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

    def _format_annotation_labels(self, annotations: List[Dict], project_class_keypoints: Optional[List[ClassKeypointConfig]] = None) -> List[str]:
        """格式化标注标签为YOLO格式"""
        label_content = []
        
        for ann in annotations:
            if 'points' in ann and ann.get('points'):
                # 实例分割格式: <class-index> <x1> <y1> <x2> <y2> ... <xn> <yn>
                points_str = []
                if isinstance(ann['points'], list):
                    for point in ann['points']:
                        if isinstance(point, list) and len(point) >= 2:
                            # 归一化坐标
                            points_str.extend([str(point[0]), str(point[1])])
                        elif isinstance(point, (int, float)):
                            # 如果points是扁平化的列表
                            points_str.append(str(point))
                label_content.append(
                    f"{ann['class_id']} {' '.join(points_str)}"
                )
            elif 'angle' in ann:
                # OBB旋转框格式: <class-index> <x1> <y1> <x2> <y2> <x3> <y3> <x4> <y4>
                # 需要将中心点、宽高、角度转换为四个角点坐标
                try:
                    cx, cy = ann['x_center'], ann['y_center']
                    w, h = ann['width'], ann['height']
                    angle = ann['angle']
                    
                    # 计算四个角点的相对坐标（相对于中心点）
                    cos_a, sin_a = math.cos(angle), math.sin(angle)
                    
                    # 未旋转的四个角点（相对于中心点）
                    corners = [
                        (-w/2, -h/2),  # 左上
                        (w/2, -h/2),   # 右上
                        (w/2, h/2),    # 右下
                        (-w/2, h/2)    # 左下
                    ]
                    
                    # 应用旋转并转换为绝对坐标
                    rotated_corners = []
                    for dx, dy in corners:
                        x_rot = dx * cos_a - dy * sin_a + cx
                        y_rot = dx * sin_a + dy * cos_a + cy
                        rotated_corners.extend([x_rot, y_rot])
                    
                    # 格式化为字符串，确保坐标在[0, 1]范围内
                    corner_str = ' '.join([f'{coord:.6f}' for coord in rotated_corners])
                    label_content.append(f"{ann['class_id']} {corner_str}")
                except Exception as e:
                    # 如果转换失败，使用原始格式作为后备
                    label_content.append(
                        f"{ann['class_id']} {ann['x_center']:.6f} {ann['y_center']:.6f} "
                        f"{ann['width']:.6f} {ann['height']:.6f} {ann['angle']:.6f}"
                    )
            elif 'keypoints' in ann and ann.get('keypoints'):
                # 关键点格式: <class-index> <x-center> <y-center> <width> <height> <kpt-x1> <kpt-y1> <kpt-v1> <kpt-x2> <kpt-y2> <kpt-v2> ...
                # 验证关键点数量并补0
                keypoints_str = []
                
                for kp in ann['keypoints']:
                    # 确保关键点坐标已归一化
                    norm_x = kp['x']
                    norm_y = kp['y']
                    visibility = kp['v'] if 'v' in kp else 2
                    keypoints_str.extend([f'{norm_x:.6f}', f'{norm_y:.6f}', str(visibility)])
                
                # 如果提供了关键点配置，验证并补全关键点数量
                if (project_class_keypoints is not None and 
                    ann.get('class_id') is not None and 
                    ann['class_id'] < len(project_class_keypoints)):
                    expected_config = project_class_keypoints[ann['class_id']]
                    # 检查关键点数量配置，支持对象属性和字典键两种形式
                    keypoints_count_value = None
                    if hasattr(expected_config, 'keypoints_count'):
                        keypoints_count_value = getattr(expected_config, 'keypoints_count', None)
                    elif isinstance(expected_config, dict) and 'keypoints_count' in expected_config:
                        keypoints_count_value = expected_config.get('keypoints_count')
                    elif hasattr(expected_config, '__getitem__'):
                        try:
                            keypoints_count_value = expected_config['keypoints_count']
                        except (TypeError, KeyError):
                            pass
                    
                    if (keypoints_count_value is not None and 
                        isinstance(keypoints_count_value, int) and 
                        keypoints_count_value > 0):
                        expected_total_values = keypoints_count_value * 3  # 每个关键点3个值(x,y,v)
                        actual_values = len(keypoints_str)
                        
                        # 如果关键点数量不足，补0
                        # 每个缺失的关键点需要补3个值：x坐标、y坐标和可见性
                        if actual_values < expected_total_values:
                            missing_count = expected_total_values - actual_values
                            # 计算需要补充多少个完整的关键点
                            keypoints_per_missing = 3  # 每个关键点有3个值(x,y,v)
                            missing_keypoints = -(-missing_count // keypoints_per_missing)  # 向上取整
                            
                            # 为每个缺失的关键点补充3个值
                            for i in range(missing_keypoints):
                                remaining_slots = expected_total_values - len(keypoints_str)
                                if remaining_slots >= 3:
                                    # 补充x坐标、y坐标和可见性
                                    keypoints_str.extend(['0.000000', '0.000000', '0'])  # x, y, visibility
                                elif remaining_slots == 2:
                                    # 如果只剩2个槽位，补充x和y坐标
                                    keypoints_str.extend(['0.000000', '0.000000'])
                                elif remaining_slots == 1:
                                    # 如果只剩1个槽位，只补充x坐标
                                    keypoints_str.append('0.000000')
                
                label_content.append(
                    f"{ann['class_id']} {ann['x_center']:.6f} {ann['y_center']:.6f} "
                    f"{ann['width']:.6f} {ann['height']:.6f} {' '.join(keypoints_str)}"
                )
            else:
                # 目标检测格式: <class-index> <x-center> <y-center> <width> <height>
                label_content.append(
                    f"{ann['class_id']} {ann['x_center']:.6f} {ann['y_center']:.6f} "
                    f"{ann['width']:.6f} {ann['height']:.6f}"
                )
        
        return label_content

    def _export_yolo_format(
        self, 
        db: Session, 
        project: AnnotationProjectModel, 
        export_dir: Path, 
        export_request: ExportRequest
    ) -> str:
        """导出YOLO格式"""
        # 通过查询获取实际的project数据
        actual_project = db.query(AnnotationProjectModel).filter(AnnotationProjectModel.id == project.id).first()
        if not actual_project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        project_id_value = UUID(str(actual_project.id)) if actual_project.id is not None else UUID(str(project.id))
        images = image_annotation.get_by_project_id(db, project_id=project_id_value)
        
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
            # 通过查询获取实际的图片数据
            actual_img = db.query(ImageAnnotationModel).filter(ImageAnnotationModel.id == img.id).first()
            if not actual_img:
                continue  # 跳过无效的图片
            img_annotations = actual_img.annotations if actual_img.annotations is not None else []
            img_annotations_value = img_annotations if isinstance(img_annotations, list) else []
            if not img_annotations_value:
                continue
                
            # 创建标签文件
            img_annotations = actual_img.annotations if actual_img.annotations is not None else []
            img_annotations_value = img_annotations if isinstance(img_annotations, list) else []
            project_class_keypoints_value = actual_project.class_keypoints if actual_project.class_keypoints is not None and isinstance(actual_project.class_keypoints, list) else None
            label_content = self._format_annotation_labels(img_annotations_value, project_class_keypoints_value)
            
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
            label_file = target_dir / "labels" / f"{Path(str(actual_img.image_name)).stem}.txt"
            with open(label_file, 'w') as f:
                f.write('\n'.join(label_content))
        
        # 创建classes.txt文件
        project_classes = actual_project.classes if actual_project.classes is not None else []
        project_classes_value = project_classes if isinstance(project_classes, list) else []
        classes_file = export_dir / "classes.txt"
        with open(classes_file, 'w', encoding='utf-8') as f:
            for class_name in project_classes_value:
                f.write(f"{class_name}\n")
        
        # 创建dataset.yaml文件
        project_type = actual_project.project_type if actual_project.project_type is not None else 'detection'
        project_type_value = project_type if project_type is not None else 'detection'
        project_class_keypoints = actual_project.class_keypoints if actual_project.class_keypoints is not None else None
        project_class_keypoints_value = project_class_keypoints if isinstance(project_class_keypoints, list) else None
        
        # 使用相对路径避免中文路径问题，path为当前目录（YAML文件所在目录）
        yaml_content = f"""# YOLO dataset configuration
path: .
train: train/images
val: val/images
test: test/images

# 任务类型: detection, segment, classify, pose, obb
task: {project_type_value}

nc: {len(project_classes_value)}
names: {project_classes_value}"""
        
        # 如果是姿态估计任务，添加关键点信息
        project_type_str = str(project_type_value) if project_type_value is not None else 'detection'
        project_class_keypoints_bool = bool(project_class_keypoints_value) and project_class_keypoints_value is not None
        if project_type_str == "pose" and project_class_keypoints_bool:
            # 计算关键点数量 - 使用用户输入的关键点数量（通常所有类别的关键点数量相同）
            total_keypoints = 0
            all_keypoint_labels = []
            project_class_keypoints_list = project_class_keypoints_value if isinstance(project_class_keypoints_value, list) else []
            project_class_keypoints_safe = project_class_keypoints_list if project_class_keypoints_list is not None else []
            if len(project_class_keypoints_safe) > 0:
                # 在姿态估计任务中，所有类别的关键点数量通常相同
                # 我们获取第一个类别的关键点数量作为标准
                first_class_kp = project_class_keypoints_safe[0]
                # 直接使用用户输入的关键点数量
                # 尝试从对象属性和字典键中获取关键点数量
                keypoints_count_value = None
                
                # 首先尝试获取对象属性
                if hasattr(first_class_kp, 'keypoints_count'):
                    keypoints_count_value = getattr(first_class_kp, 'keypoints_count', None)
                
                # 如果对象属性不存在，尝试从字典中获取（对于序列化对象）
                if keypoints_count_value is None and hasattr(first_class_kp, '__dict__'):
                    if hasattr(first_class_kp, 'keypoints_count'):
                        keypoints_count_value = first_class_kp.keypoints_count
                elif hasattr(first_class_kp, '__getitem__'):
                    try:
                        keypoints_count_value = first_class_kp.get('keypoints_count')
                    except (AttributeError, TypeError):
                        pass
                
                if keypoints_count_value is not None and isinstance(keypoints_count_value, int):
                    total_keypoints = keypoints_count_value  # 这是用户输入的关键点数量
                elif hasattr(first_class_kp, 'keypoints') and first_class_kp.keypoints:
                    keypoints_list = first_class_kp.keypoints if isinstance(first_class_kp.keypoints, list) else []
                    total_keypoints = len(keypoints_list)  # 这是每个实例的关键点数量
                # 获取关键点标签
                if hasattr(first_class_kp, 'keypoints') and first_class_kp.keypoints:
                    keypoints_list = first_class_kp.keypoints if isinstance(first_class_kp.keypoints, list) else []
                    all_keypoint_labels = keypoints_list
            yaml_content += f"""
# 关键点配置
kpt_shape: [{total_keypoints}, 3]  # [关键点数量, 每个关键点的维度(x,y,v)]
flip_idx: []  # 镜像翻转时需要交换的关键点索引
"""

            # 添加关键点标签（如果有的话）
            if all_keypoint_labels:
                yaml_content += f"\nkeypoint_labels: {all_keypoint_labels}"
        
        yaml_file = export_dir / "dataset.yaml"
        with open(yaml_file, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        # 创建ZIP文件
        project_name = actual_project.name if actual_project.name is not None else "project"
        zip_path = export_dir.parent / f"{project_name}_export.zip"
        shutil.make_archive(str(zip_path.with_suffix('')), 'zip', export_dir)
        return str(zip_path)

    def create_project_with_zip(
        self,
        db: Session,
        name: str,
        description: str,
        project_type: str,
        classes: List[str],
        class_keypoints: Optional[List[ClassKeypointConfig]] = None,
        *,  # 使用关键字参数
        zip_file: UploadFile
    ) -> AnnotationProjectModel:
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
                            new_path = images_dir / file_info.filename
                            if old_path.exists() and str(old_path) != str(new_path):
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
            project_type=project_type,
            classes=classes,
            class_keypoints=class_keypoints,
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
        # 获取实际的项目数据
        project = db.query(AnnotationProjectModel).filter(AnnotationProjectModel.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 检查数据集名称是否已存在（只检查数据库记录）
        existing_dataset = dataset.get_by_name(db, name=dataset_name)
        if existing_dataset:
            raise HTTPException(status_code=400, detail="数据集名称已存在")
        
        # 创建数据集目录 - 使用UUID避免中文路径问题
        dataset_uuid = str(uuid.uuid4())
        dataset_dir = settings.STATIC_DIR / "datasets" / dataset_uuid
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
        # 处理SQLAlchemy对象的属性访问
        completed_images = []
        for img in images:
            # 通过查询获取实际的图片数据
            actual_img = db.query(ImageAnnotationModel).filter(ImageAnnotationModel.id == img.id).first()
            if not actual_img:
                continue  # 跳过无效的图片
            img_is_completed = actual_img.is_completed if actual_img.is_completed is not None else False
            img_is_completed_value = bool(img_is_completed)
            img_annotations = actual_img.annotations if actual_img.annotations is not None else []
            img_annotations_value = img_annotations if isinstance(img_annotations, list) and len(img_annotations) > 0 else []
            if img_is_completed_value and img_annotations_value:
                completed_images.append(actual_img)
        
        if not completed_images:
            raise HTTPException(status_code=400, detail="没有已完成的标注数据")
        
        # 处理项目图片目录
        project_image_dir = project.image_directory if project.image_directory is not None else ""
        
        # 复制图片和创建标签
        for img in completed_images:
            # 处理图片路径
            img_image_name = img.image_name if img.image_name is not None else ""
            source_image = Path(str(project_image_dir)) / img_image_name
            if source_image.exists():
                target_image = train_images_dir / img_image_name
                shutil.copy2(source_image, target_image)
                
                # 创建标签文件
                img_annotations = img.annotations if img.annotations is not None else []
                img_annotations_value = img_annotations if isinstance(img_annotations, list) else []
                # 使用项目的class_keypoints配置来验证关键点数量
                project_class_keypoints_value = project.class_keypoints if project.class_keypoints is not None and isinstance(project.class_keypoints, list) else None
                label_content = self._format_annotation_labels(img_annotations_value, project_class_keypoints_value)
                
                label_file = train_labels_dir / f"{Path(str(img.image_name)).stem}.txt"
                with open(label_file, 'w') as f:
                    f.write('\n'.join(label_content))
        
        # 创建 classes.txt
        project_classes = project.classes if project.classes is not None else []
        project_classes_value = project_classes if isinstance(project_classes, list) else []
        classes_file = dataset_dir / "classes.txt"
        with open(classes_file, 'w', encoding='utf-8') as f:
            for cls in project_classes_value:
                f.write(f"{cls}\n")
        
        # 创建 dataset.yaml
        project_type = project.project_type if project.project_type is not None else 'detection'
        project_type_value = project_type if project_type is not None else 'detection'
        
        # 获取关键点配置
        project_class_keypoints = project.class_keypoints if project.class_keypoints is not None else None
        project_class_keypoints_value = project_class_keypoints if isinstance(project_class_keypoints, list) else None
        
        # 使用实际数据集目录路径，确保训练时能找到数据
        yaml_content = f"""path: {str(dataset_dir)}
train: train/images
val: val/images
test: val/images

# 任务类型: detection, segment, classify, pose, obb
task: {project_type_value}

nc: {len(project_classes_value)}
names: {project_classes_value}"""
        
        # 如果是姿态估计任务，添加关键点信息
        project_type_str = str(project_type_value) if project_type_value is not None else 'detection'
        project_class_keypoints_bool = bool(project_class_keypoints_value) and project_class_keypoints_value is not None
        if project_type_str == "pose" and project_class_keypoints_bool:
            # 计算关键点数量 - 使用用户输入的关键点数量（通常所有类别的关键点数量相同）
            total_keypoints = 0
            all_keypoint_labels = []
            project_class_keypoints_list = project_class_keypoints_value if isinstance(project_class_keypoints_value, list) else []
            project_class_keypoints_safe = project_class_keypoints_list if project_class_keypoints_list is not None else []
            if len(project_class_keypoints_safe) > 0:
                # 在姿态估计任务中，所有类别的关键点数量通常相同
                # 我们获取第一个类别的关键点数量作为标准
                first_class_kp = project_class_keypoints_safe[0]
                # 直接使用用户输入的关键点数量
                # 尝试从对象属性和字典键中获取关键点数量
                keypoints_count_value = None
                
                # 首先尝试获取对象属性
                if hasattr(first_class_kp, 'keypoints_count'):
                    keypoints_count_value = getattr(first_class_kp, 'keypoints_count', None)
                
                # 如果对象属性不存在，尝试从字典中获取（对于序列化对象）
                if keypoints_count_value is None and hasattr(first_class_kp, '__dict__'):
                    if hasattr(first_class_kp, 'keypoints_count'):
                        keypoints_count_value = first_class_kp.keypoints_count
                elif hasattr(first_class_kp, '__getitem__'):
                    try:
                        keypoints_count_value = first_class_kp.get('keypoints_count')
                    except (AttributeError, TypeError):
                        pass
                
                if keypoints_count_value is not None and isinstance(keypoints_count_value, int):
                    total_keypoints = keypoints_count_value  # 这是用户输入的关键点数量
                elif hasattr(first_class_kp, 'keypoints') and first_class_kp.keypoints:
                    keypoints_list = first_class_kp.keypoints if isinstance(first_class_kp.keypoints, list) else []
                    total_keypoints = len(keypoints_list)  # 这是每个实例的关键点数量
                # 获取关键点标签
                if hasattr(first_class_kp, 'keypoints') and first_class_kp.keypoints:
                    keypoints_list = first_class_kp.keypoints if isinstance(first_class_kp.keypoints, list) else []
                    all_keypoint_labels = keypoints_list
            yaml_content += f"""
# 关键点配置
kpt_shape: [{total_keypoints}, 3]  # [关键点数量, 每个关键点的维度(x,y,v)]
flip_idx: []  # 镜像翻转时需要交换的关键点索引"""

            # 添加关键点标签（如果有的话）
            if all_keypoint_labels:
                yaml_content += f"\nkeypoint_labels: {all_keypoint_labels}"
        
        yaml_file = dataset_dir / "dataset.yaml"
        with open(yaml_file, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        # 创建数据集记录
        dataset_data = {
            "name": dataset_name,
            "description": dataset_description,
            "classes": project_classes_value,
            "path": str(dataset_dir),
            "image_count": len(completed_images),
            "status": "available",
            "task": project_type_value  # 根据项目类型设置任务类型
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
        import importlib
        try:
            ultralytics_module = importlib.import_module("ultralytics")
            YOLO = getattr(ultralytics_module, "YOLO")
        except ImportError:
            raise HTTPException(status_code=500, detail="YOLO模型库未安装，请安装ultralytics包")
        
        # 获取实际的图片数据
        db_image = db.query(ImageAnnotationModel).filter(ImageAnnotationModel.id == image_id).first()
        if not db_image:
            raise HTTPException(status_code=404, detail="图片未找到")
        
        # 获取项目信息
        project = db.query(AnnotationProjectModel).filter(AnnotationProjectModel.id == db_image.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 构建图片文件路径
        image_path = db_image.image_path if db_image.image_path is not None else ""
        image_path_str = str(image_path) if image_path is not None else ""
        image_name = db_image.image_name if db_image.image_name is not None else ""
        image_name_str = str(image_name) if image_name is not None else ""
        project_image_directory = project.image_directory if project.image_directory is not None else ""
        project_image_directory_str = str(project_image_directory) if project_image_directory is not None else ""

        if image_path_str.startswith('datasets/'):
            image_file_path = Path("app/static") / image_path_str
        elif Path(image_path_str).is_absolute():  # 确保转换为字符串
            image_file_path = Path(image_path_str)
        else:
            image_file_path = Path(project_image_directory_str) / image_name_str
        
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
                        project_classes_value = project_classes if isinstance(project_classes, list) else []
                        if class_id < len(project_classes_value):
                            annotations.append({
                                "class_id": class_id,
                                "x_center": float(x_center),
                                "y_center": float(y_center),
                                "width": float(width),
                                "height": float(height)
                            })
            
            # 更新数据库
            db_image_annotations = db_image.annotations if db_image.annotations is not None else []
            db_image_annotations_value = db_image_annotations if isinstance(db_image_annotations, list) else []
            if overwrite or not db_image_annotations_value:
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
