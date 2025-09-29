import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 数据库连接配置
DATABASE_URL = "sqlite:///./app.db"  # 假设使用SQLite数据库

# 创建数据库引擎和会话
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def delete_detection_tasks_by_model(model_id):
    """
    删除所有引用特定模型ID的检测任务
    """
    db = SessionLocal()
    try:
        # 查询所有引用该模型的检测任务
        detection_tasks = db.execute(
            text("SELECT id FROM detection_tasks WHERE model_id = :model_id"),
            {"model_id": model_id}
        ).fetchall()
        
        if not detection_tasks:
            print(f"没有找到引用模型ID {model_id} 的检测任务")
            return
        
        task_ids = [task[0] for task in detection_tasks]
        print(f"找到 {len(task_ids)} 个引用模型ID {model_id} 的检测任务")
        print(f"任务ID列表: {task_ids}")
        
        # 确认删除
        confirm = input("确定要删除这些检测任务吗？这将允许您删除相关模型。(y/n): ")
        if confirm.lower() != 'y':
            print("操作已取消")
            return
        
        # 删除检测任务
        db.execute(
            text("DELETE FROM detection_tasks WHERE model_id = :model_id"),
            {"model_id": model_id}
        )
        db.commit()
        
        print(f"成功删除了 {len(task_ids)} 个检测任务")
        print("现在您可以删除相关的模型了")
        
    except Exception as e:
        db.rollback()
        print(f"删除检测任务时出错: {e}")
    finally:
        db.close()

def get_model_info(model_name):
    """
    根据模型名称获取模型ID
    """
    db = SessionLocal()
    try:
        # 查询模型ID
        model_result = db.execute(
            text("SELECT id, name, path FROM models WHERE name LIKE :name"),
            {"name": f"%{model_name}%"}
        ).fetchall()
        
        if not model_result:
            print(f"没有找到名称包含 '{model_name}' 的模型")
            return None
        
        print("找到以下匹配的模型:")
        for idx, model in enumerate(model_result):
            print(f"{idx+1}. ID: {model[0]}, 名称: {model[1]}, 路径: {model[2]}")
        
        if len(model_result) == 1:
            return model_result[0][0]  # 返回唯一的模型ID
        
        # 多个匹配时让用户选择
        choice = input("请输入要操作的模型编号: ")
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(model_result):
                return model_result[choice_idx][0]
            else:
                print("无效的选择")
                return None
        except ValueError:
            print("请输入有效的数字")
            return None
            
    except Exception as e:
        print(f"获取模型信息时出错: {e}")
        return None
    finally:
        db.close()

if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python delete_detection_tasks_by_model.py <模型名称关键词>")
        print("  或")
        print("  python delete_detection_tasks_by_model.py --model-id <模型ID>")
        sys.exit(1)
    
    model_id = None
    
    # 解析命令行参数
    if len(sys.argv) == 3 and sys.argv[1] == "--model-id":
        # 直接提供模型ID
        model_id = sys.argv[2]
    else:
        # 通过模型名称搜索
        model_name = sys.argv[1]
        model_id = get_model_info(model_name)
        
        if not model_id:
            print("无法获取模型ID，程序退出")
            sys.exit(1)
    
    # 执行删除操作
    delete_detection_tasks_by_model(model_id)