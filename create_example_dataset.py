#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
创建一个简单的示例数据集，用于测试YOLOv8训练程序
"""

import os
import sys
import shutil
from pathlib import Path
import numpy as np
import cv2

def create_example_dataset(dataset_path, num_images=10):
    """创建一个简单的示例数据集"""
    dataset_path = Path(dataset_path)
    
    # 创建目录结构
    train_images_dir = dataset_path / 'train' / 'images'
    train_labels_dir = dataset_path / 'train' / 'labels'
    val_images_dir = dataset_path / 'val' / 'images'
    val_labels_dir = dataset_path / 'val' / 'labels'
    
    # 确保目录存在
    train_images_dir.mkdir(parents=True, exist_ok=True)
    train_labels_dir.mkdir(parents=True, exist_ok=True)
    val_images_dir.mkdir(parents=True, exist_ok=True)
    val_labels_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建类别文件
    with open(dataset_path / 'classes.txt', 'w', encoding='utf-8') as f:
        f.write("rectangle\n")
        f.write("circle\n")
    
    # 创建训练图像和标签
    print(f"创建{num_images}张训练图像和标签...")
    for i in range(num_images):
        # 创建一个空白图像
        img = np.ones((640, 640, 3), dtype=np.uint8) * 255
        
        # 随机绘制矩形
        x1, y1 = np.random.randint(100, 400), np.random.randint(100, 400)
        x2, y2 = x1 + np.random.randint(100, 200), y1 + np.random.randint(100, 200)
        color = (0, 0, 255)  # 红色
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        
        # 随机绘制圆形
        cx, cy = np.random.randint(100, 500), np.random.randint(100, 500)
        radius = np.random.randint(30, 80)
        color = (255, 0, 0)  # 蓝色
        cv2.circle(img, (cx, cy), radius, color, 2)
        
        # 保存图像
        img_path = train_images_dir / f"image_{i:04d}.jpg"
        cv2.imwrite(str(img_path), img)
        
        # 创建标签文件 (YOLO格式: class_id x_center y_center width height)
        label_path = train_labels_dir / f"image_{i:04d}.txt"
        with open(label_path, 'w') as f:
            # 矩形标签 (类别0)
            x_center = (x1 + x2) / 2 / 640
            y_center = (y1 + y2) / 2 / 640
            width = (x2 - x1) / 640
            height = (y2 - y1) / 640
            f.write(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
            
            # 圆形标签 (类别1)
            x_center = cx / 640
            y_center = cy / 640
            width = radius * 2 / 640
            height = radius * 2 / 640
            f.write(f"1 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
    
    # 创建验证图像和标签 (复制一部分训练图像)
    print("创建验证图像和标签...")
    val_count = max(2, num_images // 5)  # 至少2张验证图像
    for i in range(val_count):
        # 复制图像
        src_img = train_images_dir / f"image_{i:04d}.jpg"
        dst_img = val_images_dir / f"image_{i:04d}.jpg"
        shutil.copy(src_img, dst_img)
        
        # 复制标签
        src_label = train_labels_dir / f"image_{i:04d}.txt"
        dst_label = val_labels_dir / f"image_{i:04d}.txt"
        shutil.copy(src_label, dst_label)
    
    print(f"示例数据集已创建在 {dataset_path}")
    print(f"- 训练图像: {num_images}张")
    print(f"- 验证图像: {val_count}张")
    print(f"- 类别: rectangle, circle")

if __name__ == "__main__":
    # 默认数据集路径
    default_path = "./dataset"
    
    # 获取命令行参数
    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]
    else:
        dataset_path = default_path
    
    # 获取图像数量
    if len(sys.argv) > 2:
        try:
            num_images = int(sys.argv[2])
        except ValueError:
            num_images = 10
    else:
        num_images = 10
    
    # 创建示例数据集
    create_example_dataset(dataset_path, num_images)
