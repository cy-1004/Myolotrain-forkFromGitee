import os
import sys
import subprocess
import time
import traceback

# 设置中文字符集
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

print('=== 重新启动训练任务工具 ===')
print('时间:', time.strftime('%Y-%m-%d %H:%M:%S'))

# 定义路径
base_dir = os.getcwd()
task_id = '6a1741ee-b8e0-402b-9342-0f84a10b6076'
train_script = os.path.join(base_dir, 'logs', 'tensorboard', task_id, 'resume_train_script.py')
log_file = os.path.join(base_dir, 'logs', 'tensorboard', task_id, 'training_log.txt')

print(f'任务ID: {task_id}')
print(f'训练脚本: {train_script}')
print(f'日志文件: {log_file}')

# 检查训练脚本是否存在
if not os.path.exists(train_script):
    print(f'错误: 训练脚本不存在: {train_script}')
    print('使用原始训练脚本替代...')
    train_script = os.path.join(base_dir, 'logs', 'tensorboard', task_id, 'train_script.py')
    
if not os.path.exists(train_script):
    print(f'错误: 找不到训练脚本!')
    exit(1)

print(f'使用的脚本: {train_script}')

# 检查模型文件是否存在
model_files = [
    os.path.join(base_dir, 'models', 'yolov8n.pt'),
    os.path.join(base_dir, 'yolov8n'),
    os.path.join(base_dir, 'yolov8n.pt')
]

print('\n=== 检查模型文件 ===')
model_exists = False
for model_file in model_files:
    exists = os.path.exists(model_file)
    print(f'{model_file}: {"存在" if exists else "不存在"}')
    if exists:
        model_exists = True

if not model_exists:
    print('错误: 没有找到有效的模型文件!')
    exit(1)

# 检查输出目录是否存在
export_dir = os.path.join(base_dir, 'app', 'static', 'models', f'training_{task_id}')
print(f'\n输出目录: {export_dir}')
os.makedirs(export_dir, exist_ok=True)
print('已确保输出目录存在')

# 创建exp子目录
exp_dir = os.path.join(export_dir, 'exp')
os.makedirs(exp_dir, exist_ok=True)
print(f'已确保TensorBoard日志目录存在: {exp_dir}')

# 启动训练任务
print('\n=== 开始启动训练任务 ===')
try:
    # 使用subprocess运行训练脚本
    print(f'正在运行: python {train_script}')
    process = subprocess.Popen(
        ['python', train_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        cwd=base_dir
    )
    
    # 实时显示输出
    print('\n=== 训练输出 ===')
    start_time = time.time()
    log_lines = []
    
    while True:
        # 读取一行输出
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        
        if line:
            # 打印到控制台
            print(line.strip())
            # 保存到日志
            log_lines.append(line)
            
            # 检查是否有错误信息
            if 'error' in line.lower() or 'exception' in line.lower() or 'failed' in line.lower():
                print('\n⚠️ 检测到可能的错误！')
        
        # 限制运行时间为2分钟
        if time.time() - start_time > 120:
            print('\n⏱️ 训练运行已超过2分钟，自动停止显示...')
            break
    
    # 获取退出码
    exit_code = process.poll()
    print(f'\n训练进程退出码: {exit_code}')
    
    # 检查是否成功启动
    if exit_code == 0:
        print('✅ 训练任务成功启动！')
    else:
        print('❌ 训练任务启动失败！')
        
        # 显示最新的日志内容
        print('\n=== 最新日志内容 ===')
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                latest_logs = f.readlines()[-20:]
                print(''.join(latest_logs))
    
    print('\n=== 启动完成 ===')
    print('如果训练正在运行，建议等待一段时间后查看TensorBoard日志。')
    print('TensorBoard URL: http://localhost:6006/')
    
except Exception as e:
    print(f'启动训练任务时发生错误: {str(e)}')
    traceback.print_exc()

print('\n=== 工具运行结束 ===')