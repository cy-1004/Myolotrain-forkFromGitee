# -*- coding: utf-8 -*-
"""
创建门窗检测数据集的简化脚本
"""
import os
import sys
from pathlib import Path
import numpy as np
import cv2

# 修复中文路径问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 创建数据集目录和配置文件
def create_door_window_dataset(dataset_path, num_images=10):
    """创建门窗检测数据集"""
    dataset_path = Path(dataset_path)
    
    # 确保主目录存在
    dataset_path.mkdir(parents=True, exist_ok=True)
    
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
    classes = ["door", "window"]
    with open(dataset_path / 'classes.txt', 'w', encoding='utf-8') as f:
        for cls in classes:
            f.write(f"{cls}\n")
    
    # 创建yaml配置文件，这是YOLO训练必需的
    yaml_content = f"""
path: {dataset_path.resolve()}
train: train/images
val: val/images

names:
  0: door
  1: window
"""
    
    with open(dataset_path / 'dataset.yaml', 'w', encoding='utf-8') as f:
        f.write(yaml_content.strip())
    
    # 创建训练图像和标签
    print(f"创建{num_images}张训练图像和标签...")
    for i in range(num_images):
        # 创建一个空白图像
        img = np.ones((640, 640, 3), dtype=np.uint8) * 255
        
        # 随机绘制门（矩形）
        x1, y1 = np.random.randint(100, 300), np.random.randint(50, 400)
        x2, y2 = x1 + np.random.randint(80, 150), y1 + np.random.randint(200, 400)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)  # 红色矩形
        
        # 随机绘制窗户（方形）
        wx1, wy1 = np.random.randint(350, 500), np.random.randint(100, 300)
        wx2, wy2 = wx1 + np.random.randint(100, 150), wy1 + np.random.randint(100, 150)
        cv2.rectangle(img, (wx1, wy1), (wx2, wy2), (255, 0, 0), 2)  # 蓝色方形
        
        # 保存图像
        img_path = train_images_dir / f"door_window_{i:04d}.jpg"
        # 使用绝对路径保存，避免路径问题
        cv2.imwrite(str(img_path.absolute()), img)
        
        # 创建标签文件 (YOLO格式: class_id x_center y_center width height)
        label_path = train_labels_dir / f"door_window_{i:04d}.txt"
        with open(label_path, 'w', encoding='utf-8') as f:
            # 门标签 (类别0)
            x_center = (x1 + x2) / 2 / 640
            y_center = (y1 + y2) / 2 / 640
            width = (x2 - x1) / 640
            height = (y2 - y1) / 640
            f.write(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
            
            # 窗户标签 (类别1)
            x_center = (wx1 + wx2) / 2 / 640
            y_center = (wy1 + wy2) / 2 / 640
            width = (wx2 - wx1) / 640
            height = (wy2 - wy1) / 640
            f.write(f"1 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
    
    # 创建验证图像和标签
    print("创建验证图像和标签...")
    val_count = max(2, num_images // 5)  # 至少2张验证图像
    for i in range(val_count):
        # 创建新的验证图像
        val_img = np.ones((640, 640, 3), dtype=np.uint8) * 255
        
        # 随机绘制门
        x1, y1 = np.random.randint(100, 300), np.random.randint(50, 400)
        x2, y2 = x1 + np.random.randint(80, 150), y1 + np.random.randint(200, 400)
        cv2.rectangle(val_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        
        # 随机绘制窗户
        wx1, wy1 = np.random.randint(350, 500), np.random.randint(100, 300)
        wx2, wy2 = wx1 + np.random.randint(100, 150), wy1 + np.random.randint(100, 150)
        cv2.rectangle(val_img, (wx1, wy1), (wx2, wy2), (255, 0, 0), 2)
        
        # 保存验证图像
        val_img_path = val_images_dir / f"val_door_window_{i:04d}.jpg"
        cv2.imwrite(str(val_img_path.absolute()), val_img)
        
        # 创建验证标签文件
        val_label_path = val_labels_dir / f"val_door_window_{i:04d}.txt"
        with open(val_label_path, 'w', encoding='utf-8') as f:
            # 门标签
            x_center = (x1 + x2) / 2 / 640
            y_center = (y1 + y2) / 2 / 640
            width = (x2 - x1) / 640
            height = (y2 - y1) / 640
            f.write(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
            
            # 窗户标签
            x_center = (wx1 + wx2) / 2 / 640
            y_center = (wy1 + wy2) / 2 / 640
            width = (wx2 - wx1) / 640
            height = (wy2 - wy1) / 640
            f.write(f"1 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
    
    print(f"\n门窗检测数据集已成功创建在: {dataset_path.absolute()}")
    print(f"- 训练图像: {num_images}张")
    print(f"- 验证图像: {val_count}张")
    print(f"- 类别: {', '.join(classes)}")
    print("- 已生成dataset.yaml配置文件")

if __name__ == "__main__":
    # 设置数据集路径
    dataset_path = "datasets_import/门窗检测"
    num_images = 10
    
    # 执行数据集创建
    create_door_window_dataset(dataset_path, num_images)