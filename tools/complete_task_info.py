import os
import sys
import datetime

# 添加项目根目录到Python搜索路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.crud import training_task

print("更新完整的训练任务信息...")

task_id = "a440da88-2bf4-4017-96d9-47877163cf4b"
print(f"正在更新任务ID: {task_id}")

# 创建数据库会话
db = SessionLocal()

# 获取指定任务
task = training_task.get(db, id=task_id)

if task:
    print(f"任务名称: {task.name}")
    print(f"当前状态: {task.status}")
    
    # 更新结束时间
    update_data = {
        "end_time": datetime.datetime.now()
    }
    
    # 尝试查找并设置输出模型
    try:
        from app.crud import model
        from app.schemas.model import ModelCreate
        
        # 获取输出目录
        output_dir = task.parameters.get("output_dir") if task.parameters else None
        if output_dir:
            # 查找最佳模型文件
            best_model_path = None
            possible_weights_paths = [
                os.path.join(output_dir, "exp", "weights", "best.pt"),  # 标准路径
                os.path.join(output_dir, "weights", "best.pt"),          # 另一种可能的路径
                os.path.join(output_dir, "best.pt")                        # 直接在输出目录下
            ]

            # 尝试每个可能的路径
            for model_path in possible_weights_paths:
                if os.path.exists(model_path):
                    best_model_path = model_path
                    print(f"找到最佳模型文件: {best_model_path}")
                    break

            # 如果找到模型文件，注册到数据库
            if best_model_path:
                # 获取模型名称和类型
                model_name = f"{task.name}_best"
                model_filename = os.path.basename(best_model_path)
                
                # 确定模型类型和任务类型
                model_type = "yolov8"  # 默认为yolov8
                model_task = "detection"  # 默认为检测任务
                
                # 创建模型记录
                model_in = ModelCreate(
                    name=model_name,
                    description=f"{task.name} 训练生成的最佳模型",
                    type=model_type,
                    task=model_task,
                    path=best_model_path,
                    source="training"
                )
                
                # 添加到数据库
                db_model = model.create(db, obj_in=model_in)
                print(f"成功注册模型: {model_name} (ID: {db_model.id})")
                
                # 更新训练任务，关联输出模型
                update_data["output_model_id"] = db_model.id
    except Exception as e:
        print(f"注册输出模型时出错: {e}")
    
    # 执行更新
    training_task.update(db, db_obj=task, obj_in=update_data)
    print("任务信息已更新完成！")
else:
    print(f"未找到任务ID: {task_id}")

# 关闭数据库会话
db.close()

print("操作完成")