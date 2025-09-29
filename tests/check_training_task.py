import os
import sys
import json

# 添加项目根目录到Python搜索路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.crud import training_task

print("查看训练任务详细信息...")

task_id = "a440da88-2bf4-4017-96d9-47877163cf4b"
print(f"任务ID: {task_id}")

# 创建数据库会话
db = SessionLocal()

# 获取指定任务
task = training_task.get(db, id=task_id)

if task:
    print(f"任务名称: {task.name}")
    print(f"状态: {task.status}")
    print(f"开始时间: {task.start_time}")
    print(f"结束时间: {task.end_time}")
    print(f"输出模型ID: {task.output_model_id}")
    
    # 打印parameters中的output_dir
    if task.parameters:
        print("\n参数详情:")
        # 尝试将parameters转换为可读格式
        if isinstance(task.parameters, str):
            try:
                params = json.loads(task.parameters)
                output_dir = params.get("output_dir", "未找到")
                print(f"output_dir: {output_dir}")
            except json.JSONDecodeError:
                print("parameters不是有效的JSON字符串")
                print(f"原始parameters: {task.parameters}")
        else:
            output_dir = task.parameters.get("output_dir", "未找到")
            print(f"output_dir: {output_dir}")
            
            # 如果找到了output_dir，检查该目录下是否存在模型文件
            if output_dir != "未找到" and os.path.exists(output_dir):
                print(f"\n检查{output_dir}目录下的文件:")
                # 列出所有子目录和文件
                for root, dirs, files in os.walk(output_dir):
                    level = root.replace(output_dir, '').count(os.sep)
                    indent = ' ' * 4 * level
                    print(f'{indent}{os.path.basename(root)}/')
                    subindent = ' ' * 4 * (level + 1)
                    for file in files:
                        print(f'{subindent}{file}')
    else:
        print("未找到parameters")
else:
    print(f"未找到任务ID: {task_id}")

# 关闭数据库会话
db.close()

print("\n查看完成")