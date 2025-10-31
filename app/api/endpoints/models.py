from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.db.session import get_db
from app.schemas.model import Model
from app.services import model_service
import sys
import os
import tempfile
import subprocess
import shutil

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.import_default_models import import_default_models

router = APIRouter()

@router.post("/", response_model=Model)
async def create_model(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    type: str = Form(...),
    task: str = Form("detect"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Create a new model from a PT file
    """
    return await model_service.create_model(
        db=db, 
        name=name, 
        description=description, 
        type=type,
        task=task,
        file=file
    )

@router.get("/", response_model=List[Model])
def read_models(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve models
    """
    models = model_service.get_models(db, skip=skip, limit=limit)
    return models

@router.get("/{model_id}", response_model=Model)
def read_model(
    model_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific model by id
    """
    model = model_service.get_model(db, model_id=model_id)
    return model

@router.delete("/{model_id}", response_model=Model)
def delete_model(
    model_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a model
    """
    return model_service.delete_model(db, model_id=model_id)

@router.get("/{model_id}/classes")
def get_model_classes(
    model_id: str,
    db: Session = Depends(get_db)
):
    """
    Get model classes
    """
    from ultralytics import YOLO
    from app.crud.crud_model import model
    
    # 获取模型信息
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    
    try:
        # 加载模型获取类别
        yolo_model = YOLO(db_model.path)
        classes = list(yolo_model.names.values())
        
        return {
            "success": True,
            "classes": classes,
            "class_count": len(classes)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型类别失败: {str(e)}")

@router.post("/import-default")
def import_default_models_endpoint():
    """
    导入默认预置模型到数据库
    """
    import logging
    
    try:
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logger = logging.getLogger("import_default_models")
        
        # 记录日志
        logger.info("通过API触发预置模型导入")
        
        # 调用导入函数并获取结果
        result = import_default_models()
        
        # 检查是否有成功导入的模型
        if result["success"]:
            if result["imported"] > 0:
                message = f"预置模型导入成功！\n共找到 {result['total']} 个模型文件，导入了 {result['imported']} 个新模型，跳过了 {result['skipped']} 个已存在的模型。"
            elif result["skipped"] > 0:
                message = f"预置模型导入完成！\n所有 {result['skipped']} 个模型文件都已存在于系统中。"
            else:
                message = "没有找到任何可导入的模型文件。"
        else:
            message = f"导入过程中发生错误：{result['errors'][0] if result['errors'] else '未知错误'}"
        
        # 返回结果，包含前端需要的数据
        return {
            "success": result["success"],
            "message": message,
            "total": result["total"],
            "imported": result["imported"],
            "skipped": result["skipped"],
            "errors": result["errors"]
        }
        
    except Exception as e:
        logger.error(f"导入预置模型时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导入预置模型失败: {str(e)}")


@router.get("/{model_id}/download/pt")
def download_model_pt(
    model_id: str,
    db: Session = Depends(get_db)
):
    """
    下载PT格式模型文件
    """
    from app.crud.crud_model import model
    
    # 检查模型ID是否为有效的UUID格式
    try:
        import uuid
        uuid.UUID(model_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="模型ID格式无效")
    
    # 获取模型信息
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    
    model_path = Path(db_model.path)
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="模型文件不存在")
    
    # 返回文件下载响应
    return FileResponse(
        path=model_path,
        filename=f"{db_model.name}.pt",
        media_type="application/octet-stream"
    )


@router.get("/{model_id}/download/onnx")
async def download_model_onnx(model_id: str, db: Session = Depends(get_db)):
    """下载模型的ONNX格式"""
    from app.crud.crud_model import model
    from ultralytics import YOLO
    import tempfile
    import os
    import sys
    
    # 将标准输出重定向到sys.stdout.buffer，确保Unicode字符正确输出
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)
    
    print("\n=== 开始ONNX模型转换操作 ===")
    print(f"请求的模型ID: {model_id}")
    
    try:
        # 获取模型信息
        db_model = model.get(db, id=model_id)
        if not db_model:
            print(f"错误: 模型未找到，ID: {model_id}")
            raise HTTPException(status_code=404, detail="模型未找到")
        
        model_path = Path(db_model.path)
        print(f"模型路径: {model_path}")
        
        if not model_path.exists():
            print(f"错误: 模型文件不存在: {model_path}")
            raise HTTPException(status_code=404, detail="模型文件不存在")
        
        # 使用临时目录存储ONNX文件
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"创建临时目录: {temp_dir}")
            
            try:
                # 加载PyTorch模型
                print("正在加载YOLO模型...")
                yolo_model = YOLO(str(model_path))
                print("YOLO模型加载成功")
                
                # 导出为ONNX格式到临时目录
                print("开始ONNX模型导出...")
                # 使用ultralytics推荐的参数
                onnx_path = yolo_model.export(
                    format="onnx", 
                    imgsz=640, 
                    opset=12,
                    project=temp_dir,
                    name="model"
                )
                
                # 检查导出是否成功并返回路径
                if not onnx_path or not os.path.exists(onnx_path):
                    # 如果返回的路径不存在，尝试手动查找
                    temp_files = os.listdir(temp_dir)
                    print(f"临时目录内容: {temp_files}")
                    
                    # 查找任何.onnx文件
                    onnx_files = [f for f in temp_files if f.endswith('.onnx')]
                    if not onnx_files:
                        print("错误: 未找到任何ONNX导出文件")
                        raise HTTPException(status_code=500, detail="ONNX模型转换失败: 导出过程未生成任何ONNX文件")
                    
                    # 使用找到的第一个ONNX文件
                    onnx_path = os.path.join(temp_dir, onnx_files[0])
                    print(f"手动找到ONNX文件: {onnx_path}")
                
                print(f"ONNX模型导出成功: {onnx_path}")
                print(f"文件大小: {os.path.getsize(onnx_path)} bytes")
                
                # 提供下载响应
                return FileResponse(
                    path=onnx_path,
                    filename=f"{db_model.name}.onnx",
                    media_type="application/octet-stream"
                )
                
            except Exception as e:
                print(f"ONNX导出过程中发生错误: {str(e)}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"ONNX模型转换失败: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"处理ONNX模型下载时发生未预期错误: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"ONNX模型处理失败: {str(e)}")
