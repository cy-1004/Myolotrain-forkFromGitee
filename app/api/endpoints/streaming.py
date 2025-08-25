"""
流媒体API端点 - 提供RTSP和RTMP流处理功能
"""
import io
import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Form, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
import cv2
import numpy as np

from app.db.session import get_db
from app.services.stream_service import stream_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/create")
async def create_stream(
    source: str = Form(...),
    stream_type: str = Form("auto"),
    db: Session = Depends(get_db)
):
    """
    创建新的流
    
    Args:
        source: 流源地址 (RTSP URL, RTMP URL, 或摄像头ID)
        stream_type: 流类型 (rtsp, rtmp, webcam, auto)
    """
    try:
        # 验证流源格式
        if stream_type == "webcam":
            try:
                int(source)
            except ValueError:
                raise HTTPException(status_code=400, detail="摄像头ID必须是数字")
        elif stream_type in ["rtsp", "rtmp"] or stream_type == "auto":
            if not source.startswith(("rtsp://", "rtmp://", "http://", "https://")):
                if not source.isdigit():  # 允许数字作为摄像头ID
                    raise HTTPException(status_code=400, detail="无效的流地址格式")
        
        stream_id = stream_service.create_stream(source, stream_type)
        
        return {
            "success": True,
            "stream_id": stream_id,
            "message": f"流 {stream_id} 创建成功"
        }
        
    except Exception as e:
        logger.error(f"创建流失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建流失败: {str(e)}")

@router.post("/start/{stream_id}")
async def start_stream(stream_id: str):
    """启动指定流"""
    try:
        success = stream_service.start_stream(stream_id)
        
        if success:
            return {
                "success": True,
                "message": f"流 {stream_id} 启动成功"
            }
        else:
            raise HTTPException(status_code=400, detail=f"启动流 {stream_id} 失败")
            
    except Exception as e:
        logger.error(f"启动流失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动流失败: {str(e)}")

@router.post("/stop/{stream_id}")
async def stop_stream(stream_id: str):
    """停止指定流"""
    try:
        success = stream_service.stop_stream(stream_id)
        
        if success:
            return {
                "success": True,
                "message": f"流 {stream_id} 停止成功"
            }
        else:
            raise HTTPException(status_code=400, detail=f"停止流 {stream_id} 失败")
            
    except Exception as e:
        logger.error(f"停止流失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"停止流失败: {str(e)}")

@router.get("/info/{stream_id}")
async def get_stream_info(stream_id: str):
    """获取流信息"""
    try:
        info = stream_service.get_stream_info(stream_id)
        
        if info:
            return {
                "success": True,
                "info": info
            }
        else:
            raise HTTPException(status_code=404, detail=f"流 {stream_id} 不存在")
            
    except Exception as e:
        logger.error(f"获取流信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取流信息失败: {str(e)}")

@router.get("/list")
async def list_streams():
    """列出所有活动流"""
    try:
        streams = stream_service.list_streams()
        
        return {
            "success": True,
            "streams": streams,
            "count": len(streams)
        }
        
    except Exception as e:
        logger.error(f"列出流失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"列出流失败: {str(e)}")

@router.get("/frame/{stream_id}")
async def get_stream_frame(stream_id: str):
    """获取流的当前帧（JPEG格式）"""
    try:
        frame = stream_service.get_frame(stream_id)
        
        if frame is None:
            raise HTTPException(status_code=404, detail=f"无法获取流 {stream_id} 的帧")
        
        # 将帧编码为JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        
        return StreamingResponse(
            io.BytesIO(buffer.tobytes()),
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache"}
        )
        
    except Exception as e:
        logger.error(f"获取流帧失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取流帧失败: {str(e)}")

@router.get("/mjpeg/{stream_id}")
async def stream_mjpeg(stream_id: str):
    """提供MJPEG流"""
    try:
        def generate_frames():
            while True:
                frame = stream_service.get_frame(stream_id)
                if frame is None:
                    break
                
                # 编码为JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + 
                       buffer.tobytes() + b'\r\n')
        
        return StreamingResponse(
            generate_frames(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )
        
    except Exception as e:
        logger.error(f"MJPEG流失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"MJPEG流失败: {str(e)}")

@router.post("/test-connection")
async def test_stream_connection(
    source: str = Form(...),
    stream_type: str = Form("auto")
):
    """测试流连接"""
    try:
        # 创建临时VideoCapture测试连接
        if stream_type == "webcam" or source.isdigit():
            cap = cv2.VideoCapture(int(source))
        else:
            cap = cv2.VideoCapture(source)
            # 设置超时
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not cap.isOpened():
            return {
                "success": False,
                "message": "无法连接到流源"
            }
        
        # 尝试读取一帧
        ret, frame = cap.read()
        cap.release()
        
        if ret and frame is not None:
            height, width = frame.shape[:2]
            return {
                "success": True,
                "message": "连接测试成功",
                "info": {
                    "width": width,
                    "height": height,
                    "channels": frame.shape[2] if len(frame.shape) > 2 else 1
                }
            }
        else:
            return {
                "success": False,
                "message": "可以连接但无法读取帧"
            }
            
    except Exception as e:
        logger.error(f"测试流连接失败: {str(e)}")
        return {
            "success": False,
            "message": f"连接测试失败: {str(e)}"
        }

@router.get("/supported-formats")
async def get_supported_formats():
    """获取支持的流格式"""
    return {
        "success": True,
        "formats": {
            "rtsp": {
                "description": "实时流协议",
                "example": "rtsp://username:password@ip:port/path",
                "ports": [554, 8554]
            },
            "rtmp": {
                "description": "实时消息协议", 
                "example": "rtmp://server/app/stream",
                "ports": [1935]
            },
            "http": {
                "description": "HTTP视频流",
                "example": "http://ip:port/video.mjpg",
                "ports": [80, 8080]
            },
            "webcam": {
                "description": "本地摄像头",
                "example": "0, 1, 2...",
                "ports": []
            }
        }
    }