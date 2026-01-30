import os
import shutil
import zipfile
import math
import logging
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
            
            # 创建包含image_directory的新对象，同时保留import_original_annotations
            project_data_dict = project_data.model_dump()
            project_data_dict['image_directory'] = image_directory
            
            # 如果没有指定类别，使用数据集的类别
            if not project_data.classes:
                project_data_dict['classes'] = db_dataset.classes
                
            # 创建项目数据对象，排除import_original_annotations
            import_original_annotations = project_data_dict.pop('import_original_annotations', False)
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
            
            # 提取import_original_annotations并从project_data中排除
            project_data_dict = project_data.model_dump()
            import_original_annotations = project_data_dict.pop('import_original_annotations', False)
            project_data_for_create = AnnotationProjectCreate(**project_data_dict)

        # 创建项目
        project = annotation_project.create(db, obj_in=project_data_for_create)
        
        # 扫描图片目录，创建图片记录
        self._scan_images(db, project, image_directory)
        
        return project

    def create_project_with_import_annotations(
        self, 
        db: Session, 
        project_data: AnnotationProjectCreate
    ) -> Dict:
        """创建标注项目并导入原标注（带统计信息）"""
        # 提取import_original_annotations并从project_data中排除
        import_original_annotations = getattr(project_data, 'import_original_annotations', False)
        
        # 创建项目数据字典，排除import_original_annotations
        project_data_dict = project_data.model_dump()
        project_data_dict.pop('import_original_annotations', None)
        
        # 创建基本项目
        project = self.create_project(db, AnnotationProjectCreate(**project_data_dict))
         
        import_result = None
        if import_original_annotations:
            import_result = self._import_existing_annotations_with_stats(db, project)
        
        # 查询完整的项目信息以确保所有字段都被加载
        actual_project = db.query(AnnotationProjectModel).filter(AnnotationProjectModel.id == project.id).first()
        
        # 构建完整的响应数据，确保所有字段都正确序列化
        result = {
            'id': actual_project.id,
            'name': actual_project.name,
            'description': actual_project.description,
            'dataset_id': actual_project.dataset_id,
            'classes': actual_project.classes,
            'class_keypoints': actual_project.class_keypoints,
            'image_directory': actual_project.image_directory,
            'project_type': actual_project.project_type,
            'import_original_annotations': actual_project.import_original_annotations,
            'created_at': actual_project.created_at,
            'updated_at': actual_project.updated_at,
            'status': actual_project.status,
        }
        if import_result:
            result['import_result'] = import_result
        
        return result

    def _import_existing_annotations_with_stats(self, db: Session, project: AnnotationProjectModel) -> Dict:
        """导入现有标注并返回统计信息"""
        stats = {
            'total_images': 0,
            'matched_annotations': 0, 
            'unannotated_images': 0,
            'errors': []
        }
        
        image_directory = project.image_directory
        if not image_directory:
            return stats
            
        image_dir_path = Path(image_directory)
        if not image_dir_path.exists():
            stats['errors'].append(f"图片目录不存在: {image_directory}")
            return stats
        
        # 获取项目中的所有图片
        all_images = self.get_project_images(db, project.id)
        stats['total_images'] = len(all_images)
        
        # 记录图片信息
        logging.info(f"项目中的图片数量: {len(all_images)}")
        if all_images:
            logging.info(f"前几张图片名称: {[img.image_name for img in all_images[:5]]}")
            logging.info(f"前几张图片的stem: {[Path(img.image_name).stem for img in all_images[:5]]}")
        
        # 查找可能的标注文件目录
        labels_dir = None
        possible_label_dirs = [
            image_dir_path / "labels",
            image_dir_path.parent / "labels",  # 如果是数据集结构
            image_dir_path / "Annotations"  # COCO格式
        ]
        
        for label_dir in possible_label_dirs:
            if label_dir.exists():
                labels_dir = label_dir
                break
        
        if labels_dir is None:
            # 没有找到标注目录，统计所有图片为无标注
            stats['unannotated_images'] = stats['total_images']
            return stats
        
        # 记录标签目录信息
        logging.info(f"标签目录: {labels_dir}")
        logging.info(f"标签目录存在: {labels_dir.exists()}")
        label_files_debug = list(labels_dir.rglob("*.txt"))
        logging.info(f"标签文件数量: {len(label_files_debug)}")
        logging.info(f"标签文件列表: {[f.name for f in label_files_debug][:10]}" if label_files_debug else "无标签文件")
        
        # 统计标注文件 - 使用rglob递归查找所有.txt文件
        label_files = {f.stem: f for f in labels_dir.rglob("*.txt")}
        
        # 记录标签文件信息
        logging.info(f"标签文件字典的keys: {list(label_files.keys())[:10]}" if label_files else "无标签文件")
        logging.info(f"标签文件总数量: {len(label_files)}")
        
        # 用于跟踪处理的标注数量
        total_processed_annotations = 0
        matched_image_count = 0
        
        for img in all_images:
            image_stem = Path(img.image_name).stem
            if image_stem in label_files:
                logging.info(f"检查图片 {img.image_name} (stem: {image_stem}) 与标签文件匹配")  # 仅当匹配时记录
            if image_stem in label_files:
                # 尝试导入此图片的标注
                try:
                    annotations = self._parse_yolo_label_file(str(label_files[image_stem]), project.classes or [], project.project_type or 'detection')
                    if annotations:
                        # 保存标注到数据库
                        self.save_annotations(db, img.id, annotations)
                        total_processed_annotations += len(annotations)
                        matched_image_count += 1  # 每张匹配到标注的图片计数
                    else:
                        stats['unannotated_images'] += 1
                except Exception as e:
                    stats['errors'].append(f"处理 {img.image_name} 的标注时出错: {str(e)}")
                    stats['unannotated_images'] += 1
            else:
                stats['unannotated_images'] += 1
        
        # 更新统计信息
        stats['matched_annotations'] = total_processed_annotations
        stats['matched_image_count'] = matched_image_count
        
        return stats

    def _parse_yolo_label_file(self, label_file_path: str, classes: List[str], project_type: str = 'detection') -> List[Dict]:
        """解析YOLO格式的标签文件，严格按照用户选择的项目类型"""
        annotations = []
        if not os.path.exists(label_file_path):
            return annotations
        
        with open(label_file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split()
                if len(parts) < 1:  # 至少要有class_id
                    continue
                
                try:
                    class_id = int(parts[0])
                    if class_id >= len(classes):
                        continue
                    
                    # 按照项目类型处理
                    if project_type == 'segmentation':
                        # 实例分割：使用所有剩余的数值作为points（展平的坐标数组）
                        values = []
                        for i in range(1, len(parts)):
                            try:
                                values.append(float(parts[i]))
                            except ValueError:
                                continue
                        
                        # 计算边界框（从展平的坐标数组中计算）
                        x_coords = []
                        y_coords = []
                        for i in range(0, len(values), 2):
                            if i + 1 < len(values):
                                x_coords.append(values[i])
                                y_coords.append(values[i + 1])
                        
                        if x_coords and y_coords:
                            x_min, x_max = min(x_coords), max(x_coords)
                            y_min, y_max = min(y_coords), max(y_coords)
                            x_center = (x_min + x_max) / 2
                            y_center = (y_min + y_max) / 2
                            width = x_max - x_min
                            height = y_max - y_min
                        else:
                            x_center, y_center, width, height = 0.5, 0.5, 0.1, 0.1
                        
                        # 将展平的坐标数组转换为嵌套列表格式 [[x1, y1], [x2, y2], ...]
                        points_list = []
                        for i in range(0, len(values), 2):
                            if i + 1 < len(values):
                                points_list.append([values[i], values[i+1]])
                        
                        annotations.append({
                            "class_id": class_id,
                            "x_center": x_center,
                            "y_center": y_center,
                            "width": width,
                            "height": height,
                            "points": points_list  # 使用嵌套列表格式 [[x,y], [x,y], ...]，与auto_annotate_image保持一致
                        })
                    elif project_type == 'obb':
                        # OBB旋转框：支持两种格式
                        # 格式1: class x1 y1 x2 y2 x3 y3 x4 y4 (YOLOv8标准格式)
                        # 格式2: class xc yc w h angle (旧格式)
                        
                        # 首先尝试解析为YOLOv8标准格式（8个坐标点）
                        if len(parts) >= 9:  # 至少有class + 8个坐标点
                            try:
                                coords = [float(p) for p in parts[1:9]]  # 提取8个坐标点
                                
                                # 计算边界框中心和尺寸（从4个角点计算）
                                x_coords = coords[::2]  # x1, x3, x5, x7 (奇数索引)
                                y_coords = coords[1::2]  # y2, y4, y6, y8 (偶数索引)
                                
                                x_center = sum(x_coords) / 4
                                y_center = sum(y_coords) / 4
                                width = max(x_coords) - min(x_coords)
                                height = max(y_coords) - min(y_coords)
                                
                                # 计算角度（使用第一个边的角度作为近似）
                                x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]
                                import math
                                angle = math.atan2(y2 - y1, x2 - x1)
                                
                                annotations.append({
                                    "class_id": class_id,
                                    "x_center": x_center,
                                    "y_center": y_center,
                                    "width": width,
                                    "height": height,
                                    "angle": angle
                                })
                            except ValueError:
                                # 如果解析失败，使用默认值
                                annotations.append({
                                    "class_id": class_id,
                                    "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1, "angle": 0.0
                                })
                        elif len(parts) >= 6:  # 旧格式: class xc yc w h angle
                            try:
                                x_center = float(parts[1])
                                y_center = float(parts[2])
                                width = float(parts[3])
                                height = float(parts[4])
                                angle = float(parts[5])
                                
                                annotations.append({
                                    "class_id": class_id,
                                    "x_center": x_center,
                                    "y_center": y_center,
                                    "width": width,
                                    "height": height,
                                    "angle": angle
                                })
                            except ValueError:
                                # 如果解析失败，使用默认值
                                annotations.append({
                                    "class_id": class_id,
                                    "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1, "angle": 0.0
                                })
                        else:
                            # 如果数值不足，使用默认值
                            annotations.append({
                                "class_id": class_id,
                                "x_center": 0.5, "y_center": 0.5, "width": 0.1, "height": 0.1, "angle": 0.0
                            })
                    elif project_type == 'pose':
                        # 关键点姿态估计：格式为 class x_center y_center width height x1 y1 v1 x2 y2 v2 ...
                        if len(parts) >= 5:
                            try:
                                x_center = float(parts[1])
                                y_center = float(parts[2])
                                width = float(parts[3])
                                height = float(parts[4])
                                
                                # 从第5个值开始解析关键点 (每3个值为一组 x,y,v)
                                keypoints = []
                                for i in range(5, len(parts), 3):
                                    if i + 2 < len(parts):
                                        try:
                                            kp_x = float(parts[i])
                                            kp_y = float(parts[i+1])
                                            kp_v = int(float(parts[i+2]))  # visibility 通常是整数
                                            keypoints.append({"x": kp_x, "y": kp_y, "v": kp_v})
                                        except ValueError:
                                            continue
                            except ValueError:
                                # 如果转换失败，使用默认值
                                x_center, y_center, width, height = 0.5, 0.5, 0.1, 0.1
                                keypoints = []
                        else:
                            # 如果数值不足，使用默认值
                            x_center, y_center, width, height = 0.5, 0.5, 0.1, 0.1
                            keypoints = []
                        
                        annotations.append({
                            "class_id": class_id,
                            "x_center": x_center,
                            "y_center": y_center,
                            "width": width,
                            "height": height,
                            "keypoints": keypoints
                        })
                    else:  # 默认为 'detection' (目标检测)
                        # 目标检测：需要5个值（class, x_center, y_center, width, height）
                        if len(parts) >= 5:
                            try:
                                x_center = float(parts[1])
                                y_center = float(parts[2])
                                width = float(parts[3])
                                height = float(parts[4])
                            except ValueError:
                                # 如果转换失败，使用默认值
                                x_center, y_center, width, height = 0.5, 0.5, 0.1, 0.1
                        else:
                            # 如果数值不足，使用默认值
                            x_center, y_center, width, height = 0.5, 0.5, 0.1, 0.1
                        
                        annotations.append({
                            "class_id": class_id,
                            "x_center": x_center,
                            "y_center": y_center,
                            "width": width,
                            "height": height
                        })
                except ValueError:
                    continue
        
        return annotations

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
        
        # 获取当前目录及其子目录中的所有图片文件（递归搜索）
        current_image_files = []
        logging.info(f"scan_images: 搜索图片目录 {image_dir}, 目录存在: {image_dir.exists()}")
        if image_dir.exists():
            all_files = list(image_dir.rglob('*'))
            logging.info(f"scan_images: 目录中所有文件: {[f.name for f in all_files][:10]}")
            image_files_found = []
            for image_file in all_files:
                if image_file.is_file() and image_file.suffix.lower() in image_extensions:
                    image_files_found.append(image_file.name)
                    # 对于ZIP上传的图片，直接使用文件名作为路径，让get_image_file函数使用project.image_directory + image_name来构建路径
                    # 这样可以确保路径一致性
                    relative_path = str(image_file.name)
                    
                    current_image_files.append({
                        'path': relative_path,
                        'name': image_file.name
                    })
            logging.info(f"scan_images: 找到 {len(image_files_found)} 个图片文件: {image_files_found[:5]}")
        else:
            logging.info(f"scan_images: 目录不存在!")
        
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
            # 直接使用传入的project对象的id，因为此时project刚创建并已持久化
            project_id_value = UUID(str(project.id))
            self.scan_images(db, project_id_value, image_directory)
        except HTTPException:
            # 如果扫描失败，不抛出异常，只是记录日志
            pass
        except Exception as e:
            # 记录其他类型的异常
            logging.error(f"扫描图片目录时发生错误: {str(e)}")
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
        
        # 获取所有图片及其标注，避免N+1查询
        # 注意：annotations是普通列（JSON字段），不是关系，所以不需要使用joinedload
        images = db.query(ImageAnnotationModel).filter(
            ImageAnnotationModel.project_id == project_id_value
        ).all()
        
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
        project_class_keypoints_value = actual_project.class_keypoints if actual_project.class_keypoints is not None and isinstance(actual_project.class_keypoints, list) else None
        for actual_img in images:
            # 直接使用预加载的标注数据，避免再次查询
            img_annotations_value = actual_img.annotations if actual_img.annotations is not None else []
            img_annotations_value = img_annotations_value if isinstance(img_annotations_value, list) else []
            if not img_annotations_value:
                continue
                
            # 创建标签文件
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
        
        # 映射数据库中的项目类型到YOLO官方支持的task名称
        task_mapping = {
            'detection': 'detect',
            'segmentation': 'segment',
            'obb': 'obb',
            'pose': 'pose',
            'classification': 'classify'
        }
        yolo_task = task_mapping.get(project_type_value, 'detect')
        
        # 使用相对路径避免中文路径问题，path为当前目录（YAML文件所在目录）
        yaml_content = f"""# YOLO dataset configuration
path: .
train: train/images
val: val/images
test: test/images

# 任务类型: detection, segment, classify, pose, obb
task: {yolo_task}

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

    def create_project_with_zip_and_import(
        self,
        db: Session,
        name: str,
        description: str,
        project_type: str,
        classes: List[str],
        class_keypoints: Optional[List[ClassKeypointConfig]] = None,
        import_original_annotations: bool = False,
        *,  # 使用关键字参数
        zip_file: UploadFile
    ) -> Dict:
        """创建标注项目并上传ZIP图片，支持导入原标注"""
        # 检查项目名称是否已存在
        existing_project = annotation_project.get_by_name(db, name=name)
        if existing_project:
            raise HTTPException(status_code=400, detail="项目名称已存在")
        
        # 创建项目目录 - 使用原有路径结构避免路径问题
        project_uuid = str(uuid.uuid4())
        project_dir = self.annotation_dir / f"project_{name}_{project_uuid}"
        images_dir = project_dir / "images"
        labels_dir = project_dir / "labels"  # 为导入的标注创建labels目录
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)
        
        # 保存并解压ZIP文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            content = zip_file.file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # 用于追踪导入统计的变量
        extracted_images_count = 0
        extracted_labels_count = 0
        parsed_classes = []
        
        try:
            with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                # 支持的图片格式
                image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
                label_extensions = {'.txt'}  # 标注文件格式
                
                # 首先检查ZIP中的顶级目录结构
                root_items = set()
                for file_info in zip_ref.filelist:
                    if not file_info.is_dir():
                        file_path = Path(file_info.filename)
                        # 获取顶级目录或文件
                        if len(file_path.parts) > 0:
                            root_items.add(file_path.parts[0])
                    else:
                        dir_path = Path(file_info.filename)
                        if len(dir_path.parts) > 0:
                            root_items.add(dir_path.parts[0])
                
                # 检查是否是用户提到的标准结构（images、labels、classes.txt）
                has_standard_structure = (
                    'images' in root_items or 'Images' in root_items or 
                    'img' in root_items or 'IMG' in root_items
                ) and (
                    'labels' in root_items or 'Labels' in root_items or 
                    'ann' in root_items or 'Ann' in root_items
                )
                
                for file_info in zip_ref.filelist:
                    if not file_info.is_dir():
                        file_path = Path(file_info.filename)
                        
                        if file_path.name.lower() == 'classes.txt':
                            # 提取classes.txt文件内容
                            with zip_ref.open(file_info) as f:
                                content = f.read().decode('utf-8')
                                parsed_classes = [line.strip() for line in content.splitlines() if line.strip()]
                            
                        elif has_standard_structure:
                            # 如果是标准结构，根据目录分类处理
                            if file_path.parts[0] in ['images', 'Images', 'img', 'IMG']:
                                # 提取到images目录，但要去掉顶级目录前缀
                                # 获取去掉顶级目录的相对路径
                                relative_path = Path(*file_path.parts[1:])  # 去掉第一个部分（images/）
                                if relative_path:  # 确保有剩余路径
                                    target_path = images_dir / relative_path
                                    # 确保目标目录存在
                                    target_path.parent.mkdir(parents=True, exist_ok=True)
                                    # 提取文件到目标路径
                                    with zip_ref.open(file_info) as source:
                                        with open(target_path, 'wb') as target:
                                            target.write(source.read())
                                else:
                                    # 如果没有剩余路径（即顶级目录本身），跳过
                                    pass
                                extracted_images_count += 1
                            elif file_path.parts[0] in ['labels', 'Labels', 'ann', 'Ann']:
                                # 提取到labels目录，但要去掉顶级目录前缀
                                relative_path = Path(*file_path.parts[1:])  # 去掉第一个部分（labels/）
                                if relative_path:  # 确保有剩余路径
                                    target_path = labels_dir / relative_path
                                    # 确保目标目录存在
                                    target_path.parent.mkdir(parents=True, exist_ok=True)
                                    # 提取文件到目标路径
                                    with zip_ref.open(file_info) as source:
                                        with open(target_path, 'wb') as target:
                                            target.write(source.read())
                                else:
                                    # 如果没有剩余路径（即顶级目录本身），跳过
                                    pass
                                extracted_labels_count += 1
                            elif file_path.suffix.lower() in image_extensions:
                                # 如果不在标准目录中，但扩展名是图片，也提取到images目录
                                zip_ref.extract(file_info, images_dir)
                                extracted_images_count += 1
                            elif file_path.suffix.lower() in label_extensions:
                                # 如果不在标准目录中，但扩展名是标签，也提取到labels目录
                                if import_original_annotations:
                                    zip_ref.extract(file_info, labels_dir)
                                    extracted_labels_count += 1
                        else:
                            # 如果不是标准结构，按扩展名分类
                            if file_path.suffix.lower() in image_extensions:
                                # 提取图片文件到images目录
                                zip_ref.extract(file_info, images_dir)
                                extracted_images_count += 1
                            elif file_path.suffix.lower() in label_extensions:
                                # 如果开启了导入原标注，提取标注文件到labels目录
                                if import_original_annotations:
                                    zip_ref.extract(file_info, labels_dir)
                                    extracted_labels_count += 1
        
        finally:
            os.unlink(temp_file_path)
        
        if extracted_images_count == 0:
            raise HTTPException(status_code=400, detail="ZIP文件中没有找到支持的图片文件")
        
        # 记录导入统计信息
        logging.info(f"解压了 {extracted_images_count} 张图片到 {images_dir}")
        logging.info(f"解压了 {extracted_labels_count} 个标签文件到 {labels_dir}")
        logging.info(f"images_dir 存在: {images_dir.exists()}, 内容: {[f.name for f in images_dir.iterdir()][:5] if images_dir.exists() else 'NOT EXISTS'}")
        logging.info(f"labels_dir 存在: {labels_dir.exists()}, 内容: {[f.name for f in labels_dir.iterdir()][:5] if labels_dir.exists() else 'NOT EXISTS'}")
        
        # 如果启用了导入原标注并且解析到了classes，使用解析到的classes
        final_classes = classes
        if import_original_annotations and parsed_classes:
            final_classes = parsed_classes
        
        # 创建数据库记录
        project_data_dict = {
            'name': name,
            'description': description,
            'project_type': project_type,
            'classes': final_classes,
            'class_keypoints': class_keypoints,
            'image_directory': str(images_dir),
        }
        
        # 创建项目
        project = annotation_project.create(db, obj_in=project_data_dict)
        
        # 设置导入原标注标识用于后续处理
        project.import_original_annotations = import_original_annotations
        
        # 扫描图片目录
        logging.info(f"开始扫描图片目录 {str(images_dir)}")
        self._scan_images(db, project, str(images_dir))
        
        # 如果开启了导入原标注，执行导入
        import_result = None
        if import_original_annotations:
            import_result = self._import_existing_annotations_with_stats(db, project)
            # 添加解析的类别到结果中
            if import_result and parsed_classes:
                import_result['parsed_classes'] = parsed_classes
        
        # 查询完整的项目信息以确保所有字段都被加载
        from sqlalchemy import inspect
        actual_project = db.query(AnnotationProjectModel).filter(AnnotationProjectModel.id == project.id).first()
        
        # 将项目对象转换为字典，确保所有字段都被正确序列化
        result = {
            'id': actual_project.id,
            'name': actual_project.name,
            'description': actual_project.description,
            'dataset_id': actual_project.dataset_id,
            'classes': actual_project.classes,
            'class_keypoints': actual_project.class_keypoints,
            'image_directory': actual_project.image_directory,
            'project_type': actual_project.project_type,
            'import_original_annotations': actual_project.import_original_annotations,
            'created_at': actual_project.created_at,
            'updated_at': actual_project.updated_at,
            'status': actual_project.status,
        }
        
        if import_result:
            result['import_result'] = import_result
        
        return result

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
        
        # 防止路径穿越攻击：使用Path.resolve()规范化路径
        from app.core.config import settings
        static_dir = settings.STATIC_DIR
        
        if image_path_str.startswith('datasets/'):
            image_file_path = Path("app/static") / image_path_str
        elif Path(image_path_str).is_absolute():  # 确保转换为字符串
            image_file_path = Path(image_path_str)
        else:
            image_file_path = Path(project_image_directory_str) / image_name_str
        
        # 规范化路径并验证其在允许的目录范围内
        resolved_path = image_file_path.resolve()
        static_dir_resolved = static_dir.resolve()
        
        # 检查路径是否在静态目录范围内
        try:
            resolved_path.relative_to(static_dir_resolved)
        except ValueError:
            raise HTTPException(status_code=400, detail="非法路径访问")
        
        if not resolved_path.exists():
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
                
                # 如果是实例分割项目，尝试使用YOLO+SAM3结合的方式
                if project.project_type == 'segmentation':
                    # 尝试导入SAM模块
                    try:
                        # 1. 引用 sam3.py 中的共享资源
                        from app.api.endpoints.sam3 import get_shared_sam_model, BEST_DEVICE
                        
                        # 查找SAM模型 - 在相同目录下寻找sam开头的模型文件
                        model_dir = Path(model_path).parent
                        sam_model_path = None
                        for file in model_dir.iterdir():
                            if file.suffix in ['.pt', '.engine'] and 'sam' in file.name.lower():
                                sam_model_path = str(file)
                                break
                        
                        # 如果没找到，尝试默认的sam3.pt
                        if not sam_model_path:
                            sam_model_path = "sam3.pt"
                        
                        # 使用YOLO检测结果作为SAM的提示
                        if result.boxes is not None and len(result.boxes) > 0:
                            # === 关键：从共享缓存拿模型 ===
                            # 绝对不要再 create 新的 SAM() 对象了
                            sam_model = get_shared_sam_model(sam_model_path)
                            
                            # 获取YOLO检测到的边界框
                            boxes = result.boxes
                            bboxes_xyxy = boxes.xyxy.cpu().numpy().tolist()
                            
                            # 使用YOLO检测的边界框作为SAM的输入
                            import torch
                            
                            # 从配置文件加载用户设置的参数
                            from app.api.endpoints.sam3 import load_sam3_config
                            sam3_config = load_sam3_config()
                            imgsz_value = sam3_config.get("imgsz", 1024)  # 默认1024
                            half_precision = sam3_config.get("half_precision", True)  # 默认True
                            
                            with torch.no_grad():
                                sam_results = sam_model.predict(
                                    source=str(image_file_path),
                                    bboxes=bboxes_xyxy,
                                    imgsz=imgsz_value,         # 使用用户配置的图像尺寸
                                    half=half_precision,       # 使用用户配置的半精度设置
                                    device=BEST_DEVICE,
                                    retina_masks=False,
                                    verbose=False
                                )
                            
                            # 解析SAM结果
                            if sam_results and len(sam_results) > 0:
                                sam_result = sam_results[0]
                                
                                if sam_result.masks is not None:
                                    # 获取归一化多边形
                                    xyn = sam_result.masks.xyn
                                    cls_ids = boxes.cls.cpu().numpy()  # 类别沿用 YOLO 的
                                    
                                    for i, poly in enumerate(xyn):
                                        if len(poly) > 0:
                                            # 构造标注数据
                                            class_id = int(cls_ids[i])
                                            if class_id < len(project_classes):
                                                # 转换为 annotation.js 需要的格式
                                                # 注意这里后端存的是归一化的 points 列表
                                                flat_points = poly.flatten().tolist()
                                                
                                                # 计算中心点和宽高
                                                xs = flat_points[0::2]
                                                ys = flat_points[1::2]
                                                x_min, x_max = min(xs), max(xs)
                                                y_min, y_max = min(ys), max(ys)
                                                
                                                annotations.append({
                                                    "class_id": class_id,
                                                    "x_center": (x_min + x_max) / 2,
                                                    "y_center": (y_min + y_max) / 2,
                                                    "width": x_max - x_min,
                                                    "height": y_max - y_min,
                                                    "points": flat_points  # [x1, y1, x2, y2...]
                                                })
                            else:
                                # 如果SAM失败，降级使用YOLO的检测结果
                                boxes = result.boxes
                                img_height, img_width = result.orig_shape
                                
                                for i in range(len(boxes)):
                                    box = boxes.xyxy[i].cpu().numpy()
                                    x1, y1, x2, y2 = box
                                    
                                    x_center = (x1 + x2) / 2 / img_width
                                    y_center = (y1 + y2) / 2 / img_height
                                    width = (x2 - x1) / img_width
                                    height = (y2 - y1) / img_height
                                    
                                    class_id = int(boxes.cls[i].cpu().numpy())
                                    
                                    if class_id < len(project_classes):
                                        annotations.append({
                                            "class_id": class_id,
                                            "x_center": float(x_center),
                                            "y_center": float(y_center),
                                            "width": float(width),
                                            "height": float(height)
                                        })
                    except Exception as e:
                        # 如果SAM失败，使用常规的YOLO检测
                        print(f"SAM3 refinement failed: {e}")
                        # 继续使用常规的YOLO处理逻辑
                        if result.boxes is not None:
                            boxes = result.boxes
                            img_height, img_width = result.orig_shape
                            
                            for i in range(len(boxes)):
                                box = boxes.xyxy[i].cpu().numpy()
                                x1, y1, x2, y2 = box
                                
                                x_center = (x1 + x2) / 2 / img_width
                                y_center = (y1 + y2) / 2 / img_height
                                width = (x2 - x1) / img_width
                                height = (y2 - y1) / img_height
                                
                                class_id = int(boxes.cls[i].cpu().numpy())
                                
                                if class_id < len(project_classes):
                                    annotations.append({
                                        "class_id": class_id,
                                        "x_center": float(x_center),
                                        "y_center": float(y_center),
                                        "width": float(width),
                                        "height": float(height)
                                    })
                # 如果是OBB项目且模型返回了obb属性
                elif project.project_type == 'obb' and hasattr(result, 'obb') and result.obb is not None:
                    obbs = result.obb
                    
                    # 获取图片尺寸
                    img_height, img_width = result.orig_shape
                    
                    for i in range(len(obbs)):
                        # 获取OBB坐标 (xywhr格式: 中心点x, 中心点y, 宽, 高, 角度)
                        xywhr = obbs.xywhr[i].cpu().numpy()
                        x_center_norm = xywhr[0] / img_width
                        y_center_norm = xywhr[1] / img_height
                        width_norm = xywhr[2] / img_width
                        height_norm = xywhr[3] / img_height
                        angle = xywhr[4]  # 角度不需要归一化
                        
                        # 获取类别 ID
                        class_id = int(obbs.cls[i].cpu().numpy())
                        
                        # 检查类别 ID 是否在项目类别范围内
                        project_classes_value = project_classes if isinstance(project_classes, list) else []
                        if class_id < len(project_classes_value):
                            annotations.append({
                                "class_id": class_id,
                                "x_center": float(x_center_norm),
                                "y_center": float(y_center_norm),
                                "width": float(width_norm),
                                "height": float(height_norm),
                                "angle": float(angle)
                            })
                elif result.boxes is not None:
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

    def merge_projects(
        self,
        db: Session,
        target_project_name: str,
        source_project_ids: List[UUID],
        delete_source_projects: bool = False,
        duplicate_handling: str = 'rename'
    ) -> Dict[str, Any]:
        """合并多个标注项目到新项目中"""
        from shutil import copy2
        import re
        from app.crud import annotation_project, image_annotation
        
        # 验证重名处理选项
        if duplicate_handling not in ['rename', 'overwrite', 'skip']:
            raise HTTPException(status_code=400, detail="重名处理选项必须是 'rename', 'overwrite', 或 'skip'")
        
        # 验证源项目是否存在且类型一致
        source_projects = []
        base_project_type = None
        base_classes = None
        
        for project_id in source_project_ids:
            project = annotation_project.get(db, id=project_id)
            if not project:
                raise HTTPException(status_code=404, detail=f"源项目 {project_id} 未找到")
            
            source_projects.append(project)
            
            # 验证项目类型一致性
            if base_project_type is None:
                base_project_type = project.project_type
                base_classes = project.classes or []
            elif project.project_type != base_project_type:
                raise HTTPException(
                    status_code=400, 
                    detail=f"项目类型不匹配: {project.name} ({project.project_type}) 与第一个项目 ({base_project_type}) 不一致"
                )
            
            # 检查类别是否一致（可以有不同的顺序）
            project_classes = project.classes or []
            if set(base_classes) != set(project_classes):
                raise HTTPException(
                    status_code=400,
                    detail=f"项目 {project.name} 的类别与基准项目不一致"
                )
        
        # 检查目标项目名称是否已存在
        existing_target = annotation_project.get_by_name(db, name=target_project_name)
        if existing_target:
            raise HTTPException(status_code=400, detail="目标项目名称已存在")
        
        # 创建合并后的项目目录
        merged_project_uuid = str(uuid.uuid4())
        merged_project_dir = self.annotation_dir / f"project_{target_project_name}_{merged_project_uuid}"
        merged_images_dir = merged_project_dir / "images"
        merged_labels_dir = merged_project_dir / "labels"
        
        merged_images_dir.mkdir(parents=True, exist_ok=True)
        merged_labels_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        total_merged_images = 0
        total_merged_annotations = 0
        duplicate_file_conflicts = []
        
        # 用于跟踪已处理的文件名
        processed_filenames = set()
        
        # 遍历所有源项目进行合并
        for source_project in source_projects:
            source_images_dir = Path(source_project.image_directory) if source_project.image_directory else None
            
            if not source_images_dir or not source_images_dir.exists():
                # 尝试寻找可能的图片目录结构
                possible_dirs = [
                    self.annotation_dir / f"project_{source_project.name}",
                    self.annotation_dir / f"project_{source_project.name}_{source_project.id}"
                ]
                for possible_dir in possible_dirs:
                    if (possible_dir / "images").exists():
                        source_images_dir = possible_dir / "images"
                        break
            
            if not source_images_dir or not source_images_dir.exists():
                continue
            
            # 获取源项目中的图片
            source_images = image_annotation.get_by_project_id(db, project_id=source_project.id, skip=0, limit=10000)
            
            for source_img in source_images:
                source_img_name = source_img.image_name
                if not source_img_name:
                    continue
                
                # 源图片文件路径
                source_img_path = source_images_dir / source_img_name
                if not source_img_path.exists():
                    # 尝试使用完整的image_path
                    if source_img.image_path:
                        full_source_path = Path(source_img.image_path)
                        if full_source_path.exists():
                            source_img_path = full_source_path
                        elif Path(source_project.image_directory or "") / source_img_name:
                            source_img_path = Path(source_project.image_directory or "") / source_img_name
                
                if not source_img_path.exists():
                    continue
                
                # 处理目标文件名，根据重名处理选项
                target_img_name = source_img_name
                counter = 1
                original_stem = Path(source_img_name).stem
                original_suffix = Path(source_img_name).suffix
                
                # 检查目标文件是否已存在
                target_img_path = merged_images_dir / target_img_name
                
                if target_img_path.exists():
                    if duplicate_handling == 'skip':
                        # 跳过重名文件
                        duplicate_file_conflicts.append(f"跳过重名文件: {source_img_name}")
                        continue
                    elif duplicate_handling == 'overwrite':
                        # 覆盖重名文件
                        pass  # 直接继续，使用当前名称
                    elif duplicate_handling == 'rename':
                        # 重命名文件
                        while True:
                            new_name = f"{original_stem}_{counter}{original_suffix}"
                            new_target_path = merged_images_dir / new_name
                            if not new_target_path.exists():
                                target_img_name = new_name
                                break
                            counter += 1
                            
                            if counter > 1000:  # 防止无限循环
                                duplicate_file_conflicts.append(f"无法为 {source_img_name} 生成唯一名称")
                                break
                        
                        if counter > 1000:
                            continue  # 跳过此文件
                
                # 复制图片文件
                copy2(source_img_path, merged_images_dir / target_img_name)
                
                # 如果有标注，也需要复制对应的标签文件
                if source_img.annotations and len(source_img.annotations) > 0:
                    # 使用目标图片名称生成标签文件名
                    label_filename = f"{Path(target_img_name).stem}.txt"
                    target_label_path = merged_labels_dir / label_filename
                    
                    # 使用项目的class_keypoints配置来格式化标注
                    project_class_keypoints = source_project.class_keypoints if source_project.class_keypoints is not None else None
                    label_content_lines = self._format_annotation_labels(source_img.annotations, project_class_keypoints)
                    
                    # 写入标签文件
                    with open(target_label_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(label_content_lines))
                    
                    total_merged_annotations += len(source_img.annotations)
                
                total_merged_images += 1
        
        # 创建目标项目
        target_project_data = AnnotationProjectCreate(
            name=target_project_name,
            description=f"由 {len(source_projects)} 个项目合并而成",
            project_type=base_project_type,
            classes=base_classes,
            class_keypoints=source_projects[0].class_keypoints if source_projects else None,
            image_directory=str(merged_images_dir)
        )
        
        target_project = annotation_project.create(db, obj_in=target_project_data)
        
        # 扫描合并后的图片目录，创建图片标注记录
        self._scan_images(db, target_project, str(merged_images_dir))
        
        # 读取合并的标签文件并将标注信息存入数据库
        self._import_merged_annotations(db, target_project, str(merged_images_dir), str(merged_labels_dir))
        
        # 如果需要删除源项目
        if delete_source_projects:
            for source_project in source_projects:
                # 删除源项目记录
                annotation_project.remove(db, id=source_project.id)
                
                # 尝试删除源项目目录
                source_project_dir = Path(source_project.image_directory) if source_project.image_directory else None
                if source_project_dir and source_project_dir.exists():
                    try:
                        if source_project_dir.parent.name.startswith("project_"):
                            shutil.rmtree(source_project_dir.parent)  # 删除整个项目目录
                    except Exception as e:
                        logging.warning(f"删除源项目目录失败 {source_project_dir}: {str(e)}")
        
        # 返回合并结果
        result = {
            "message": f"成功合并了 {len(source_projects)} 个项目",
            "merged_projects_count": len(source_projects),
            "total_images": total_merged_images,
            "total_annotations": total_merged_annotations,
            "target_project_id": target_project.id,
            "target_project_name": target_project_name
        }
        
        if duplicate_file_conflicts:
            result["duplicate_conflicts"] = duplicate_file_conflicts
        
        return result
        
    def _import_merged_annotations(self, db: Session, project: AnnotationProjectModel, image_directory: str, labels_directory: str):
        """导入合并后的标注文件并将其信息存入数据库"""
        image_dir_path = Path(image_directory)
        labels_dir_path = Path(labels_directory)
        
        if not image_dir_path.exists() or not labels_dir_path.exists():
            return
        
        # 获取项目中的所有图片
        all_images = self.get_project_images(db, project.id)
        
        # 获取所有标签文件
        label_files = {f.stem: f for f in labels_dir_path.rglob("*.txt")}
        
        for img in all_images:
            image_stem = Path(img.image_name).stem
            if image_stem in label_files:
                # 尝试导入此图片的标注
                try:
                    annotations = self._parse_yolo_label_file(str(label_files[image_stem]), project.classes or [], project.project_type or 'detection')
                    if annotations:
                        # 保存标注到数据库
                        self.save_annotations(db, img.id, annotations)
                except Exception as e:
                    logging.error(f"处理 {img.image_name} 的标注时出错: {str(e)}")

    def expand_project_data(
        self,
        db: Session,
        project_id: UUID,
        import_original_annotations: bool,
        zip_file: UploadFile
    ) -> Dict[str, Any]:
        """为现有项目扩展数据"""
        # 获取项目信息
        project = annotation_project.get(db, id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目未找到")
        
        # 获取项目目录
        project_dir = Path(project.image_directory) if project.image_directory else None
        if not project_dir:
            raise HTTPException(status_code=400, detail="项目目录未设置")
        
        # 确保是images目录，如果不是，则添加images子目录
        if project_dir.name != "images":
            images_dir = project_dir / "images"
            if not images_dir.exists():
                images_dir = project_dir  # 如果不存在images子目录，就使用当前目录
        else:
            images_dir = project_dir
        
        # 如果不存在，创建labels目录用于存放标注文件
        labels_dir = images_dir.parent / "labels" if images_dir.name == "images" else images_dir / "labels"
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存并解压ZIP文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            content = zip_file.file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # 统计变量
        extracted_images_count = 0
        extracted_labels_count = 0
        
        try:
            with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                # 支持的图片格式
                image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
                label_extensions = {'.txt'}  # 标注文件格式
                
                # 检查ZIP中的顶级目录结构
                root_items = set()
                for file_info in zip_ref.filelist:
                    if not file_info.is_dir():
                        file_path = Path(file_info.filename)
                        # 获取顶级目录或文件
                        if len(file_path.parts) > 0:
                            root_items.add(file_path.parts[0])
                    else:
                        dir_path = Path(file_info.filename)
                        if len(dir_path.parts) > 0:
                            root_items.add(dir_path.parts[0])
                
                # 检查是否是标准结构（images、labels）
                has_standard_structure = (
                    'images' in root_items or 'Images' in root_items or 
                    'img' in root_items or 'IMG' in root_items
                ) and (
                    'labels' in root_items or 'Labels' in root_items or 
                    'ann' in root_items or 'Ann' in root_items
                )
                
                for file_info in zip_ref.filelist:
                    if not file_info.is_dir():
                        file_path = Path(file_info.filename)
                        
                        if has_standard_structure:
                            # 如果是标准结构，根据目录分类处理
                            if file_path.parts[0] in ['images', 'Images', 'img', 'IMG']:
                                # 提取到images目录，但要去掉顶级目录前缀
                                relative_path = Path(*file_path.parts[1:])  # 去掉第一个部分（images/）
                                if relative_path:  # 确保有剩余路径
                                    target_path = images_dir / relative_path
                                    # 确保目标目录存在
                                    target_path.parent.mkdir(parents=True, exist_ok=True)
                                    # 提取文件到目标路径
                                    with zip_ref.open(file_info) as source:
                                        with open(target_path, 'wb') as target:
                                            target.write(source.read())
                                extracted_images_count += 1
                            elif file_path.parts[0] in ['labels', 'Labels', 'ann', 'Ann']:
                                # 提取到labels目录，但要去掉顶级目录前缀
                                relative_path = Path(*file_path.parts[1:])  # 去掉第一个部分（labels/）
                                if relative_path:  # 确保有剩余路径
                                    target_path = labels_dir / relative_path
                                    # 确保目标目录存在
                                    target_path.parent.mkdir(parents=True, exist_ok=True)
                                    # 提取文件到目标路径
                                    with zip_ref.open(file_info) as source:
                                        with open(target_path, 'wb') as target:
                                            target.write(source.read())
                                extracted_labels_count += 1
                            elif file_path.suffix.lower() in image_extensions:
                                # 如果不在标准目录中，但扩展名是图片，也提取到images目录
                                zip_ref.extract(file_info, images_dir)
                                extracted_images_count += 1
                            elif file_path.suffix.lower() in label_extensions:
                                # 如果不在标准目录中，但扩展名是标签，也提取到labels目录
                                if import_original_annotations:
                                    zip_ref.extract(file_info, labels_dir)
                                    extracted_labels_count += 1
                        else:
                            # 如果不是标准结构，按扩展名分类
                            if file_path.suffix.lower() in image_extensions:
                                # 提取图片文件到images目录
                                zip_ref.extract(file_info, images_dir)
                                extracted_images_count += 1
                            elif file_path.suffix.lower() in label_extensions:
                                # 如果开启了导入原标注，提取标注文件到labels目录
                                if import_original_annotations:
                                    zip_ref.extract(file_info, labels_dir)
                                    extracted_labels_count += 1
        
        finally:
            os.unlink(temp_file_path)
        
        if extracted_images_count == 0:
            raise HTTPException(status_code=400, detail="ZIP文件中没有找到支持的图片文件")
        
        # 扫描图片目录，更新数据库记录
        self._scan_images(db, project, str(images_dir))
        
        # 如果开启了导入原标注，执行导入
        import_result = None
        if import_original_annotations:
            import_result = self._import_existing_annotations_with_stats(db, project)
        
        # 返回结果
        result = {
            "message": f"成功扩展项目数据，添加了 {extracted_images_count} 张图片",
            "added_images_count": extracted_images_count,
            "added_labels_count": extracted_labels_count,
            "import_original_annotations": import_original_annotations,
            "project_id": project_id,
            "project_name": project.name
        }
        
        if import_result:
            result["import_result"] = import_result
        
        return result
