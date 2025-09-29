import os
import sys

# 添加项目根目录到Python搜索路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.crud import training_task

print("验证训练任务状态...")

task_id = "a440da88-2bf4-4017-96d9-47877163cf4b"
print(f"正在查询任务ID: {task_id}")

# 创建数据库会话
db = SessionLocal()

# 获取指定任务
task = training_task.get(db, id=task_id)

if task:
    print(f"任务名称: {task.name}")
    print(f"当前状态: {task.status}")
    print(f"开始时间: {task.start_time}")
    print(f"结束时间: {task.end_time}")
    print(f"输出模型ID: {task.output_model_id}")
else:
    print(f"未找到任务ID: {task_id}")

# 关闭数据库会话
db.close()

print("验证完成")