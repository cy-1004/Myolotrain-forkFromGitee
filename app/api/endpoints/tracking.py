"""
目标追踪 API 端点 - 提供基于自注意力机制的目标追踪功能
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.services.tracking_service import tracking_service

# 设置日志记录器
logger = logging.getLogger(__name__)

router = APIRouter()

# 视频追踪功能已移除，仅保留摄像头追踪功能


@router.post("/track-frame")
async def track_frame(
    image: UploadFile = File(...),
    detections: str = Form("[]"),
    target_class_id: Optional[int] = Form(None),
    enable_tracking: bool = Form(False),
    cancel_tracking: bool = Form(False)
):
    """
    追踪单帧中的目标 - 不保存任何本地文件

    参数:
        image: 输入帧
        detections: 检测结果列表，JSON格式
        target_class_id: 要追踪的目标类别ID
        enable_tracking: 是否启用追踪特定类别
        cancel_tracking: 是否取消追踪
    """
    try:
        # 解析检测结果
        detections_list = json.loads(detections)

        # 验证检测结果格式
        if not isinstance(detections_list, list):
            raise HTTPException(status_code=400, detail="检测结果必须是列表")

        # 确保每个检测都有必要的字段
        for i, det in enumerate(detections_list):
            if not isinstance(det, dict):
                raise HTTPException(status_code=400, detail=f"检测结果 #{i} 必须是字典")

            # 确保必要的字段存在
            if 'bbox' not in det:
                raise HTTPException(status_code=400, detail=f"检测结果 #{i} 缺少 'bbox' 字段")
            if 'class_id' not in det:
                raise HTTPException(status_code=400, detail=f"检测结果 #{i} 缺少 'class_id' 字段")
            if 'confidence' not in det:
                raise HTTPException(status_code=400, detail=f"检测结果 #{i} 缺少 'confidence' 字段")

        # 直接读取上传的图像数据，不保存到本地
        import cv2
        import numpy as np

        # 读取图像数据（确保不保存到本地文件）
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="无法读取图像")

        # 追踪目标 - 传递追踪参数
        tracks = tracking_service.track_frame(
            frame,
            detections_list,
            target_class_id=target_class_id,
            enable_tracking=enable_tracking,
            cancel_tracking=cancel_tracking
        )

        # 确保返回一致的格式
        return {
            "tracks": tracks,
            "tracking_status": {
                "is_tracking": enable_tracking and not cancel_tracking,
                "target_class_id": target_class_id if enable_tracking and not cancel_tracking else None
            }
        }

    except Exception as e:
        logger.error(f"帧追踪失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"帧追踪失败: {str(e)}")


@router.post("/reset-tracker")
async def reset_tracker():
    """重置追踪器状态"""
    try:
        tracking_service.reset_tracker()
        return {"message": "追踪器已重置"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置追踪器失败: {str(e)}")


@router.post("/set-single-target")
async def set_single_target(
    enable: bool = Form(True),
    target_id: Optional[int] = Form(None),
    target_class_id: Optional[int] = Form(None)
):
    """
    设置单目标追踪模式

    参数:
        enable: 是否启用单目标模式
        target_id: 目标ID
        target_class_id: 目标类别ID
    """
    try:
        # 记录请求参数
        logger.info(f"设置单目标追踪模式: enable={enable}, target_id={target_id}, target_class_id={target_class_id}")

        # 调用服务方法
        tracking_service.set_single_target_mode(enable, target_id, target_class_id)

        # 返回结果
        return {
            "message": f"单目标模式已{'启用' if enable else '禁用'}",
            "target_id": target_id if enable else None,
            "target_class_id": target_class_id if enable else None
        }

    except Exception as e:
        logger.error(f"设置单目标模式失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"设置单目标模式失败: {str(e)}")
