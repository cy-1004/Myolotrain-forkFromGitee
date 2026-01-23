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

    # Validate file type - only allow image files
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file_extension}. 只允许上传图片文件 ({', '.join(allowed_extensions)})"
        )

    # Generate unique ID for the detection task
    task_id = str(uuid.uuid4())

    # Create input and output directories
    input_dir = settings.UPLOADS_DIR / task_id
    output_dir = settings.RESULTS_DIR / task_id
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Save the uploaded file
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
        import io
        import sys
        from contextlib import redirect_stdout, redirect_stderr
        import torch
        
        # 自动检测设备：如果有CUDA则使用GPU，否则使用CPU
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Detection using device: {device}")
        
        # 加载模型
        model_path = db_model.path
        yolo_model = YOLO(model_path)

        # 捕获YOLO的输出信息
        # 通过重定向系统级输出来捕获YOLO的详细输出信息
        import time
        import sys
        import tempfile
                
        output_log = ""  # 初始化变量
        temp_filename = None  # 初始化变量
                
        import subprocess
        import threading
        from io import StringIO
        import contextlib
        
        # 使用subprocess方法来更可靠地捕获所有输出
        def run_detection_with_capture():
            # 创建一个线程安全的字符串缓冲区来捕获输出
            import io
            old_stdout, old_stderr = sys.stdout, sys.stderr
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            
            try:
                # 重定向输出
                sys.stdout, sys.stderr = stdout_buffer, stderr_buffer
                
                # 执行检测 - 指定设备
                results = yolo_model(str(input_path), conf=parameters.get('conf_thres', 0.25), iou=parameters.get('iou_thres', 0.45), device=device, verbose=True)
                
                # 获取输出
                stdout_str = stdout_buffer.getvalue()
                stderr_str = stderr_buffer.getvalue()
                
                return results, stdout_str + stderr_str
            finally:
                # 恢复原始输出
                sys.stdout, sys.stderr = old_stdout, old_stderr
        
        # 执行检测并捕获输出
        results, output_log = run_detection_with_capture()
                
        # 如果输出日志为空，使用回退方法测量时间
        if not output_log.strip():
            # 只有在日志为空时才执行第二次检测并测量时间
            start_time = time.time()
            results = yolo_model(str(input_path), conf=parameters.get('conf_thres', 0.25), iou=parameters.get('iou_thres', 0.45), device=device, verbose=False)
            execution_time = (time.time() - start_time) * 1000  # 转换为毫秒
            output_log = f"image 1/1 {input_path}: 480x640 1 object, {execution_time:.1f}ms\nSpeed: 1.0ms preprocess, {execution_time:.1f}ms inference, 1.0ms postprocess per image at shape (1, 3, 480, 640)\n"
        else:
            # 如果日志不为空，我们已经获得了结果，不需要再次运行
            # 但需要确保results变量已设置（已经在上面设置了）
            pass  # 输出已被成功捕获，无需其他操作
        
        # 从输出日志中提取推理时间
        import re
        inference_time = 0
        
        # 打印日志内容用于调试
        print(f"Detection output log: {output_log}")
        
        # 尝试多种模式匹配推理时间
        print(f"Looking for inference time in log: {repr(output_log)}")
        
        # 模式1: 直接匹配 'X.Xms inference'
        inference_matches = re.findall(r'(\d+(?:\.\d+)?)ms\s+inference', output_log)
        print(f"Pattern 1 - Direct 'ms inference' matches: {inference_matches}")
        
        if inference_matches:
            # 取最后一个匹配项（通常是最新的推理时间）
            try:
                inference_time = float(inference_matches[-1])
                print(f"Extracted inference time from direct pattern: {inference_time}ms")
            except (ValueError, IndexError):
                print("Failed to convert direct pattern inference time, using default 0")
                inference_time = 0
        else:
            # 模式2: 匹配 'Speed: X.Xms preprocess, Y.Yms inference, Z.Zms postprocess' 格式
            speed_match = re.search(r'Speed:.*?(\d+(?:\.\d+)?)ms\s+inference', output_log)
            if speed_match:
                try:
                    inference_time = float(speed_match.group(1))
                    print(f"Extracted inference time from Speed pattern: {inference_time}ms")
                except (ValueError, IndexError):
                    print("Failed to convert Speed pattern inference time, using default 0")
                    inference_time = 0
            else:
                # 模式3: 匹配 'preprocess, X.Xms inference' 格式
                speed_match2 = re.search(r'preprocess,\s*(\d+(?:\.\d+)?)ms\s+inference', output_log)
                if speed_match2:
                    try:
                        inference_time = float(speed_match2.group(1))
                        print(f"Extracted inference time from preprocess-inference pattern: {inference_time}ms")
                    except (ValueError, IndexError):
                        print("Failed to convert preprocess-inference pattern inference time, using default 0")
                        inference_time = 0
                else:
                    print("No inference time patterns matched, using default 0")

        # 保存结果 - 根据模型任务类型分发处理
        import numpy as np
        import json
        
        if db_model.task == 'detect':
            # ===== 目标检测 (矩形框) =====
            for i, result in enumerate(results):
                # 保存可视化结果
                result_path = output_dir / f"result_{i}.jpg"
                result.save(filename=str(result_path))
                
                # 保存JSON
                json_path = output_dir / f"result_{i}.json"
                with open(json_path, 'w') as f:
                    json_results = []
                    for box in result.boxes:
                        json_results.append({
                            'class_id': int(box.cls.item()),
                            'class_name': result.names[int(box.cls.item())],
                            'confidence': float(box.conf.item()),
                            'bbox': [round(x, 2) for x in box.xyxy.tolist()[0]],  # [x1,y1,x2,y2]
                        })
                    json.dump(json_results, f, indent=2)

        elif db_model.task == 'segment':
            # ===== 实例分割 (掩码+框) =====
            for i, result in enumerate(results):
                result_path = output_dir / f"result_{i}.jpg"
                result.save(filename=str(result_path))  # 自动叠加掩码
                
                json_path = output_dir / f"result_{i}.json"
                with open(json_path, 'w') as f:
                    json_results = []
                    for j, box in enumerate(result.boxes):
                        # 基础检测信息
                        result_dict = {
                            'class_id': int(box.cls.item()),
                            'class_name': result.names[int(box.cls.item())],
                            'confidence': float(box.conf.item()),
                            'bbox': [round(x, 2) for x in box.xyxy.tolist()[0]],
                        }
                        
                        # 添加掩码数据 (压缩为边界坐标)
                        if result.masks:
                            mask = result.masks[j].xy[0].astype(float).tolist()  # 轮廓点集
                            result_dict['mask_polygon'] = [[round(x,2), round(y,2)] for x,y in mask]
                        
                        json_results.append(result_dict)
                    json.dump(json_results, f, indent=2)

        elif db_model.task == 'obb':
            # ===== 旋转框 (OBB) =====
            for i, result in enumerate(results):
                result_path = output_dir / f"result_{i}.jpg"
                result.save(filename=str(result_path))  # 绘制旋转框
                
                json_path = output_dir / f"result_{i}.json"
                with open(json_path, 'w') as f:
                    json_results = []
                    for obb in result.obb:  # 注意：使用obb属性
                        # OBB核心参数: [x_center, y_center, width, height, angle(radians)]
                        obb_params = obb.xywhr.cpu().numpy().flatten().tolist()
                        
                        json_results.append({
                            'class_id': int(obb.cls.item()),
                            'class_name': result.names[int(obb.cls.item())],
                            'confidence': float(obb.conf.item()),
                            'obb': {
                                'center': [round(obb_params[0],2), round(obb_params[1],2)],
                                'size': [round(obb_params[2],2), round(obb_params[3],2)],
                                'angle_deg': round(np.degrees(obb_params[4]), 2)  # 转角度
                            }
                        })
                    json.dump(json_results, f, indent=2)

        elif db_model.task == 'pose':
            # ===== 姿态估计 (关键点) =====
            for i, result in enumerate(results):
                result_path = output_dir / f"result_{i}.jpg"
                result.save(filename=str(result_path))  # 绘制骨架
                
                json_path = output_dir / f"result_{i}.json"
                with open(json_path, 'w') as f:
                    json_results = []
                    for j, kpt in enumerate(result.keypoints):  # 注意：使用keypoints属性
                        # 获取对应检测框
                        if result.boxes and j < len(result.boxes):
                            box = result.boxes[j]
                        else:
                            # 如果没有对应的检测框，跳过此关键点
                            continue
                        
                        # 提取关键点 (x,y,confidence)
                        points = []
                        if kpt is not None and kpt.xy.shape[1] > 0:
                            for idx, pt in enumerate(kpt.xy[0].cpu().numpy()):
                                conf_val = 0.0
                                if kpt.conf is not None and idx < kpt.conf.shape[1]:
                                    conf_val = float(kpt.conf[0][idx])
                                points.append({
                                    'x': round(float(pt[0]), 2),
                                    'y': round(float(pt[1]), 2),
                                    'confidence': round(conf_val, 2)
                                })
                        
                        json_results.append({
                            'class_id': int(box.cls.item()),
                            'class_name': result.names[int(box.cls.item())],
                            'confidence': float(box.conf.item()),
                            'bbox': [round(x,2) for x in box.xyxy.tolist()[0]],
                            'keypoints': points,  # N个关键点
                            'skeleton': result.skeleton if hasattr(result, 'skeleton') else []  # 骨架连接关系
                        })
                    json.dump(json_results, f, indent=2)

        else:
            # 默认按目标检测处理
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
                            'class_id': int(box.cls.item()),
                            'class_name': result.names[int(box.cls.item())],
                            'confidence': float(box.conf.item()),
                            'bbox': [round(x, 2) for x in box.xyxy.tolist()[0]],
                        })
                    json.dump(json_results, f, indent=2)

        # 更新任务状态为已完成，包含推理时间
        db_task = detection_task.update(db, db_obj=db_task, obj_in={
            "status": "completed",
            "parameters": {**parameters, "inference_time_ms": inference_time}
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

    # 获取推理时间
    inference_time_ms = 0
    if hasattr(db_task, 'parameters') and db_task.parameters:
        try:
            inference_time_ms = db_task.parameters.get('inference_time_ms', 0)
            print(f"Retrieved inference time from parameters: {inference_time_ms}ms")
        except Exception as e:
            print(f"Error getting inference time from parameters: {e}")
            inference_time_ms = 0
    else:
        print("No parameters found or parameters is None")
    
    return {
        "status": "completed",
        "message": "Detection completed successfully",
        "results": results,
        "input_image": str(Path(db_task.input_path).name),
        "inference_time_ms": inference_time_ms
    }
