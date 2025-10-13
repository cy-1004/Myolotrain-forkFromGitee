"""
OpenCV 服务模块 - 提供图像处理和计算机视觉功能
"""
import os
import cv2
import numpy as np
import math
import shutil
import yaml
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class OpenCVService:
    """
    OpenCV 服务类，提供图像处理、数据增强和可视化功能
    """

    @staticmethod
    def read_image(image_path: Union[str, Path]) -> np.ndarray:
        """
        读取图像文件

        Args:
            image_path: 图像文件路径

        Returns:
            numpy.ndarray: 图像数据

        Raises:
            HTTPException: 如果图像无法读取
        """
        try:
            image_path = str(image_path)
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"无法读取图像: {image_path}")
            return img
        except Exception as e:
            logger.error(f"读取图像失败: {str(e)}")
            raise HTTPException(status_code=400, detail=f"读取图像失败: {str(e)}")

    @staticmethod
    def save_image(image: np.ndarray, output_path: Union[str, Path]) -> str:
        """
        保存图像到文件

        Args:
            image: 图像数据
            output_path: 输出文件路径

        Returns:
            str: 保存的文件路径

        Raises:
            HTTPException: 如果图像无法保存
        """
        try:
            output_path = str(output_path)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cv2.imwrite(output_path, image)
            return output_path
        except Exception as e:
            logger.error(f"保存图像失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"保存图像失败: {str(e)}")

    # ==================== 图像预处理功能 ====================

    @staticmethod
    def resize_image(image: np.ndarray, width: int, height: int) -> np.ndarray:
        """调整图像大小"""
        return cv2.resize(image, (width, height))

    @staticmethod
    def normalize_image(image: np.ndarray) -> np.ndarray:
        """标准化图像 (0-255)"""
        return cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX)

    @staticmethod
    def denoise_image(image: np.ndarray, strength: int = 5) -> np.ndarray:
        """
        去除图像噪点

        Args:
            image: 输入图像
            strength: 去噪强度 (1-10)

        Returns:
            np.ndarray: 去噪后的图像
        """
        # 确保强度在合理范围内
        strength = max(1, min(10, strength))
        kernel_size = 2 * strength + 1

        # 应用高斯模糊
        return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)

    @staticmethod
    def adjust_brightness_contrast(
        image: np.ndarray,
        brightness: float = 0,
        contrast: float = 1.0
    ) -> np.ndarray:
        """
        调整图像亮度和对比度

        Args:
            image: 输入图像
            brightness: 亮度调整值 (-100 到 100)
            contrast: 对比度调整值 (0.0 到 3.0)

        Returns:
            np.ndarray: 调整后的图像
        """
        # 将亮度值转换为图像可用的值
        brightness = int(brightness * 2.55)  # 将百分比转换为像素值

        # 应用对比度和亮度调整
        return cv2.convertScaleAbs(image, alpha=contrast, beta=brightness)

    @staticmethod
    def sharpen_image(image: np.ndarray, amount: float = 1.0) -> np.ndarray:
        """
        锐化图像

        Args:
            image: 输入图像
            amount: 锐化强度 (0.0 到 5.0)

        Returns:
            np.ndarray: 锐化后的图像
        """
        # 创建锐化核
        kernel = np.array([
            [-1, -1, -1],
            [-1,  9, -1],
            [-1, -1, -1]
        ])

        # 应用锐化
        sharpened = cv2.filter2D(image, -1, kernel * amount)
        return cv2.convertScaleAbs(sharpened)

    # ==================== 数据增强功能 ====================

    @staticmethod
    def flip_image(image: np.ndarray, flip_code: int) -> np.ndarray:
        """
        翻转图像

        Args:
            image: 输入图像
            flip_code: 翻转代码 (0: 水平翻转, 1: 垂直翻转, -1: 同时水平和垂直翻转)

        Returns:
            np.ndarray: 翻转后的图像
        """
        return cv2.flip(image, flip_code)

    @staticmethod
    def rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
        """
        旋转图像

        Args:
            image: 输入图像
            angle: 旋转角度 (度)

        Returns:
            np.ndarray: 旋转后的图像
        """
        height, width = image.shape[:2]
        center = (width // 2, height // 2)

        # 获取旋转矩阵
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

        # 应用旋转
        return cv2.warpAffine(image, rotation_matrix, (width, height))

    @staticmethod
    def add_noise(image: np.ndarray, noise_type: str = 'gaussian', amount: float = 0.05) -> np.ndarray:
        """
        添加噪声到图像

        Args:
            image: 输入图像
            noise_type: 噪声类型 ('gaussian', 'salt_pepper')
            amount: 噪声量 (0.0 到 1.0)

        Returns:
            np.ndarray: 添加噪声后的图像
        """
        output = image.copy()

        if noise_type == 'gaussian':
            # 高斯噪声
            row, col, ch = output.shape
            mean = 0
            sigma = 255 * amount
            gauss = np.random.normal(mean, sigma, (row, col, ch))
            gauss = gauss.reshape(row, col, ch)
            output = output + gauss
            output = np.clip(output, 0, 255).astype(np.uint8)

        elif noise_type == 'salt_pepper':
            # 椒盐噪声
            s_vs_p = 0.5
            row, col, ch = output.shape

            # 盐噪声 (白点)
            num_salt = np.ceil(amount * output.size * s_vs_p)
            coords = [np.random.randint(0, i - 1, int(num_salt)) for i in output.shape]
            output[coords[0], coords[1], :] = 255

            # 椒噪声 (黑点)
            num_pepper = np.ceil(amount * output.size * (1. - s_vs_p))
            coords = [np.random.randint(0, i - 1, int(num_pepper)) for i in output.shape]
            output[coords[0], coords[1], :] = 0

        return output

    @staticmethod
    def apply_perspective_transform(
        image: np.ndarray,
        strength: float = 0.2
    ) -> np.ndarray:
        """
        应用透视变换

        Args:
            image: 输入图像
            strength: 变换强度 (0.0 到 1.0)

        Returns:
            np.ndarray: 变换后的图像
        """
        height, width = image.shape[:2]

        # 定义变换前的四个角点
        pts1 = np.float32([
            [0, 0],
            [width, 0],
            [0, height],
            [width, height]
        ])

        # 定义变换后的四个角点 (根据强度调整)
        offset = int(width * strength / 2)
        pts2 = np.float32([
            [offset, offset],
            [width - offset, offset],
            [offset, height - offset],
            [width - offset, height - offset]
        ])

        # 获取透视变换矩阵
        matrix = cv2.getPerspectiveTransform(pts1, pts2)

        # 应用透视变换
        return cv2.warpPerspective(image, matrix, (width, height))

    # ==================== 图像质量评估功能 ====================

    @staticmethod
    def detect_blur(image: np.ndarray, threshold: float = 100.0) -> Tuple[bool, float]:
        """
        检测图像是否模糊

        Args:
            image: 输入图像
            threshold: 模糊检测阈值 (越低越敏感)

        Returns:
            Tuple[bool, float]: (是否模糊, 清晰度得分)
        """
        # 转换为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # 计算拉普拉斯方差
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # 判断是否模糊
        is_blurry = laplacian_var < threshold

        return is_blurry, laplacian_var

    @staticmethod
    def detect_overexposure(image: np.ndarray, threshold: float = 0.7) -> Tuple[bool, float]:
        """
        检测图像是否过度曝光

        Args:
            image: 输入图像
            threshold: 过度曝光阈值 (0.0 到 1.0)

        Returns:
            Tuple[bool, float]: (是否过度曝光, 过度曝光比例)
        """
        # 转换为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # 计算过度曝光的像素比例
        overexposed_ratio = np.sum(gray > 240) / gray.size

        # 判断是否过度曝光
        is_overexposed = overexposed_ratio > threshold

        return is_overexposed, overexposed_ratio

    @staticmethod
    def detect_underexposure(image: np.ndarray, threshold: float = 0.7) -> Tuple[bool, float]:
        """
        检测图像是否曝光不足

        Args:
            image: 输入图像
            threshold: 曝光不足阈值 (0.0 到 1.0)

        Returns:
            Tuple[bool, float]: (是否曝光不足, 曝光不足比例)
        """
        # 转换为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # 计算曝光不足的像素比例
        underexposed_ratio = np.sum(gray < 30) / gray.size

        # 判断是否曝光不足
        is_underexposed = underexposed_ratio > threshold

        return is_underexposed, underexposed_ratio

    # ==================== 批量处理功能 ====================

    @classmethod
    def batch_process_images(
        cls,
        image_paths: List[str],
        output_dir: str,
        operations: List[Dict[str, Any]]
    ) -> List[str]:
        """
        批量处理图像

        Args:
            image_paths: 输入图像路径列表
            output_dir: 输出目录
            operations: 操作列表，每个操作是一个字典，包含操作名称和参数
                例如: [
                    {"name": "resize_image", "params": {"width": 640, "height": 480}},
                    {"name": "denoise_image", "params": {"strength": 3}}
                ]

        Returns:
            List[str]: 处理后的图像路径列表
        """
        os.makedirs(output_dir, exist_ok=True)
        output_paths = []

        for image_path in image_paths:
            try:
                # 读取图像
                img = cls.read_image(image_path)

                # 应用操作
                for operation in operations:
                    op_name = operation["name"]
                    op_params = operation.get("params", {})

                    # 获取操作方法
                    op_method = getattr(cls, op_name, None)
                    if op_method is None:
                        logger.warning(f"未知的操作: {op_name}")
                        continue

                    # 应用操作
                    img = op_method(img, **op_params)

                # 保存处理后的图像
                filename = os.path.basename(image_path)
                output_path = os.path.join(output_dir, filename)
                cls.save_image(img, output_path)
                output_paths.append(output_path)

            except Exception as e:
                logger.error(f"处理图像 {image_path} 失败: {str(e)}")
                continue

        return output_paths

    # ==================== 数据集增强功能 ====================

    @staticmethod
    def load_yolo_labels(label_path: str) -> List[List[float]]:
        """
        加载YOLO格式的标签文件

        Args:
            label_path: 标签文件路径

        Returns:
            List[List[float]]: 标签列表，每个标签是 [class_id, x_center, y_center, width, height]
        """
        if not os.path.exists(label_path):
            return []

        try:
            labels = []
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:  # 确保格式正确
                        # 转换为浮点数
                        label = [float(p) for p in parts]
                        labels.append(label)
            return labels
        except Exception as e:
            logger.error(f"加载标签文件失败: {str(e)}")
            return []

    @staticmethod
    def save_yolo_labels(label_path: str, labels: List[List[float]]) -> bool:
        """
        保存YOLO格式的标签文件

        Args:
            label_path: 标签文件路径
            labels: 标签列表，每个标签是 [class_id, x_center, y_center, width, height]

        Returns:
            bool: 是否保存成功
        """
        try:
            os.makedirs(os.path.dirname(label_path), exist_ok=True)
            with open(label_path, 'w') as f:
                for label in labels:
                    # 确保class_id是整数
                    class_id = int(label[0])
                    # 确保坐标在0-1范围内
                    x = max(0, min(1, label[1]))
                    y = max(0, min(1, label[2]))
                    w = max(0, min(1, label[3]))
                    h = max(0, min(1, label[4]))
                    f.write(f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n")
            return True
        except Exception as e:
            logger.error(f"保存标签文件失败: {str(e)}")
            return False

    @staticmethod
    def transform_labels_flip_horizontal(labels: List[List[float]]) -> List[List[float]]:
        """
        水平翻转标签坐标

        Args:
            labels: 原始标签列表

        Returns:
            List[List[float]]: 变换后的标签列表
        """
        transformed = []
        for label in labels:
            # 复制标签
            new_label = label.copy()
            # 水平翻转：x = 1 - x
            new_label[1] = 1.0 - label[1]
            transformed.append(new_label)
        return transformed

    @staticmethod
    def transform_labels_flip_vertical(labels: List[List[float]]) -> List[List[float]]:
        """
        垂直翻转标签坐标

        Args:
            labels: 原始标签列表

        Returns:
            List[List[float]]: 变换后的标签列表
        """
        transformed = []
        for label in labels:
            # 复制标签
            new_label = label.copy()
            # 垂直翻转：y = 1 - y
            new_label[2] = 1.0 - label[2]
            transformed.append(new_label)
        return transformed

    @staticmethod
    def transform_labels_rotate(labels: List[List[float]], angle: float, img_width: int, img_height: int) -> List[List[float]]:
        """
        旋转标签坐标

        Args:
            labels: 原始标签列表
            angle: 旋转角度（度）
            img_width: 图像宽度
            img_height: 图像高度

        Returns:
            List[List[float]]: 变换后的标签列表
        """
        # 对于90度的倍数旋转，我们可以直接计算
        transformed = []

        # 将角度转换为弧度
        angle_rad = math.radians(angle)

        # 计算旋转中心（归一化坐标）
        cx, cy = 0.5, 0.5

        for label in labels:
            # 复制标签
            new_label = label.copy()

            # 获取归一化坐标
            x, y = label[1], label[2]
            w, h = label[3], label[4]

            # 特殊情况处理：90度的倍数
            if angle == 90:
                # 90度旋转：(x,y) -> (1-y,x)
                new_x = 1.0 - y
                new_y = x
                # 宽高互换
                new_w = h
                new_h = w
            elif angle == 180:
                # 180度旋转：(x,y) -> (1-x,1-y)
                new_x = 1.0 - x
                new_y = 1.0 - y
                new_w = w
                new_h = h
            elif angle == 270:
                # 270度旋转：(x,y) -> (y,1-x)
                new_x = y
                new_y = 1.0 - x
                # 宽高互换
                new_w = h
                new_h = w
            else:
                # 一般角度旋转（不常用，可能会导致标注框变形）
                # 将归一化坐标转换为像素坐标
                px = x * img_width
                py = y * img_height

                # 计算相对于中心的偏移
                dx = px - img_width / 2
                dy = py - img_height / 2

                # 应用旋转
                new_dx = dx * math.cos(angle_rad) - dy * math.sin(angle_rad)
                new_dy = dx * math.sin(angle_rad) + dy * math.cos(angle_rad)

                # 计算新的像素坐标
                new_px = new_dx + img_width / 2
                new_py = new_dy + img_height / 2

                # 转换回归一化坐标
                new_x = new_px / img_width
                new_y = new_py / img_height

                # 对于非90度的倍数旋转，宽高计算比较复杂，这里简化处理
                new_w = w
                new_h = h

            # 更新标签
            new_label[1] = max(0, min(1, new_x))
            new_label[2] = max(0, min(1, new_y))
            new_label[3] = max(0, min(1, new_w))
            new_label[4] = max(0, min(1, new_h))

            transformed.append(new_label)

        return transformed

    @staticmethod
    def transform_labels_perspective(labels: List[List[float]], strength: float) -> List[List[float]]:
        """
        透视变换标签坐标

        Args:
            labels: 原始标签列表
            strength: 变换强度

        Returns:
            List[List[float]]: 变换后的标签列表
        """
        # 透视变换对标注框的影响比较复杂，这里做一个简化处理
        # 对于小幅度的透视变换，我们可以近似保持中心点不变，但缩小标注框的大小
        transformed = []

        # 缩放因子，随着强度增加而减小
        scale_factor = 1.0 - strength * 0.5

        for label in labels:
            # 复制标签
            new_label = label.copy()

            # 保持中心点不变，缩小宽高
            new_label[3] = label[3] * scale_factor
            new_label[4] = label[4] * scale_factor

            transformed.append(new_label)

        return transformed

    @classmethod
    def augment_dataset(
        cls,
        dataset_dir: str,
        output_dir: str,
        augmentation_options: Dict[str, Any],
        multiplier: int = 2
    ) -> Dict[str, Any]:
        """
        增强数据集，并自动处理标注文件

        Args:
            dataset_dir: 数据集目录
            output_dir: 输出目录
            augmentation_options: 增强选项
                例如: {
                    "flip": True,
                    "rotate": {"angles": [90, 180, 270]},
                    "noise": {"types": ["gaussian"], "amount": 0.05},
                    "brightness_contrast": {"brightness": [-20, 20], "contrast": [0.8, 1.2]}
                }
            multiplier: 数据集扩增倍数

        Returns:
            Dict[str, Any]: 增强结果统计
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 获取数据集中的所有图像
        image_paths = []
        for root, _, files in os.walk(dataset_dir):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                    image_paths.append(os.path.join(root, file))

        # 统计信息
        stats = {
            "original_images": len(image_paths),
            "augmented_images": 0,
            "total_images": 0,
            "augmentations_applied": {},
            "labels_processed": 0
        }

        # 处理每个图像
        for image_path in image_paths:
            try:
                # 读取图像
                img = cls.read_image(image_path)
                img_height, img_width = img.shape[:2]

                # 查找对应的标签文件
                # 假设标签文件与图像文件在相同的相对路径下，但在labels目录而不是images目录
                label_path = image_path.replace('images', 'labels').rsplit('.', 1)[0] + '.txt'

                # 加载标签
                labels = cls.load_yolo_labels(label_path)
                has_labels = len(labels) > 0

                # 保存原始图像
                rel_path = os.path.relpath(image_path, dataset_dir)
                output_path = os.path.join(output_dir, rel_path)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                cls.save_image(img, output_path)
                stats["total_images"] += 1

                # 如果有标签，保存原始标签
                if has_labels:
                    output_label_path = output_path.replace('images', 'labels').rsplit('.', 1)[0] + '.txt'
                    cls.save_yolo_labels(output_label_path, labels)
                    stats["labels_processed"] += 1

                # 应用增强
                augmented_count = 0

                # 水平翻转
                if augmentation_options.get("flip", False) and augmented_count < multiplier - 1:
                    flipped = cls.flip_image(img, 1)
                    flip_path = os.path.join(
                        os.path.dirname(output_path),
                        f"flip_h_{os.path.basename(output_path)}"
                    )
                    cls.save_image(flipped, flip_path)

                    # 处理标签
                    if has_labels:
                        flip_label_path = flip_path.replace('images', 'labels').rsplit('.', 1)[0] + '.txt'
                        flipped_labels = cls.transform_labels_flip_horizontal(labels)
                        cls.save_yolo_labels(flip_label_path, flipped_labels)
                        stats["labels_processed"] += 1

                    augmented_count += 1
                    stats["augmentations_applied"]["flip_h"] = stats["augmentations_applied"].get("flip_h", 0) + 1

                # 垂直翻转
                if augmentation_options.get("flip", False) and augmented_count < multiplier - 1:
                    flipped = cls.flip_image(img, 0)
                    flip_path = os.path.join(
                        os.path.dirname(output_path),
                        f"flip_v_{os.path.basename(output_path)}"
                    )
                    cls.save_image(flipped, flip_path)

                    # 处理标签
                    if has_labels:
                        flip_label_path = flip_path.replace('images', 'labels').rsplit('.', 1)[0] + '.txt'
                        flipped_labels = cls.transform_labels_flip_vertical(labels)
                        cls.save_yolo_labels(flip_label_path, flipped_labels)
                        stats["labels_processed"] += 1

                    augmented_count += 1
                    stats["augmentations_applied"]["flip_v"] = stats["augmentations_applied"].get("flip_v", 0) + 1

                # 旋转
                if "rotate" in augmentation_options and augmented_count < multiplier - 1:
                    angles = augmentation_options["rotate"].get("angles", [90, 180, 270])
                    for angle in angles:
                        if augmented_count >= multiplier - 1:
                            break
                        rotated = cls.rotate_image(img, angle)
                        rotate_path = os.path.join(
                            os.path.dirname(output_path),
                            f"rotate_{angle}_{os.path.basename(output_path)}"
                        )
                        cls.save_image(rotated, rotate_path)

                        # 处理标签
                        if has_labels:
                            rotate_label_path = rotate_path.replace('images', 'labels').rsplit('.', 1)[0] + '.txt'
                            rotated_labels = cls.transform_labels_rotate(labels, angle, img_width, img_height)
                            cls.save_yolo_labels(rotate_label_path, rotated_labels)
                            stats["labels_processed"] += 1

                        augmented_count += 1
                        stats["augmentations_applied"][f"rotate_{angle}"] = stats["augmentations_applied"].get(f"rotate_{angle}", 0) + 1

                # 添加噪声
                if "noise" in augmentation_options and augmented_count < multiplier - 1:
                    noise_types = augmentation_options["noise"].get("types", ["gaussian"])
                    noise_amount = augmentation_options["noise"].get("amount", 0.05)
                    for noise_type in noise_types:
                        if augmented_count >= multiplier - 1:
                            break
                        noisy = cls.add_noise(img, noise_type, noise_amount)
                        noise_path = os.path.join(
                            os.path.dirname(output_path),
                            f"noise_{noise_type}_{os.path.basename(output_path)}"
                        )
                        cls.save_image(noisy, noise_path)

                        # 处理标签 (噪声不影响标注框位置)
                        if has_labels:
                            noise_label_path = noise_path.replace('images', 'labels').rsplit('.', 1)[0] + '.txt'
                            cls.save_yolo_labels(noise_label_path, labels)
                            stats["labels_processed"] += 1

                        augmented_count += 1
                        stats["augmentations_applied"][f"noise_{noise_type}"] = stats["augmentations_applied"].get(f"noise_{noise_type}", 0) + 1

                # 亮度和对比度调整
                if "brightness_contrast" in augmentation_options and augmented_count < multiplier - 1:
                    brightness_range = augmentation_options["brightness_contrast"].get("brightness", [-20, 20])
                    contrast_range = augmentation_options["brightness_contrast"].get("contrast", [0.8, 1.2])

                    # 生成亮度和对比度组合
                    combinations = [
                        (brightness_range[0], contrast_range[0]),  # 暗+低对比度
                        (brightness_range[1], contrast_range[1]),  # 亮+高对比度
                        (brightness_range[0], contrast_range[1]),  # 暗+高对比度
                        (brightness_range[1], contrast_range[0])   # 亮+低对比度
                    ]

                    for i, (brightness, contrast) in enumerate(combinations):
                        if augmented_count >= multiplier - 1:
                            break
                        adjusted = cls.adjust_brightness_contrast(img, brightness, contrast)
                        adjust_path = os.path.join(
                            os.path.dirname(output_path),
                            f"adjust_{i}_{os.path.basename(output_path)}"
                        )
                        cls.save_image(adjusted, adjust_path)

                        # 处理标签 (亮度和对比度不影响标注框位置)
                        if has_labels:
                            adjust_label_path = adjust_path.replace('images', 'labels').rsplit('.', 1)[0] + '.txt'
                            cls.save_yolo_labels(adjust_label_path, labels)
                            stats["labels_processed"] += 1

                        augmented_count += 1
                        stats["augmentations_applied"][f"brightness_contrast_{i}"] = stats["augmentations_applied"].get(f"brightness_contrast_{i}", 0) + 1

                # 透视变换
                if augmentation_options.get("perspective", False) and augmented_count < multiplier - 1:
                    strength = augmentation_options.get("perspective_strength", 0.2)
                    perspective = cls.apply_perspective_transform(img, strength)
                    perspective_path = os.path.join(
                        os.path.dirname(output_path),
                        f"perspective_{os.path.basename(output_path)}"
                    )
                    cls.save_image(perspective, perspective_path)

                    # 处理标签
                    if has_labels:
                        perspective_label_path = perspective_path.replace('images', 'labels').rsplit('.', 1)[0] + '.txt'
                        perspective_labels = cls.transform_labels_perspective(labels, strength)
                        cls.save_yolo_labels(perspective_label_path, perspective_labels)
                        stats["labels_processed"] += 1

                    augmented_count += 1
                    stats["augmentations_applied"]["perspective"] = stats["augmentations_applied"].get("perspective", 0) + 1

                stats["augmented_images"] += augmented_count
                stats["total_images"] += augmented_count

            except Exception as e:
                logger.error(f"增强图像 {image_path} 失败: {str(e)}")
                continue

        return stats

    # ==================== 可视化功能 ====================

    @staticmethod
    def draw_bounding_boxes(
        image: np.ndarray,
        boxes: List[List[float]],
        labels: List[str] = None,
        confidences: List[float] = None,
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        在图像上绘制边界框

        Args:
            image: 输入图像
            boxes: 边界框列表，每个框是 [x1, y1, x2, y2] 或 [x, y, w, h, is_xywh]
            labels: 标签列表
            confidences: 置信度列表
            color: 边界框颜色 (B, G, R)
            thickness: 边界框线条粗细

        Returns:
            np.ndarray: 绘制了边界框的图像
        """
        output = image.copy()

        for i, box in enumerate(boxes):
            # 检查框的格式
            if len(box) == 5 and box[4]:  # [x, y, w, h, is_xywh]
                x, y, w, h = map(int, box[:4])
                x1, y1, x2, y2 = x, y, x + w, y + h
            else:  # [x1, y1, x2, y2]
                x1, y1, x2, y2 = map(int, box[:4])

            # 绘制边界框
            cv2.rectangle(output, (x1, y1), (x2, y2), color, thickness)

            # 绘制标签和置信度
            if labels is not None and i < len(labels):
                label = labels[i]
                if confidences is not None and i < len(confidences):
                    label = f"{label}: {confidences[i]:.2f}"

                # 计算标签位置
                text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                cv2.rectangle(output, (x1, y1 - text_size[1] - 5), (x1 + text_size[0], y1), color, -1)
                cv2.putText(output, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        return output

    @staticmethod
    def create_comparison_image(images: List[np.ndarray], titles: List[str] = None) -> np.ndarray:
        """
        创建图像比较视图

        Args:
            images: 图像列表
            titles: 标题列表

        Returns:
            np.ndarray: 比较图像
        """
        if not images:
            return None

        # 确保所有图像具有相同的大小
        height, width = images[0].shape[:2]
        for i in range(1, len(images)):
            images[i] = cv2.resize(images[i], (width, height))

        # 创建画布
        n_images = len(images)
        canvas_width = width * n_images
        canvas = np.zeros((height + 30, canvas_width, 3), dtype=np.uint8)

        # 放置图像
        for i, img in enumerate(images):
            # 确保图像是彩色的
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            # 放置图像
            x_offset = i * width
            canvas[30:height+30, x_offset:x_offset+width] = img

            # 添加标题
            if titles is not None and i < len(titles):
                title = titles[i]
                cv2.putText(canvas, title, (x_offset + 5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        return canvas

    @staticmethod
    def create_grid_image(images: List[np.ndarray], rows: int, cols: int, cell_size: Tuple[int, int] = None) -> np.ndarray:
        """
        创建图像网格

        Args:
            images: 图像列表
            rows: 行数
            cols: 列数
            cell_size: 单元格大小 (宽, 高)

        Returns:
            np.ndarray: 网格图像
        """
        if not images:
            return None

        n_images = len(images)
        n_cells = rows * cols

        # 如果图像数量少于单元格数量，填充空白图像
        if n_images < n_cells:
            blank_image = np.zeros_like(images[0])
            images.extend([blank_image] * (n_cells - n_images))
        # 如果图像数量多于单元格数量，截断
        elif n_images > n_cells:
            images = images[:n_cells]

        # 确定单元格大小
        if cell_size is None:
            cell_width, cell_height = images[0].shape[1], images[0].shape[0]
        else:
            cell_width, cell_height = cell_size

        # 调整所有图像大小
        for i in range(len(images)):
            images[i] = cv2.resize(images[i], (cell_width, cell_height))
            # 确保图像是彩色的
            if len(images[i].shape) == 2:
                images[i] = cv2.cvtColor(images[i], cv2.COLOR_GRAY2BGR)

        # 创建网格
        grid = np.zeros((cell_height * rows, cell_width * cols, 3), dtype=np.uint8)

        # 填充网格
        for i in range(rows):
            for j in range(cols):
                idx = i * cols + j
                if idx < len(images):
                    y_start = i * cell_height
                    y_end = (i + 1) * cell_height
                    x_start = j * cell_width
                    x_end = (j + 1) * cell_width
                    grid[y_start:y_end, x_start:x_end] = images[idx]

        return grid

    # ==================== 高级数据增强功能 ====================

    @staticmethod
    def apply_cutmix(img1: np.ndarray, img2: np.ndarray, alpha: float = 0.5) -> np.ndarray:
        """
        应用CutMix数据增强

        Args:
            img1: 第一张图像
            img2: 第二张图像
            alpha: 混合参数，控制裁剪区域大小

        Returns:
            np.ndarray: 增强后的图像
        """
        # 确保两张图像大小一致
        h, w = img1.shape[:2]
        img2 = cv2.resize(img2, (w, h))

        # 生成随机裁剪区域
        lam = np.random.beta(alpha, alpha)

        # 计算裁剪区域大小
        cut_w = int(w * np.sqrt(1 - lam))
        cut_h = int(h * np.sqrt(1 - lam))

        # 随机选择裁剪区域中心点
        cx = np.random.randint(w)
        cy = np.random.randint(h)

        # 计算裁剪区域边界
        x1 = max(0, cx - cut_w // 2)
        y1 = max(0, cy - cut_h // 2)
        x2 = min(w, cx + cut_w // 2)
        y2 = min(h, cy + cut_h // 2)

        # 创建结果图像
        result = img1.copy()

        # 将img2的区域粘贴到img1上
        result[y1:y2, x1:x2] = img2[y1:y2, x1:x2]

        return result

    @staticmethod
    def apply_mixup(img1: np.ndarray, img2: np.ndarray, alpha: float = 0.5) -> np.ndarray:
        """
        应用MixUp数据增强

        Args:
            img1: 第一张图像
            img2: 第二张图像
            alpha: 混合参数，控制混合权重

        Returns:
            np.ndarray: 增强后的图像
        """
        # 确保两张图像大小一致
        h, w = img1.shape[:2]
        img2 = cv2.resize(img2, (w, h))

        # 生成混合权重
        lam = np.random.beta(alpha, alpha)

        # 混合图像
        result = cv2.addWeighted(img1, lam, img2, 1 - lam, 0)

        return result

    @staticmethod
    def apply_mosaic(images: List[np.ndarray]) -> np.ndarray:
        """
        应用Mosaic数据增强

        Args:
            images: 四张图像的列表

        Returns:
            np.ndarray: 增强后的图像
        """
        if len(images) != 4:
            raise ValueError("Mosaic需要四张图像")

        # 确定输出图像大小
        output_size = 640

        # 创建空白画布
        mosaic_img = np.zeros((output_size, output_size, 3), dtype=np.uint8)

        # 计算中心点
        cx = output_size // 2
        cy = output_size // 2

        # 调整图像大小并放置到画布上
        # 左上
        img1 = cv2.resize(images[0], (cx, cy))
        mosaic_img[:cy, :cx] = img1

        # 右上
        img2 = cv2.resize(images[1], (cx, cy))
        mosaic_img[:cy, cx:] = img2

        # 左下
        img3 = cv2.resize(images[2], (cx, cy))
        mosaic_img[cy:, :cx] = img3

        # 右下
        img4 = cv2.resize(images[3], (cx, cy))
        mosaic_img[cy:, cx:] = img4

        return mosaic_img

    @staticmethod
    def apply_weather_effect(img: np.ndarray, weather_type: str, intensity: float = 0.5) -> np.ndarray:
        """
        应用天气效果

        Args:
            img: 输入图像
            weather_type: 天气类型 (rain, snow, fog)
            intensity: 效果强度 (0.0-1.0)

        Returns:
            np.ndarray: 增强后的图像
        """
        h, w = img.shape[:2]
        result = img.copy()

        # 限制强度范围
        intensity = max(0.1, min(1.0, intensity))

        if weather_type == "rain":
            # 模拟雨滴
            rain_drops = np.zeros((h, w, 3), dtype=np.uint8)

            # 雨滴数量与强度成正比
            num_drops = int(intensity * 1000)

            # 随机生成雨滴
            for _ in range(num_drops):
                x = np.random.randint(0, w)
                y = np.random.randint(0, h)
                length = np.random.randint(5, 15)
                angle = np.random.uniform(0.7, 0.9) * np.pi  # 雨滴角度

                # 绘制雨滴
                x2 = int(x + length * np.cos(angle))
                y2 = int(y + length * np.sin(angle))

                # 确保雨滴在图像范围内
                if 0 <= x2 < w and 0 <= y2 < h:
                    cv2.line(rain_drops, (x, y), (x2, y2), (200, 200, 255), 1)

            # 添加雨滴到原图
            result = cv2.addWeighted(result, 1.0, rain_drops, intensity, 0)

            # 降低亮度和对比度
            result = cv2.addWeighted(result, 0.8, np.zeros_like(result), 0, 0)

        elif weather_type == "snow":
            # 模拟雪花
            snow_layer = np.zeros((h, w, 3), dtype=np.uint8)

            # 雪花数量与强度成正比
            num_flakes = int(intensity * 1000)

            # 随机生成雪花
            for _ in range(num_flakes):
                x = np.random.randint(0, w)
                y = np.random.randint(0, h)
                size = np.random.randint(1, 4)

                # 绘制雪花
                cv2.circle(snow_layer, (x, y), size, (255, 255, 255), -1)

            # 添加雪花到原图
            result = cv2.addWeighted(result, 1.0, snow_layer, intensity, 0)

            # 增加亮度
            brightness = int(intensity * 30)
            result = cv2.addWeighted(result, 1.0, np.zeros_like(result), 0, brightness)

        elif weather_type == "fog":
            # 创建雾效果
            fog = np.ones((h, w, 3), dtype=np.uint8) * 255

            # 添加雾到原图
            result = cv2.addWeighted(result, 1 - intensity * 0.7, fog, intensity * 0.7, 0)

        else:
            raise ValueError(f"不支持的天气类型: {weather_type}")

        return result

    # ==================== 视频处理功能 ====================

    @staticmethod
    def get_video_info(video_path: Union[str, Path]) -> Dict[str, Any]:
        """
        获取视频信息

        Args:
            video_path: 视频文件路径

        Returns:
            Dict: 视频信息，包括宽度、高度、帧率、总帧数、时长等
        """
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"无法打开视频: {video_path}")

            # 获取视频属性
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0

            # 释放视频对象
            cap.release()

            return {
                "width": width,
                "height": height,
                "fps": fps,
                "frame_count": frame_count,
                "duration": duration,
                "duration_formatted": f"{int(duration // 60):02d}:{int(duration % 60):02d}"
            }
        except Exception as e:
            logger.error(f"获取视频信息失败: {str(e)}")
            raise HTTPException(status_code=400, detail=f"获取视频信息失败: {str(e)}")

    @classmethod
    def extract_frames(
        cls,
        video_path: Union[str, Path],
        output_dir: Union[str, Path],
        interval: float = 1.0,
        max_frames: Optional[int] = None,
        resize: Optional[Tuple[int, int]] = None,
        start_time: float = 0.0,
        end_time: Optional[float] = None,
        frame_format: str = "jpg",
        quality: int = 95,
        include_timestamp: bool = True
    ) -> Dict[str, Any]:
        """
        从视频中提取帧

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            interval: 提取帧的间隔（秒）
            max_frames: 最大提取帧数
            resize: 调整大小 (width, height)
            start_time: 开始时间（秒）
            end_time: 结束时间（秒），None表示到视频结束
            frame_format: 帧图像格式 ("jpg", "png")
            quality: 图像质量 (1-100)，仅对jpg有效
            include_timestamp: 是否在文件名中包含时间戳

        Returns:
            Dict: 提取结果，包括提取的帧数量、帧路径列表等
        """
        try:
            # 确保输出目录存在
            output_dir = Path(output_dir)
            os.makedirs(output_dir, exist_ok=True)

            # 创建进度文件
            progress_file = output_dir / "progress.json"
            with open(progress_file, "w") as f:
                json.dump({"status": "started", "progress": 0}, f)

            # 打开视频
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"无法打开视频: {video_path}")

            # 获取视频属性
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0

            # 计算帧间隔
            frame_interval = int(interval * fps)
            if frame_interval < 1:
                frame_interval = 1

            # 设置开始位置
            start_frame = int(start_time * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            # 计算结束位置
            end_frame = frame_count
            if end_time is not None:
                end_frame = min(int(end_time * fps), frame_count)

            # 计算总的预期帧数（用于进度计算）
            total_expected_frames = min(
                (end_frame - start_frame) // frame_interval + 1,
                max_frames if max_frames is not None else float('inf')
            )
            
            # 提取帧
            extracted_frames = []
            frame_index = start_frame
            extracted_count = 0

            while frame_index < end_frame:
                # 更新进度 - 基于实际提取的帧数而不是帧索引
                if total_expected_frames != float('inf'):
                    progress = min(99, int((extracted_count / total_expected_frames) * 100))
                else:
                    # 如果没有最大帧数限制，基于帧索引位置计算进度
                    progress = min(99, int(((frame_index - start_frame) / (end_frame - start_frame)) * 99))
                    
                with open(progress_file, "w") as f:
                    json.dump({"status": "processing", "progress": progress, "extracted_frames": extracted_count}, f)

                # 设置当前帧位置
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

                # 读取帧
                ret, frame = cap.read()
                if not ret:
                    break

                # 调整大小
                if resize is not None:
                    frame = cv2.resize(frame, resize)

                # 生成文件名
                timestamp = frame_index / fps
                if include_timestamp:
                    filename = f"frame_{frame_index:06d}_{timestamp:.2f}s.{frame_format}"
                else:
                    filename = f"frame_{frame_index:06d}.{frame_format}"

                # 保存帧
                output_path = output_dir / filename
                if frame_format.lower() == "jpg":
                    cv2.imwrite(str(output_path), frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
                else:
                    cv2.imwrite(str(output_path), frame)

                # 添加到结果列表
                extracted_frames.append({
                    "path": str(output_path),
                    "frame_index": frame_index,
                    "timestamp": timestamp,
                    "filename": filename
                })

                # 更新计数
                extracted_count += 1
                if max_frames is not None and extracted_count >= max_frames:
                    break

                # 更新帧索引
                frame_index += frame_interval

            # 更新最终进度
            with open(progress_file, "w") as f:
                json.dump({
                    "status": "completed", 
                    "progress": 100, 
                    "extracted_frames": extracted_count,
                    "total_frames": frame_count
                }, f)

            # 释放视频对象
            cap.release()

            return {
                "total_frames": frame_count,
                "extracted_frames": extracted_count,
                "frames": [frame["filename"] for frame in extracted_frames],  # 只返回文件名
                "video_info": {
                    "fps": fps,
                    "duration": duration,
                    "frame_count": frame_count
                }
            }
        except Exception as e:
            # 记录错误进度
            progress_file = Path(output_dir) / "progress.json"
            if progress_file.exists():
                with open(progress_file, "w") as f:
                    json.dump({"status": "failed", "error": str(e)}, f)
            
            logger.error(f"提取视频帧失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"提取视频帧失败: {str(e)}")

    @classmethod
    def detect_scenes(
        cls,
        video_path: Union[str, Path],
        threshold: float = 30.0,
        min_scene_length: int = 15
    ) -> Dict[str, Any]:
        """
        检测视频场景变化

        Args:
            video_path: 视频文件路径
            threshold: 场景变化阈值 (0-100)，值越小越敏感
            min_scene_length: 最小场景长度（帧数）

        Returns:
            Dict: 场景检测结果，包括场景列表、场景数量等
        """
        try:
            # 打开视频
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"无法打开视频: {video_path}")

            # 获取视频属性
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 读取第一帧
            ret, prev_frame = cap.read()
            if not ret:
                raise ValueError("无法读取视频帧")

            # 转换为灰度图
            prev_frame_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

            # 场景检测
            scenes = []
            current_scene_start = 0
            frame_index = 1

            while True:
                # 读取当前帧
                ret, frame = cap.read()
                if not ret:
                    break

                # 转换为灰度图
                frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # 计算帧差异
                diff = cv2.absdiff(prev_frame_gray, frame_gray)
                diff_mean = np.mean(diff)

                # 检测场景变化
                if diff_mean > threshold and (frame_index - current_scene_start) >= min_scene_length:
                    # 添加场景
                    scenes.append({
                        "start_frame": current_scene_start,
                        "end_frame": frame_index - 1,
                        "start_time": current_scene_start / fps,
                        "end_time": (frame_index - 1) / fps,
                        "duration": (frame_index - 1 - current_scene_start) / fps
                    })

                    # 更新场景起始帧
                    current_scene_start = frame_index

                # 更新前一帧
                prev_frame_gray = frame_gray
                frame_index += 1

            # 添加最后一个场景
            if current_scene_start < frame_count - 1:
                scenes.append({
                    "start_frame": current_scene_start,
                    "end_frame": frame_count - 1,
                    "start_time": current_scene_start / fps,
                    "end_time": (frame_count - 1) / fps,
                    "duration": (frame_count - 1 - current_scene_start) / fps
                })

            # 释放视频对象
            cap.release()

            return {
                "scene_count": len(scenes),
                "scenes": scenes,
                "video_info": {
                    "fps": fps,
                    "frame_count": frame_count,
                    "duration": frame_count / fps
                }
            }
        except Exception as e:
            logger.error(f"检测视频场景失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"检测视频场景失败: {str(e)}")

    @classmethod
    def detect_motion(
        cls,
        video_path: Union[str, Path],
        sensitivity: float = 20.0,
        blur_size: int = 21,
        min_area: int = 500
    ) -> Dict[str, Any]:
        """
        检测视频中的运动

        Args:
            video_path: 视频文件路径
            sensitivity: 运动检测灵敏度 (0-100)，值越小越敏感
            blur_size: 高斯模糊核大小，必须是奇数
            min_area: 最小运动区域面积（像素）

        Returns:
            Dict: 运动检测结果，包括运动帧列表、运动区域等
        """
        try:
            # 打开视频
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"无法打开视频: {video_path}")

            # 获取视频属性
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 创建背景减除器
            bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)

            # 确保blur_size是奇数
            if blur_size % 2 == 0:
                blur_size += 1

            # 运动检测
            motion_frames = []
            frame_index = 0

            while True:
                # 读取当前帧
                ret, frame = cap.read()
                if not ret:
                    break

                # 应用高斯模糊
                blurred = cv2.GaussianBlur(frame, (blur_size, blur_size), 0)

                # 应用背景减除
                fg_mask = bg_subtractor.apply(blurred)

                # 去除阴影
                _, fg_mask = cv2.threshold(fg_mask, 128, 255, cv2.THRESH_BINARY)

                # 形态学操作
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

                # 查找轮廓
                contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                # 过滤小轮廓
                significant_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_area]

                # 如果有显著运动
                if significant_contours:
                    # 计算运动区域
                    motion_regions = []
                    for contour in significant_contours:
                        x, y, w, h = cv2.boundingRect(contour)
                        area = w * h
                        motion_regions.append({
                            "x": x,
                            "y": y,
                            "width": w,
                            "height": h,
                            "area": area
                        })

                    # 添加到运动帧列表
                    motion_frames.append({
                        "frame_index": frame_index,
                        "timestamp": frame_index / fps,
                        "motion_regions": motion_regions,
                        "motion_count": len(significant_contours)
                    })

                frame_index += 1

            # 释放视频对象
            cap.release()

            return {
                "motion_frame_count": len(motion_frames),
                "motion_frames": motion_frames,
                "video_info": {
                    "fps": fps,
                    "frame_count": frame_count,
                    "duration": frame_count / fps
                }
            }
        except Exception as e:
            logger.error(f"检测视频运动失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"检测视频运动失败: {str(e)}")

    @classmethod
    def create_dataset_from_video(
        cls,
        video_path: Union[str, Path],
        output_dir: Union[str, Path],
        extraction_method: str = "interval",
        interval: float = 1.0,
        scene_threshold: float = 30.0,
        motion_sensitivity: float = 20.0,
        max_frames: Optional[int] = None,
        resize: Optional[Tuple[int, int]] = None,
        split_ratio: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        从视频创建数据集

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            extraction_method: 提取方法 ("interval", "scene", "motion")
            interval: 提取帧的间隔（秒），用于interval方法
            scene_threshold: 场景变化阈值，用于scene方法
            motion_sensitivity: 运动检测灵敏度，用于motion方法
            max_frames: 最大提取帧数
            resize: 调整大小 (width, height)
            split_ratio: 数据集分割比例 {"train": 0.7, "val": 0.2, "test": 0.1}

        Returns:
            Dict: 数据集创建结果
        """
        try:
            # 确保输出目录存在
            output_dir = Path(output_dir)
            os.makedirs(output_dir, exist_ok=True)

            # 创建数据集子目录
            train_dir = output_dir / "train" / "images"
            val_dir = output_dir / "val" / "images"
            test_dir = output_dir / "test" / "images"

            os.makedirs(train_dir, exist_ok=True)
            os.makedirs(val_dir, exist_ok=True)
            os.makedirs(test_dir, exist_ok=True)
            os.makedirs(output_dir / "train" / "labels", exist_ok=True)
            os.makedirs(output_dir / "val" / "labels", exist_ok=True)
            os.makedirs(output_dir / "test" / "labels", exist_ok=True)

            # 设置默认分割比例
            if split_ratio is None:
                split_ratio = {"train": 0.7, "val": 0.2, "test": 0.1}

            # 根据提取方法获取帧
            frames = []

            if extraction_method == "interval":
                # 按间隔提取帧
                result = cls.extract_frames(
                    video_path=video_path,
                    output_dir=output_dir / "temp",
                    interval=interval,
                    max_frames=max_frames,
                    resize=resize
                )
                frames = result["frames"]

            elif extraction_method == "scene":
                # 按场景提取帧
                os.makedirs(output_dir / "temp", exist_ok=True)

                # 检测场景
                scene_result = cls.detect_scenes(
                    video_path=video_path,
                    threshold=scene_threshold
                )

                # 从每个场景中提取关键帧
                cap = cv2.VideoCapture(str(video_path))
                if not cap.isOpened():
                    raise ValueError(f"无法打开视频: {video_path}")

                for i, scene in enumerate(scene_result["scenes"]):
                    # 计算场景中点
                    mid_frame = int((scene["start_frame"] + scene["end_frame"]) / 2)

                    # 设置帧位置
                    cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)

                    # 读取帧
                    ret, frame = cap.read()
                    if not ret:
                        continue

                    # 调整大小
                    if resize is not None:
                        frame = cv2.resize(frame, resize)

                    # 保存帧
                    filename = f"scene_{i:03d}_frame_{mid_frame:06d}.jpg"
                    output_path = output_dir / "temp" / filename
                    cv2.imwrite(str(output_path), frame)

                    # 添加到帧列表
                    frames.append({
                        "path": str(output_path),
                        "frame_index": mid_frame,
                        "timestamp": mid_frame / scene_result["video_info"]["fps"],
                        "scene_index": i
                    })

                    # 检查是否达到最大帧数
                    if max_frames is not None and len(frames) >= max_frames:
                        break

                cap.release()

            elif extraction_method == "motion":
                # 按运动提取帧
                os.makedirs(output_dir / "temp", exist_ok=True)

                # 检测运动
                motion_result = cls.detect_motion(
                    video_path=video_path,
                    sensitivity=motion_sensitivity
                )

                # 从运动帧中提取图像
                cap = cv2.VideoCapture(str(video_path))
                if not cap.isOpened():
                    raise ValueError(f"无法打开视频: {video_path}")

                for i, motion_frame in enumerate(motion_result["motion_frames"]):
                    # 设置帧位置
                    frame_index = motion_frame["frame_index"]
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

                    # 读取帧
                    ret, frame = cap.read()
                    if not ret:
                        continue

                    # 调整大小
                    if resize is not None:
                        frame = cv2.resize(frame, resize)

                    # 保存帧
                    filename = f"motion_{i:03d}_frame_{frame_index:06d}.jpg"
                    output_path = output_dir / "temp" / filename
                    cv2.imwrite(str(output_path), frame)

                    # 添加到帧列表
                    frames.append({
                        "path": str(output_path),
                        "frame_index": frame_index,
                        "timestamp": motion_frame["timestamp"],
                        "motion_index": i
                    })

                    # 检查是否达到最大帧数
                    if max_frames is not None and len(frames) >= max_frames:
                        break

                cap.release()

            else:
                raise ValueError(f"未知的提取方法: {extraction_method}")

            # 随机打乱帧列表
            import random
            random.shuffle(frames)

            # 分割数据集
            total_frames = len(frames)
            train_count = int(total_frames * split_ratio["train"])
            val_count = int(total_frames * split_ratio["val"])
            test_count = total_frames - train_count - val_count

            train_frames = frames[:train_count]
            val_frames = frames[train_count:train_count+val_count]
            test_frames = frames[train_count+val_count:]

            # 移动文件到相应目录
            dataset_files = {
                "train": [],
                "val": [],
                "test": []
            }

            # 处理训练集
            for i, frame in enumerate(train_frames):
                src_path = frame["path"]
                dst_filename = f"train_{i:06d}.jpg"
                dst_path = train_dir / dst_filename
                shutil.copy2(src_path, dst_path)
                dataset_files["train"].append(str(dst_path))

            # 处理验证集
            for i, frame in enumerate(val_frames):
                src_path = frame["path"]
                dst_filename = f"val_{i:06d}.jpg"
                dst_path = val_dir / dst_filename
                shutil.copy2(src_path, dst_path)
                dataset_files["val"].append(str(dst_path))

            # 处理测试集
            for i, frame in enumerate(test_frames):
                src_path = frame["path"]
                dst_filename = f"test_{i:06d}.jpg"
                dst_path = test_dir / dst_filename
                shutil.copy2(src_path, dst_path)
                dataset_files["test"].append(str(dst_path))

            # 创建classes.txt文件
            with open(output_dir / "classes.txt", "w", encoding="utf-8") as f:
                f.write("object\n")

            # 创建dataset.yaml文件
            dataset_yaml = {
                "path": str(output_dir.resolve()),
                "train": str((output_dir / "train" / "images").resolve()),
                "val": str((output_dir / "val" / "images").resolve()),
                "test": str((output_dir / "test" / "images").resolve()),
                "nc": 1,
                "names": ["object"]
            }

            import yaml
            with open(output_dir / "dataset.yaml", "w", encoding="utf-8") as f:
                yaml.dump(dataset_yaml, f, default_flow_style=False)

            # 清理临时文件
            if (output_dir / "temp").exists():
                shutil.rmtree(output_dir / "temp")

            return {
                "dataset_dir": str(output_dir),
                "total_frames": total_frames,
                "train_frames": len(train_frames),
                "val_frames": len(val_frames),
                "test_frames": len(test_frames),
                "classes": ["object"],
                "dataset_files": dataset_files
            }
        except Exception as e:
            logger.error(f"从视频创建数据集失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"从视频创建数据集失败: {str(e)}")

# 创建单例实例
opencv_service = OpenCVService()
