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

print(f"=== 修复训练脚本，确保使用CPU训练 ===")
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"任务ID: {task_id}")
print(f"训练脚本路径: {train_script_path}")

# 读取训练脚本内容
with open(train_script_path, 'r', encoding='utf-8') as f:
    script_content = f.read()

# 修复1：确保在训练参数中添加device='cpu'
fixed_script_content = script_content.replace(
    "# 准备训练参数\n        train_args = {", 
    "# 准备训练参数\n        train_args = {\n            'device': 'cpu',  # 明确指定使用CPU训练"
)

# 修复2：再次确认CUDA环境变量设置正确
fixed_script_content = fixed_script_content.replace(
    "# 设置运行设备\n        os.environ['CUDA_VISIBLE_DEVICES'] = '0' if device_type == 'gpu' else '-1'",
    "# 设置运行设备\n        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # 强制禁用GPU，只使用CPU\n        print('\n=== 环境变量设置: CUDA_VISIBLE_DEVICES=' + os.environ['CUDA_VISIBLE_DEVICES'] + ' ===')"
)

# 保存修复后的脚本
with open(train_script_path, 'w', encoding='utf-8') as f:
    f.write(fixed_script_content)

print(f"✓ 已修复训练脚本，在训练参数中添加了device='cpu'")
print(f"✓ 已确保CUDA环境变量设置为禁用GPU")

# 获取当前所有Python进程状态
print("\n=== 当前运行的Python进程 ===")
process_output = subprocess.run(
    ['powershell', 'Get-Process', '-Name', 'python', '-IncludeUserName'],
    capture_output=True, text=True, encoding='utf-8'
)
print(process_output.stdout)

# 重启训练
print(f"\n=== 开始重启训练任务 (使用CPU) ===")
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 使用subprocess启动训练脚本，并实时显示输出
with open(log_file_path, 'a', encoding='utf-8') as log_file:
    log_file.write(f"\n\n=== 重启训练 (强制CPU) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    
    # 在Windows上，使用shell=True来正确处理路径中的中文
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