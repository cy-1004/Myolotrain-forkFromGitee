from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import time
import asyncio
import tempfile
import os
from pathlib import Path
from fastapi.datastructures import UploadFile as FastAPIUploadFile
import io

from app.db.session import get_db
from app.services import detection_service
from app.crud import model
from app.models.model import Model

router = APIRouter()

async def run_single_detection(db, model_id, file, parameters):
    """
    执行单个检测任务并返回结果和执行时间
    """
    result = await detection_service.create_detection_task(
        db=db,
        model_id=model_id,
        file=file,
        parameters=parameters
    )
    result_data = detection_service.get_detection_result(db, result.id)
    # 使用从检测服务中获取的真实推理时间
    execution_time = result_data.get('inference_time_ms', 0)
    return result_data, execution_time

@router.post("/compare-detection")
async def compare_detection(
    model_a_id: str = Form(...),
    model_b_id: str = Form(...),
    file: UploadFile = File(...),
    conf_thres_a: float = Form(0.25),
    iou_thres_a: float = Form(0.45),
    conf_thres_b: float = Form(0.25),
    iou_thres_b: float = Form(0.45),
    db: Session = Depends(get_db)
):
    """
    执行两个模型的对比检测
    """
    try:
        # 检查模型是否存在
        model_a = model.get(db, id=model_a_id)
        model_b = model.get(db, id=model_b_id)
        
        if not model_a:
            raise HTTPException(status_code=404, detail="模型 A 未找到")
        if not model_b:
            raise HTTPException(status_code=404, detail="模型 B 未找到")

        # 读取上传的文件内容
        file_content = await file.read()
        
        # 准备参数
        parameters_a = {
            "conf_thres": conf_thres_a,
            "iou_thres": iou_thres_a
        }
        
        parameters_b = {
            "conf_thres": conf_thres_b,
            "iou_thres": iou_thres_b
        }
        
        # 创建新的文件对象用于检测A
        file_a = FastAPIUploadFile(
            filename=file.filename,
            file=io.BytesIO(file_content),
            size=len(file_content)
        )
        
        # 创建新的文件对象用于检测B
        file_b = FastAPIUploadFile(
            filename=file.filename,
            file=io.BytesIO(file_content),
            size=len(file_content)
        )
        
        # 并行执行两个模型的检测
        import asyncio
        result_a_data, execution_time_a = await run_single_detection(db, model_a_id, file_a, parameters_a)
        result_b_data, execution_time_b = await run_single_detection(db, model_b_id, file_b, parameters_b)
        
        # 注意：由于检测服务内部是异步的，时间计算可能不够精确
        # 为了更好的时间对比，我们可能需要修改检测服务以返回执行时间
        # 这里的时间是API调用时间，包含网络和数据库操作时间
        
        # 返回对比结果
        return {
            "model_a": {
                "model_info": {
                    "id": model_a.id,
                    "name": model_a.name,
                    "type": model_a.type,
                    "task": model_a.task
                },
                "result": result_a_data,
                "execution_time_ms": execution_time_a
            },
            "model_b": {
                "model_info": {
                    "id": model_b.id,
                    "name": model_b.name,
                    "type": model_b.type,
                    "task": model_b.task
                },
                "result": result_b_data,
                "execution_time_ms": execution_time_b
            },
            "comparison": {
                "execution_time_a": execution_time_a,
                "execution_time_b": execution_time_b,
                "faster_model": "model_a" if execution_time_a < execution_time_b else "model_b",
                "time_difference_ms": abs(execution_time_a - execution_time_b),
                "performance_improvement_percent": (
                    (abs(execution_time_a - execution_time_b) / max(execution_time_a, execution_time_b)) * 100
                ) if max(execution_time_a, execution_time_b) > 0 else 0
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对比检测失败: {str(e)}")