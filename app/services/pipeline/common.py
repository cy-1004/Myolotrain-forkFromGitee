"""阶段之间共用的小工具：视频列表、清单文件读写、文件链接"""
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm.attributes import flag_modified

from app.models.pipeline import PipelineVideo


def load_videos(ctx, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """取出 Run 的视频（脱离会话的普通 dict），默认只含 status=ok 的视频"""
    with ctx.session() as db:
        rows = db.query(PipelineVideo).filter(PipelineVideo.run_id == ctx.run_id).order_by(PipelineVideo.position).all()
        return [{
            "id": v.id, "key": v.key, "class_name": v.class_name, "class_id": v.class_id,
            "class_names": video_class_names(v),
            "expected_instances": v.expected_instances, "options": dict(v.options or {}),
            "rel_path": v.rel_path, "original_filename": v.original_filename, "fps": v.fps,
            "frame_count": v.frame_count, "duration": v.duration, "width": v.width, "height": v.height,
            "status": v.status, "stats": dict(v.stats or {}),
        } for v in rows if include_inactive or v.status == "ok"]


def video_class_names(video: PipelineVideo) -> List[str]:
    """视频声明的全部类别（老数据只有 class_name）"""
    return list(video.class_names or [video.class_name])


def update_video(ctx, video_id, stats: Dict[str, Any] = None, **fields):
    """更新视频字段；stats 为合并更新（只覆盖给出的键）"""
    with ctx.session() as db:
        v = db.query(PipelineVideo).filter(PipelineVideo.id == video_id).one()
        for k, val in fields.items():
            setattr(v, k, val)
        if stats:
            merged = dict(v.stats or {})
            merged.update(stats)
            v.stats = merged
            flag_modified(v, "stats")


def write_json(path: Path, data: Any):
    """先写临时文件再改名，进程中途被杀也不会留下写了一半的清单"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def link_or_copy(src: Path, dst: Path):
    """优先硬链接（同一文件系统上不占额外空间），失败再复制"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def frame_name(video_key: str, frame_index: int) -> str:
    """清洗后进入标注项目的帧文件名：<视频key>_<帧号>.jpg（全局唯一，可反查来源视频与帧位置）"""
    return f"{video_key}_{frame_index:06d}.jpg"
