# GPU 设置指南 (CUDA 12.6)

本文档提供了如何设置GPU环境以运行本项目的详细说明，特别针对CUDA 12.6版本。

## 前提条件

在安装GPU版本的PyTorch之前，您需要确保您的系统满足以下条件：

1. **NVIDIA GPU**：确保您的计算机有NVIDIA GPU
2. **NVIDIA驱动程序**：安装最新的NVIDIA驱动程序
3. **CUDA工具包**：您已安装CUDA 12.6

## 检查GPU状态

您可以使用以下命令检查GPU状态：

```bash
# 检查NVIDIA驱动是否正确安装
nvidia-smi

# 检查CUDA版本
nvcc --version
```

## 安装GPU版本的PyTorch

我们的`requirements.txt`文件已经配置为安装与CUDA 12.6兼容的PyTorch版本，这与您的CUDA 12.6兼容。按照以下步骤安装：

```bash
# 创建并激活虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

## 验证安装

安装完成后，您可以使用以下Python代码验证PyTorch是否能够检测到GPU：

```python
import torch

print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA是否可用: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA版本: {torch.version.cuda}")
    print(f"GPU数量: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
```

## 常见问题

### 1. `torch.cuda.is_available()` 返回 `False`

可能的原因：
- NVIDIA驱动程序未正确安装
- CUDA工具包未正确安装
- PyTorch安装的是CPU版本
- PyTorch与CUDA版本不兼容

解决方案：
- 重新安装NVIDIA驱动程序
- 确保CUDA工具包正确安装
- 使用与您的CUDA版本兼容的PyTorch版本

### 2. 内存不足错误

如果您在训练过程中遇到GPU内存不足的错误，可以尝试：
- 减小批量大小（batch size）
- 减小输入图像尺寸
- 使用梯度累积
- 在创建训练任务时设置合理的GPU显存限制

### 3. 多GPU设置

如果您的系统有多个GPU，您可以在创建训练任务时选择特定的GPU。在我们的系统中，您可以：
1. 选择设备类型为"GPU"
2. 点击"获取GPU信息"按钮
3. 从下拉列表中选择要使用的GPU
4. 设置显存限制
5. 创建训练任务

## CUDA 12.6 特别说明

PyTorch官方目前支持的最高CUDA版本是12.1，但它通常与更高版本的CUDA兼容。如果您遇到任何兼容性问题，可以考虑以下解决方案：

1. 降级CUDA版本到12.1
2. 从源代码编译PyTorch以支持CUDA 12.6
3. 使用NVIDIA容器（如NGC容器）来避免兼容性问题

## 其他资源

- [PyTorch官方安装指南](https://pytorch.org/get-started/locally/)
- [NVIDIA CUDA安装指南](https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/index.html)
- [NVIDIA驱动程序下载](https://www.nvidia.com/Download/index.aspx)
