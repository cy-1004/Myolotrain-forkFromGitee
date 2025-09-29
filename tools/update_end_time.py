import os
import sys
import datetime

# 添加项目根目录到Python搜索路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.crud import training_task

print("更新训练任务结束时间...")

task_id = "a440da88-2bf4-4017-96d9-47877163cf4b"
print(f"正在更新任务ID: {task_id}")

# 创建数据库会话
db = SessionLocal()

# 获取指定任务
task = training_task.get(db, id=task_id)

if task:
    print(f"任务名称: {task.name}")
    print(f"当前状态: {task.status}")
    print(f"开始时间: {task.start_time}")
    print(f"原结束时间: {task.end_time}")
    
    # 简单地更新结束时间
    training_task.update(db, db_obj=task, obj_in={
        "end_time": datetime.datetime.now()
    })
    
    # 重新获取任务查看更新后的值
    updated_task = training_task.get(db, id=task_id)
    print(f"更新后结束时间: {updated_task.end_time}")
    print("任务结束时间已更新！")
else:
    print(f"未找到任务ID: {task_id}")

# 关闭数据库会话
db.close()

print("操作完成")