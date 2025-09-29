import os
import sys

# 添加项目根目录到Python搜索路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.process_monitor import process_monitor
from app.db.session import SessionLocal
from app.crud import training_task

print("开始手动检查训练任务状态...")

task_id = "a440da88-2bf4-4017-96d9-47877163cf4b"
print(f"正在检查任务ID: {task_id}")

# 创建数据库会话
db = SessionLocal()

# 获取指定任务
task = training_task.get(db, id=task_id)

if task:
    print(f"找到任务: {task.name}")
    print(f"当前状态: {task.status}")
    print(f"进程ID: {task.process_id}")
    
    # 检查进程是否运行
    is_running = False
    if task.process_id:
        try:
            pid = int(task.process_id)
            if os.name == 'nt':  # Windows
                # 使用tasklist命令检查进程
                output = os.popen(f'tasklist /FI "PID eq {pid}"').read()
                is_running = str(pid) in output
            else:  # Unix/Linux
                try:
                    os.kill(pid, 0)
                    is_running = True
                except OSError:
                    is_running = False
        except:
            is_running = False
    
    print(f"进程是否运行: {is_running}")
    
    # 如果进程不再运行，分析日志
    if not is_running:
        print("进程已结束，开始分析训练日志...")
        status = process_monitor._analyze_training_log(task_id)
        print(f"日志分析结果: {status}")
        
        # 如果识别为完成，更新状态
        if status == "completed":
            print("识别到训练完成，更新任务状态...")
            # 这里简单更新状态，完整的模型注册逻辑由process_monitor自动处理
            training_task.update(db, db_obj=task, obj_in={"status": "completed"})
            print("任务状态已更新为'completed'！")
    else:
        print("进程仍在运行中，无需更新状态")
else:
    print(f"未找到任务ID: {task_id}")

# 关闭数据库会话
db.close()

print("手动检查完成")