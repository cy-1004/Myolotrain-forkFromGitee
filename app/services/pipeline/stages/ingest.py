"""① 接收：确认视频文件就位并探测元数据（帧率、帧数、时长、分辨率）"""
import cv2

from app.core.config import settings
from app.core.paths import from_data_relative
from app.services.pipeline import errors
from app.services.pipeline.common import load_videos, update_video
from app.services.pipeline.errors import PipelineError


def probe_video(path) -> dict:
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError("无法打开视频（文件损坏或编码格式不支持）")
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        ok, _ = cap.read()
        if not ok or fps <= 0 or frames <= 0:
            raise ValueError("视频没有可读取的帧或帧率无效")
        return {"fps": float(fps), "frame_count": frames, "duration": round(frames / fps, 3),
                "width": width, "height": height}
    finally:
        cap.release()


def run(ctx):
    videos = load_videos(ctx, include_inactive=True)
    usable = 0
    for i, v in enumerate(videos):
        ctx.check_cancel()
        if v["status"] == "excluded":
            continue
        try:
            info = probe_video(from_data_relative(v["rel_path"]))
            if info["duration"] > settings.PIPELINE_MAX_VIDEO_SECONDS:
                raise ValueError(f"视频时长 {info['duration']:.0f}s 超过上限 {settings.PIPELINE_MAX_VIDEO_SECONDS}s")
            update_video(ctx, v["id"], status="ok", error=None, **info)
            usable += 1
        except Exception as e:
            update_video(ctx, v["id"], status="failed", error=str(e))
            ctx.warn(f"视频 {v['key']}（{v['original_filename']}）无法使用: {e}", data={"video": v["key"]})
        ctx.progress((i + 1) / len(videos))
    if usable == 0:
        raise PipelineError(errors.EXTRACT_FAILED, "所有视频都无法读取，请检查文件格式（支持 mp4/mov/avi/mkv 等常见格式）")
