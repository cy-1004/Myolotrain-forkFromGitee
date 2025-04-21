import os
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
import yaml
import random
from pathlib import Path

class YOLODataset(Dataset):
    def __init__(self, dataset_path, img_size=640, augment=True, cache_images=False):
        """
        YOLO数据集加载器
        
        Args:
            dataset_path: 数据集路径
            img_size: 输入图像大小
            augment: 是否使用数据增强
            cache_images: 是否缓存图像到内存
        """
        self.img_size = img_size
        self.augment = augment
        self.cache_images = cache_images
        
        # 检查数据集路径
        self.dataset_path = Path(dataset_path)
        assert self.dataset_path.exists(), f'数据集路径 {dataset_path} 不存在'
        
        # 查找图像和标签文件
        self.img_files = sorted(list(self.dataset_path.glob('images/**/*.jpg')) + 
                               list(self.dataset_path.glob('images/**/*.png')))
        
        assert len(self.img_files) > 0, f'未在 {dataset_path} 找到图像'
        
        # 获取对应的标签文件
        self.label_files = [Path(str(img_file).replace('images', 'labels').replace(os.path.splitext(img_file)[1], '.txt')) 
                           for img_file in self.img_files]
        
        # 缓存图像
        self.imgs = [None] * len(self.img_files)
        if self.cache_images:
            self.cache_images_to_memory()
            
        # 加载类别名称
        self.class_names = self.load_class_names()
        
    def load_class_names(self):
        """加载类别名称"""
        names_file = self.dataset_path / 'classes.txt'
        if names_file.exists():
            with open(names_file, 'r') as f:
                return [line.strip() for line in f.readlines()]
        else:
            print(f"警告: 未找到类别文件 {names_file}，使用索引作为类别名")
            return [str(i) for i in range(80)]  # 默认80个类别
    
    def cache_images_to_memory(self):
        """将图像缓存到内存"""
        print(f'缓存 {len(self.img_files)} 张图像到内存...')
        for i, img_file in enumerate(self.img_files):
            self.imgs[i] = cv2.imread(str(img_file))
    
    def __len__(self):
        return len(self.img_files)
    
    def __getitem__(self, index):
        # 加载图像
        img = self.load_image(index)
        h, w = img.shape[:2]
        
        # 加载标签
        labels = self.load_labels(index)
        
        # 数据增强
        if self.augment:
            img, labels = self.augment_image(img, labels)
        
        # 调整图像大小
        img, ratio, pad = self.resize_image(img, self.img_size)
        
        # 调整标签坐标
        if len(labels) > 0:
            labels[:, 1:] = self.adjust_boxes(labels[:, 1:], ratio, pad, h, w)
        
        # 转换为张量
        img = img.transpose(2, 0, 1)  # HWC -> CHW
        img = np.ascontiguousarray(img)
        img = torch.from_numpy(img).float() / 255.0
        
        if len(labels) > 0:
            labels = torch.from_numpy(labels)
        else:
            labels = torch.zeros((0, 5))
        
        return img, labels, str(self.img_files[index])
    
    def load_image(self, index):
        """加载图像"""
        if self.imgs[index] is not None:
            return self.imgs[index]
        else:
            img_path = self.img_files[index]
            img = cv2.imread(str(img_path))
            assert img is not None, f'图像 {img_path} 不存在或损坏'
            return img
    
    def load_labels(self, index):
        """加载标签"""
        label_path = self.label_files[index]
        if not label_path.exists():
            return np.zeros((0, 5))
        
        try:
            with open(label_path, 'r') as f:
                labels = np.array([x.split() for x in f.read().strip().splitlines()], dtype=np.float32)
            if len(labels) == 0:
                return np.zeros((0, 5))
            return labels
        except Exception as e:
            print(f'警告: 加载标签 {label_path} 时出错: {e}')
            return np.zeros((0, 5))
    
    def resize_image(self, img, target_size):
        """调整图像大小"""
        h, w = img.shape[:2]
        ratio = min(target_size / h, target_size / w)
        new_h, new_w = int(h * ratio), int(w * ratio)
        
        # 调整大小
        if ratio != 1:
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # 计算填充
        dw, dh = target_size - new_w, target_size - new_h
        dw, dh = dw / 2, dh / 2
        
        # 添加填充
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        
        return img, ratio, (dw, dh)
    
    def adjust_boxes(self, boxes, ratio, pad, h, w):
        """调整边界框坐标"""
        # 将标签从 [x_center, y_center, width, height] 转换为 [x1, y1, x2, y2]
        boxes[:, 0] = ratio * boxes[:, 0] * w + pad[0]
        boxes[:, 1] = ratio * boxes[:, 1] * h + pad[1]
        boxes[:, 2] = ratio * boxes[:, 2] * w
        boxes[:, 3] = ratio * boxes[:, 3] * h
        
        return boxes
    
    def augment_image(self, img, labels):
        """数据增强"""
        h, w = img.shape[:2]
        
        # 随机水平翻转
        if random.random() < 0.5:
            img = np.fliplr(img)
            if len(labels) > 0:
                labels[:, 1] = 1 - labels[:, 1]  # 翻转 x 坐标
        
        # HSV增强
        if random.random() < 0.5:
            img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            # 随机调整色调、饱和度和亮度
            h_gain = random.uniform(0.8, 1.2)
            s_gain = random.uniform(0.8, 1.2)
            v_gain = random.uniform(0.8, 1.2)
            
            img_hsv[:, :, 0] = img_hsv[:, :, 0] * h_gain
            img_hsv[:, :, 1] = img_hsv[:, :, 1] * s_gain
            img_hsv[:, :, 2] = img_hsv[:, :, 2] * v_gain
            
            img = cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR)
        
        return img, labels

def create_dataloader(dataset_path, batch_size, img_size, augment=True, cache_images=False):
    """创建数据加载器"""
    dataset = YOLODataset(dataset_path, img_size=img_size, augment=augment, cache_images=cache_images)
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=min(8, os.cpu_count() or 1),
        pin_memory=True,
        collate_fn=collate_fn
    )
    return dataloader, dataset

def collate_fn(batch):
    """自定义批次收集函数"""
    imgs, labels, paths = zip(*batch)
    
    # 移除空标签
    for i, l in enumerate(labels):
        if l.shape[0]:
            l[:, 0] = i  # 添加批次索引
    
    # 堆叠图像
    imgs = torch.stack(imgs, 0)
    
    # 连接标签
    labels = torch.cat(labels, 0)
    
    return imgs, labels, paths
