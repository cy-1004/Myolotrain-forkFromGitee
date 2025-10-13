import os
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.models.model import Model
from app.crud import model
from app.core.config import settings

# 配置日志
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def get_model_type(filename: str) -> str:
    """
    从文件名中提取模型类型
    """
    # 检查文件名中的关键字来确定模型类型
    filename_lower = filename.lower()
    if "yolo8n" in filename_lower:
        return "yolov8n"
    elif "yolo8s" in filename_lower:
        return "yolov8s"
    elif "yolo8m" in filename_lower:
        return "yolov8m"
    elif "yolo8l" in filename_lower:
        return "yolov8l"
    elif "yolo8x" in filename_lower:
        return "yolov8x"
    elif "yolo11n" in filename_lower:
        return "yolov11n"
    elif "yolo11s" in filename_lower:
        return "yolov11s"
    elif "yolo11m" in filename_lower:
        return "yolov11m"
    elif "yolo11l" in filename_lower:
        return "yolov11l"
    elif "yolo11x" in filename_lower:
        return "yolov11x"
    else:
        # 默认返回检测模型
        return "yolov8n"

def get_model_task(filename: str) -> str:
    """
    从文件名中提取任务类型
    """
    # 简单逻辑，默认返回detect
    # 实际应用中可能需要更复杂的判断逻辑
    filename_lower = filename.lower()
    if "seg" in filename_lower:
        return "segment"
    elif "cls" in filename_lower:
        return "classify"
    elif "pose" in filename_lower:
        return "pose"
    else:
        return "detect"

def import_default_models():
    """
    导入默认模型到数据库
    
    Returns:
        dict: 包含以下键的字典：
            - success: 布尔值，表示导入是否成功
            - total: 整数，表示找到的模型文件总数
            - imported: 整数，表示成功导入的模型数量
            - skipped: 整数，表示跳过的已存在模型数量
            - errors: 列表，包含导入失败的模型信息
    """
    logger.info("开始导入默认模型...")
    
    # 要搜索的目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    search_dirs = [
        os.path.join(project_root, "models")  # 仅搜索项目根目录下的models目录
    ]
    
    # 去重目录列表
    search_dirs = list(set(search_dirs))
    
    # 存储已找到的模型路径
    model_files = []
    
    # 在指定目录中搜索.pt文件
    for search_dir in search_dirs:
        if os.path.exists(search_dir):
            logger.info(f"在目录中搜索模型文件: {search_dir}")
            for root, _, files in os.walk(search_dir):
                for file in files:
                    if file.lower().endswith('.pt'):
                        model_path = os.path.abspath(os.path.join(root, file))
                        # 排除可能的临时文件或非模型文件
                        if 'temp' not in model_path.lower() and os.path.getsize(model_path) > 10000:
                            model_files.append(model_path)
    
    # 去重模型文件列表
    model_files = list(set(model_files))
    
    # 结果统计
    result = {
        "success": True,
        "total": len(model_files),
        "imported": 0,
        "skipped": 0,
        "errors": []
    }
    
    if not model_files:
        logger.warning("没有找到任何模型文件")
        return result
    
    logger.info(f"找到 {len(model_files)} 个模型文件")
    
    # 连接数据库
    db = SessionLocal()
    
    try:
        # 遍历找到的模型文件
        for model_path in model_files:
            try:
                # 获取文件名
                filename = os.path.basename(model_path)
                model_name = os.path.splitext(filename)[0]
                
                # 检查模型是否已经存在于数据库中
                existing_model = db.query(Model).filter(Model.name == model_name).first()
                if existing_model:
                    logger.info(f"模型 '{model_name}' 已存在于数据库中，跳过")
                    result["skipped"] += 1
                    continue
                
                # 确定模型类型和任务类型
                model_type = get_model_type(filename)
                model_task = get_model_task(filename)
                
                # 创建模型记录
                model_data = {
                    "name": model_name,
                    "description": f"默认预置模型 {filename}",
                    "type": model_type,
                    "task": model_task,
                    "path": model_path,
                    "source": "default"
                }
                
                # 添加到数据库
                model.create_with_fields(db, obj_in=model_data)
                logger.info(f"成功导入模型: '{model_name}' ({model_type}, {model_task})")
                result["imported"] += 1
                
            except Exception as e:
                error_msg = f"导入模型 '{model_path}' 失败: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
        
        # 提交事务
        db.commit()
        logger.info("所有模型导入完成！")
        
    except Exception as e:
        error_msg = f"导入过程中发生错误: {str(e)}"
        logger.error(error_msg)
        result["errors"].append(error_msg)
        result["success"] = False
        db.rollback()
    finally:
        db.close()
    
    return result

if __name__ == "__main__":
    # 确保在虚拟环境中运行
    if sys.prefix == sys.base_prefix:
        logger.warning("警告: 当前不在Python虚拟环境中运行")
        response = input("是否继续? [y/n]: ")
        if response.lower() not in ['y', 'yes']:
            sys.exit(0)
    
    # 导入默认模型
    import_default_models()