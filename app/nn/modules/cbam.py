"""
CBAM (Convolutional Block Attention Module) 模块

CBAM是一种有效的注意力机制，结合了通道注意力和空间注意力，
可以显著提高模型性能。

主要组件:
1. 通道注意力 (ChannelAttention): 捕获通道间的依赖关系，强调"什么"是重要的特征
2. 空间注意力 (SpatialAttention): 捕获空间位置的依赖关系，强调"哪里"有重要特征
3. CBAM模块 (CBAM): 组合通道和空间注意力

参考文献:
- "CBAM: Convolutional Block Attention Module" (Woo et al., 2018)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple, List, Union


class ChannelAttention(nn.Module):
    """
    通道注意力模块
    
    使用全局平均池化和最大池化提取通道统计信息，
    然后通过共享MLP生成通道注意力权重。
    
    参数:
        in_channels (int): 输入特征的通道数
        reduction_ratio (int): 通道减少比例，用于降低计算复杂度
    """
    
    def __init__(self, in_channels: int, reduction_ratio: int = 16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)  # 全局平均池化
        self.max_pool = nn.AdaptiveMaxPool2d(1)  # 全局最大池化
        
        # 共享MLP
        self.fc = nn.Sequential(
            nn.Conv2d(in_channels, in_channels // reduction_ratio, kernel_size=1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels // reduction_ratio, in_channels, kernel_size=1, bias=False)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        参数:
            x (torch.Tensor): 输入特征 [B, C, H, W]
            
        返回:
            torch.Tensor: 通道注意力权重 [B, C, 1, 1]
        """
        # 全局平均池化分支
        avg_out = self.fc(self.avg_pool(x))
        
        # 全局最大池化分支
        max_out = self.fc(self.max_pool(x))
        
        # 融合两个分支
        out = avg_out + max_out
        
        # 应用sigmoid激活函数
        return torch.sigmoid(out)


class SpatialAttention(nn.Module):
    """
    空间注意力模块
    
    使用通道平均池化和最大池化提取空间统计信息，
    然后通过卷积层生成空间注意力权重。
    
    参数:
        kernel_size (int): 卷积核大小
    """
    
    def __init__(self, kernel_size: int = 7):
        super().__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size, padding=kernel_size//2, bias=False)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        参数:
            x (torch.Tensor): 输入特征 [B, C, H, W]
            
        返回:
            torch.Tensor: 空间注意力权重 [B, 1, H, W]
        """
        # 通道平均池化
        avg_out = torch.mean(x, dim=1, keepdim=True)
        
        # 通道最大池化
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        
        # 拼接平均池化和最大池化结果
        out = torch.cat([avg_out, max_out], dim=1)
        
        # 应用卷积和sigmoid激活函数
        out = self.conv(out)
        
        return torch.sigmoid(out)


class CBAM(nn.Module):
    """
    CBAM (Convolutional Block Attention Module)
    
    结合通道注意力和空间注意力，先应用通道注意力，再应用空间注意力。
    
    参数:
        in_channels (int): 输入特征的通道数
        reduction_ratio (int): 通道减少比例
        spatial_kernel_size (int): 空间注意力卷积核大小
    """
    
    def __init__(
        self, 
        in_channels: int, 
        reduction_ratio: int = 16, 
        spatial_kernel_size: int = 7
    ):
        super().__init__()
        self.channel_attention = ChannelAttention(in_channels, reduction_ratio)
        self.spatial_attention = SpatialAttention(spatial_kernel_size)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        参数:
            x (torch.Tensor): 输入特征 [B, C, H, W]
            
        返回:
            torch.Tensor: 注意力增强后的特征 [B, C, H, W]
        """
        # 应用通道注意力
        x = x * self.channel_attention(x)
        
        # 应用空间注意力
        x = x * self.spatial_attention(x)
        
        return x


class CBAMResBlock(nn.Module):
    """
    带有CBAM的残差块
    
    在残差连接后应用CBAM注意力机制。
    
    参数:
        in_channels (int): 输入特征的通道数
        out_channels (int): 输出特征的通道数
        stride (int): 卷积步长
        reduction_ratio (int): 通道减少比例
        spatial_kernel_size (int): 空间注意力卷积核大小
    """
    
    def __init__(
        self, 
        in_channels: int, 
        out_channels: int, 
        stride: int = 1, 
        reduction_ratio: int = 16, 
        spatial_kernel_size: int = 7
    ):
        super().__init__()
        
        # 主分支
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)
        
        # 残差连接
        self.shortcut = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )
        
        # CBAM注意力
        self.cbam = CBAM(out_channels, reduction_ratio, spatial_kernel_size)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        参数:
            x (torch.Tensor): 输入特征 [B, C, H, W]
            
        返回:
            torch.Tensor: 注意力增强后的特征 [B, C, H, W]
        """
        # 主分支
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        
        # 残差连接
        shortcut = self.shortcut(x)
        
        # 应用CBAM
        out = self.cbam(out)
        
        # 残差连接
        out += shortcut
        out = self.relu(out)
        
        return out


class SelfAttentionWithCBAM(nn.Module):
    """
    带有CBAM的自注意力模块
    
    在自注意力计算前应用CBAM增强特征表示。
    
    参数:
        dim (int): 输入特征的通道维度
        num_heads (int): 注意力头的数量
        qkv_bias (bool): 是否在QKV投影中使用偏置
        attn_drop (float): 注意力dropout率
        proj_drop (float): 输出投影dropout率
        reduction_ratio (int): CBAM通道减少比例
    """
    
    def __init__(
        self,
        dim: int,
        num_heads: int = 8,
        qkv_bias: bool = False,
        attn_drop: float = 0.0,
        proj_drop: float = 0.0,
        reduction_ratio: int = 16
    ):
        super().__init__()
        
        # 从attention模块导入SelfAttention
        from app.nn.modules.attention import SelfAttention
        
        # 自注意力模块
        self.self_attn = SelfAttention(
            dim=dim,
            num_heads=num_heads,
            qkv_bias=qkv_bias,
            attn_drop=attn_drop,
            proj_drop=proj_drop
        )
        
        # CBAM注意力
        self.cbam = CBAM(dim, reduction_ratio)
        
        # 特征转换
        self.to_2d = lambda x, h, w: x.permute(0, 2, 1).reshape(x.shape[0], -1, h, w)
        self.to_1d = lambda x: x.flatten(2).permute(0, 2, 1)
    
    def forward(self, x: torch.Tensor, h: int = None, w: int = None) -> torch.Tensor:
        """
        前向传播
        
        参数:
            x (torch.Tensor): 输入特征 [B, N, C] 或 [B, C, H, W]
            h (int): 特征图高度，当输入为[B, N, C]时需要提供
            w (int): 特征图宽度，当输入为[B, N, C]时需要提供
            
        返回:
            torch.Tensor: 注意力增强后的特征，与输入形状相同
        """
        # 检查输入维度
        if x.dim() == 4:  # [B, C, H, W]
            h, w = x.shape[2], x.shape[3]
            x_2d = x
            x_1d = self.to_1d(x)
        elif x.dim() == 3:  # [B, N, C]
            assert h is not None and w is not None, "需要提供特征图的高度和宽度"
            x_1d = x
            x_2d = self.to_2d(x, h, w)
        else:
            raise ValueError(f"不支持的输入维度: {x.dim()}")
        
        # 应用CBAM
        enhanced_x_2d = self.cbam(x_2d)
        
        # 转换回序列形式
        enhanced_x_1d = self.to_1d(enhanced_x_2d)
        
        # 应用自注意力
        output = self.self_attn(enhanced_x_1d)
        
        # 返回与输入相同形状的输出
        if x.dim() == 4:
            return self.to_2d(output, h, w)
        else:
            return output
