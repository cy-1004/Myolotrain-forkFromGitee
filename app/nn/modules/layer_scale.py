"""
Layer Scale 和 Stochastic Depth 模块

这些模块用于增强深层网络的训练稳定性和泛化能力。
- Layer Scale: 在每个层的输出添加可学习的深度缩放参数
- Stochastic Depth: 在训练期间随机丢弃整个层
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Callable


class LayerScale(nn.Module):
    """
    Layer Scale 模块
    
    在每个层的输出添加可学习的深度缩放参数，以稳定深层网络的训练。
    这些参数初始化为很小的值，随着训练逐渐增大。
    
    参数:
        dim (int): 特征维度
        init_value (float): 初始化值，通常很小，如1e-6
    """
    
    def __init__(self, dim: int, init_value: float = 1e-6):
        super().__init__()
        self.gamma = nn.Parameter(torch.ones(dim) * init_value)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        参数:
            x (torch.Tensor): 输入特征
            
        返回:
            torch.Tensor: 缩放后的特征
        """
        # 根据输入维度调整gamma的形状
        if x.dim() == 3:  # [B, N, C]
            return x * self.gamma.unsqueeze(0).unsqueeze(0)
        elif x.dim() == 4:  # [B, C, H, W]
            return x * self.gamma.unsqueeze(0).unsqueeze(-1).unsqueeze(-1)
        else:
            raise ValueError(f"不支持的输入维度: {x.dim()}")


class DropPath(nn.Module):
    """
    随机深度 (Stochastic Depth) 模块
    
    在训练期间随机丢弃整个层，以提高模型的泛化能力和稳定性。
    
    参数:
        drop_prob (float): 丢弃概率，0.0表示不丢弃
    """
    
    def __init__(self, drop_prob: float = 0.0):
        super().__init__()
        self.drop_prob = drop_prob
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        参数:
            x (torch.Tensor): 输入特征
            
        返回:
            torch.Tensor: 随机丢弃后的特征
        """
        if self.drop_prob == 0.0 or not self.training:
            return x
        
        keep_prob = 1.0 - self.drop_prob
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)  # 保持批次维度，其他维度为1
        random_tensor = keep_prob + torch.rand(shape, dtype=x.dtype, device=x.device)
        random_tensor.floor_()  # 二值化
        output = x.div(keep_prob) * random_tensor  # 缩放保留的激活
        
        return output


class TransformerEncoderLayerWithLayerScale(nn.Module):
    """
    带有Layer Scale的Transformer编码器层
    
    在自注意力和前馈网络的残差连接后应用Layer Scale，以稳定深层网络的训练。
    
    参数:
        d_model (int): 模型的维度
        nhead (int): 多头注意力中的头数
        dim_feedforward (int): 前馈网络的隐藏层维度
        dropout (float): dropout率
        activation (str): 激活函数，'relu'或'gelu'
        layer_scale_init_value (float): Layer Scale初始化值
        drop_path_rate (float): 随机深度丢弃概率
    """
    
    def __init__(
        self, 
        d_model: int, 
        nhead: int, 
        dim_feedforward: int = 2048, 
        dropout: float = 0.1,
        activation: str = "relu",
        layer_scale_init_value: float = 1e-6,
        drop_path_rate: float = 0.0
    ):
        super().__init__()
        
        # 多头自注意力
        from app.nn.modules.attention import SelfAttention
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
        
        # Layer Scale
        self.layer_scale_1 = LayerScale(d_model, init_value=layer_scale_init_value)
        self.layer_scale_2 = LayerScale(d_model, init_value=layer_scale_init_value)
        
        # 随机深度
        self.drop_path = DropPath(drop_path_rate) if drop_path_rate > 0.0 else nn.Identity()
        
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
        src = src + self.drop_path(self.layer_scale_1(self.dropout1(src2)))
        
        # 前馈网络子层
        src2 = self.linear2(self.dropout(self.activation(self.linear1(self.norm2(src)))))
        src = src + self.drop_path(self.layer_scale_2(self.dropout2(src2)))
        
        return src


class TransformerEncoderWithLayerScale(nn.Module):
    """
    带有Layer Scale的Transformer编码器
    
    由多个带有Layer Scale的编码器层堆叠而成。
    
    参数:
        d_model (int): 模型的维度
        nhead (int): 多头注意力中的头数
        num_layers (int): 编码器层的数量
        dim_feedforward (int): 前馈网络的隐藏层维度
        dropout (float): dropout率
        activation (str): 激活函数，'relu'或'gelu'
        layer_scale_init_value (float): Layer Scale初始化值
        drop_path_rates (List[float]): 每一层的随机深度丢弃概率
    """
    
    def __init__(
        self, 
        d_model: int, 
        nhead: int, 
        num_layers: int, 
        dim_feedforward: int = 2048, 
        dropout: float = 0.1,
        activation: str = "relu",
        layer_scale_init_value: float = 1e-6,
        drop_path_rate: float = 0.1
    ):
        super().__init__()
        
        # 为每一层计算不同的丢弃概率（深层更高）
        drop_path_rates = [x.item() for x in torch.linspace(0, drop_path_rate, num_layers)]
        
        # 创建编码器层
        self.layers = nn.ModuleList([
            TransformerEncoderLayerWithLayerScale(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
                activation=activation,
                layer_scale_init_value=layer_scale_init_value,
                drop_path_rate=drop_path_rates[i]
            )
            for i in range(num_layers)
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
