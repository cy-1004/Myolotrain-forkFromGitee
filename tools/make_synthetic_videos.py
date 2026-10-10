"""生成用于流水线端到端测试的合成"文物"视频：带纹理的背景上，一个彩色物体缓慢移动、缩放

    python tools/make_synthetic_videos.py --out ./synthetic_videos --per-class 3 --seconds 6

类别：RedDisc（红色圆盘）、BlueBox（蓝色方块）、GreenTri（绿色三角）。配合 VLM_PROVIDER=mock
（OpenCV 前景定位）可以在完全离线、不调用任何大模型的情况下跑通整条流水线。
--empty 额外生成一个"空镜头"视频（没有物体），用于测试质量闸门的暂停逻辑。
"""
import argparse
import math
from pathlib import Path

import cv2
import numpy as np

CLASSES = {
    "RedDisc": (40, 40, 220),
    "BlueBox": (220, 80, 40),
    "GreenTri": (60, 190, 60),
}


def draw(cls: str, img, cx, cy, r, angle):
    color = CLASSES[cls]
    if cls == "RedDisc":
        cv2.circle(img, (int(cx), int(cy)), int(r), color, -1, cv2.LINE_AA)
    elif cls == "BlueBox":
        box = cv2.boxPoints(((cx, cy), (2 * r, 1.4 * r), angle))
        cv2.fillPoly(img, [box.astype(np.int32)], color, cv2.LINE_AA)
    else:
        pts = [(cx + r * math.cos(math.radians(angle + k * 120)), cy + r * math.sin(math.radians(angle + k * 120)))
               for k in range(3)]
        cv2.fillPoly(img, [np.array(pts, np.int32)], color, cv2.LINE_AA)


def make_video(path: Path, cls, seed: int, seconds: float, fps: int = 10, size=(320, 240), empty=False):
    rng = np.random.default_rng(seed)
    w, h = size
    base = rng.integers(170, 230, size=(h, w, 3), dtype=np.uint8)
    base = cv2.GaussianBlur(base, (0, 0), 3)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
    n = int(seconds * fps)
    x0, y0 = rng.uniform(0.3, 0.7) * w, rng.uniform(0.35, 0.65) * h
    for i in range(n):
        t = i / max(1, n - 1)
        img = base.copy()
        if not empty:
            cx = x0 + 0.25 * w * math.sin(2 * math.pi * t + seed)
            cy = y0 + 0.12 * h * math.cos(2 * math.pi * t + seed)
            r = (0.12 + 0.04 * math.sin(4 * math.pi * t)) * min(w, h)
            draw(cls, img, cx, cy, r, angle=360 * t)
        writer.write(img)
    writer.release()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="synthetic_videos")
    p.add_argument("--per-class", type=int, default=3)
    p.add_argument("--seconds", type=float, default=6)
    p.add_argument("--empty", action="store_true")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    seed = 0
    for cls in CLASSES:
        for k in range(a.per_class):
            seed += 1
            make_video(out / f"{cls}_{k + 1:02d}.avi", cls, seed, a.seconds)
    if a.empty:
        make_video(out / "RedDisc_empty.avi", "RedDisc", 99, a.seconds, empty=True)
    print(f"已生成到 {out.resolve()}")


if __name__ == "__main__":
    main()
