from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import numpy as np
import cv2
from PIL import Image
import io

from app.db.session import get_db
from app.services import detection_service
from app.crud import model
import uuid
import os
from pathlib import Path
from app.core.config import settings

router = APIRouter()

@router.post("/sync-detect")
async def sync_detect(
    model_id: str = Form(...),
    file: UploadFile = File(...),
    conf_thres: float = Form(0.25),
    iou_thres: float = Form(0.45),
    db: Session = Depends(get_db)
):
    """
    同步检测端点 - 直接返回检测结果，不创建异步任务
    专门用于视觉追踪功能
    
    与传统的异步检测API不同，此端点：
    1. 直接处理图像并返回检测结果
    2. 不创建数据库任务记录
    3. 不保存中间文件到磁盘
    4. 适用于实时摄像头追踪场景
    """
    try:
        # Check if model exists
        db_model = model.get(db, id=model_id)
        if not db_model:
            raise HTTPException(
                status_code=404,
                detail="Model not found",
            )

        # 为临时文件生成唯一标识符
        task_id = str(uuid.uuid4())

        #创建临时目录
        temp_dir = settings.UPLOADS_DIR / f"temp_{task_id}"
        os.makedirs(temp_dir, exist_ok=True)


        #保存上传的文件到临时目录
        file_extension = Path(file.filename).suffix if file.filename else ".jpg"
        temp_path = temp_dir / f"temp{file_extension}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Import YOLO model - suppress lint warning
        from ultralytics import YOLO  # type: ignore

        # Load model
        model_path = str(db_model.path)  # Convert Column to string
        yolo_model = YOLO(model_path)

        # 检测临时文件
        results = yolo_model(str(temp_path), conf=conf_thres, iou=iou_thres)

        # Collect results
        all_detections = []
        for i, result in enumerate(results):
            # Process detection results
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    detection = {
                        'class_id': int(box.cls.item()),
                        'class_name': result.names[int(box.cls.item())],
                        'confidence': float(box.conf.item()),
                        'bbox': box.xyxy.tolist()[0],
                    }
                    all_detections.append(detection)

        # Clean up temporary files
        try:
            os.remove(temp_path)
            os.rmdir(temp_dir)
        except:
            pass  # Ignore cleanup errors

        return {
            "detections": all_detections,
            "count": len(all_detections)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Detection failed: {str(e)}",
        )