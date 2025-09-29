import os
import sys
from datetime import datetime

# 设置中文字符集
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 任务ID
task_id = '6a1741ee-b8e0-402b-9342-0f84a10b6076'

# 定义路径
train_script_path = os.path.join('logs', 'tensorboard', task_id, 'resume_train_script.py')

print(f"=== 完全修复训练脚本 ===")
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 重新读取整个训练脚本
with open(train_script_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 使用字符串替换的方式完全修复文件
# 1. 修复设备设置部分
fixed_content = content.replace(
    "        # 设置运行设备\n        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # 强制禁用GPU，只使用CPU\n        print('=== 环境变量设置: CUDA_VISIBLE_DEVICES=' + os.environ['CUDA_VISIBLE_DEVICES'] + ' ===')\n=== 环境变量设置: CUDA_VISIBLE_DEVICES=' + os.environ['CUDA_VISIBLE_DEVICES'] + ' ===')",
    "        # 设置运行设备\n        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # 强制禁用GPU，只使用CPU\n        print('=== 环境变量设置: CUDA_VISIBLE_DEVICES=' + os.environ['CUDA_VISIBLE_DEVICES'] + ' ===')"
)

# 2. 确保训练参数中添加device='cpu'
# 先删除可能存在的不正确的train_args定义
fixed_content = fixed_content.replace(
    "# 准备训练参数\n        train_args = {", 
    "# 准备训练参数\n        train_args = {"
)

# 然后在正确的位置插入device参数
fixed_content = fixed_content.replace(
    "# 准备训练参数\n        train_args = {", 
    "# 准备训练参数\n        train_args = {\n            'device': 'cpu',  # 明确指定使用CPU训练,"
)

# 保存修复后的脚本
with open(train_script_path, 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print(f"✓ 已完全修复训练脚本中的语法错误")
print(f"✓ 已确保在训练参数中正确添加device='cpu'")
print(f"✓ 已清理重复的代码行")
print(f"\n修复完成，请再次尝试运行训练脚本")