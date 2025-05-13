"""
基于自注意力机制的目标追踪模块

该模块实现了一个基于自注意力机制的目标追踪器，可以在视频序列中追踪多个目标。
追踪器结合了外观特征和运动特征，使用自注意力机制计算目标在不同帧之间的关联性。
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import cv2
from typing import List, Dict, Tuple, Optional, Union, Any
from pathlib import Path
import time
import uuid
import logging
from collections import deque

from app.nn.modules.attention import SelfAttention, TransformerEncoder

logger = logging.getLogger(__name__)


class FeatureExtractor(nn.Module):
    """
    特征提取器，用于从目标图像中提取特征

    参数:
        input_dim (int): 输入特征的维度
        feature_dim (int): 输出特征的维度
    """

    def __init__(self, input_dim: int = 1024, feature_dim: int = 256):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1)
        self.bn1 = nn.BatchNorm2d(64)
        self.conv2 = nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1)
        self.bn2 = nn.BatchNorm2d(128)
        self.conv3 = nn.Conv2d(128, 256, kernel_size=3, stride=2, padding=1)
        self.bn3 = nn.BatchNorm2d(256)
        self.gap = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Linear(256, feature_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        参数:
            x (torch.Tensor): 输入图像 [B, 3, H, W]

        返回:
            torch.Tensor: 提取的特征 [B, feature_dim]
        """
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.gap(x).squeeze(-1).squeeze(-1)
        x = self.fc(x)
        return x


class AttentionTracker:
    """
    基于自注意力机制的目标追踪器

    参数:
        max_age (int): 目标消失后保持跟踪的最大帧数
        min_hits (int): 确认目标存在所需的最小检测次数
        iou_threshold (float): IOU匹配阈值
        feature_similarity_weight (float): 特征相似度权重
        motion_weight (float): 运动预测权重
        device (str): 使用的设备 ('cpu' 或 'cuda')
    """

    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3,
        feature_similarity_weight: float = 0.7,
        motion_weight: float = 0.3,
        device: str = 'cpu'
    ):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.feature_similarity_weight = feature_similarity_weight
        self.motion_weight = motion_weight
        self.device = device

        # 初始化特征提取器
        self.feature_extractor = FeatureExtractor().to(device)
        self.feature_extractor.eval()

        # 初始化自注意力模块
        self.attention = SelfAttention(dim=256, num_heads=8).to(device)
        self.attention.eval()

        # 初始化轨迹列表
        self.tracks = []
        self.next_id = 1

        # 初始化帧计数器
        self.frame_count = 0

        # 是否处于单目标模式
        self.single_target_mode = False
        self.target_id = None

    def reset(self):
        """重置追踪器状态"""
        self.tracks = []
        self.next_id = 1
        self.frame_count = 0
        self.single_target_mode = False
        self.target_id = None

    def set_single_target_mode(self, enable: bool, target_id: Optional[int] = None, target_class_id: Optional[int] = None):
        """
        设置单目标追踪模式

        参数:
            enable (bool): 是否启用单目标模式
            target_id (int, optional): 要追踪的目标ID
            target_class_id (int, optional): 要追踪的目标类别ID
        """
        logger.info(f"设置单目标追踪模式: enable={enable}, target_id={target_id}, target_class_id={target_class_id}")

        # 更新单目标模式状态
        self.single_target_mode = enable

        # 如果禁用单目标模式，清除目标ID
        if not enable:
            self.target_id = None
            logger.info("已禁用单目标追踪模式")
            return

        # 启用单目标模式
        if target_id is not None:
            # 如果提供了目标ID，直接使用
            self.target_id = target_id
            logger.info(f"已启用单目标追踪模式，追踪目标ID: {target_id}")
        elif target_class_id is not None:
            # 如果提供了类别ID，保存类别ID，在update方法中处理
            self.target_class_id = target_class_id
            logger.info(f"已启用单目标追踪模式，追踪类别ID: {target_class_id}")

            # 如果已有轨迹，查找该类别的第一个目标
            for track in self.tracks:
                if track['class_id'] == target_class_id:
                    self.target_id = track['id']
                    logger.info(f"找到类别ID为 {target_class_id} 的目标，目标ID: {self.target_id}")
                    break

            # 如果没有找到该类别的目标，记录信息
            if self.target_id is None:
                logger.info(f"未找到类别ID为 {target_class_id} 的目标，将在下一帧中查找")
        else:
            logger.warning("启用单目标追踪模式但未提供目标ID或类别ID，单目标追踪模式可能无效")

    def extract_features(self, image: np.ndarray, boxes: List[List[int]]) -> torch.Tensor:
        """
        从图像中提取目标特征

        参数:
            image (np.ndarray): 输入图像
            boxes (List[List[int]]): 目标边界框列表 [[x1, y1, x2, y2], ...]

        返回:
            torch.Tensor: 提取的特征 [num_boxes, feature_dim]
        """
        if not boxes:
            return torch.zeros((0, 256), device=self.device)

        # 裁剪目标区域
        crops = []
        for box in boxes:
            x1, y1, x2, y2 = box
            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                # 如果裁剪区域为空，使用整个图像
                crop = image
            # 调整大小为固定尺寸
            crop = cv2.resize(crop, (64, 64))
            crops.append(crop)

        # 转换为张量
        crops_tensor = torch.stack([
            torch.from_numpy(crop.transpose(2, 0, 1)).float() / 255.0
            for crop in crops
        ]).to(self.device)

        # 提取特征
        with torch.no_grad():
            features = self.feature_extractor(crops_tensor)

        return features

    def compute_attention_similarity(self, track_features: torch.Tensor, detection_features: torch.Tensor) -> torch.Tensor:
        """
        使用自注意力机制计算轨迹和检测之间的相似度

        参数:
            track_features (torch.Tensor): 轨迹特征 [num_tracks, feature_dim]
            detection_features (torch.Tensor): 检测特征 [num_detections, feature_dim]

        返回:
            torch.Tensor: 相似度矩阵 [num_tracks, num_detections]
        """
        if track_features.size(0) == 0 or detection_features.size(0) == 0:
            return torch.zeros((track_features.size(0), detection_features.size(0)), device=self.device)

        # 合并特征
        combined_features = torch.cat([track_features, detection_features], dim=0)

        # 添加位置编码
        batch_size, seq_len = 1, combined_features.size(0)
        combined_features = combined_features.unsqueeze(0)  # [1, N, feature_dim]

        # 应用自注意力
        with torch.no_grad():
            attended_features, attention_weights = self.attention(
                combined_features,
                combined_features,
                combined_features
            )

        # 提取相似度矩阵
        num_tracks = track_features.size(0)
        similarity = attention_weights[0, :num_tracks, num_tracks:]

        return similarity

    def compute_iou(self, box1: List[int], box2: List[int]) -> float:
        """
        计算两个边界框的IOU

        参数:
            box1 (List[int]): 第一个边界框 [x1, y1, x2, y2]
            box2 (List[int]): 第二个边界框 [x1, y1, x2, y2]

        返回:
            float: IOU值
        """
        try:
            # 确保边界框至少有4个元素
            if len(box1) < 4 or len(box2) < 4:
                logger.warning(f"边界框维度不足4: box1={len(box1)}, box2={len(box2)}")
                # 填充边界框
                if len(box1) < 4:
                    box1 = box1 + [0] * (4 - len(box1))
                if len(box2) < 4:
                    box2 = box2 + [0] * (4 - len(box2))

            # 确保边界框坐标是浮点数
            x1_1, y1_1, x2_1, y2_1 = map(float, box1[:4])
            x1_2, y1_2, x2_2, y2_2 = map(float, box2[:4])

            # 计算交集区域
            x1_i = max(x1_1, x1_2)
            y1_i = max(y1_1, y1_2)
            x2_i = min(x2_1, x2_2)
            y2_i = min(y2_1, y2_2)

            if x2_i < x1_i or y2_i < y1_i:
                return 0.0

            intersection = (x2_i - x1_i) * (y2_i - y1_i)

            # 计算各自面积
            area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
            area2 = (x2_2 - x1_2) * (y2_2 - y1_2)

            # 计算IOU
            iou = intersection / (area1 + area2 - intersection + 1e-6)

            return iou
        except Exception as e:
            logger.warning(f"计算IOU时出错: {str(e)}")
            return 0.0

    def predict(self):
        """预测所有轨迹的下一个位置"""
        for track in self.tracks:
            # 获取最后一个边界框
            box = track['boxes'][-1]

            # 如果有足够的历史记录，使用卡尔曼滤波或简单线性预测
            if len(track['boxes']) >= 2:
                prev_box = track['boxes'][-2]

                # 计算速度
                vx = box[0] - prev_box[0]
                vy = box[1] - prev_box[1]
                vw = (box[2] - box[0]) - (prev_box[2] - prev_box[0])
                vh = (box[3] - box[1]) - (prev_box[3] - prev_box[1])

                # 预测下一个位置
                x1 = box[0] + vx
                y1 = box[1] + vy
                x2 = box[2] + vx + vw
                y2 = box[3] + vy + vh

                track['predicted_box'] = [x1, y1, x2, y2]
            else:
                # 如果没有足够的历史记录，使用当前位置作为预测
                track['predicted_box'] = box

    def update(self, image: np.ndarray, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        更新追踪器状态

        参数:
            image (np.ndarray): 当前帧图像
            detections (List[Dict]): 检测结果列表，每个检测包含 'bbox', 'class_id', 'confidence' 等字段

        返回:
            List[Dict]: 更新后的轨迹列表
        """
        self.frame_count += 1

        # 如果没有轨迹，初始化轨迹
        if len(self.tracks) == 0:
            for i, det in enumerate(detections):
                if self.single_target_mode and i != self.target_id:
                    continue

                # 确保检测结果格式正确
                if not isinstance(det, dict):
                    logger.warning(f"检测结果 #{i} 不是字典: {det}")
                    continue

                # 获取必要的字段，使用安全的方式
                try:
                    bbox = det.get('bbox', None)
                    if bbox is None or not isinstance(bbox, list) or len(bbox) != 4:
                        logger.warning(f"检测结果 #{i} 的边界框格式不正确: {bbox}")
                        continue

                    class_id = det.get('class_id', 0)
                    confidence = det.get('confidence', 0.5)
                except Exception as e:
                    logger.warning(f"处理检测结果 #{i} 时出错: {str(e)}")
                    continue

                # 提取特征
                features = self.extract_features(image, [bbox])

                # 创建新轨迹
                self.tracks.append({
                    'id': self.next_id,
                    'boxes': [bbox],
                    'class_id': class_id,
                    'confidence': confidence,
                    'features': [features[0]],
                    'age': 1,
                    'hits': 1,
                    'time_since_update': 0,
                    'predicted_box': bbox,
                    'trajectory': [((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)]
                })

                self.next_id += 1

            return self.get_active_tracks()

        # 预测轨迹的下一个位置
        self.predict()

        # 如果没有检测，更新轨迹状态
        if len(detections) == 0:
            for track in self.tracks:
                track['time_since_update'] += 1

            return self.get_active_tracks()

        # 提取检测特征
        detection_boxes = []
        for det in detections:
            try:
                if isinstance(det, dict) and 'bbox' in det:
                    bbox = det['bbox']
                    if isinstance(bbox, list) and len(bbox) == 4:
                        detection_boxes.append(bbox)
            except Exception as e:
                logger.warning(f"提取检测框时出错: {str(e)}")

        # 如果没有有效的检测框，返回空结果
        if not detection_boxes:
            return self.get_active_tracks()

        detection_features = self.extract_features(image, detection_boxes)

        # 提取轨迹特征
        track_features = torch.stack([track['features'][-1] for track in self.tracks])

        # 计算特征相似度
        feature_similarity = self.compute_attention_similarity(track_features, detection_features)

        # 计算IOU矩阵
        iou_matrix = torch.zeros((len(self.tracks), len(detections)), device=self.device)
        for i, track in enumerate(self.tracks):
            for j, det in enumerate(detections):
                try:
                    if isinstance(det, dict) and 'bbox' in det:
                        bbox = det['bbox']
                        if isinstance(bbox, list) and len(bbox) == 4:
                            iou = self.compute_iou(track['predicted_box'], bbox)
                            iou_matrix[i, j] = iou
                except Exception as e:
                    logger.warning(f"计算IOU时出错: {str(e)}")

        # 计算综合相似度
        similarity_matrix = (
            self.feature_similarity_weight * feature_similarity +
            self.motion_weight * iou_matrix
        )

        # 匹配轨迹和检测
        matched_indices = []
        unmatched_tracks = list(range(len(self.tracks)))
        unmatched_detections = list(range(len(detections)))

        # 贪心匹配
        similarity_matrix_np = similarity_matrix.cpu().numpy()
        while len(unmatched_tracks) > 0 and len(unmatched_detections) > 0:
            # 找到最大相似度
            track_idx, det_idx = np.unravel_index(
                np.argmax(similarity_matrix_np[unmatched_tracks][:, unmatched_detections]),
                (len(unmatched_tracks), len(unmatched_detections))
            )

            track_idx = unmatched_tracks[track_idx]
            det_idx = unmatched_detections[det_idx]

            # 如果相似度太低，停止匹配
            if similarity_matrix_np[track_idx, det_idx] < self.iou_threshold:
                break

            # 添加匹配
            matched_indices.append((track_idx, det_idx))

            # 从未匹配列表中移除
            unmatched_tracks.remove(track_idx)
            unmatched_detections.remove(det_idx)

        # 更新匹配的轨迹
        for track_idx, det_idx in matched_indices:
            try:
                track = self.tracks[track_idx]
                det = detections[det_idx]

                # 确保检测结果格式正确
                if not isinstance(det, dict):
                    logger.warning(f"匹配的检测结果 #{det_idx} 不是字典: {det}")
                    continue

                # 获取必要的字段
                bbox = det.get('bbox', None)
                if bbox is None or not isinstance(bbox, list) or len(bbox) != 4:
                    logger.warning(f"匹配的检测结果 #{det_idx} 的边界框格式不正确: {bbox}")
                    continue

                class_id = det.get('class_id', track['class_id'])
                confidence = det.get('confidence', track['confidence'])

                # 更新轨迹
                track['boxes'].append(bbox)
                track['features'].append(detection_features[det_idx])
                track['class_id'] = class_id  # 更新类别ID
                track['confidence'] = confidence  # 更新置信度
                track['age'] += 1
                track['hits'] += 1
                track['time_since_update'] = 0

                # 更新轨迹中心点
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                track['trajectory'].append((center_x, center_y))
            except Exception as e:
                logger.warning(f"更新轨迹 #{track_idx} 时出错: {str(e)}")

        # 更新未匹配的轨迹
        for track_idx in unmatched_tracks:
            track = self.tracks[track_idx]
            track['time_since_update'] += 1

        # 创建新轨迹
        for det_idx in unmatched_detections:
            try:
                det = detections[det_idx]

                # 如果是单目标模式且已有目标，不创建新轨迹
                if self.single_target_mode and len(self.tracks) > 0:
                    continue

                # 确保检测结果格式正确
                if not isinstance(det, dict):
                    logger.warning(f"未匹配的检测结果 #{det_idx} 不是字典: {det}")
                    continue

                # 获取必要的字段
                bbox = det.get('bbox', None)
                if bbox is None or not isinstance(bbox, list) or len(bbox) != 4:
                    logger.warning(f"未匹配的检测结果 #{det_idx} 的边界框格式不正确: {bbox}")
                    continue

                class_id = det.get('class_id', 0)
                confidence = det.get('confidence', 0.5)

                # 提取特征
                if det_idx >= len(detection_features):
                    logger.warning(f"检测特征索引越界: {det_idx} >= {len(detection_features)}")
                    continue

                features = detection_features[det_idx].unsqueeze(0)

                # 创建新轨迹
                self.tracks.append({
                    'id': self.next_id,
                    'boxes': [bbox],
                    'class_id': class_id,
                    'confidence': confidence,
                    'features': [features[0]],
                    'age': 1,
                    'hits': 1,
                    'time_since_update': 0,
                    'predicted_box': bbox,
                    'trajectory': [((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)]
                })

                self.next_id += 1
            except Exception as e:
                logger.warning(f"创建新轨迹时出错: {str(e)}")

        # 删除过期的轨迹
        self.tracks = [
            track for track in self.tracks
            if track['time_since_update'] <= self.max_age
        ]

        return self.get_active_tracks()

    def get_active_tracks(self) -> List[Dict[str, Any]]:
        """
        获取活跃的轨迹

        返回:
            List[Dict]: 活跃轨迹列表
        """
        active_tracks = []

        for track in self.tracks:
            # 只返回命中次数足够的轨迹
            if track['hits'] >= self.min_hits and track['time_since_update'] <= 1:
                # 如果是单目标模式，只返回目标轨迹
                if self.single_target_mode and track['id'] != self.target_id:
                    continue

                # 复制轨迹信息
                track_info = {
                    'id': track['id'],
                    'bbox': track['boxes'][-1],
                    'class_id': track['class_id'],
                    'confidence': track['confidence'],
                    'age': track['age'],
                    'time_since_update': track['time_since_update'],
                    'trajectory': track['trajectory']
                }

                active_tracks.append(track_info)

        return active_tracks

    # 追踪报告功能已移除
