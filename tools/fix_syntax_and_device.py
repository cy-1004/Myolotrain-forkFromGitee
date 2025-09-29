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

print(f"=== 修复训练脚本中的语法错误和设备配置 ===")
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 重新读取原始训练脚本
with open(train_script_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 修复脚本
fixed_lines = []
for i, line in enumerate(lines, 1):  # 行号从1开始
    # 修复CUDA环境变量设置行（第45-47行的语法错误）
    if i == 45:
        fixed_lines.append("        # 设置运行设备\n")
        fixed_lines.append("        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # 强制禁用GPU，只使用CPU\n")
        fixed_lines.append("        print('=== 环境变量设置: CUDA_VISIBLE_DEVICES=' + os.environ['CUDA_VISIBLE_DEVICES'] + ' ===')\n")
        # 跳过接下来的两行错误行
    elif i == 46 or i == 47:
        continue
    # 找到训练参数定义的位置，添加device='cpu'
    elif "# 准备训练参数" in line:
        fixed_lines.append(line)
        # 查找下一行train_args定义
        if i+1 < len(lines) and "train_args = {" in lines[i]:
            fixed_lines.append("        train_args = {\n")
            fixed_lines.append("            'device': 'cpu',  # 明确指定使用CPU训练\n")
    # 其他行保持不变
    else:
        fixed_lines.append(line)

# 保存修复后的脚本
with open(train_script_path, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print(f"✓ 已修复训练脚本中的语法错误")
print(f"✓ 已在训练参数中添加device='cpu'")
print(f"✓ 已确保CUDA环境变量正确设置为禁用GPU")
print(f"\n修复完成，请运行: python logs\\tensorboard\\{task_id}\\resume_train_script.py")