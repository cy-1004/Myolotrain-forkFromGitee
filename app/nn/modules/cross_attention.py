"""
交叉注意力 (Cross-Attention) 模块

交叉注意力机制允许模型在不同特征集之间建立关联，
非常适合目标追踪任务中的目标匹配。

主要组件:
1. 交叉注意力 (CrossAttention): 使用一组特征作为查询(Q)，另一组特征作为键(K)和值(V)
2. 交叉注意力追踪器 (CrossAttentionTracker): 使用交叉注意力进行目标匹配

技术原理:
- 与自注意力不同，交叉注意力使用不同的特征集作为查询和键/值
- 这允许模型学习两组特征之间的关系，而不仅仅是单个特征集内的关系
- 在目标追踪中，可以使用当前帧的目标特征作为查询，历史帧的目标特征作为键和值
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple, List, Union


class CrossAttention(nn.Module):
    """
    交叉注意力模块

    使用一组特征作为查询(Q)，另一组特征作为键(K)和值(V)，
    计算它们之间的关联性。

    参数:
        dim (int): 特征维度
        num_heads (int): 注意力头的数量
        qkv_bias (bool): 是否在QKV投影中使用偏置
        attn_drop (float): 注意力dropout率
        proj_drop (float): 输出投影dropout率
    """

    def __init__(
        self,
        dim: int,
        num_heads: int = 8,
        qkv_bias: bool = False,
        attn_drop: float = 0.0,
        proj_drop: float = 0.0
    ):
        super().__init__()
        self.num_heads = num_heads
        head_dim = dim // num_heads
        self.scale = head_dim ** -0.5  # 缩放因子

        # 查询、键、值的线性投影
        self.q_proj = nn.Linear(dim, dim, bias=qkv_bias)
        self.k_proj = nn.Linear(dim, dim, bias=qkv_bias)
        self.v_proj = nn.Linear(dim, dim, bias=qkv_bias)

        self.attn_drop = nn.Dropout(attn_drop)
        self.proj = nn.Linear(dim, dim)
        self.proj_drop = nn.Dropout(proj_drop)

    def forward(
        self,
        query: torch.Tensor,
        key_value: torch.Tensor,
        attn_mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        前向传播

        参数:
            query (torch.Tensor): 查询特征 [B, Nq, C]
            key_value (torch.Tensor): 键值特征 [B, Nkv, C]
            attn_mask (torch.Tensor, optional): 注意力掩码 [B, Nq, Nkv]

        返回:
            Tuple[torch.Tensor, torch.Tensor]:
                - 输出特征 [B, Nq, C]
                - 注意力权重 [B, num_heads, Nq, Nkv]
        """
        B, Nq, C = query.shape
        _, Nkv, _ = key_value.shape

        # 投影查询、键、值
        q = self.q_proj(query).reshape(B, Nq, self.num_heads, C // self.num_heads).permute(0, 2, 1, 3)
        k = self.k_proj(key_value).reshape(B, Nkv, self.num_heads, C // self.num_heads).permute(0, 2, 1, 3)
        v = self.v_proj(key_value).reshape(B, Nkv, self.num_heads, C // self.num_heads).permute(0, 2, 1, 3)

        # 计算注意力分数
        attn = (q @ k.transpose(-2, -1)) * self.scale  # [B, num_heads, Nq, Nkv]

        # 应用掩码（如果提供）
        if attn_mask is not None:
            if attn_mask.dim() == 3:  # [B, Nq, Nkv]
                attn_mask = attn_mask.unsqueeze(1)  # [B, 1, Nq, Nkv]
            attn = attn.masked_fill(attn_mask == 0, float('-inf'))

        # 应用softmax和dropout
        attn = attn.softmax(dim=-1)
        attn = self.attn_drop(attn)

        # 加权聚合
        x = (attn @ v).transpose(1, 2).reshape(B, Nq, C)
        x = self.proj(x)
        x = self.proj_drop(x)

        return x, attn


class CrossAttentionTracker(nn.Module):
    """
    基于交叉注意力的目标追踪器

    使用交叉注意力机制计算当前帧目标与历史帧目标之间的关联性，
    实现目标匹配和轨迹管理。

    参数:
        feature_dim (int): 特征维度
        num_heads (int): 注意力头的数量
        dropout (float): dropout率
        appearance_weight (float): 外观特征权重
        motion_weight (float): 运动特征权重
    """

    def __init__(
        self,
        feature_dim: int = 256,
        num_heads: int = 8,
        dropout: float = 0.1,
        appearance_weight: float = 0.7,
        motion_weight: float = 0.3
    ):
        super().__init__()
        self.feature_dim = feature_dim
        self.appearance_weight = appearance_weight
        self.motion_weight = motion_weight

        # 交叉注意力模块
        self.cross_attention = CrossAttention(
            dim=feature_dim,
            num_heads=num_heads,
            attn_drop=dropout,
            proj_drop=dropout
        )

        # 特征转换
        self.appearance_transform = nn.Sequential(
            nn.Linear(feature_dim, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.ReLU(inplace=True)
        )

        self.motion_transform = nn.Sequential(
            nn.Linear(4, feature_dim // 4),
            nn.ReLU(inplace=True),
            nn.Linear(feature_dim // 4, feature_dim),
            nn.LayerNorm(feature_dim)
        )

        # 特征融合
        self.fusion = nn.Sequential(
            nn.Linear(feature_dim * 2, feature_dim),
            nn.LayerNorm(feature_dim),
            nn.ReLU(inplace=True)
        )

    def compute_motion_features(
        self,
        current_boxes: torch.Tensor,
        history_boxes: torch.Tensor
    ) -> torch.Tensor:
        """
        计算运动特征

        参数:
            current_boxes (torch.Tensor): 当前帧边界框 [num_current, 4]
            history_boxes (torch.Tensor): 历史帧边界框 [num_history, 4]

        返回:
            torch.Tensor: 运动特征 [num_current, num_history, feature_dim]
        """
        try:
            # 检查边界框维度
            if current_boxes.dim() < 2 or history_boxes.dim() < 2:
                raise ValueError(f"边界框维度不正确: current_boxes.dim()={current_boxes.dim()}, history_boxes.dim()={history_boxes.dim()}")

            # 确保边界框是4维的
            if current_boxes.size(-1) != 4 or history_boxes.size(-1) != 4:
                logger.warning(f"边界框维度不是4: current_boxes.size(-1)={current_boxes.size(-1)}, history_boxes.size(-1)={history_boxes.size(-1)}")
                # 如果维度不是4，创建一个全零的特征张量
                num_current = current_boxes.size(0)
                num_history = history_boxes.size(0)
                return torch.zeros((num_current, num_history, self.feature_dim), device=current_boxes.device)

            num_current = current_boxes.size(0)
            num_history = history_boxes.size(0)

            # 计算边界框中心点和尺寸
            def box_to_center_size(boxes):
                # 确保boxes的最后一个维度是4
                if boxes.size(-1) != 4:
                    logger.warning(f"边界框维度不是4: {boxes.size()}")
                    # 如果不是4，填充或截断到4
                    if boxes.size(-1) < 4:
                        # 填充
                        padding = torch.zeros(*boxes.shape[:-1], 4 - boxes.size(-1), device=boxes.device)
                        boxes = torch.cat([boxes, padding], dim=-1)
                    else:
                        # 截断
                        boxes = boxes[..., :4]

                x1, y1, x2, y2 = boxes.unbind(-1)
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                w = x2 - x1
                h = y2 - y1
                return torch.stack([cx, cy, w, h], dim=-1)

            current_centers = box_to_center_size(current_boxes)  # [num_current, 4]
            history_centers = box_to_center_size(history_boxes)  # [num_history, 4]

            # 计算所有当前框与历史框之间的差异
            current_expanded = current_centers.unsqueeze(1).expand(-1, num_history, -1)  # [num_current, num_history, 4]
            history_expanded = history_centers.unsqueeze(0).expand(num_current, -1, -1)  # [num_current, num_history, 4]

            # 计算中心点距离和尺寸比例
            motion_features = torch.cat([
                current_expanded - history_expanded,  # 中心点位移
                current_expanded / (history_expanded + 1e-6)  # 尺寸比例
            ], dim=-1)  # [num_current, num_history, 8]

            # 转换为特征表示
            motion_features = self.motion_transform(motion_features[:, :, :4])  # 只使用位移信息

            return motion_features
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"计算运动特征时出错: {str(e)}")
            # 创建一个全零的特征张量作为备选
            num_current = current_boxes.size(0) if current_boxes.dim() > 0 else 0
            num_history = history_boxes.size(0) if history_boxes.dim() > 0 else 0
            return torch.zeros((max(num_current, 1), max(num_history, 1), self.feature_dim),
                              device=current_boxes.device)

    def compute_similarity(
        self,
        current_features: torch.Tensor,
        history_features: torch.Tensor,
        current_boxes: Optional[torch.Tensor] = None,
        history_boxes: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        计算当前帧目标与历史帧目标之间的相似度

        参数:
            current_features (torch.Tensor): 当前帧目标特征 [num_current, feature_dim]
            history_features (torch.Tensor): 历史帧目标特征 [num_history, feature_dim]
            current_boxes (torch.Tensor, optional): 当前帧边界框 [num_current, 4]
            history_boxes (torch.Tensor, optional): 历史帧边界框 [num_history, 4]

        返回:
            torch.Tensor: 相似度矩阵 [num_current, num_history]
        """
        num_current = current_features.size(0)
        num_history = history_features.size(0)

        if num_current == 0 or num_history == 0:
            return torch.zeros((num_current, num_history), device=current_features.device)

        # 转换外观特征
        current_appearance = self.appearance_transform(current_features)  # [num_current, feature_dim]
        history_appearance = self.appearance_transform(history_features)  # [num_history, feature_dim]

        # 添加批次维度
        current_appearance = current_appearance.unsqueeze(0)  # [1, num_current, feature_dim]
        history_appearance = history_appearance.unsqueeze(0)  # [1, num_history, feature_dim]

        # 应用交叉注意力
        _, appearance_attn = self.cross_attention(current_appearance, history_appearance)

        # 提取外观相似度（取第一个头的注意力权重）并分离梯度
        appearance_similarity = appearance_attn[0, 0].detach()  # [num_current, num_history]

        # 如果提供了边界框，计算运动相似度
        if current_boxes is not None and history_boxes is not None:
            try:
                # 计算运动特征
                motion_features = self.compute_motion_features(current_boxes, history_boxes)  # [num_current, num_history, feature_dim]

                # 计算运动相似度并分离梯度
                motion_similarity = torch.sum(motion_features, dim=-1).detach()  # [num_current, num_history]
                motion_similarity = torch.sigmoid(motion_similarity)  # 归一化到[0,1]

                # 融合外观和运动相似度
                similarity = (
                    self.appearance_weight * appearance_similarity +
                    self.motion_weight * motion_similarity
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"计算运动相似度时出错: {str(e)}")
                # 如果出错，只使用外观相似度
                similarity = appearance_similarity
        else:
            similarity = appearance_similarity

        return similarity
