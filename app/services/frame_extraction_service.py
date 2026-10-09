"""
视频抽帧与自动命名服务

面向数据集构建场景：将一个或多个视频批量抽帧切片，按结构化模板重命名后输出到指定目录，
为后续在线标注提供规整的原始图像库。与 opencv_service.extract_frames 的区别是本服务
支持批量视频、命名模板（{video_name}/{index}/{timestamp}）、按视频建子目录以及损坏视频跳过。
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2

logger = logging.getLogger(__name__)

# 支持的视频扩展名（小写，带点）
SUPPORTED_VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv"}
# 命名模板中会被替换掉的图像扩展名，避免模板自带扩展名与所选格式冲突
_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


class FrameExtractionService:
    """批量视频抽帧 + 自动命名"""

    @staticmethod
    def is_supported_video(filename: str) -> bool:
        return Path(filename).suffix.lower() in SUPPORTED_VIDEO_EXTS

    @staticmethod
    def render_filename(
        template: str,
        video_name: str,
        index: int,
        timestamp: float,
        image_format: str,
    ) -> str:
        """按模板渲染文件名。

        模板支持 Python 格式化语法，例如 ``{video_name}_{index:05d}`` 或 ``{video_name}_{timestamp:.2f}s``。
        无论模板是否自带扩展名，最终都会统一成所选的 image_format 扩展名，避免格式选择与模板不一致。
        """
        rendered = template.format(
            video_name=video_name,
            index=index,
            timestamp=timestamp,
        )
        # 去掉模板可能自带的图像扩展名，统一用所选格式
        stem, ext = os.path.splitext(rendered)
        if ext.lower() in _IMAGE_EXTS:
            rendered = stem
        # 清理跨平台非法字符，避免建目录/写文件失败
        for ch in '<>:"/\\|?*':
            rendered = rendered.replace(ch, "_")
        return f"{rendered}.{image_format.lower()}"

    @staticmethod
    def validate_template(template: str) -> Tuple[bool, str]:
        """校验命名模板是否可用，返回 (是否合法, 错误信息)。"""
        try:
            FrameExtractionService.render_filename(template, "sample_video", 1, 1.5, "jpg")
            return True, ""
        except (KeyError, ValueError, IndexError) as e:
            return False, f"命名模板不合法: {e}。仅支持变量 {{video_name}}、{{index}}、{{timestamp}}"

    @classmethod
    def extract_from_video(
        cls,
        video_path: str,
        original_name: str,
        output_dir: Path,
        *,
        method: str = "time",
        interval_seconds: float = 1.0,
        interval_frames: int = 5,
        skip_start: float = 0.0,
        skip_end: float = 0.0,
        naming_template: str = "{video_name}_{index:05d}",
        image_format: str = "jpg",
        jpg_quality: int = 95,
        resize: Optional[Tuple[int, int]] = None,
        subfolder: bool = False,
        progress_cb=None,
    ) -> Dict[str, Any]:
        """对单个视频抽帧。返回该视频的处理结果。抛出异常表示该视频处理失败（由调用方捕获记录）。"""
        video_stem = Path(original_name).stem

        # 目标目录：扁平则直接写 output_dir，按视频建子目录则写 output_dir/<video_stem>
        target_dir = output_dir / video_stem if subfolder else output_dir
        os.makedirs(target_dir, exist_ok=True)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"无法打开视频（可能已损坏或格式不支持）: {original_name}")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if not fps or fps <= 0:
                raise ValueError(f"无法读取视频帧率: {original_name}")
            duration = frame_count / fps if fps > 0 else 0

            # 计算抽帧步长（帧数）
            if method == "frame":
                step = max(1, int(interval_frames))
            else:  # time
                step = max(1, int(round(interval_seconds * fps)))

            start_frame = max(0, int(skip_start * fps))
            end_frame = frame_count - int(skip_end * fps)
            if end_frame <= start_frame:
                end_frame = frame_count

            extracted = 0
            index = 1
            frame_index = start_frame
            total_expected = max(1, (end_frame - start_frame) // step)

            while frame_index < end_frame:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ret, frame = cap.read()
                if not ret:
                    break

                if resize is not None:
                    frame = cv2.resize(frame, resize)

                timestamp = frame_index / fps
                filename = cls.render_filename(
                    naming_template, video_stem, index, timestamp, image_format
                )
                output_path = cls._resolve_collision(target_dir / filename)

                # 走 unicode 安全写出：中文视频名会派生出中文帧文件名，
                # 而 cv2.imwrite 在 Windows 上对中文路径直接失败
                from app.services.opencv_service import opencv_service
                if image_format.lower() in ("jpg", "jpeg"):
                    ok = opencv_service.imwrite_unicode(
                        output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, int(jpg_quality)]
                    )
                else:
                    ok = opencv_service.imwrite_unicode(output_path, frame)
                if not ok:
                    raise IOError(f"写入图像失败: {output_path}")

                extracted += 1
                index += 1
                frame_index += step

                if progress_cb and extracted % 10 == 0:
                    progress_cb(min(99, int(extracted / total_expected * 100)), extracted)

            return {
                "video": original_name,
                "status": "success",
                "extracted_frames": extracted,
                "fps": round(fps, 2),
                "duration": round(duration, 2),
                "frame_count": frame_count,
            }
        finally:
            cap.release()

    @staticmethod
    def _resolve_collision(path: Path) -> Path:
        """输出目录已存在同名图片时自动递增，避免覆盖。"""
        if not path.exists():
            return path
        stem, ext = path.stem, path.suffix
        counter = 1
        while True:
            candidate = path.with_name(f"{stem}_dup{counter}{ext}")
            if not candidate.exists():
                return candidate
            counter += 1

    @classmethod
    def run_batch(
        cls,
        videos: List[Dict[str, str]],
        output_dir: Path,
        status_file: Path,
        **kwargs,
    ) -> None:
        """批量处理入口（后台任务中调用）。

        videos: [{"path": 临时文件路径, "name": 原始文件名}, ...]
        逐个视频处理，损坏/失败的视频跳过并记录日志，不阻塞整体任务。
        处理进度实时写入 status_file。
        """
        os.makedirs(output_dir, exist_ok=True)
        total = len(videos)
        status: Dict[str, Any] = {
            "status": "processing",
            "total_videos": total,
            "processed_videos": 0,
            "total_frames": 0,
            "current_video": "",
            "videos": [],
            "started_at": kwargs.pop("_started_at", None),
        }

        def flush():
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(status, f, ensure_ascii=False, indent=2)

        flush()

        for i, item in enumerate(videos):
            temp_path = item["path"]
            name = item["name"]
            status["current_video"] = name
            status["processed_videos"] = i
            flush()

            def progress_cb(pct, extracted, _name=name):
                status["current_progress"] = pct
                status["current_extracted"] = extracted
                flush()

            try:
                result = cls.extract_from_video(
                    temp_path, name, output_dir, progress_cb=progress_cb, **kwargs
                )
                status["total_frames"] += result["extracted_frames"]
                status["videos"].append(result)
                logger.info(f"抽帧完成: {name} -> {result['extracted_frames']} 帧")
            except Exception as e:
                logger.warning(f"跳过损坏/失败视频 {name}: {e}")
                status["videos"].append(
                    {"video": name, "status": "failed", "extracted_frames": 0, "error": str(e)}
                )
            finally:
                # 清理临时上传文件
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except OSError:
                    pass

            status["processed_videos"] = i + 1
            status.pop("current_progress", None)
            status.pop("current_extracted", None)
            flush()

        status["status"] = "completed"
        status["current_video"] = ""
        flush()

    @staticmethod
    def collect_images(task_dir: Path) -> List[Path]:
        """递归收集任务目录下的所有图像文件（兼容扁平与子目录两种结构）。"""
        images: List[Path] = []
        for p in task_dir.rglob("*"):
            # 跳过为“送入标注”临时汇总的目录，避免与原始帧重复计数
            if "_annotation_images" in p.parts:
                continue
            if p.is_file() and p.suffix.lower() in _IMAGE_EXTS:
                images.append(p)
        return images


frame_extraction_service = FrameExtractionService()
