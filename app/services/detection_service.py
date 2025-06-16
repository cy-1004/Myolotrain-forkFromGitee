import os
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import detection_task, model
from app.models.detection_task import DetectionTask
from app.schemas.detection_task import DetectionTaskCreate, DetectionTaskUpdate

async def create_detection_task(
    db: Session,
    model_id: str,
    file: UploadFile,
    parameters: Dict[str, Any]
) -> DetectionTask:
    """
    Create a new detection task
    """
    # Check if model exists
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(
            status_code=404,
            detail="Model not found",
        )

    # Generate unique ID for the detection task
    task_id = str(uuid.uuid4())

    # Create input and output directories
    input_dir = settings.UPLOADS_DIR / task_id
    output_dir = settings.RESULTS_DIR / task_id
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Save the uploaded file
    file_extension = Path(file.filename).suffix
    input_path = input_dir / f"input{file_extension}"
    with open(input_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Create detection task with all required fields
    obj_in_data = {
        "model_id": model_id,
        "parameters": parameters,
        "input_path": str(input_path),
        "output_path": str(output_dir),
        "status": "pending"
    }

    # 使用create_with_fields方法创建完整的记录
    db_task = detection_task.create_with_fields(db, obj_in=obj_in_data)

    # 在实际实现中，这将由后台任务处理
    # 现在，我们将执行实际的检测过程
    try:
        # 导入YOLO模型
        from ultralytics import YOLO

        # 加载模型
        model_path = db_model.path
        yolo_model = YOLO(model_path)

        # 执行检测
        results = yolo_model(str(input_path), conf=parameters.get('conf_thres', 0.25), iou=parameters.get('iou_thres', 0.45))

        # 保存结果
        for i, result in enumerate(results):
            # 保存带有检测框的图像
            result_path = output_dir / f"result_{i}.jpg"
            result.save(filename=str(result_path))

            # 保存JSON结果
            json_path = output_dir / f"result_{i}.json"
            with open(json_path, 'w') as f:
                import json
                # 将检测结果转换为JSON格式
                boxes = result.boxes
                json_results = []
                for box in boxes:
                    json_results.append({
                        'class': int(box.cls.item()),
                        'class_name': result.names[int(box.cls.item())],
                        'confidence': float(box.conf.item()),
                        'bbox': box.xyxy.tolist()[0],
                    })
                json.dump(json_results, f, indent=2)

        # 更新任务状态为已完成
        db_task = detection_task.update(db, db_obj=db_task, obj_in={
            "status": "completed"
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
    Get the detection result for a task
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
