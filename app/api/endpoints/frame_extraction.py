"""
视频抽帧与自动命名 API 端点

面向数据集构建：批量上传视频 -> 按帧/时间间隔抽帧 -> 结构化命名 -> 输出图像库，
可直接下载 ZIP，或一键送入在线标注创建标注项目。
"""
import json
import logging
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.annotation_service import AnnotationService
from app.services.frame_extraction_service import frame_extraction_service
from app.schemas.annotation import AnnotationProjectCreate
from app.utils.file_utils import save_upload_file_temp

logger = logging.getLogger(__name__)

router = APIRouter()

# 临时视频目录 & 抽帧输出目录
TEMP_DIR = Path(settings.TEMP_DIR) / "frame_extraction"
OUTPUT_ROOT = Path(settings.STATIC_DIR) / "extracted_frames"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_ROOT, exist_ok=True)


def _task_dir(task_id: str) -> Path:
    return OUTPUT_ROOT / task_id


@router.post("/validate-template")
async def validate_template(template: str = Body(..., embed=True)):
    """校验命名模板是否合法（前端实时反馈）。"""
    ok, msg = frame_extraction_service.validate_template(template)
    return {"valid": ok, "message": msg}


@router.post("/extract")
async def extract(
    background_tasks: BackgroundTasks,
    videos: List[UploadFile] = File(...),
    method: str = Form("time"),
    interval_seconds: float = Form(1.0),
    interval_frames: int = Form(5),
    skip_start: float = Form(0.0),
    skip_end: float = Form(0.0),
    naming_template: str = Form("{video_name}_{index:05d}"),
    image_format: str = Form("jpg"),
    jpg_quality: int = Form(95),
    resize_width: Optional[int] = Form(None),
    resize_height: Optional[int] = Form(None),
    subfolder: bool = Form(False),
    db: Session = Depends(get_db),
):
    """批量抽帧（后台任务）。返回 task_id 供轮询状态。"""
    # 校验命名模板
    valid, msg = frame_extraction_service.validate_template(naming_template)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    if image_format.lower() not in ("jpg", "jpeg", "png"):
        raise HTTPException(status_code=400, detail="图像格式仅支持 jpg / png")

    # 过滤出受支持的视频并落盘到临时目录
    saved_videos = []
    for video in videos:
        if not video.filename or not frame_extraction_service.is_supported_video(video.filename):
            logger.warning(f"跳过不支持的文件: {video.filename}")
            continue
        temp_path = await save_upload_file_temp(video, TEMP_DIR)
        saved_videos.append({"path": str(temp_path), "name": os.path.basename(video.filename)})

    if not saved_videos:
        raise HTTPException(status_code=400, detail="没有可处理的视频文件（支持 .mp4/.avi/.mov/.mkv）")

    task_id = str(uuid.uuid4())
    output_dir = _task_dir(task_id)
    os.makedirs(output_dir, exist_ok=True)
    status_file = output_dir / "status.json"

    resize = None
    if resize_width and resize_height:
        resize = (int(resize_width), int(resize_height))

    kwargs = dict(
        method=method,
        interval_seconds=interval_seconds,
        interval_frames=interval_frames,
        skip_start=skip_start,
        skip_end=skip_end,
        naming_template=naming_template,
        image_format=image_format,
        jpg_quality=jpg_quality,
        resize=resize,
        subfolder=subfolder,
    )

    background_tasks.add_task(
        frame_extraction_service.run_batch,
        saved_videos,
        output_dir,
        status_file,
        **kwargs,
    )

    return {
        "success": True,
        "message": "抽帧任务已启动",
        "task_id": task_id,
        "video_count": len(saved_videos),
    }


@router.get("/status/{task_id}")
async def get_status(task_id: str):
    """获取抽帧任务状态与进度。"""
    output_dir = _task_dir(task_id)
    status_file = output_dir / "status.json"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="任务不存在")
    if not status_file.exists():
        return {"status": "in_progress", "total_videos": 0, "processed_videos": 0, "total_frames": 0}
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # 后台正在写入，返回处理中占位
        return {"status": "processing"}


@router.get("/frames/{task_id}")
async def list_frames(task_id: str, limit: int = 60):
    """列出已抽取的帧文件名（相对任务目录），供前端预览画廊。"""
    output_dir = _task_dir(task_id)
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="任务不存在")
    images = frame_extraction_service.collect_images(output_dir)
    rels = [str(p.relative_to(output_dir)).replace("\\", "/") for p in images]
    rels.sort()
    return {"total": len(rels), "frames": rels[:limit]}


@router.get("/frame/{task_id}/{rel_path:path}")
async def get_frame(task_id: str, rel_path: str):
    """获取单帧图像用于预览。"""
    output_dir = _task_dir(task_id)
    # 防止路径穿越
    file_path = (output_dir / rel_path).resolve()
    if not str(file_path).startswith(str(output_dir.resolve())) or not file_path.exists():
        raise HTTPException(status_code=404, detail="帧不存在")
    return FileResponse(path=str(file_path))


@router.get("/download/{task_id}")
async def download(task_id: str):
    """打包下载全部抽取的帧为 ZIP。"""
    output_dir = _task_dir(task_id)
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="任务不存在")

    zip_path = OUTPUT_ROOT / f"frames_{task_id}.zip"
    if zip_path.exists():
        zip_path.unlink()

    images = frame_extraction_service.collect_images(output_dir)
    if not images:
        raise HTTPException(status_code=400, detail="没有可下载的帧")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for img in images:
            zipf.write(img, str(img.relative_to(output_dir)))

    return FileResponse(path=str(zip_path), media_type="application/zip", filename=f"frames_{task_id}.zip")


@router.post("/to-annotation/{task_id}")
async def to_annotation(
    task_id: str,
    name: str = Body(...),
    description: str = Body(""),
    project_type: str = Body("detection"),
    classes: List[str] = Body(...),
    db: Session = Depends(get_db),
):
    """一键将抽帧结果送入在线标注：把所有帧汇总到扁平目录并创建标注项目。"""
    output_dir = _task_dir(task_id)
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="任务不存在")

    images = frame_extraction_service.collect_images(output_dir)
    if not images:
        raise HTTPException(status_code=400, detail="没有可用于标注的帧")

    # 标注项目需要一个扁平的图像目录；若原本按视频建了子目录，这里汇总到 _annotation_images
    flat_dir = output_dir / "_annotation_images"
    os.makedirs(flat_dir, exist_ok=True)
    for img in images:
        if img.parent == flat_dir:
            continue
        dest = flat_dir / img.name
        counter = 1
        while dest.exists():
            dest = flat_dir / f"{img.stem}_dup{counter}{img.suffix}"
            counter += 1
        shutil.copy2(img, dest)

    project_data = AnnotationProjectCreate(
        name=name,
        description=description or f"来自视频抽帧任务 {task_id}",
        project_type=project_type,
        classes=classes,
        image_directory=str(flat_dir.resolve()),
    )
    service = AnnotationService()
    project = service.create_project(db=db, project_data=project_data)
    return {
        "success": True,
        "message": "已创建标注项目",
        "project_id": str(project.id),
        "image_count": len(images),
    }


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除任务缓存（帧目录 + ZIP）。"""
    output_dir = _task_dir(task_id)
    zip_path = OUTPUT_ROOT / f"frames_{task_id}.zip"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        shutil.rmtree(output_dir)
        if zip_path.exists():
            zip_path.unlink()
        return {"success": True, "message": "缓存已删除"}
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"删除缓存失败: {e}")
