import os
import uuid
import torch
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import detection_task, model
from app.models.detection_task import DetectionTask
from app.schemas.detection_task import DetectionTaskCreate, DetectionTaskUpdate

# 导入可能需要的PyTorch和Ultralytics模型类
try:
    # 导入PyTorch核心类
    from torch.nn.modules.container import Sequential
    from torch.nn import Module, ModuleList, ModuleDict

    # 导入Ultralytics模型类
    from ultralytics.nn.tasks import DetectionModel, SegmentationModel, ClassificationModel, PoseModel

    # 导入Ultralytics模块类
    from ultralytics.nn.modules import conv
    from ultralytics.nn.modules import block
    from ultralytics.nn.modules import head

    # 添加PyTorch核心类到安全全局变量
    torch.serialization.add_safe_globals([Sequential, Module, ModuleList, ModuleDict])

    # 添加Ultralytics模型类到安全全局变量
    torch.serialization.add_safe_globals([DetectionModel, SegmentationModel, ClassificationModel, PoseModel])

    # 添加Ultralytics模块类
    torch.serialization.add_safe_globals([conv.Conv])

    # 添加所有Ultralytics模块类
    for module in [conv, block, head]:
        for name in dir(module):
            if name[0].isupper():  # 类名通常以大写字母开头
                try:
                    cls = getattr(module, name)
                    if isinstance(cls, type):  # 确保是类
                        torch.serialization.add_safe_globals([cls])
                except Exception as e:
                    print(f"Could not add {module.__name__}.{name} to safe globals: {e}")
except ImportError as e:
    print(f"Warning: Could not import required classes: {e}")

async def create_detection_task(
    db: Session,
    model_id: str = None,
    file: UploadFile = None,
    parameters: Dict[str, Any] = None
) -> DetectionTask:
    """
    Create a new detection task
    """
    # 初始化参数
    if parameters is None:
        parameters = {}

    # 默认模型ID和路径
    DEFAULT_MODEL_ID = "6b30123c-2c33-43c0-a045-41cda7e61d37"  # 使用生成的UUID
    model_path = "yolov8n.pt"  # 默认模型路径

    # 如果没有提供模型ID，使用默认模型ID
    if not model_id:
        model_id = DEFAULT_MODEL_ID
        print(f"使用默认模型ID: {model_id}")

    # 检查模型是否存在
    db_model = model.get(db, id=model_id)
    if not db_model:
        # 如果找不到模型，创建一个默认模型记录
        db_model = model.create_with_fields(db, obj_in={
            "id": DEFAULT_MODEL_ID,
            "name": "YOLOv8n",
            "description": "默认YOLOv8n模型",
            "path": model_path,
            "type": "detection",
            "task": "object_detection",
            "source": "default"
        })
        print(f"创建默认模型: {db_model.name}")

    # 使用模型路径
    model_path = db_model.path

    # Generate unique ID for the detection task
    task_id = str(uuid.uuid4())

    # 直接读取上传的文件内容到内存中，不保存到本地
    content = await file.read()

    # 创建内存中的检测任务记录
    obj_in_data = {
        "model_id": model_id,  # 确保model_id总是有值
        "parameters": parameters,
        "input_path": f"memory:{file.filename}",  # 使用内存标识符
        "output_path": f"memory:{task_id}",       # 使用内存标识符
        "status": "pending"
    }

    # 使用create_with_fields方法创建完整的记录
    db_task = detection_task.create_with_fields(db, obj_in=obj_in_data)

    # 在实际实现中，这将由后台任务处理
    # 执行实际的检测过程
    try:
        # 导入YOLO模型
        from ultralytics import YOLO

        # 确保添加安全全局变量
        try:
            # 导入PyTorch核心类
            from torch.nn.modules.container import Sequential
            from torch.nn import Module, ModuleList, ModuleDict

            # 导入Ultralytics模型类
            from ultralytics.nn.tasks import DetectionModel

            # 导入Ultralytics模块类
            from ultralytics.nn.modules import conv
            from ultralytics.nn.modules import block
            from ultralytics.nn.modules import head

            # 添加PyTorch核心类到安全全局变量
            torch.serialization.add_safe_globals([Sequential, Module, ModuleList, ModuleDict])

            # 添加Ultralytics模型类到安全全局变量
            torch.serialization.add_safe_globals([DetectionModel])

            # 添加Ultralytics模块类
            torch.serialization.add_safe_globals([conv.Conv])

            # 添加所有Ultralytics模块类
            for module in [conv, block, head]:
                for name in dir(module):
                    if name[0].isupper():  # 类名通常以大写字母开头
                        try:
                            cls = getattr(module, name)
                            if isinstance(cls, type):  # 确保是类
                                torch.serialization.add_safe_globals([cls])
                        except Exception as e:
                            print(f"Could not add {module.__name__}.{name} to safe globals: {e}")
        except ImportError as e:
            print(f"Warning: Could not import required classes: {e}")

        # 导入必要的库
        import cv2
        import numpy as np
        from io import BytesIO

        # 加载模型
        yolo_model = YOLO(model_path)
        print(f"成功加载模型: {model_path}")

        # 将内容转换为numpy数组
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("无法解码图像数据")

        # 执行检测 - 直接传递图像数组而不是文件路径
        results = yolo_model(img, conf=parameters.get('conf_thres', 0.25), iou=parameters.get('iou_thres', 0.45))

        # 在内存中处理结果
        import json
        memory_results = []

        for i, result in enumerate(results):
            # 获取绘制后的图像
            if hasattr(result, 'plot') and callable(getattr(result, 'plot')):
                plotted_img = result.plot()
            else:
                # 如果没有plot方法，手动绘制检测框
                plotted_img = img.copy()
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy.tolist()[0])
                    conf = float(box.conf.item())
                    cls = int(box.cls.item())
                    label = f"{result.names[cls]} {conf:.2f}"

                    # 绘制检测框
                    color = (0, 255, 0)  # BGR格式，绿色
                    cv2.rectangle(plotted_img, (x1, y1), (x2, y2), color, 2)

                    # 绘制标签
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    cv2.putText(plotted_img, label, (x1, y1 - 10), font, 0.5, color, 2)

            # 将检测结果转换为JSON格式
            boxes = result.boxes
            json_results = []
            for box in boxes:
                class_id = int(box.cls.item())
                json_results.append({
                    'class': class_id,  # 保留'class'字段以兼容旧代码
                    'class_id': class_id,  # 添加'class_id'字段以兼容前端代码
                    'class_name': result.names[class_id],
                    'confidence': float(box.conf.item()),
                    'bbox': box.xyxy.tolist()[0],
                })

            # 不保存图像数据，只保存检测结果
            # 这样可以大幅减少内存占用
            memory_results.append({
                'detections': json_results
            })

        # 将结果存储在参数中
        updated_parameters = {
            **parameters,
            'memory_results': memory_results
        }

        # 更新任务状态为已完成
        db_task = detection_task.update(db, db_obj=db_task, obj_in={
            "status": "completed",
            "parameters": updated_parameters
        })
    except Exception as e:
        # 如果发生错误，更新任务状态为失败
        db_task = detection_task.update(db, db_obj=db_task, obj_in={
            "status": "failed",
            "parameters": {**parameters, "error": str(e)}
        })
        raise HTTPException(
            status_code=500,
            detail=f"Detection failed: {str(e)}",
        )

    return db_task

def get_detection_task(db: Session, task_id: str) -> DetectionTask:
    """
    Get a detection task by ID
    """
    db_task = detection_task.get(db, id=task_id)
    if not db_task:
        raise HTTPException(
            status_code=404,
            detail="Detection task not found",
        )
    return db_task

def get_detection_tasks(db: Session, skip: int = 0, limit: int = 100) -> List[DetectionTask]:
    """
    Get all detection tasks
    """
    return detection_task.get_multi(db, skip=skip, limit=limit)

def get_detection_result(db: Session, task_id: str) -> Dict[str, Any]:
    """
    Get the detection result for a task - 支持内存中的结果
    """
    # 获取任务信息
    db_task = detection_task.get(db, id=task_id)
    if not db_task:
        raise HTTPException(
            status_code=404,
            detail="Detection task not found",
        )

    # 检查任务状态
    if db_task.status != "completed":
        return {
            "status": db_task.status,
            "message": f"Detection task is {db_task.status}",
            "results": None
        }

    # 检查是否是内存中的结果
    if db_task.output_path.startswith("memory:"):
        # 从参数中获取内存结果
        memory_results = db_task.parameters.get('memory_results', [])

        if not memory_results:
            return {
                "status": "error",
                "message": "No detection results found in memory",
                "results": None
            }

        # 构建结果对象
        results = []
        for i, result in enumerate(memory_results):
            try:
                # 从内存结果中提取检测结果
                detections = result.get('detections', [])

                # 不返回图像数据，只返回检测结果
                results.append({
                    "memory_image_id": f"memory_image_{i}",  # 使用内存标识符
                    "detections": detections,
                    "count": len(detections)
                })
            except Exception as e:
                print(f"Error processing memory result #{i}: {e}")

        return {
            "status": "completed",
            "message": "Detection completed successfully (memory mode)",
            "results": results,
            "input_image": db_task.input_path.replace("memory:", "")
        }

    # 以下是原有的文件系统处理逻辑，保留以兼容旧数据
    # 获取输出目录
    output_dir = Path(db_task.output_path)
    if not output_dir.exists():
        return {
            "status": "error",
            "message": "Output directory not found",
            "results": None
        }

    # 查找结果文件
    result_images = list(output_dir.glob("result_*.jpg"))
    result_jsons = list(output_dir.glob("result_*.json"))

    if not result_images or not result_jsons:
        return {
            "status": "error",
            "message": "No detection results found",
            "results": None
        }

    # 构建结果对象
    results = []
    for i, (img_path, json_path) in enumerate(zip(sorted(result_images), sorted(result_jsons))):
        # 读取JSON结果
        try:
            import json
            with open(json_path, 'r') as f:
                detections = json.load(f)

            # 构建相对URL路径
            img_rel_path = img_path.relative_to(settings.STATIC_DIR)
            img_url = f"/static/{img_rel_path.as_posix()}"

            results.append({
                "image_url": img_url,
                "detections": detections,
                "count": len(detections)
            })
        except Exception as e:
            print(f"Error loading detection result {json_path}: {e}")

    return {
        "status": "completed",
        "message": "Detection completed successfully",
        "results": results,
        "input_image": str(Path(db_task.input_path).name)
    }
