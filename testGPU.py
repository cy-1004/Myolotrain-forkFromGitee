import torch
print(torch.cuda.is_available())  # 应该返回 True
print(torch.cuda.device_count())  # 应该显示 GPU 数量
print(torch.cuda.get_device_name(0))  # 应该显示 GPU 名称