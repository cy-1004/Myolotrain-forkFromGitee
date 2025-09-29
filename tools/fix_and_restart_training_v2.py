import os
import sys
import traceback
import subprocess
from datetime import datetime

# 设置中文字符集
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 任务ID
task_id = '6a1741ee-b8e0-402b-9342-0f84a10b6076'

# 定义路径
train_script_path = os.path.join('logs', 'tensorboard', task_id, 'resume_train_script.py')
log_file_path = os.path.join('logs', 'tensorboard', task_id, 'training_log.txt')
model_file_path = os.path.join('models', 'yolov8n.pt')  # 正确的模型文件路径

print(f"=== 修复训练脚本，更正模型文件路径 ===")
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"任务ID: {task_id}")
print(f"训练脚本路径: {train_script_path}")
print(f"正确的模型文件路径: {model_file_path}")

# 检查模型文件是否存在
if not os.path.exists(model_file_path):
    print(f"错误: 模型文件不存在: {model_file_path}")
    sys.exit(1)
else:
    print(f"✓ 模型文件已找到: {model_file_path}")
    print(f"模型文件大小: {os.path.getsize(model_file_path) / (1024 * 1024):.2f} MB")

# 读取训练脚本内容
with open(train_script_path, 'r', encoding='utf-8') as f:
    script_content = f.read()

# 修复模型文件路径
fixed_script_content = script_content.replace(
    "model_file = r'yolov8n'", 
    f"model_file = r'{model_file_path}'"
)

# 保存修复后的脚本
with open(train_script_path, 'w', encoding='utf-8') as f:
    f.write(fixed_script_content)

print(f"✓ 已修复训练脚本中的模型文件路径")

# 获取当前所有Python进程，用于后续检查
print("\n=== 当前运行的Python进程 ===")
process_output = subprocess.run(
    ['powershell', 'Get-Process', '-Name', 'python', '-IncludeUserName'],
    capture_output=True, text=True, encoding='utf-8'
)
print(process_output.stdout)

# 重启训练
print(f"\n=== 开始重启训练任务 ===")
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 使用subprocess启动训练脚本，并实时显示输出
with open(log_file_path, 'a', encoding='utf-8') as log_file:
    log_file.write(f"\n\n=== 重启训练 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    
    # 在Windows上，使用shell=True来正确处理路径中的中文
    # 并设置正确的编码处理
    process = subprocess.Popen(
        ['python', train_script_path],
        cwd=os.getcwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True
    )
    
    # 实时显示和记录输出，使用正确的编码处理
    while True:
        # 读取一行输出，但不进行解码
        line = process.stdout.readline()
        if not line:
            break
        
        try:
            # 尝试用utf-8解码
            decoded_line = line.decode('utf-8')
        except UnicodeDecodeError:
            try:
                # 尝试用gbk解码（Windows默认编码）
                decoded_line = line.decode('gbk')
            except UnicodeDecodeError:
                # 如果都失败，用replace策略处理
                decoded_line = line.decode('utf-8', errors='replace')
        
        print(decoded_line, end='')  # 实时显示到控制台
        log_file.write(decoded_line)  # 写入日志文件
        log_file.flush()  # 确保立即写入
    
    # 等待进程完成并获取返回码
    return_code = process.wait()
    
    if return_code == 0:
        print(f"\n=== 训练成功完成 ===")
    else:
        print(f"\n=== 训练异常退出，返回码: {return_code} ===")

print(f"\n=== 训练任务处理完成 ===")
print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")