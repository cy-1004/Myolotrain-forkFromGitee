"""
自注意力(Self-Attention)模块

该模块实现了Transformer架构中的自注意力机制，可用于各种深度学习任务。
自注意力机制允许模型在处理序列数据时考虑序列中所有位置之间的关系，
从而捕获长距离依赖和全局上下文信息。

主要组件:
1. 标准自注意力 (SelfAttention): 实现经典的多头自注意力
2. 空间自注意力 (SpatialSelfAttention): 专为图像特征设计的自注意力
3. 高效自注意力 (EfficientSelfAttention): 使用空间降采样减少计算量
4. 自注意力块 (SelfAttentionBlock): 包含自注意力模块和残差连接
5. 位置编码 (PositionalEncoding): 为序列添加位置信息
6. Transformer编码器层 (TransformerEncoderLayer): 完整的Transformer编码器层
7. Transformer编码器 (TransformerEncoder): 堆叠多个编码器层

技术架构:
- 自注意力机制基于"注意力即权重"的概念，通过计算查询(Q)和键(K)之间的相似度，
  然后用这些权重对值(V)进行加权求和，得到注意力输出。
- 多头注意力将输入分割为多个头，每个头独立计算自注意力，然后合并结果，
  这允许模型同时关注不同表示子空间的信息。
- Transformer架构通过堆叠自注意力层和前馈神经网络层，配合残差连接和层归一化，
  构建了强大的序列处理能力。

使用场景:
- 序列建模: 文本处理、时间序列分析
- 计算机视觉: 图像分类、目标检测、语义分割
- 多模态任务: 图像描述、视觉问答

参考文献:
- "Attention Is All You Need" (Vaswani et al., 2017)
- "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale" (Dosovitskiy et al., 2020)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from typing import Optional, Tuple, List, Union


class SelfAttention(nn.Module):
    """
    自注意力模块

    参数:
        dim (int): 输入特征的通道维度
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
        self.dim = dim
        self.num_heads = num_heads
        head_dim = dim // num_heads
        self.scale = head_dim ** -0.5  # 缩放因子

        # QKV投影
        self.qkv = nn.Linear(dim, dim * 3, bias=qkv_bias)
        self.attn_drop = nn.Dropout(attn_drop)
        self.proj = nn.Linear(dim, dim)
        self.proj_drop = nn.Dropout(proj_drop)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        参数:
            x (torch.Tensor): 输入特征 [B, N, C]，其中N是序列长度，C是通道数

        返回:
            torch.Tensor: 注意力增强后的特征 [B, N, C]
        """
        B, N, C = x.shape

        # 计算QKV
        qkv = self.qkv(x).reshape(B, N, 3, self.num_heads, C // self.num_heads).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]  # [B, num_heads, N, head_dim]

        # 计算注意力分数
        attn = (q @ k.transpose(-2, -1)) * self.scale  # [B, num_heads, N, N]
        attn = attn.softmax(dim=-1)
        attn = self.attn_drop(attn)

        # 加权聚合
        x = (attn @ v).transpose(1, 2).reshape(B, N, C)
        x = self.proj(x)
        x = self.proj_drop(x)

        return x


class SpatialSelfAttention(nn.Module):
    """
    空间自注意力模块，专为图像特征设计

    参数:
        in_channels (int): 输入特征的通道数
        out_channels (int): 输出特征的通道数，默认与输入相同
        num_heads (int): 注意力头的数量
        reduction_ratio (int): 用于减少计算量的通道减少比例
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: Optional[int] = None,
        num_heads: int = 8,
        reduction_ratio: int = 8
    ):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels or in_channels
        self.num_heads = num_heads

        # 通道减少以降低计算复杂度
        self.reduced_channels = max(1, in_channels // reduction_ratio)

        # QKV投影
        self.q_conv = nn.Conv2d(in_channels, self.reduced_channels, kernel_size=1, bias=False)
        self.k_conv = nn.Conv2d(in_channels, self.reduced_channels, kernel_size=1, bias=False)
        self.v_conv = nn.Conv2d(in_channels, self.reduced_channels, kernel_size=1, bias=False)

        # 输出投影
        self.out_conv = nn.Conv2d(self.reduced_channels, out_channels or in_channels, kernel_size=1)

        # 初始化
        self._init_weights()

    def _init_weights(self):
        """初始化权重"""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        参数:
            x (torch.Tensor): 输入特征图 [B, C, H, W]

        返回:
            torch.Tensor: 注意力增强后的特征图 [B, C, H, W]
        """
        B, C, H, W = x.shape

        # 计算QKV
        q = self.q_conv(x)  # [B, reduced_C, H, W]
        k = self.k_conv(x)  # [B, reduced_C, H, W]
        v = self.v_conv(x)  # [B, reduced_C, H, W]

        # 重塑为序列形式
        q = q.flatten(2).permute(0, 2, 1)  # [B, H*W, reduced_C]
        k = k.flatten(2).permute(0, 2, 1)  # [B, H*W, reduced_C]
        v = v.flatten(2).permute(0, 2, 1)  # [B, H*W, reduced_C]

        # 计算注意力分数
        attn = (q @ k.transpose(-2, -1)) / math.sqrt(self.reduced_channels)  # [B, H*W, H*W]
        attn = F.softmax(attn, dim=-1)

        # 加权聚合
        out = (attn @ v).permute(0, 2, 1).reshape(B, self.reduced_channels, H, W)  # [B, reduced_C, H, W]
        out = self.out_conv(out)  # [B, C, H, W]

        return out


class EfficientSelfAttention(nn.Module):
    """
    高效自注意力模块，使用空间降采样减少计算量

    参数:
        in_channels (int): 输入特征的通道数
        key_channels (int): 键和查询的通道数
        value_channels (int): 值的通道数
        out_channels (int): 输出特征的通道数
        scale (int): 空间降采样比例
    """

    def __init__(
        self,
        in_channels: int,
        key_channels: int,
        value_channels: int,
        out_channels: int,
        scale: int = 1
    ):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.scale = scale

        # 查询、键、值投影
        self.query_conv = nn.Conv2d(in_channels, key_channels, kernel_size=1)
        self.key_conv = nn.Conv2d(in_channels, key_channels, kernel_size=1)
        self.value_conv = nn.Conv2d(in_channels, value_channels, kernel_size=1)

        # 输出投影
        self.out_conv = nn.Conv2d(value_channels, out_channels, kernel_size=1)

        # 初始化
        self._init_weights()

    def _init_weights(self):
        """初始化权重"""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        参数:
            x (torch.Tensor): 输入特征图 [B, C, H, W]

        返回:
            torch.Tensor: 注意力增强后的特征图 [B, C, H, W]
        """
        B, C, H, W = x.shape

        # 计算查询
        query = self.query_conv(x)  # [B, key_channels, H, W]

        # 如果启用降采样，对键和值进行降采样
        if self.scale > 1:
            x_sampled = F.avg_pool2d(x, kernel_size=self.scale, stride=self.scale)
            key = self.key_conv(x_sampled)  # [B, key_channels, H/scale, W/scale]
            value = self.value_conv(x_sampled)  # [B, value_channels, H/scale, W/scale]
        else:
            key = self.key_conv(x)  # [B, key_channels, H, W]
            value = self.value_conv(x)  # [B, value_channels, H, W]

        # 重塑为序列形式
        query = query.flatten(2).permute(0, 2, 1)  # [B, H*W, key_channels]
        key = key.flatten(2)  # [B, key_channels, H*W/scale^2]
        value = value.flatten(2).permute(0, 2, 1)  # [B, H*W/scale^2, value_channels]

        # 计算注意力分数
        sim_map = torch.matmul(query, key)  # [B, H*W, H*W/scale^2]
        sim_map = (sim_map / math.sqrt(self.key_conv.out_channels)).softmax(dim=-1)

        # 加权聚合
        context = torch.matmul(sim_map, value)  # [B, H*W, value_channels]
        context = context.permute(0, 2, 1).reshape(B, -1, H, W)  # [B, value_channels, H, W]

        # 输出投影
        output = self.out_conv(context)  # [B, out_channels, H, W]

        return output


class SelfAttentionBlock(nn.Module):
    """
    自注意力块，包含自注意力模块和残差连接

    参数:
        in_channels (int): 输入特征的通道数
        attention_type (str): 注意力类型，可选 'standard', 'spatial', 'efficient'
        **kwargs: 传递给具体注意力模块的参数
    """

    def __init__(
        self,
        in_channels: int,
        attention_type: str = 'spatial',
        **kwargs
    ):
        super().__init__()
        self.in_channels = in_channels
        self.attention_type = attention_type

        # 根据注意力类型选择相应的模块
        if attention_type == 'standard':
            # 标准自注意力需要先将特征图转换为序列
            self.norm = nn.LayerNorm(in_channels)
            self.attention = SelfAttention(in_channels, **kwargs)
        elif attention_type == 'spatial':
            self.norm = nn.BatchNorm2d(in_channels)
            self.attention = SpatialSelfAttention(in_channels, **kwargs)
        elif attention_type == 'efficient':
            self.norm = nn.BatchNorm2d(in_channels)
            self.attention = EfficientSelfAttention(
                in_channels=in_channels,
                key_channels=kwargs.get('key_channels', in_channels // 8),
                value_channels=kwargs.get('value_channels', in_channels // 2),
                out_channels=in_channels,
                scale=kwargs.get('scale', 1)
            )
        else:
            raise ValueError(f"不支持的注意力类型: {attention_type}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        参数:
            x (torch.Tensor): 输入特征

        返回:
            torch.Tensor: 注意力增强后的特征
        """
        if self.attention_type == 'standard':
            # 标准自注意力需要特殊处理
            B, C, H, W = x.shape
            shortcut = x

            # 将特征图转换为序列
            x = x.flatten(2).permute(0, 2, 1)  # [B, H*W, C]
            x = self.norm(x)
            x = self.attention(x)  # [B, H*W, C]

            # 将序列转换回特征图
            x = x.permute(0, 2, 1).reshape(B, C, H, W)
        else:
            # 空间和高效自注意力直接处理特征图
            shortcut = x
            x = self.norm(x)
            x = self.attention(x)

        # 残差连接
        return x + shortcut


class PositionalEncoding(nn.Module):
    """
    位置编码模块

    为序列添加位置信息，使模型能够利用序列的顺序信息。
    使用正弦和余弦函数的组合来表示位置。

    参数:
        d_model (int): 模型的维度
        max_len (int): 最大序列长度
        dropout (float): dropout率
    """

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        # 创建位置编码矩阵
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))

        # 使用正弦和余弦函数
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # [1, max_len, d_model]

        # 注册为缓冲区，不作为模型参数
        self.register_buffer('pe', pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        参数:
            x: 输入张量 [batch_size, seq_len, d_model]

        返回:
            添加位置编码后的张量 [batch_size, seq_len, d_model]
        """
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


class TransformerEncoderLayer(nn.Module):
    """
    Transformer编码器层

    包含自注意力和前馈神经网络，以及残差连接和层归一化。

    参数:
        d_model (int): 模型的维度
        nhead (int): 多头注意力中的头数
        dim_feedforward (int): 前馈网络的隐藏层维度
        dropout (float): dropout率
        activation (str): 激活函数，'relu'或'gelu'
    """

    def __init__(
        self,
        d_model: int,
        nhead: int,
        dim_feedforward: int = 2048,
        dropout: float = 0.1,
        activation: str = "relu"
    ):
        super().__init__()

        # 多头自注意力
        self.self_attn = SelfAttention(d_model, num_heads=nhead, attn_drop=dropout, proj_drop=dropout)

        # 前馈神经网络
        self.linear1 = nn.Linear(d_model, dim_feedforward)
        self.dropout = nn.Dropout(dropout)
        self.linear2 = nn.Linear(dim_feedforward, d_model)

        # 层归一化
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        # dropout
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)

        # 激活函数
        self.activation = F.relu if activation == "relu" else F.gelu

    def forward(self, src: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        参数:
            src: 输入序列 [batch_size, seq_len, d_model]

        返回:
            输出序列 [batch_size, seq_len, d_model]
        """
        # 自注意力子层
        src2 = self.self_attn(self.norm1(src))
        src = src + self.dropout1(src2)  # 残差连接

        # 前馈网络子层
        src2 = self.linear2(self.dropout(self.activation(self.linear1(self.norm2(src)))))
        src = src + self.dropout2(src2)  # 残差连接

        return src


class TransformerEncoder(nn.Module):
    """
    Transformer编码器

    由多个编码器层堆叠而成。

    参数:
        d_model (int): 模型的维度
        nhead (int): 多头注意力中的头数
        num_layers (int): 编码器层的数量
        dim_feedforward (int): 前馈网络的隐藏层维度
        dropout (float): dropout率
        activation (str): 激活函数，'relu'或'gelu'
    """

    def __init__(
        self,
        d_model: int,
        nhead: int,
        num_layers: int,
        dim_feedforward: int = 2048,
        dropout: float = 0.1,
        activation: str = "relu"
    ):
        super().__init__()

        # 创建编码器层
        self.layers = nn.ModuleList([
            TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
                activation=activation
            )
            for _ in range(num_layers)
        ])

        self.num_layers = num_layers
        self.norm = nn.LayerNorm(d_model)

    def forward(self, src: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        参数:
            src: 输入序列 [batch_size, seq_len, d_model]

        返回:
            输出序列 [batch_size, seq_len, d_model]
        """
        output = src

        for layer in self.layers:
            output = layer(output)

        return self.norm(output)
