"""
补丁文件，用于覆盖PyTorch的torch.load函数，确保在加载模型时使用weights_only=False
"""
import torch
import functools
import logging

logger = logging.getLogger(__name__)

# 保存原始的torch.load函数
original_torch_load = torch.load

# 创建一个新的torch.load函数，默认使用weights_only=False
@functools.wraps(original_torch_load)
def patched_torch_load(*args, **kwargs):
    # 如果没有明确指定weights_only参数，则设置为False
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
        logger.info("Patched torch.load: Setting weights_only=False")
    
    return original_torch_load(*args, **kwargs)

# 应用补丁
def apply_patch():
    """应用补丁，替换torch.load函数"""
    torch.load = patched_torch_load
    logger.info("Applied patch to torch.load: weights_only=False by default")

# 恢复原始函数
def remove_patch():
    """移除补丁，恢复原始的torch.load函数"""
    torch.load = original_torch_load
    logger.info("Removed patch from torch.load")
