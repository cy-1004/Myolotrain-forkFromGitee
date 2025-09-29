import os
import sys
import uuid
from datetime import datetime

# 添加项目根目录到Python搜索路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.crud import training_task, model as model_crud
# 不再需要ModelCreate，直接使用字典创建模型

print("开始注册模型...")

task_id = "a440da88-2bf4-4017-96d9-47877163cf4b"
print(f"任务ID: {task_id}")

# 创建数据库会话
db = SessionLocal()

# 获取指定任务
task = training_task.get(db, id=task_id)

if not task:
    print(f"错误: 未找到任务ID: {task_id}")
    db.close()
    sys.exit(1)

print(f"任务名称: {task.name}")
print(f"当前状态: {task.status}")

# 模型文件路径
output_dir = r"D:\项目开发\Myolotrain\app\static\models\training_a440da88-2bf4-4017-96d9-47877163cf4b"
best_model_path = os.path.join(output_dir, "exp", "weights", "best.pt")
last_model_path = os.path.join(output_dir, "exp", "weights", "last.pt")

print(f"\n检查模型文件路径:")
print(f"best.pt: {best_model_path} - {'存在' if os.path.exists(best_model_path) else '不存在'}")
print(f"last.pt: {last_model_path} - {'存在' if os.path.exists(last_model_path) else '不存在'}")

# 确保模型文件存在
if not os.path.exists(best_model_path):
    print("错误: 模型文件best.pt不存在")
    db.close()
    sys.exit(1)

# 准备模型数据
model_name = f"{task.name}_最佳模型"
model_type = "yolov8m"  # 假设这是训练使用的模型类型
model_task = "detect"  # 检测任务

# 尝试创建模型
try:
    # 创建正确的模型字段字典
    model_fields = {
        "name": model_name,
        "description": f"由训练任务 '{task.name}' 生成的最佳模型",
        "path": best_model_path,
        "type": model_type,
        "task": model_task,
        "source": "training"  # 设置来源为training
    }
    # 正确调用create_with_fields方法，使用obj_in参数名
    new_model = model_crud.create_with_fields(db, obj_in=model_fields)
    print(f"\n成功创建模型:")
    print(f"模型ID: {new_model.id}")
    print(f"模型名称: {new_model.name}")
    print(f"模型路径: {new_model.path}")
    print(f"模型类型: {new_model.type}")
    print(f"模型任务: {new_model.task}")
    print(f"创建时间: {new_model.created_at}")
    
    # 将模型与训练任务关联
    task.output_model_id = new_model.id
    db.commit()
    print(f"\n已将模型与训练任务关联")
    print(f"训练任务新的output_model_id: {task.output_model_id}")
    
except Exception as e:
    print(f"\n创建模型时出错: {str(e)}")
    import traceback
    traceback.print_exc()  # 打印完整的错误堆栈
    db.rollback()

# 关闭数据库会话
db.close()

print("\n模型注册完成")