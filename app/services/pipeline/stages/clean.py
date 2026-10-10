"""③ 清洗：曝光 → 模糊 → 近重复 → 数量上限（由便宜到昂贵），保留帧平铺复制到标注目录

- 模糊用拉普拉斯方差，按视频内分位数剔除最差的一部分：不同视频清晰度差异很大，固定阈值不可用；
- 近重复用 pHash，只在同一视频内、与最近保留的几帧比较，重复时留更清晰的那张；
- 每个视频有帧数上限（默认 200），超出时按时间均匀抽样——全自动时直接决定训练集规模，
  需要人工复核时直接决定复核工作量，宁可少而精。
每帧的去留原因写进清单，控制台可以看到漏斗、捞回误删的帧。
"""
from typing import Dict, List

import cv2
import numpy as np

from app.services.pipeline import errors
from app.services.pipeline.common import frame_name, link_or_copy, load_videos, read_json, update_video, write_json
from app.services.pipeline.errors import PipelineError

DEDUP_LOOKBACK = 5          # 与最近保留的几帧比较
ANALYSIS_LONG_EDGE = 640    # 清晰度在统一尺寸上计算，不同分辨率的视频之间才可比
# 近重复还要求缩略图逐像素平均差小于该值（0~255 灰度）。只看 pHash 不够：转台拍摄时背景静止、
# 只有文物在转，整帧 pHash 几乎不变，会把不同角度的画面误判为重复删掉；真正的重复帧（镜头停住）像素几乎不变
DEDUP_MAX_MEAN_DIFF = 2.5
THUMB_SIZE = (64, 48)


def _read(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def frame_metrics(img: np.ndarray) -> Dict:
    h, w = img.shape[:2]
    scale = ANALYSIS_LONG_EDGE / float(max(h, w))
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return {
        "blur": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "brightness": float(gray.mean()),
        "clipped": float(((gray <= 5) | (gray >= 250)).mean()),
        "phash": phash(gray),
        "thumb": cv2.resize(gray, THUMB_SIZE, interpolation=cv2.INTER_AREA),
    }


def phash(gray: np.ndarray) -> int:
    """64 位感知哈希：32x32 灰度图 DCT 后取左上 8x8 低频系数，与中位数比较"""
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    low = cv2.dct(small)[:8, :8].flatten()
    med = np.median(low[1:])   # 排除直流分量
    bits = 0
    for v in low:
        bits = (bits << 1) | int(v > med)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def is_near_duplicate(a: Dict, b: Dict, max_hamming: int) -> bool:
    """pHash 相近且缩略图几乎逐像素相同，才算重复帧"""
    if hamming(a["phash"], b["phash"]) > max_hamming:
        return False
    ta, tb = a.get("thumb"), b.get("thumb")
    if ta is None or tb is None:
        return True
    return float(np.abs(ta.astype(np.int16) - tb.astype(np.int16)).mean()) < DEDUP_MAX_MEAN_DIFF


def select_frames(frames: List[Dict], cfg) -> List[Dict]:
    """给每帧打上 keep / drop_reason。frames 需含 blur/brightness/clipped/phash/ts"""
    for f in frames:
        f["keep"], f["drop_reason"] = True, None
        if f["brightness"] < cfg.min_mean_brightness or f["brightness"] > cfg.max_mean_brightness \
                or f["clipped"] > cfg.max_clipped_ratio:
            f["keep"], f["drop_reason"] = False, "exposure"

    candidates = [f for f in frames if f["keep"]]
    if candidates and cfg.blur_drop_ratio > 0:
        threshold = float(np.quantile([f["blur"] for f in candidates], cfg.blur_drop_ratio))
        for f in candidates:
            if f["blur"] < threshold:
                f["keep"], f["drop_reason"] = False, "blur"

    if cfg.dedup_hamming > 0:
        kept: List[Dict] = []
        for f in sorted((f for f in frames if f["keep"]), key=lambda x: x["ts"]):
            dup = next((k for k in kept[-DEDUP_LOOKBACK:] if is_near_duplicate(k, f, cfg.dedup_hamming)), None)
            if dup is None:
                kept.append(f)
            elif f["blur"] > dup["blur"]:
                dup["keep"], dup["drop_reason"] = False, "duplicate"   # 留下更清晰的
                kept[kept.index(dup)] = f
            else:
                f["keep"], f["drop_reason"] = False, "duplicate"

    kept = sorted((f for f in frames if f["keep"]), key=lambda x: x["ts"])
    if len(kept) > cfg.max_frames_per_video:
        chosen = set(np.linspace(0, len(kept) - 1, cfg.max_frames_per_video).round().astype(int).tolist())
        for i, f in enumerate(kept):
            if i not in chosen:
                f["keep"], f["drop_reason"] = False, "cap"
    return frames


def run(ctx):
    cfg = ctx.config.clean
    videos = load_videos(ctx)
    images_dir = ctx.path("images")
    total_kept = 0
    for vi, v in enumerate(videos):
        ctx.check_cancel()
        manifest_path = ctx.path("manifest", f"{v['key']}.json")
        existing = read_json(manifest_path)
        if existing and existing.get("complete"):
            total_kept += existing["kept"]
            continue
        extracted = read_json(ctx.path("frames", v["key"], "frames.json"), {}).get("frames", [])
        frames = []
        for i, rec in enumerate(extracted):
            img = _read(ctx.path("frames", v["key"], rec["file"]))
            if img is None:
                continue
            frames.append({**rec, **frame_metrics(img)})
            if i % 10 == 0:
                ctx.check_cancel()
                ctx.progress((vi + 0.8 * (i + 1) / max(1, len(extracted))) / len(videos), detail={"video": v["key"]})

        select_frames(frames, cfg)
        kept = [f for f in frames if f["keep"]]
        for f in kept:
            f["image"] = frame_name(v["key"], f["frame_index"])
            link_or_copy(ctx.path("frames", v["key"], f["file"]), images_dir / f["image"])

        dropped = {}
        for f in frames:
            if not f["keep"]:
                dropped[f["drop_reason"]] = dropped.get(f["drop_reason"], 0) + 1
        stats = {"extracted": len(extracted), "kept": len(kept), "dropped": dropped,
                 "kept_ratio": round(len(kept) / len(extracted), 4) if extracted else 0.0}
        for f in frames:
            f["phash"] = format(f["phash"], "016x")   # 64 位整数存成十六进制，JSON 里不丢精度
            f.pop("thumb", None)
        write_json(manifest_path, {"complete": True, "kept": len(kept), "frames": frames})
        update_video(ctx, v["id"], stats={"clean": stats})
        if len(kept) < cfg.min_frames_per_video:
            ctx.warn(f"视频 {v['key']} 清洗后只剩 {len(kept)} 帧（少于 {cfg.min_frames_per_video}）",
                     data={"video": v["key"], **stats})
        total_kept += len(kept)
        ctx.progress((vi + 1) / len(videos), detail={"video": v["key"], "kept": len(kept)}, force=True)

    if total_kept == 0:
        raise PipelineError(errors.NO_USABLE_FRAMES, "清洗后没有剩余可用的帧：视频可能过暗、过曝或严重模糊")
