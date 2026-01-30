from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
import os
import tempfile
from typing import Optional, Dict
import logging
import torch
import gc
from pathlib import Path

from app.db.session import get_db
from app.schemas.model import Model
from app.crud import model as model_crud
from app.models.annotation import AnnotationProject as ProjectModel
import json
from datetime import datetime

router = APIRouter()

# 存储SAM3配置的文件路径
SAM3_CONFIG_FILE = "sam3_config.json"


def load_sam3_config():
    """加载SAM3配置"""
    try:
        with open(SAM3_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 如果配置文件不存在，返回默认配置
        return {
            "model_path": "",
            "imgsz": 1024,
            "half_precision": True,
            "last_updated": None
        }
    except Exception as e:
        logger.error(f"加载SAM3配置失败: {e}")
        return {
            "model_path": "",
            "imgsz": 1024,
            "half_precision": True,
            "last_updated": None
        }


def save_sam3_config(config):
    """保存SAM3配置"""
    try:
        with open(SAM3_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存SAM3配置失败: {e}")
        return False
logger = logging.getLogger(__name__)

# === 全局模型缓存 (单例模式) ===
MODEL_CACHE: Dict[str, object] = {}
# 全局变量存储最佳设备
BEST_DEVICE = "cpu"

SAM3_AVAILABLE = False
try:
    from ultralytics import SAM
    import cv2
    import numpy as np
    SAM3_AVAILABLE = True
    
    # === 智能显卡选择逻辑 ===
    if torch.cuda.is_available():
        count = torch.cuda.device_count()
        BEST_DEVICE = "cuda:0" # 默认
        
        # 遍历所有显卡，寻找 NVIDIA 独显
        for i in range(count):
            name = torch.cuda.get_device_name(i).lower()
            # 如果发现 nvidia，优先使用该索引
            if "nvidia" in name or "geforce" in name:
                BEST_DEVICE = f"cuda:{i}"
                logger.info(f"SAM3: Found NVIDIA GPU at index {i}: {name}")
                break
        
        logger.info(f"SAM3: Using computation device: {BEST_DEVICE}")
    else:
        logger.warning("SAM3: CUDA not found, using CPU.")

except ImportError:
    logger.warning("SAM3 dependencies missing. Install ultralytics>=8.3.237")


def get_shared_sam_model(model_path: str):
    """
    【核心修复】共享模型加载函数
    1. 不复制文件
    2. 自动复用内存
    3. 自动使用最佳显卡
    """
    if not SAM3_AVAILABLE:
        raise Exception("Ultralytics libraries are not installed.")

    # 1. 绝对路径标准化
    p = Path(model_path).resolve()
    key = str(p)

    if not p.exists():
        raise FileNotFoundError(f"Model file not found: {key}")

    # 2. 检查缓存 (如果内存里有，直接返回，不再加载)
    if key in MODEL_CACHE:
        return MODEL_CACHE[key]

    # 3. 内存大清洗 (加载新模型前，先把垃圾清掉)
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    logger.info(f"Loading SAM3 model: {key} to {BEST_DEVICE}")

    # 4. 加载模型
    try:
        model = SAM(key)
        
        MODEL_CACHE[key] = model
        return model
    except Exception as e:
        logger.error(f"Failed to load SAM model: {e}")
        raise e


@router.get("/available")
async def check_sam3_availability():
    msg = f"Available on {BEST_DEVICE}" if SAM3_AVAILABLE else "Not Available"
    return {"available": SAM3_AVAILABLE, "message": msg}


@router.post("/validate")
async def validate_sam3_model(
    model_path: str = Form(...),
    imgsz: int = Form(1024),  # 接收用户配置的imgsz参数
    db: Session = Depends(get_db)
):
    """验证模型接口：直接检查路径，不复制"""
    if not SAM3_AVAILABLE:
        raise HTTPException(status_code=500, detail="SAM3 environment not ready")
    
    # 兼容 Linux/Windows 路径
    p = Path(model_path)
    if not p.exists():
        # 尝试修正相对路径
        if not p.is_absolute():
            # 这里可以添加一些默认搜索路径，比如项目根目录
            pass
        raise HTTPException(status_code=404, detail=f"Model file not found: {model_path}")

    # 检查文件名是否合规 (Ultralytics 要求)
    # 如果用户的文件名不包含 'sam'，给予警告但尝试加载
    if "sam" not in p.name.lower():
        logger.warning(f"Model filename '{p.name}' does not contain 'sam'. Ultralytics might fail to load config.")

    try:
        # 尝试加载（利用共享缓存）
        model = get_shared_sam_model(str(p))
        
        # 验证推理 (使用用户配置的imgsz，确保模型支持该配置)
        import numpy as np
        # 使用更小的 dummy 图片，避免CUDA超时
        dummy = np.zeros((64, 64, 3), dtype=np.uint8)
        
        # 根据设备动态决定是否使用半精度
        use_half = True if "cuda" in BEST_DEVICE else False
        
        with torch.no_grad():
            # 使用较小的imgsz进行快速验证，避免超时
            model.predict(source=dummy, imgsz=min(imgsz, 256), device=BEST_DEVICE, half=use_half, verbose=False)

        return {
            "valid": True, 
            "message": f"Valid SAM3. Running on {BEST_DEVICE}",
            "runtime_path": str(p.resolve())
        }
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid model: {str(e)}")


@router.post("/segment")
async def sam3_segmentation(
    image_id: str = Form(...),  # 图像ID，用于直接从服务器获取图片
    model_path: str = Form(...),
    prompt_type: str = Form("point"),  # point, box, text
    points: Optional[str] = Form(None),  # format: "x1,y1,x2,y2,..."
    bboxes: Optional[str] = Form(None),  # format: "x1,y1,x2,y2"
    text_prompt: Optional[str] = Form(None),
    imgsz: Optional[int] = Form(512),  # 图像大小，默认512
    half_precision: Optional[bool] = Form(True),  # 半精度开关，默认开启
    db: Session = Depends(get_db)
):
    """执行SAM3分割，返回多边形坐标"""
    if not SAM3_AVAILABLE:
        raise HTTPException(status_code=500, detail="SAM3 is not available")
    
    try:
        # 直接从数据库获取图片路径，避免上传
        from app.crud import image_annotation as image_crud
        from app.models.annotation import ImageAnnotation as ImageAnnotationModel
        from app.core.config import settings
        
        # 获取图片记录
        image_record = db.query(ImageAnnotationModel).filter(ImageAnnotationModel.id == image_id).first()
        if not image_record:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # 构建图片文件路径 - 参考annotation.py的成功逻辑
        image_path_str = str(image_record.image_path) if image_record.image_path is not None else ""
        image_name_str = str(image_record.image_name) if image_record.image_name is not None else ""
        
        # 获取项目信息以获取项目目录
        from app.crud import annotation_project as project_crud
        project = db.query(ProjectModel).filter(ProjectModel.id == image_record.project_id).first()
        image_directory_str = str(project.image_directory) if project and project.image_directory is not None else ""
        
        logger.info(f"SAM3 get_image_file: image_path={image_path_str}, image_name={image_name_str}, project_directory={image_directory_str}")
        
        image_file_path = None
        
        if image_path_str.startswith('datasets/'):
            # 如果路径已经包含datasets，直接使用
            image_file_path = Path("app/static") / image_path_str
            logger.info(f"SAM3: Using datasets path: {image_file_path}")
        elif Path(image_path_str).is_absolute():
            # 如果是绝对路径，直接使用
            image_file_path = Path(image_path_str)
            logger.info(f"SAM3: Using absolute path: {image_file_path}")
        else:
            # 首先检查image_path是否只包含文件名（没有路径分隔符）
            if Path(image_path_str).name == image_path_str:
                # 如果image_path只包含文件名，则使用项目的image_directory和image_path组合
                if image_directory_str and image_path_str:
                    image_file_path = Path(image_directory_str) / image_path_str
                    logger.info(f"SAM3: Using project_dir + image_path: {image_file_path}")
            else:
                # 否则先尝试直接使用image_path作为相对路径
                image_file_path = Path(image_path_str)
                logger.info(f"SAM3: Using direct image_path: {image_file_path}")
                
            # 如果文件不存在，尝试使用项目的image_directory和image_name组合
            if not image_file_path.exists():
                image_path_str_fallback = str(image_record.image_name) if image_record.image_name is not None else ""
                if image_directory_str and image_path_str_fallback:
                    fallback_path = Path(image_directory_str) / image_path_str_fallback
                    logger.info(f"SAM3: Trying fallback path: {fallback_path}")
                    if fallback_path.exists():
                        image_file_path = fallback_path
                    else:
                        logger.info(f"SAM3: Fallback path does not exist")
        
        if not image_file_path or not image_file_path.exists():
            logger.info(f"SAM3: Final path does not exist: {image_file_path}")
            raise HTTPException(status_code=404, detail="Image file not found")
        else:
            logger.info(f"SAM3: Final path exists: {image_file_path}")
        
        logger.info(f"Using image file path: {image_file_path}")
        
        try:
            # 1. 获取模型 (使用共享缓存，不复制)
            model = get_shared_sam_model(model_path)

            # 2. 构造参数
            args = {
                "source": str(image_file_path),
                "conf": 0.25,
                "imgsz": imgsz,
                "device": BEST_DEVICE, # 使用选定的显卡
                "half": half_precision,
                "verbose": False,
                "retina_masks": False # 关闭视网膜级掩码以提速
            }
            
            if prompt_type == "box" and bboxes:
                # 解析框 [x1, y1, x2, y2]
                bbox_list = [float(x) for x in bboxes.split(",")]
                args["bboxes"] = [bbox_list] # 需要嵌套一层列表
                
            elif prompt_type == "point" and points:
                # 解析点 [x1, y1, x2, y2...] -> [[x1,y1], [x2,y2]]
                p_raw = [float(x) for x in points.split(",")]
                points_list = []
                for i in range(0, len(p_raw), 2):
                    points_list.append([p_raw[i], p_raw[i+1]])
                
                args["points"] = [points_list] # 需要嵌套，对应batch维度
                # 默认全是正点(1)
                args["labels"] = [[1] * len(points_list)]
                
            elif prompt_type == "text" and text_prompt:
                # 文本提示
                text_list = [item.strip() for item in text_prompt.split(",")]
                # 修正：使用 'text' 参数，避免与内部 'prompts' 冲突
                # 这会触发 SAM3 的文本编码器
                args["text"] = text_list
            
            # === 优化 3: 强制关闭梯度计算 (最关键的一步) ===
            # 如果不加这个，PyTorch会构建巨大的计算图用于反向传播，导致内存爆炸
            with torch.no_grad():
                results = model.predict(**args)
            
            # 后处理：Mask 转 Polygon (核心步骤)
            polygons = []
            result = results[0]
            
            if result.masks is not None:
                # 获取原始图像尺寸
                h, w = result.orig_shape
                
                # result.masks.xy 包含了已经转好的多边形坐标，但通常是绝对坐标
                # 如果 Ultralytics 版本较新，直接用 xyn (归一化坐标) 更方便
                if hasattr(result.masks, 'xyn'):
                    # 直接获取归一化多边形
                    for poly in result.masks.xyn:
                        if len(poly) > 0:
                            # 展平为 [x1, y1, x2, y2, ...]
                            flat_poly = poly.flatten().tolist()
                            polygons.append(flat_poly)
                else:
                    # 手动转换降级方案
                    masks_data = result.masks.data.cpu().numpy() # (N, H, W)
                    for mask in masks_data:
                        # 调整mask尺寸至原图
                        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
                        mask = (mask * 255).astype(np.uint8)
                        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        if contours:
                            # 取最大轮廓
                            c = max(contours, key=cv2.contourArea)
                            # 简化轮廓减少点数
                            epsilon = 0.005 * cv2.arcLength(c, True)
                            approx = cv2.approxPolyDP(c, epsilon, True)
                            if len(approx) >= 3:
                                # 归一化
                                norm_poly = []
                                for p in approx:
                                    norm_poly.extend([p[0][0]/w, p[0][1]/h])
                                polygons.append(norm_poly)

            return {
                "masks": polygons, # 返回归一化多边形数组
                "success": True
            }

        finally:
            pass  # 不需要清理临时文件，因为我们直接使用本地路径

    except Exception as e:
        logger.error(f"SAM3 Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def get_sam3_models(db: Session = Depends(get_db)):
    """获取可用的SAM3模型列表"""
    # 获取所有类型为SAM相关的模型
    all_models = model_crud.get_multi(db, skip=0, limit=100)
    
    sam3_models = []
    for model in all_models:
        model_dict = model.__dict__ if hasattr(model, '__dict__') else model
        # 检查模型是否可能是SAM3模型（通过名称判断）
        model_name = model_dict.get('name', '').lower()
        model_type = model_dict.get('type', '').lower()
        
        if ('sam' in model_name or 'sam' in model_type or 
            'sam3' in model_name or 'sam3' in model_type):
            sam3_models.append({
                "id": model_dict.get('id'),
                "name": model_dict.get('name'),
                "type": model_dict.get('type'),
                "path": model_dict.get('path'),
                "task": model_dict.get('task')
            })
    
    return {"models": sam3_models}


@router.get("/check_config")
async def check_sam3_config():
    """检查SAM3配置是否存在并验证"""
    try:
        config = load_sam3_config()
        
        # 检查是否有模型路径
        if not config.get('model_path'):
            return {"configured": False, "message": "未配置SAM3模型路径"}
        
        # 验证模型文件是否存在
        model_path = Path(config['model_path'])
        if not model_path.exists():
            return {"configured": False, "message": f"模型文件不存在: {config['model_path']}"}
        
        # 只检查模型文件是否存在，不进行加载验证
        # 加载和验证只在用户主动点击验证时执行
        return {
            "configured": True, 
            "message": "SAM3配置有效",
            "config": config
        }
            
    except Exception as e:
        logger.error(f"检查SAM3配置时出错: {e}")
        return {"configured": False, "message": f"检查配置时出错: {str(e)}"}


@router.post("/save_config")
async def save_sam3_config_endpoint(
    model_path: str = Form(...),
    imgsz: int = Form(1024),
    half_precision: bool = Form(True)
):
    """保存SAM3配置"""
    try:
        # 验证模型路径是否存在
        model_path_obj = Path(model_path)
        if not model_path_obj.exists():
            raise HTTPException(status_code=400, detail=f"模型文件不存在: {model_path}")
        
        # 创建配置对象
        config = {
            "model_path": str(model_path_obj.resolve()),
            "imgsz": imgsz,
            "half_precision": half_precision,
            "last_updated": datetime.now().isoformat()
        }
        
        # 直接保存配置（保存操作不执行验证）
        success = save_sam3_config(config)
        if success:
            return {
                "success": True, 
                "message": "SAM3配置保存成功",
                "config": config
            }
        else:
            raise HTTPException(status_code=500, detail="保存配置失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存SAM3配置时出错: {e}")
        raise HTTPException(status_code=500, detail=f"保存配置时出错: {str(e)}")