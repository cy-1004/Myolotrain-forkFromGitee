"""② 切帧：按时间间隔抽帧（复用 FrameExtractionService），并记录每帧的帧号与时间戳"""
import shutil

from app.core.paths import from_data_relative
from app.services.frame_extraction_service import FrameExtractionService
from app.services.pipeline import errors
from app.services.pipeline.common import load_videos, read_json, update_video, write_json
from app.services.pipeline.errors import PipelineError


def _resize_for(v, max_long_edge):
    w, h = v.get("width") or 0, v.get("height") or 0
    if not w or not h or max(w, h) <= max_long_edge:
        return None
    scale = max_long_edge / float(max(w, h))
    return (int(round(w * scale)) // 2 * 2, int(round(h * scale)) // 2 * 2)


def run(ctx):
    cfg = ctx.config.extract
    videos = load_videos(ctx)
    if not videos:
        raise PipelineError(errors.EXTRACT_FAILED, "没有可用的视频")
    done_videos = 0
    for vi, v in enumerate(videos):
        ctx.check_cancel()
        out_dir = ctx.path("frames", v["key"])
        manifest_path = out_dir / "frames.json"
        manifest = read_json(manifest_path)
        if manifest and manifest.get("complete"):
            done_videos += 1
            continue   # 幂等：已完整抽过
        if out_dir.exists():
            shutil.rmtree(out_dir)   # 上次中途中断留下的半截结果

        records = []
        expected = max(1, int((v.get("duration") or 1) / cfg.interval_seconds))

        def on_frame(path, frame_index, ts):
            records.append({"file": path.name, "frame_index": int(frame_index), "ts": round(float(ts), 3)})
            if len(records) % 20 == 0:
                ctx.progress((vi + min(1.0, len(records) / expected)) / len(videos),
                             detail={"video": v["key"], "frames": len(records)})

        opts = v["options"]
        try:
            result = FrameExtractionService.extract_from_video(
                str(from_data_relative(v["rel_path"])), f"{v['key']}.mp4", out_dir,
                method="time", interval_seconds=cfg.interval_seconds,
                skip_start=opts.get("skip_start", cfg.skip_start), skip_end=opts.get("skip_end", cfg.skip_end),
                naming_template="{video_name}_{index:05d}", image_format="jpg", jpg_quality=95,
                resize=_resize_for(v, cfg.max_long_edge),
                on_frame=on_frame, should_stop=ctx.is_cancel_requested,
            )
        except Exception as e:
            update_video(ctx, v["id"], status="failed", error=f"抽帧失败: {e}")
            ctx.warn(f"视频 {v['key']} 抽帧失败: {e}", data={"video": v["key"]})
            continue
        ctx.check_cancel(force=True)
        if not records:
            update_video(ctx, v["id"], status="failed", error="没有抽出任何帧（视频过短或跳过的时长过长）")
            ctx.warn(f"视频 {v['key']} 没有抽出任何帧", data={"video": v["key"]})
            continue
        write_json(manifest_path, {"complete": True, "frames": records, "fps": result.get("fps")})
        update_video(ctx, v["id"], stats={"extracted": len(records)})
        done_videos += 1
        ctx.progress((vi + 1) / len(videos), detail={"video": v["key"], "frames": len(records)}, force=True)

    if done_videos == 0:
        raise PipelineError(errors.EXTRACT_FAILED, "所有视频都抽帧失败")
