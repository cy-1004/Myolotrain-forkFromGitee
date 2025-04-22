"""
视频处理 API 端点 - 提供视频处理和分析功能
"""
import os
import json
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.db.session import get_db
from app.core.config import settings
from app.services.opencv_service import opencv_service
from app.utils.file_utils import save_upload_file_temp, get_temp_file_path

router = APIRouter()

# 临时文件目录
TEMP_DIR = Path(settings.TEMP_DIR) / "video"
os.makedirs(TEMP_DIR, exist_ok=True)

# 处理后的视频目录
PROCESSED_DIR = Path(settings.STATIC_DIR) / "processed_videos"
os.makedirs(PROCESSED_DIR, exist_ok=True)

# 提取的帧目录
FRAMES_DIR = Path(settings.STATIC_DIR) / "video_frames"
os.makedirs(FRAMES_DIR, exist_ok=True)

# 视频数据集目录
VIDEO_DATASETS_DIR = Path(settings.STATIC_DIR) / "video_datasets"
os.makedirs(VIDEO_DATASETS_DIR, exist_ok=True)


@router.post("/info")
async def get_video_info(
    video: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """获取视频信息"""
    try:
        # 保存上传的视频
        temp_file = await save_upload_file_temp(video, TEMP_DIR)
        
        # 获取视频信息
        video_info = opencv_service.get_video_info(temp_file)
        
        # 添加文件信息
        video_info["filename"] = video.filename
        video_info["size"] = os.path.getsize(temp_file)
        video_info["size_mb"] = round(video_info["size"] / (1024 * 1024), 2)
        
        return video_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取视频信息失败: {str(e)}")
    finally:
        # 清理临时文件
        if 'temp_file' in locals():
            try:
                os.remove(temp_file)
            except:
                pass


@router.post("/extract-frames")
async def extract_frames(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    interval: float = Form(1.0),
    max_frames: Optional[int] = Form(None),
    resize_width: Optional[int] = Form(None),
    resize_height: Optional[int] = Form(None),
    start_time: float = Form(0.0),
    end_time: Optional[float] = Form(None),
    db: Session = Depends(get_db)
):
    """从视频中提取帧"""
    try:
        # 保存上传的视频
        temp_file = await save_upload_file_temp(video, TEMP_DIR)
        
        # 创建输出目录
        extraction_id = str(uuid.uuid4())
        output_dir = FRAMES_DIR / extraction_id
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置调整大小参数
        resize = None
        if resize_width is not None and resize_height is not None:
            resize = (resize_width, resize_height)
        
        # 在后台任务中提取帧
        def extract_frames_task():
            try:
                result = opencv_service.extract_frames(
                    video_path=temp_file,
                    output_dir=output_dir,
                    interval=interval,
                    max_frames=max_frames,
                    resize=resize,
                    start_time=start_time,
                    end_time=end_time
                )
                
                # 保存结果信息
                with open(output_dir / "info.json", "w") as f:
                    json.dump({
                        "video_filename": video.filename,
                        "extraction_id": extraction_id,
                        "parameters": {
                            "interval": interval,
                            "max_frames": max_frames,
                            "resize": resize,
                            "start_time": start_time,
                            "end_time": end_time
                        },
                        "result": result
                    }, f, indent=2)
                
                # 清理临时文件
                try:
                    os.remove(temp_file)
                except:
                    pass
            except Exception as e:
                # 记录错误
                with open(output_dir / "error.txt", "w") as f:
                    f.write(f"提取帧失败: {str(e)}")
                
                # 清理临时文件
                try:
                    os.remove(temp_file)
                except:
                    pass
        
        # 添加后台任务
        background_tasks.add_task(extract_frames_task)
        
        # 返回任务信息
        return {
            "success": True,
            "message": "帧提取任务已启动",
            "extraction_id": extraction_id,
            "output_dir": str(output_dir)
        }
    except Exception as e:
        # 清理临时文件
        if 'temp_file' in locals():
            try:
                os.remove(temp_file)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"启动帧提取任务失败: {str(e)}")


@router.get("/extraction-status/{extraction_id}")
async def get_extraction_status(extraction_id: str):
    """获取帧提取任务状态"""
    output_dir = FRAMES_DIR / extraction_id
    
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="提取任务不存在")
    
    # 检查是否有错误
    error_file = output_dir / "error.txt"
    if error_file.exists():
        with open(error_file, "r") as f:
            error_message = f.read()
        return {
            "status": "failed",
            "error": error_message
        }
    
    # 检查是否完成
    info_file = output_dir / "info.json"
    if info_file.exists():
        with open(info_file, "r") as f:
            info = json.load(f)
        return {
            "status": "completed",
            "info": info
        }
    
    # 任务仍在进行中
    return {
        "status": "in_progress"
    }


@router.get("/frames/{extraction_id}/{filename}")
async def get_frame(extraction_id: str, filename: str):
    """获取提取的帧"""
    file_path = FRAMES_DIR / extraction_id / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="帧不存在")
    
    return FileResponse(path=file_path)


@router.post("/detect-scenes")
async def detect_scenes(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    threshold: float = Form(30.0),
    min_scene_length: int = Form(15),
    db: Session = Depends(get_db)
):
    """检测视频场景变化"""
    try:
        # 保存上传的视频
        temp_file = await save_upload_file_temp(video, TEMP_DIR)
        
        # 创建任务ID
        task_id = str(uuid.uuid4())
        output_dir = PROCESSED_DIR / f"scenes_{task_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        # 在后台任务中检测场景
        def detect_scenes_task():
            try:
                result = opencv_service.detect_scenes(
                    video_path=temp_file,
                    threshold=threshold,
                    min_scene_length=min_scene_length
                )
                
                # 保存结果信息
                with open(output_dir / "info.json", "w") as f:
                    json.dump({
                        "video_filename": video.filename,
                        "task_id": task_id,
                        "parameters": {
                            "threshold": threshold,
                            "min_scene_length": min_scene_length
                        },
                        "result": result
                    }, f, indent=2)
                
                # 清理临时文件
                try:
                    os.remove(temp_file)
                except:
                    pass
            except Exception as e:
                # 记录错误
                with open(output_dir / "error.txt", "w") as f:
                    f.write(f"检测场景失败: {str(e)}")
                
                # 清理临时文件
                try:
                    os.remove(temp_file)
                except:
                    pass
        
        # 添加后台任务
        background_tasks.add_task(detect_scenes_task)
        
        # 返回任务信息
        return {
            "success": True,
            "message": "场景检测任务已启动",
            "task_id": task_id,
            "output_dir": str(output_dir)
        }
    except Exception as e:
        # 清理临时文件
        if 'temp_file' in locals():
            try:
                os.remove(temp_file)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"启动场景检测任务失败: {str(e)}")


@router.get("/scene-detection-status/{task_id}")
async def get_scene_detection_status(task_id: str):
    """获取场景检测任务状态"""
    output_dir = PROCESSED_DIR / f"scenes_{task_id}"
    
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="场景检测任务不存在")
    
    # 检查是否有错误
    error_file = output_dir / "error.txt"
    if error_file.exists():
        with open(error_file, "r") as f:
            error_message = f.read()
        return {
            "status": "failed",
            "error": error_message
        }
    
    # 检查是否完成
    info_file = output_dir / "info.json"
    if info_file.exists():
        with open(info_file, "r") as f:
            info = json.load(f)
        return {
            "status": "completed",
            "info": info
        }
    
    # 任务仍在进行中
    return {
        "status": "in_progress"
    }


@router.post("/detect-motion")
async def detect_motion(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    sensitivity: float = Form(20.0),
    blur_size: int = Form(21),
    min_area: int = Form(500),
    db: Session = Depends(get_db)
):
    """检测视频中的运动"""
    try:
        # 保存上传的视频
        temp_file = await save_upload_file_temp(video, TEMP_DIR)
        
        # 创建任务ID
        task_id = str(uuid.uuid4())
        output_dir = PROCESSED_DIR / f"motion_{task_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        # 在后台任务中检测运动
        def detect_motion_task():
            try:
                result = opencv_service.detect_motion(
                    video_path=temp_file,
                    sensitivity=sensitivity,
                    blur_size=blur_size,
                    min_area=min_area
                )
                
                # 保存结果信息
                with open(output_dir / "info.json", "w") as f:
                    json.dump({
                        "video_filename": video.filename,
                        "task_id": task_id,
                        "parameters": {
                            "sensitivity": sensitivity,
                            "blur_size": blur_size,
                            "min_area": min_area
                        },
                        "result": result
                    }, f, indent=2)
                
                # 清理临时文件
                try:
                    os.remove(temp_file)
                except:
                    pass
            except Exception as e:
                # 记录错误
                with open(output_dir / "error.txt", "w") as f:
                    f.write(f"检测运动失败: {str(e)}")
                
                # 清理临时文件
                try:
                    os.remove(temp_file)
                except:
                    pass
        
        # 添加后台任务
        background_tasks.add_task(detect_motion_task)
        
        # 返回任务信息
        return {
            "success": True,
            "message": "运动检测任务已启动",
            "task_id": task_id,
            "output_dir": str(output_dir)
        }
    except Exception as e:
        # 清理临时文件
        if 'temp_file' in locals():
            try:
                os.remove(temp_file)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"启动运动检测任务失败: {str(e)}")


@router.get("/motion-detection-status/{task_id}")
async def get_motion_detection_status(task_id: str):
    """获取运动检测任务状态"""
    output_dir = PROCESSED_DIR / f"motion_{task_id}"
    
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="运动检测任务不存在")
    
    # 检查是否有错误
    error_file = output_dir / "error.txt"
    if error_file.exists():
        with open(error_file, "r") as f:
            error_message = f.read()
        return {
            "status": "failed",
            "error": error_message
        }
    
    # 检查是否完成
    info_file = output_dir / "info.json"
    if info_file.exists():
        with open(info_file, "r") as f:
            info = json.load(f)
        return {
            "status": "completed",
            "info": info
        }
    
    # 任务仍在进行中
    return {
        "status": "in_progress"
    }


@router.post("/create-dataset")
async def create_dataset_from_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    dataset_name: str = Form(...),
    extraction_method: str = Form("interval"),
    interval: float = Form(1.0),
    scene_threshold: float = Form(30.0),
    motion_sensitivity: float = Form(20.0),
    max_frames: Optional[int] = Form(None),
    resize_width: Optional[int] = Form(None),
    resize_height: Optional[int] = Form(None),
    train_ratio: float = Form(0.7),
    val_ratio: float = Form(0.2),
    test_ratio: float = Form(0.1),
    db: Session = Depends(get_db)
):
    """从视频创建数据集"""
    try:
        # 验证分割比例
        if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.001:
            raise HTTPException(status_code=400, detail="分割比例总和必须为1.0")
        
        # 保存上传的视频
        temp_file = await save_upload_file_temp(video, TEMP_DIR)
        
        # 创建数据集目录
        dataset_id = str(uuid.uuid4())
        output_dir = VIDEO_DATASETS_DIR / dataset_id
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置调整大小参数
        resize = None
        if resize_width is not None and resize_height is not None:
            resize = (resize_width, resize_height)
        
        # 设置分割比例
        split_ratio = {
            "train": train_ratio,
            "val": val_ratio,
            "test": test_ratio
        }
        
        # 在后台任务中创建数据集
        def create_dataset_task():
            try:
                result = opencv_service.create_dataset_from_video(
                    video_path=temp_file,
                    output_dir=output_dir,
                    extraction_method=extraction_method,
                    interval=interval,
                    scene_threshold=scene_threshold,
                    motion_sensitivity=motion_sensitivity,
                    max_frames=max_frames,
                    resize=resize,
                    split_ratio=split_ratio
                )
                
                # 保存结果信息
                with open(output_dir / "info.json", "w") as f:
                    json.dump({
                        "dataset_name": dataset_name,
                        "video_filename": video.filename,
                        "dataset_id": dataset_id,
                        "parameters": {
                            "extraction_method": extraction_method,
                            "interval": interval,
                            "scene_threshold": scene_threshold,
                            "motion_sensitivity": motion_sensitivity,
                            "max_frames": max_frames,
                            "resize": resize,
                            "split_ratio": split_ratio
                        },
                        "result": result
                    }, f, indent=2)
                
                # 清理临时文件
                try:
                    os.remove(temp_file)
                except:
                    pass
                
                # 导入数据集到系统
                from app.services.dataset_service import import_external_dataset
                try:
                    # 导入数据集
                    db_dataset = import_external_dataset(
                        db=db,
                        name=dataset_name,
                        description=f"从视频 {video.filename} 创建的数据集",
                        path=str(output_dir)
                    )
                    
                    # 更新信息文件
                    with open(output_dir / "info.json", "r") as f:
                        info = json.load(f)
                    
                    info["dataset_db_id"] = str(db_dataset.id)
                    info["import_status"] = "success"
                    
                    with open(output_dir / "info.json", "w") as f:
                        json.dump(info, f, indent=2)
                except Exception as e:
                    # 记录导入错误
                    with open(output_dir / "import_error.txt", "w") as f:
                        f.write(f"导入数据集失败: {str(e)}")
                    
                    # 更新信息文件
                    with open(output_dir / "info.json", "r") as f:
                        info = json.load(f)
                    
                    info["import_status"] = "failed"
                    info["import_error"] = str(e)
                    
                    with open(output_dir / "info.json", "w") as f:
                        json.dump(info, f, indent=2)
            except Exception as e:
                # 记录错误
                with open(output_dir / "error.txt", "w") as f:
                    f.write(f"创建数据集失败: {str(e)}")
                
                # 清理临时文件
                try:
                    os.remove(temp_file)
                except:
                    pass
        
        # 添加后台任务
        background_tasks.add_task(create_dataset_task)
        
        # 返回任务信息
        return {
            "success": True,
            "message": "数据集创建任务已启动",
            "dataset_id": dataset_id,
            "output_dir": str(output_dir)
        }
    except Exception as e:
        # 清理临时文件
        if 'temp_file' in locals():
            try:
                os.remove(temp_file)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"启动数据集创建任务失败: {str(e)}")


@router.get("/dataset-creation-status/{dataset_id}")
async def get_dataset_creation_status(dataset_id: str):
    """获取数据集创建任务状态"""
    output_dir = VIDEO_DATASETS_DIR / dataset_id
    
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="数据集创建任务不存在")
    
    # 检查是否有错误
    error_file = output_dir / "error.txt"
    if error_file.exists():
        with open(error_file, "r") as f:
            error_message = f.read()
        return {
            "status": "failed",
            "error": error_message
        }
    
    # 检查是否完成
    info_file = output_dir / "info.json"
    if info_file.exists():
        with open(info_file, "r") as f:
            info = json.load(f)
        
        # 检查导入状态
        import_error_file = output_dir / "import_error.txt"
        if import_error_file.exists():
            with open(import_error_file, "r") as f:
                import_error = f.read()
            return {
                "status": "completed_with_import_error",
                "info": info,
                "import_error": import_error
            }
        
        # 检查是否有导入状态
        if "import_status" in info:
            if info["import_status"] == "success":
                return {
                    "status": "completed_and_imported",
                    "info": info
                }
            else:
                return {
                    "status": "completed_but_import_failed",
                    "info": info
                }
        
        return {
            "status": "completed",
            "info": info
        }
    
    # 任务仍在进行中
    return {
        "status": "in_progress"
    }
