import os
import sys

# 添加项目根目录到Python搜索路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.crud import model as model_crud
from app.crud import training_task

print("验证模型注册状态...")

# 创建数据库会话
db = SessionLocal()

task_id = "a440da88-2bf4-4017-96d9-47877163cf4b"
print(f"任务ID: {task_id}")

# 获取训练任务
task = training_task.get(db, id=task_id)

if task:
    print(f"任务名称: {task.name}")
    print(f"任务状态: {task.status}")
    print(f"输出模型ID: {task.output_model_id}")
    
    # 如果有输出模型ID，获取模型信息
    if task.output_model_id:
        print(f"\n获取模型详细信息...")
        model = model_crud.get(db, id=task.output_model_id)
        
        if model:
            print(f"模型ID: {model.id}")
            print(f"模型名称: {model.name}")
            print(f"模型描述: {model.description}")
            print(f"模型路径: {model.path}")
            print(f"模型类型: {model.type}")
            print(f"模型任务: {model.task}")
            print(f"模型来源: {model.source}")
            print(f"创建时间: {model.created_at}")
            print(f"更新时间: {model.updated_at}")
            
            # 检查模型文件是否存在
            if os.path.exists(model.path):
                print(f"\n模型文件存在，大小: {os.path.getsize(model.path)} 字节")
            else:
                print(f"\n警告: 模型文件不存在: {model.path}")
        else:
            print(f"未找到模型ID: {task.output_model_id}")
    else:
        print("训练任务没有关联的输出模型")
else:
    print(f"未找到任务ID: {task_id}")

# 尝试直接通过名称搜索模型
print(f"\n尝试通过名称搜索模型...")
model_by_name = model_crud.get_by_name(db, name="门窗检测_最佳模型")

if model_by_name:
    print(f"找到模型: {model_by_name.name}")
    print(f"模型ID: {model_by_name.id}")
    print(f"模型路径: {model_by_name.path}")
else:
    print("未找到名称为'门窗检测_最佳模型'的模型")

# 关闭数据库会话
db.close()

print("\n验证完成")