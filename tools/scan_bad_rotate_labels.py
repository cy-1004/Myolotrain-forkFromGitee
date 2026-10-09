#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
扫描历史增强产物中受"旋转标签 bug"影响的文件。

背景
----
修复前的 opencv_service 有两个缺陷：

1. `transform_labels_rotate` 对 90/270 度用的是顺时针映射 `(x,y) -> (1-y, x)`，
   而 `cv2.getRotationMatrix2D` 的正角度是逆时针 —— 90 度和 270 度的标签被互换了；
2. `rotate_image` 固定输出 (W, H) 画布，非正方形图片旋转 90/270 后内容被裁掉，
   而标签公式却是按"画布跟着变"推导的。

因此凡是「数据集增强 → 旋转」且角度为 90/270 的产物，标注框都是错的。
180 度、翻转、缩放、以及全部像素类操作不受影响。

本脚本只读不写，列出受影响的文件清单，供你决定是否重新生成。

用法
----
    python tools/scan_bad_rotate_labels.py
    python tools/scan_bad_rotate_labels.py --root app/static/augmented_datasets
    python tools/scan_bad_rotate_labels.py --root D:/some/dir --json report.json
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

# augment_dataset 产出的文件名形如 rotate_{angle}_{原文件名}
ROTATE_PREFIX = re.compile(r'^rotate_(-?\d+(?:\.\d+)?)_')
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

# 只有 180 度（及 0/360）的标签在修复前是正确的
def is_affected(angle):
    a = angle % 360
    return abs(a - 180.0) > 1e-6 and abs(a) > 1e-6


def image_size(path):
    """尽量不依赖 opencv 读取图片尺寸；读不到就返回 None"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size  # (width, height)
    except Exception:
        pass
    try:
        import cv2
        img = cv2.imread(path)
        if img is not None:
            return img.shape[1], img.shape[0]
    except Exception:
        pass
    return None


def scan(root):
    findings = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in IMAGE_EXTS:
                continue
            m = ROTATE_PREFIX.match(name)
            if not m:
                continue
            angle = float(m.group(1))
            if not is_affected(angle):
                continue

            img_path = os.path.join(dirpath, name)
            # augment_dataset 的约定：把路径里的 images 换成 labels，扩展名换成 .txt
            label_path = img_path.replace('images', 'labels').rsplit('.', 1)[0] + '.txt'
            has_label = os.path.exists(label_path)
            box_count = 0
            if has_label:
                try:
                    with open(label_path, 'r', encoding='utf-8', errors='ignore') as f:
                        box_count = sum(1 for line in f if len(line.split()) == 5)
                except Exception:
                    pass

            size = image_size(img_path)
            square = None if size is None else (size[0] == size[1])

            findings.append({
                'image': img_path,
                'label': label_path if has_label else None,
                'angle': angle,
                'boxes': box_count,
                'size': list(size) if size else None,
                # 正方形图只中了"方向反了"这一条，像素没丢，标签可按正确公式重算；
                # 非正方形图旋转时内容已被裁掉，像素信息不可恢复，只能重新生成
                'repairable': square,
            })
    return findings


def main():
    parser = argparse.ArgumentParser(description='扫描受旋转标签 bug 影响的历史增强产物')
    parser.add_argument('--root', action='append', default=None,
                        help='要扫描的目录，可重复指定。默认扫描 app/static/augmented_datasets 和 datasets_import')
    parser.add_argument('--json', default=None, help='把完整清单写入该 JSON 文件')
    args = parser.parse_args()

    roots = args.root or ['app/static/augmented_datasets', 'app/static/datasets', 'datasets_import']
    roots = [r for r in roots if os.path.isdir(r)]
    if not roots:
        print('没有找到可扫描的目录，请用 --root 指定。')
        return 1

    print('扫描目录: %s\n' % ', '.join(roots))
    findings = []
    for r in roots:
        findings.extend(scan(r))

    if not findings:
        print('未发现受影响的文件。')
        print('（本脚本按文件名前缀 rotate_90_ / rotate_270_ 等识别，')
        print('  如果你的增强产物已改名或已导出到别处，请用 --root 指向那里再扫一次。）')
        return 0

    by_dir = defaultdict(list)
    for f in findings:
        by_dir[os.path.dirname(f['image'])].append(f)

    total_boxes = sum(f['boxes'] for f in findings)
    unrepairable = [f for f in findings if f['repairable'] is False]
    unknown = [f for f in findings if f['repairable'] is None]

    print('发现 %d 个受影响的图片，涉及 %d 个目录，共 %d 个错误标注框。\n'
          % (len(findings), len(by_dir), total_boxes))

    for d in sorted(by_dir):
        items = by_dir[d]
        angles = sorted({f['angle'] for f in items})
        print('  %s' % d)
        print('      文件 %d 个，角度 %s，标注框 %d 个'
              % (len(items), '/'.join('%g°' % a for a in angles),
                 sum(f['boxes'] for f in items)))

    print('\n处置建议:')
    print('  - 正方形图片: 像素没丢，只是标签方向反了，重新生成即可（或按正确公式重算标签）。')
    if unrepairable:
        print('  - 非正方形图片 %d 个: 旋转时画面已被裁掉，像素信息不可恢复，'
              '必须用修复后的代码重新生成。' % len(unrepairable))
    if unknown:
        print('  - %d 个文件读不到尺寸（未安装 Pillow 或 opencv），无法判断是否正方形。'
              '装一下 Pillow 再扫一次会更准。' % len(unknown))
    print('\n  修复后的代码已经是正确的，重新跑一次「数据集增强 → 旋转」即可得到正确产物。')

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(findings, f, ensure_ascii=False, indent=2)
        print('\n完整清单已写入: %s' % args.json)

    return 0


if __name__ == '__main__':
    sys.exit(main())
