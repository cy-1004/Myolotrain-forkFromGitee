from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session
from pathlib import Path
from app.db.session import get_db
import sys
import os
import tempfile
import subprocess
import shutil
import json
from pydantic import BaseModel

from app.services.opencv_service import opencv_service
from app.services.export_service import get_model_imgsz
from tools.import_default_models import import_default_models

router = APIRouter()

@router.post("/", response_model=None)
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
    from app.services import model_service
    return await model_service.create_model(
        db=db, 
        name=name, 
        description=description, 
        type=type,
        task=task,
        file=file
    )

@router.get("/", response_model=List[dict])
def read_models(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve models
    """
    from app.services import model_service
    models = model_service.get_models(db, skip=skip, limit=limit)
    
    # 将SQLAlchemy模型对象转换为字典
    result = []
    for model in models:
        if hasattr(model, '__dict__'):
            model_dict = {}
            for column in model.__table__.columns:
                value = getattr(model, column.name)
                # 确保UUID类型的字段转换为字符串
                if column.name == 'id' and hasattr(value, '__class__') and value.__class__.__name__ == 'UUID':
                    model_dict[column.name] = str(value)
                else:
                    model_dict[column.name] = value
            result.append(model_dict)
        else:
            # 如果已经是字典格式，直接添加
            result.append(model)
    
    return result

@router.get("/{model_id}", response_model=dict)
def read_model(
    model_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific model by id
    """
    from app.services import model_service
    model = model_service.get_model(db, model_id=model_id)
    
    # 将SQLAlchemy模型对象转换为字典
    if hasattr(model, '__dict__'):
        model_dict = {column.name: getattr(model, column.name) for column in model.__table__.columns}
        return model_dict
    else:
        # 如果已经是字典格式，直接返回
        return model

@router.delete("/{model_id}")
def delete_model(
    model_id: str,
    delete_file: bool = Body(True),
    db: Session = Depends(get_db)
):
    """
    删除模型
    """
    import os
    from app.crud.crud_model import model as model_crud
    
    db_model = model_crud.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    
    # 根据参数决定是否删除模型文件
    if delete_file and os.path.exists(db_model.path):
        try:
            os.remove(db_model.path)
            print(f"✅ 模型文件已删除: {db_model.path}")
        except Exception as e:
            print(f"⚠️ 删除模型文件失败: {e}")
    elif not delete_file:
        print(f"⚠️ 仅从清单移除模型，保留文件: {db_model.path}")
    
    # 删除模型记录
    model_crud.remove(db, id=model_id)
    
    return {"success": True, "message": "模型删除成功"}

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
        raise HTTPException(status_code=400, detail="模型ID格式无效")
    
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
    import logging
    
    # 检查模型ID是否为有效的UUID格式
    try:
        import uuid
        uuid.UUID(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="模型ID格式无效")
    
    logger = logging.getLogger(__name__)
    logger.info("开始ONNX模型转换操作")
    logger.info(f"请求的模型ID: {model_id}")
    
    try:
        # 获取模型信息
        db_model = model.get(db, id=model_id)
        if not db_model:
            logger.error(f"模型未找到，ID: {model_id}")
            raise HTTPException(status_code=404, detail="模型未找到")
        
        model_path = Path(db_model.path)
        logger.info(f"模型路径: {model_path}")
        
        if not model_path.exists():
            logger.error(f"模型文件不存在: {model_path}")
            raise HTTPException(status_code=404, detail="模型文件不存在")
        
        # 使用临时目录存储ONNX文件
        # 注意：不能用 `with tempfile.TemporaryDirectory()`，因为FileResponse是在
        # 函数返回之后才异步读取文件内容的，with块会在那之前就把临时目录删掉，
        # 导致"文件不存在"。这里手动创建目录，通过BackgroundTask在响应发送完毕后再清理。
        temp_dir = tempfile.mkdtemp()
        logger.info(f"创建临时目录: {temp_dir}")

        try:
            # 加载PyTorch模型
            logger.info("正在加载YOLO模型...")
            yolo_model = YOLO(str(model_path))
            logger.info("YOLO模型加载成功")

            # 导出为ONNX格式到临时目录
            logger.info("开始ONNX模型导出...")
            # 使用ultralytics推荐的参数
            onnx_path = yolo_model.export(
                format="onnx",
                imgsz=get_model_imgsz(str(model_path)),  # TFLite/ONNX 输入尺寸固定，必须与训练一致
                opset=12,
                project=temp_dir,
                name="model"
            )

            # 检查导出是否成功并返回路径
            if not onnx_path or not os.path.exists(onnx_path):
                # 如果返回的路径不存在，尝试手动查找
                temp_files = os.listdir(temp_dir)
                logger.warning(f"临时目录内容: {temp_files}")

                # 查找任何.onnx文件
                onnx_files = [f for f in temp_files if f.endswith('.onnx')]
                if not onnx_files:
                    logger.error("未找到任何ONNX导出文件")
                    raise HTTPException(status_code=500, detail="ONNX模型转换失败: 导出过程未生成任何ONNX文件")

                # 使用找到的第一个ONNX文件
                onnx_path = os.path.join(temp_dir, onnx_files[0])
                logger.info(f"手动找到ONNX文件: {onnx_path}")

            logger.info(f"ONNX模型导出成功: {onnx_path}")
            logger.info(f"文件大小: {os.path.getsize(onnx_path)} bytes")

            # 提供下载响应，响应发送完毕后清理临时目录
            return FileResponse(
                path=onnx_path,
                filename=f"{db_model.name}.onnx",
                media_type="application/octet-stream",
                background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True)
            )

        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.error(f"ONNX导出过程中发生错误: {str(e)}")
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


@router.get("/{model_id}/download/tflite")
async def download_model_tflite(
    model_id: str,
    imgsz: Optional[int] = Query(None, ge=32, le=2048, description="输入尺寸，默认取模型训练时的尺寸"),
    db: Session = Depends(get_db)
):
    """下载模型的TFLite格式

    转换结果持久化保存，模型文件不变时重复下载直接返回已有文件（转换一次要几十秒到几分钟）。
    """
    from app.crud.crud_model import model
    from app.services import export_service
    from fastapi.concurrency import run_in_threadpool
    import logging

    # 检查模型ID是否为有效的UUID格式
    try:
        import uuid
        uuid.UUID(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="模型ID格式无效")

    logger = logging.getLogger(__name__)
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    model_path = Path(db_model.path)
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="模型文件不存在")

    try:
        # 转换是 CPU 密集的同步操作，放到线程池里，避免阻塞其他请求
        tflite_path, meta = await run_in_threadpool(
            export_service.get_or_export_tflite, model_id, str(model_path), imgsz)
    except export_service.ExportError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"TFLite导出过程中发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TFLite模型转换失败: {str(e)}")

    return FileResponse(
        path=str(tflite_path),
        filename=f"{db_model.name}.tflite",
        media_type="application/octet-stream",
        headers={"X-Model-Imgsz": str(meta.get("imgsz", ""))},
    )


@router.post("/{model_id}/verify-tflite")
async def verify_model_tflite(
    model_id: str,
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """转换模型为TFLite并做一次真实推理测试，验证转换后的模型是否可用

    复用已持久化的 TFLite 文件（没有则先转换），
    然后分别用原始PT模型和转换出的TFLite模型对同一张图片做推理，对比检测结果，
    从而判断转换后的TFLite模型是否可用。
    """
    from app.crud.crud_model import model
    from app.services import export_service
    from ultralytics import YOLO
    import tempfile
    import logging

    try:
        import uuid
        uuid.UUID(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="模型ID格式无效")

    logger = logging.getLogger(__name__)
    logger.info(f"开始验证TFLite模型，模型ID: {model_id}")

    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")

    model_path = Path(db_model.path)
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="模型文件不存在")

    temp_dir = tempfile.mkdtemp()
    try:
        # 第一步：准备测试图片，优先使用用户上传的真实图片
        used_real_image = False
        test_image_path = os.path.join(temp_dir, "test_image.jpg")
        if file is not None and file.filename:
            content = await file.read()
            with open(test_image_path, "wb") as f:
                f.write(content)
            used_real_image = True
        else:
            import numpy as np
            from PIL import Image
            rng = np.random.default_rng(42)
            noise = rng.integers(0, 255, size=(640, 640, 3), dtype=np.uint8)
            Image.fromarray(noise).save(test_image_path)

        # 第二步：转换为TFLite（已导出过且模型未变化时直接复用）
        tflite_path, meta = export_service.get_or_export_tflite(model_id, str(model_path))
        imgsz = int(meta["imgsz"])

        # 第三步：用tf.lite.Interpreter做一次基础完整性检查（能否正常加载、输入输出形状）
        interpreter, input_details, output_details = export_service.load_tflite_interpreter(str(tflite_path))

        # 第四步：分别用PT模型和TFLite模型对同一张图片做推理，对比检测结果
        pt_model = YOLO(str(model_path))
        pt_results = pt_model.predict(source=test_image_path, imgsz=imgsz, verbose=False)
        pt_boxes = pt_results[0].boxes
        pt_count = int(len(pt_boxes)) if pt_boxes is not None else 0
        pt_classes = sorted(set(int(c) for c in pt_boxes.cls.cpu().tolist())) if pt_count else []

        # TFLite 侧直接用 tf.lite.Interpreter 推理 + 自己做后处理。
        # 不走 YOLO(tflite_path).predict()：ultralytics 的 LiteRT 后端与
        # 已安装的 ai_edge_litert 版本不兼容，会抛
        # "CreateWrapperFromFile(): incompatible function arguments"。
        tflite_count, tflite_classes, numeric = export_service.run_tflite_and_compare(
            interpreter, input_details, output_details,
            str(model_path), test_image_path, imgsz=imgsz)

        warnings = []
        if not used_real_image:
            warnings.append("未提供测试图片，使用的是随机噪声图片，只能验证模型能否正常加载/推理，检测结果本身没有参考意义，建议上传一张真实图片重新验证。")
        else:
            if pt_count != tflite_count:
                warnings.append(f"PT模型检测到{pt_count}个目标，TFLite模型检测到{tflite_count}个目标，数量不一致，转换后的模型效果可能有偏差。")
            if pt_classes != tflite_classes:
                warnings.append(f"PT与TFLite模型识别出的类别不完全一致：PT={pt_classes}，TFLite={tflite_classes}。")

        logger.info("TFLite模型验证完成")

        return {
            "success": True,
            "used_real_image": used_real_image,
            "input_shape": [int(x) for x in input_details[0]["shape"]],
            "output_shape": [int(x) for x in output_details[0]["shape"]],
            "pt_detection_count": pt_count,
            "tflite_detection_count": tflite_count,
            "pt_classes": pt_classes,
            "tflite_classes": tflite_classes,
            # 转换前后原始输出的逐元素误差 —— 判断"有没有掉精度"的直接证据
            "numeric_diff": numeric,
            "warnings": warnings,
        }
    except HTTPException:
        raise
    except export_service.ExportError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"验证TFLite模型时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"验证TFLite模型失败: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


class PruneRequest(BaseModel):
    modules_to_prune: List[str]
    prune_type: str = "unstructured"  # unstructured (非结构化), structured (结构化)
    prune_method: str = "l1"  # unstructured: l1; structured: channel
    prune_ratio: float = 0.5
    new_model_name: Optional[str] = None  # 新模型名称

class AutoPrunePlanRequest(BaseModel):
    prune_type: str = "structured"  # 默认为结构化剪枝
    prune_ratio: float = 0.5


@router.post("/{model_id}/analyze-structure")
def analyze_model_structure_for_pruning(
    model_id: str,
    request: AutoPrunePlanRequest,
    db: Session = Depends(get_db)
):
    """
    分析模型结构，生成自动剪枝计划
    """
    from ultralytics import YOLO
    from app.crud.crud_model import model as model_crud
    import torch
    
    # 获取模型信息
    db_model = model_crud.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    
    try:
        # 使用YOLO官方方法加载模型
        yolo_model = YOLO(db_model.path)
        original_model = yolo_model.model
        
        # 准备示例输入
        example_input = torch.randn(1, 3, 640, 640)  # 典型的YOLO输入
        
        # 生成剪枝计划
        plan_analysis = generate_pruning_plan(original_model, example_input, request.prune_ratio)
        
        # 返回分析结果
        return {
            "success": True,
            "message": "模型结构分析完成",
            "analysis": plan_analysis,
            "prune_ratio": request.prune_ratio,
            "model_info": {
                "id": db_model.id,
                "name": db_model.name,
                "path": db_model.path
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型结构分析失败: {str(e)}")


@router.post("/{model_id}/prune")
def unified_prune_model(
    model_id: str,
    request: PruneRequest,
    db: Session = Depends(get_db)
):
    """
    统一剪枝接口 - 支持非结构化和结构化剪枝，返回详细剪枝日志
    """
    from ultralytics import YOLO
    from app.crud.crud_model import model as model_crud
    import torch
    import torch.nn as nn
    import uuid
    from app.models.model import Model
    import io
    import logging
    import sys
    from datetime import datetime
    
    # 获取模型信息
    db_model = model_crud.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    
    try:
        # 使用YOLO官方方法加载模型
        yolo_model = YOLO(db_model.path)
        original_model = yolo_model.model
        
        # 根据剪枝类型决定如何处理模块列表
        if request.prune_type == "structured" and request.prune_method == "dependency" and request.modules_to_prune:
            # 依赖图结构化剪枝：直接使用用户选择的模块，不做任何过滤
            valid_modules_to_prune = request.modules_to_prune
        elif request.prune_type == "structured" and not request.modules_to_prune:
            # 自动结构化剪枝：不需要指定模块列表
            valid_modules_to_prune = []
        elif request.prune_type == "structured":
            # 其他结构化剪枝方法：使用宽松模式分析
            structure_info = analyze_model_structure(original_model, strict_pruning=False)
            prunable_modules_set = set(structure_info["prunable_modules"])
            
            # 过滤出真正可剪枝的模块
            valid_modules_to_prune = []
            for module_path in request.modules_to_prune:
                if module_path in prunable_modules_set:
                    valid_modules_to_prune.append(module_path)
                else:
                    print(f"警告: 模块 {module_path} 不可剪枝，已跳过")
            
            if not valid_modules_to_prune:
                raise HTTPException(status_code=400, detail="所选模块均不可剪枝，请选择其他模块")
        else:
            # 非结构化剪枝：使用严格模式分析
            structure_info = analyze_model_structure(original_model)
            prunable_modules_set = set(structure_info["prunable_modules"])
            
            # 过滤出真正可剪枝的模块
            valid_modules_to_prune = []
            for module_path in request.modules_to_prune:
                if module_path in prunable_modules_set:
                    valid_modules_to_prune.append(module_path)
                else:
                    print(f"警告: 模块 {module_path} 不可剪枝，已跳过")
            
            if not valid_modules_to_prune:
                raise HTTPException(status_code=400, detail="所选模块均不可剪枝，请选择其他模块")
        
        # 捕获剪枝过程的日志
        log_capture_string = io.StringIO()
        ch = logging.StreamHandler(log_capture_string)
        ch.setLevel(logging.INFO)
        
        # 创建logger并添加处理器
        logger = logging.getLogger('app.api.endpoints.models')
        logger.addHandler(ch)
        
        # 移除日志处理器（无论哪种剪枝方式都要移除）
        logger.removeHandler(ch)
        
        # 执行剪枝操作
        if request.prune_type == "structured":
            # 对于结构化剪枝，如果是依赖图方法(dependency)且用户指定了模块，则使用simple_structured_pruning
            if request.prune_method == "dependency" and request.modules_to_prune:
                # 依赖图剪枝：完全按照用户选择的模块，不做任何过滤
                pruned_model, successfully_pruned, failed_layers = simple_structured_pruning(
                    original_model, 
                    request.modules_to_prune,  # 直接使用用户选择的模块
                    request.prune_ratio
                )
            else:
                # 其他结构化剪枝方法使用原来的逻辑
                if request.modules_to_prune:
                    # 完全按照用户选择的模块，不做任何验证或过滤
                    selected_modules = request.modules_to_prune
                else:
                    # 如果没有指定模块，则对所有可剪枝模块进行剪枝
                    # 使用宽松模式，因为这是自动选择而非用户指定
                    structure_info = analyze_model_structure(original_model, strict_pruning=False)
                    selected_modules = structure_info["prunable_modules"]
                        
                # 使用简单结构化剪枝方法，完全按照用户指定的模块进行剪枝
                pruned_model, successfully_pruned, failed_layers = simple_structured_pruning(original_model, selected_modules, request.prune_ratio)
            
            # 对于结构化剪枝，使用返回的结果
            successful_modules = [item["layer"] for item in successfully_pruned] if successfully_pruned else []
            failed_modules = [item["layer"] for item in failed_layers] if failed_layers else []
            skipped_modules = []  # 结构化剪枝中没有显式的跳过模块，跳过的模块在failed_layers中
            
            # 生成结构化剪枝的日志内容
            if successfully_pruned:
                success_list = '\n'.join(['  - {} (从 {} 个通道剪到 {} 个通道)'.format(item["layer"], item["original_channels"], item["original_channels"] - item["channels_pruned"]) for item in successfully_pruned])
            else:
                success_list = '无'
            if failed_layers:
                failure_list = '\n'.join(['  - {} ({})'.format(item["layer"], item["reason"]) for item in failed_layers])
            else:
                failure_list = '无'
            log_contents = "结构化剪枝完成:\n成功剪枝 {} 层\n失败 {} 层\n\n成功列表:\n{}\n\n失败列表:\n{}\n".format(len(successfully_pruned), len(failed_layers), success_list, failure_list)
        else:
            pruned_model = perform_unstructured_pruning(original_model, valid_modules_to_prune, request.prune_method, request.prune_ratio)
            
            # 获取日志内容
            log_contents = log_capture_string.getvalue()
            log_capture_string.close()
            
            # 解析日志内容
            successful_modules = []
            failed_modules = []
            skipped_modules = []
            
            if log_contents:
                for line in log_contents.split('\n'):
                    if '✅ 成功剪枝:' in line:
                        # 提取模块名称
                        parts = line.split('✅ 成功剪枝:')
                        if len(parts) > 1:
                            module_info = parts[1].strip()
                            # 提取模块名
                            module_name = module_info.split(',')[0].strip() if ',' in module_info else module_info.strip()
                            successful_modules.append(module_name)
                    elif '跳过' in line:
                        # 提取跳过的模块名称
                        parts = line.split(':')
                        if len(parts) > 1:
                            # 提取模块路径部分
                            for i, part in enumerate(parts):
                                if '跳过' in parts[i-1] if i > 0 else '':
                                    continue
                                elif '跳过' in part:
                                    continue
                                elif '模块' in part or 'layer' in part.lower():
                                    module_part = part.strip()
                                    if module_part and '跳过' not in module_part and '模块' in part:
                                        skipped_modules.append(module_part)
                                else:
                                    # 查找包含model.的部分
                                    words = line.split()
                                    for word in words:
                                        if word.startswith('model.') and word.endswith('层') or word.endswith('conv'):
                                            skipped_modules.append(word.strip(',.:'))
                    elif '失败' in line:
                        # 提取失败的模块名称
                        parts = line.split('剪枝模块')
                        if len(parts) > 1:
                            for part in parts[1].split('失败'):
                                if 'model.' in part:
                                    # 提取模块名
                                    for word in part.split():
                                        if word.startswith('model.'):
                                            failed_modules.append(word.strip(',.:'))

            # 如果没有从日志中提取到，使用原始请求的模块列表
            if not successful_modules and not failed_modules and not skipped_modules:
                successful_modules = valid_modules_to_prune
        
        # 生成新模型路径
        new_model_path = f"models/pruned_{model_id}_{uuid.uuid4().hex[:8]}.pt"
        
        # 确保models目录存在
        import os
        os.makedirs(os.path.dirname(new_model_path), exist_ok=True)
        
        # 对于结构化剪枝，直接保存模型权重，避免YOLO保存方法的配置不一致问题
        import torch
        
        # 创建检查点字典
        # 安全地获取原始模型属性
        try:
            original_nc = getattr(yolo_model.model, 'nc', None)
            original_names = getattr(yolo_model.model, 'names', None)
        except:
            original_nc = None
            original_names = None
        
        ckpt = {
            'model': pruned_model.float(),  # 使用float()保持标准精度
            'epoch': -1,
            'best_fitness': 0.0,
            'ema': None,
            'updates': None,
            'optimizer': None,
            'train_args': {},
            'model_yaml': None,  # 关键修复：必须设为None，避免加载时尺寸不匹配
            'nc': original_nc,  # 类别数
            'names': original_names,  # 类别名称
            'args': None,        # 清空 args 避免干扰
            'task': getattr(yolo_model, 'task', 'detect'),  # 任务类型
        }
        
        torch.save(ckpt, new_model_path)
        
        # 使用用户提供的模型名称，如果没有提供则使用默认名称
        model_name = request.new_model_name or f"{db_model.name}_pruned_{request.prune_type}_{request.prune_method}"
        
        # 创建新模型记录到数据库
        new_model_data = {
            "name": model_name,
            "path": new_model_path,
            "type": db_model.type,
            "task": db_model.task,
            "description": f"Pruned version of {db_model.name} using {request.prune_type} {request.prune_method} pruning",
            "source": "pruned"
        }
        
        try:
            new_model = Model(**new_model_data)
            db.add(new_model)
            db.commit()
            db.refresh(new_model)
            
            # 验证保存的模型
            test_model = YOLO(new_model_path)
            
            logger.info(f"✅ 剪枝模型已保存: {new_model_path}")
            logger.info(f"✅ 模型验证成功，参数数量: {sum(p.numel() for p in test_model.model.parameters())}")
            
            return {
                "success": True,
                "message": f"模型{request.prune_type}剪枝成功",
                "new_model_id": new_model.id,
                "new_model_path": new_model_path,
                "pruned_modules": valid_modules_to_prune,
                "prune_ratio": request.prune_ratio,
                "pruning_details": {
                    "successful_modules": successful_modules,
                    "failed_modules": failed_modules,
                    "skipped_modules": skipped_modules,
                    "log_content": log_contents,
                    "summary": {
                        "total_selected": len(valid_modules_to_prune),
                        "successfully_pruned": len(successful_modules),
                        "failed_attempts": len(failed_modules),
                        "skipped_modules": len(skipped_modules)
                    }
                }
            }
        except Exception as e:
            # 如果数据库操作失败，删除已保存的模型文件
            try:
                if os.path.exists(new_model_path):
                    os.remove(new_model_path)
            except:
                pass  # 忽略删除失败
            db.rollback()
            raise HTTPException(status_code=500, detail=f"模型保存失败: {str(e)}")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型剪枝失败: {str(e)}")


def perform_unstructured_pruning(model, modules_to_prune, method, ratio):
    """
    执行非结构化剪枝 - 使用torch.nn.utils.prune
    """
    import torch.nn.utils.prune as prune
    import torch.nn as nn
    
    # 创建模型副本以避免污染原始模型
    import copy
    pruned_model = copy.deepcopy(model)
    pruned_model.eval()
    
    # 使用named_modules精确查找模块
    named_modules = dict(pruned_model.named_modules())
    
    for module_path in modules_to_prune:
        try:
            if module_path in named_modules:
                module = named_modules[module_path]
                
                # 1️⃣ 必须有 weight
                if not hasattr(module, "weight"):
                    continue
                
                # 2️⃣ 跳过 BatchNorm（不是限制，是防数值炸）
                if isinstance(module, nn.BatchNorm2d):
                    continue
                
                # 3️⃣ 执行非结构化剪枝
                if isinstance(module, (nn.Conv2d, nn.Linear)):
                    if method in ["l1", "l1_unstructured"]:
                        # L1范数非结构化剪枝
                        prune.l1_unstructured(module, name="weight", amount=ratio)
                        # 4️⃣ 关键：永久化
                        prune.remove(module, "weight")
                    elif method in ["random", "random_unstructured"]:
                        # 随机非结构化剪枝
                        prune.random_unstructured(module, name="weight", amount=ratio)
                        # 永久化
                        prune.remove(module, "weight")
                    elif method in ["magnitude", "magnitude_unstructured"]:
                        # 幅值非结构化剪枝
                        prune.magnitude_unstructured(module, name="weight", amount=ratio)
                        # 永久化
                        prune.remove(module, "weight")
                
                print(f"已对模块 {module_path} ({type(module).__name__}) 使用 {method} 方法进行非结构化剪枝，比例: {ratio}")
            else:
                print(f"警告: 未找到模块 {module_path}")
                continue
                
        except Exception as e:
            print(f"非结构化剪枝模块 {module_path} 时出错: {e}")
            continue
    
    return pruned_model


def analyze_prunable_layers(model, for_dependency_pruning=False):
    """
    分析模型结构，识别所有可剪枝的层
    for_dependency_pruning: 是否为依赖图剪枝分析，如果是则使用更宽松的规则
    """
    import torch.nn as nn
    
    # 自动识别所有可剪枝的卷积层
    prunable_layers = []
    for name, module in model.named_modules():
        if isinstance(module, nn.Conv2d):
            name_lower = name.lower()
            
            # 如果是为依赖图剪枝分析，则使用更宽松的规则
            if for_dependency_pruning:
                # 对于依赖图剪枝分析，我们只排除明确不能剪枝的层（如检测头）
                # 下采样层和深度可分离卷积也会被包含在分析中，
                # 但它们最终在剪枝执行阶段会被跳过
                
                # 排除检测头等关键输出层
                if any(keyword in name_lower for keyword in ['dfl', 'anchor', 'head', 'predictor', 'classifier', 'detect', 'segment', 'pose']):
                    continue
                # 排除输入层（通常输入通道不能剪）
                if 'stem' in name_lower or ('input' in name_lower and 'proj' in name_lower):
                    continue
                # 包含所有卷积层，包括下采样层和深度可分离卷积，
                # 因为依赖图需要了解所有层的关系
                # 但它们在实际剪枝时会被跳过
                prunable_layers.append({"name": name, "module": module, "out_channels": module.out_channels, "kernel_size": module.kernel_size})
            else:
                # 检查是否是下采样层或深度可分离卷积
                if module.stride[0] > 1 or module.stride[1] > 1:
                    continue
                if module.groups == module.in_channels and module.out_channels == module.groups:
                    continue
                # 检查名称是否包含关键输出层关键词
                if any(keyword in name_lower for keyword in ['dfl', 'anchor', 'head', 'predictor', 'classifier']):
                    continue
                # 添加到可剪枝层列表
                prunable_layers.append({"name": name, "module": module, "out_channels": module.out_channels, "kernel_size": module.kernel_size})
    
    return prunable_layers

def generate_pruning_plan(model, example_input, prune_ratio):
    """
    生成剪枝计划
    """
    import torch
    import torch.nn as nn
    import torch_pruning as tp
    import logging
    
    logger = logging.getLogger(__name__)
    
    model = model.cpu()
    example_input = example_input.cpu()
    
    # 构建依赖图，只忽略真正不能剪枝的层
    ignored_layers = []
    
    for name, m in model.named_modules():
        name_lower = name.lower()
        
        # 1. 绝对不能剪枝的层：检测头、DFL层等
        if any(keyword in name_lower for keyword in ['detect', 'dfl', 'cls', 'reg', 'segment', 'pose']):
            ignored_layers.append(m)
            continue
        
        # 2. 跳过下采样层（stride > 1）- 这些层通常不能剪枝
        if isinstance(m, nn.Conv2d) and (m.stride[0] > 1 or m.stride[1] > 1):
            ignored_layers.append(m)
            continue
        
        # 3. 深度可分离卷积不能剪枝
        if isinstance(m, nn.Conv2d) and m.groups == m.in_channels and m.out_channels == m.groups:
            ignored_layers.append(m)
            continue
        
        # 4. 其他层都不忽略，让torch-pruning自动处理依赖关系
        # 特别是BatchNorm、激活函数等必须包含在依赖图中

    dg = tp.DependencyGraph().build_dependency(
        model,
        example_inputs=example_input,
        ignored_layers=ignored_layers
    )
    
    # 打印调试信息
    logger.info(f"依赖图中包含的模块数量: {len(dg.module2node)}")
    
    # 获取可剪枝层
    prunable_layers = analyze_prunable_layers(model, for_dependency_pruning=True)
    
    logger.info(f"总共找到 {len(prunable_layers)} 个可分析的层")
    
    plan_analysis = {
        "layers_to_prune": [],
        "layers_failed_check": [],
        "total_prunable": len(prunable_layers),
        "prune_ratio": prune_ratio
    }
    
    # 逐层分析剪枝可行性
    for layer_info in prunable_layers:
        layer_name = layer_info["name"]
        layer = layer_info["module"]
        
        # 检查是否是深度可分离卷积或下采样层，这些层在分析阶段被包括
        # 但在实际剪枝时会被跳过
        is_depthwise_conv = layer.groups == layer.in_channels and layer.out_channels == layer.groups
        is_downsample_layer = layer.stride[0] > 1 or layer.stride[1] > 1
        
        # 检查该层是否在依赖图中
        if layer not in dg.module2node:
            # 检查是否是深度可分离卷积或下采样层，这些是正常的跳过情况
            if is_depthwise_conv:
                plan_analysis["layers_failed_check"].append({"layer": layer_name, "reason": "深度可分离卷积层"})
            elif is_downsample_layer:
                plan_analysis["layers_failed_check"].append({"layer": layer_name, "reason": "下采样层"})
            else:
                plan_analysis["layers_failed_check"].append({"layer": layer_name, "reason": "模块不在依赖图中"})
            continue
        
        # 对于深度可分离卷积和下采样层，将其标记为无法剪枝
        if is_depthwise_conv:
            plan_analysis["layers_failed_check"].append({"layer": layer_name, "reason": "深度可分离卷积层"})
            continue
        elif is_downsample_layer:
            plan_analysis["layers_failed_check"].append({"layer": layer_name, "reason": "下采样层"})
            continue
        
        try:
            # 计算该层应剪枝的通道数量
            out_channels = layer.out_channels
            prune_channels = int(out_channels * prune_ratio)
            
            if prune_channels <= 0 or prune_channels >= out_channels or out_channels <= 1:
                plan_analysis["layers_failed_check"].append({"layer": layer_name, "reason": f"剪枝比例非法 (out_channels={out_channels}, prune_channels={prune_channels})"})
                continue
            
            # 添加到待剪枝列表
            plan_analysis["layers_to_prune"].append({
                "layer": layer_name,
                "original_channels": out_channels,
                "channels_to_prune": prune_channels,
                "channels_after_pruning": out_channels - prune_channels,
                "kernel_size": layer_info["kernel_size"]
            })
        except Exception as e:
            plan_analysis["layers_failed_check"].append({"layer": layer_name, "reason": f"分析失败: {str(e)}"})
            logger.error(f"分析层 {layer_name} 时发生错误: {str(e)}")
            continue
    
    return plan_analysis

def structured_prune_with_dependency_graph(model, example_input, prune_ratio):
    """
    torch-pruning 依赖图结构化剪枝（全自动版）
    自动识别可剪枝层并执行剪枝
    """
    import torch
    import torch.nn as nn
    import torch_pruning as tp
    import logging

    logger = logging.getLogger(__name__)

    model = model.cpu()
    example_input = example_input.cpu()

    # 构建依赖图，只忽略真正不能剪枝的层
    ignored_layers = []
    
    for name, m in model.named_modules():
        name_lower = name.lower()
        
        # 1. 绝对不能剪枝的层：检测头、DFL层等
        if any(keyword in name_lower for keyword in ['detect', 'dfl', 'cls', 'reg', 'segment', 'pose']):
            ignored_layers.append(m)
            continue
        
        # 2. 跳过下采样层（stride > 1）- 这些层通常不能剪枝
        if isinstance(m, nn.Conv2d) and (m.stride[0] > 1 or m.stride[1] > 1):
            ignored_layers.append(m)
            continue
        
        # 3. 深度可分离卷积不能剪枝
        if isinstance(m, nn.Conv2d) and m.groups == m.in_channels and m.out_channels == m.groups:
            ignored_layers.append(m)
            continue
        
        # 4. 其他层都不忽略，让torch-pruning自动处理依赖关系
        # 特别是BatchNorm、激活函数等必须包含在依赖图中

    # 构建依赖图 - 使用更精确的参数
    dg = tp.DependencyGraph().build_dependency(
        model,
        example_inputs=example_input,
        ignored_layers=ignored_layers
    )
    
    # 打印调试信息
    logger.info(f"依赖图中包含的模块数量: {len(dg.module2node)}")
    
    # 验证依赖图是否包含目标层
    prunable_layers = analyze_prunable_layers(model, for_dependency_pruning=True)
    
    logger.info(f"自动识别到 {len(prunable_layers)} 个可分析的卷积层")
    
    pruned_count = 0
    failed_layers = []
    successfully_pruned = []
    
    for layer_info in prunable_layers:
        layer_name = layer_info["name"]
        layer = layer_info["module"]
        
        # 首先检查是否是特殊层（如深度可分离卷积或下采样层）
        if layer.groups == layer.in_channels and layer.out_channels == layer.groups:
            # 深度可分离卷积，跳过
            failed_layers.append({"layer": layer_name, "reason": "深度可分离卷积层"})
            logger.debug(f"跳过 {layer_name}: 深度可分离卷积层")
            continue
        
        if layer.stride[0] > 1 or layer.stride[1] > 1:
            # 下采样层，跳过
            failed_layers.append({"layer": layer_name, "reason": "下采样层"})
            logger.debug(f"跳过 {layer_name}: 下采样层")
            continue
        
        # 验证该层是否在依赖图中
        if layer not in dg.module2node:
            failed_layers.append({"layer": layer_name, "reason": "模块不在依赖图中"})
            logger.debug(f"跳过 {layer_name}: 模块不在依赖图中")
            continue
        
        try:
            # 计算该层应剪枝的通道数量
            out_channels = layer.out_channels
            prune_channels = int(out_channels * prune_ratio)
            
            if prune_channels <= 0 or prune_channels >= out_channels or out_channels <= 1:
                failed_layers.append({"layer": layer_name, "reason": f"剪枝比例非法 (out_channels={out_channels}, prune_channels={prune_channels})"})
                logger.debug(f"跳过 {layer_name}: 剪枝比例非法 (out_channels={out_channels}, prune_channels={prune_channels})")
                continue
            
            # 使用依赖图和重要性指标进行剪枝
            try:
                # 获取要剪枝的通道索引（基于L1范数）
                # 对于结构化剪枝，考虑更全面的通道重要性评估
                weight = layer.weight.data.abs().sum(dim=(1, 2, 3))
                
                # 使用更合理的通道重要性评估方法
                # 对于结构化剪枝，L1范数是一个常用的重要性的指标
                importance = weight
                
                prune_idxs = torch.argsort(importance)[:prune_channels].tolist()
                
                # 通过依赖图获取安全的剪枝组
                pruning_group = dg.get_pruning_group(
                    layer, 
                    tp.prune_conv_out_channels, 
                    idxs=prune_idxs
                )
                
                # 检查并执行剪枝
                if pruning_group is not None:
                    # 检查group是否有内容（兼容不同版本的torch-pruning）
                    if hasattr(pruning_group, '__len__') and len(pruning_group) > 0:
                        # 检查group是否可以执行剪枝（兼容不同版本的torch-pruning）
                        if not hasattr(pruning_group, 'executable') or pruning_group.executable():
                            pruning_group.prune()
                            pruned_count += 1
                            successfully_pruned.append({"layer": layer_name, "channels_pruned": prune_channels, "original_channels": out_channels})
                            logger.info(f"✅ 成功剪枝层: {layer_name}，从 {out_channels} 通道剪到 {out_channels - prune_channels} 通道")
                        else:
                            failed_layers.append({"layer": layer_name, "reason": "剪枝组不可执行"})
                            logger.warning(f"跳过 {layer_name}: 剪枝组不可执行")
                    else:
                        failed_layers.append({"layer": layer_name, "reason": "剪枝组为空"})
                        logger.warning(f"跳过 {layer_name}: 剪枝组为空")
                else:
                    failed_layers.append({"layer": layer_name, "reason": "依赖图无法安全剪枝该层"})
                    logger.warning(f"跳过 {layer_name}: 依赖图无法安全剪枝该层")
            except Exception as e:
                failed_layers.append({"layer": layer_name, "reason": f"生成剪枝计划时出错: {str(e)}"})
                logger.warning(f"跳过 {layer_name}: 生成剪枝计划时出错: {e}")
                
        except Exception as e:
            failed_layers.append({"layer": layer_name, "reason": f"处理异常: {str(e)}"})
            logger.debug(f"处理模块 {layer_name} 时出错: {e}")  # 改为debug级别，避免过多错误日志
            continue

    if pruned_count == 0:
        raise RuntimeError(f"结构化剪枝失败：共识别到 {len(prunable_layers)} 个可剪枝层，但成功剪枝 0 层")
    
    logger.info(f"结构化剪枝完成: 成功 {pruned_count} 层，失败 {len(failed_layers)} 层")
    
    return model, successfully_pruned, failed_layers


# YOLO_PRUNABLE_BLOCKS 和相关函数已移除，因为我们现在使用更简单的按层剪枝方法
# 而不是按Block剪枝

def perform_structured_pruning(model, modules_to_prune, method, ratio):
    """
    执行结构化剪枝入口
    """
    import copy
    import torch
    import logging
    
    logger = logging.getLogger(__name__)
    
    # 1. Deepcopy 模型
    pruned_model = copy.deepcopy(model)
    pruned_model.eval()
    
    # 2. 准备输入 (YOLO 默认尺寸)
    device = next(pruned_model.parameters()).device
    example_inputs = torch.randn(1, 3, 640, 640).to(device)
    
    # 3. 执行剪枝 - 现在自动识别可剪枝层，忽略用户指定的modules_to_prune
    try:
        pruned_model, successfully_pruned, failed_layers = structured_prune_with_dependency_graph(
            pruned_model, example_inputs, ratio
        )
    except Exception as e:
        logger.error(f"结构化剪枝致命错误: {e}")
        raise
    
    # 4. 再次清理模型 (将模型转回 CPU 并清理显存)
    pruned_model = pruned_model.cpu()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    return pruned_model, successfully_pruned, failed_layers


@router.get("/{model_id}/structure")
def get_model_structure(
    model_id: str,
    db: Session = Depends(get_db)
):
    """
    获取模型结构信息
    """
    from ultralytics import YOLO
    from app.crud.crud_model import model
    import torch
    import torch.nn as nn
    
    # 获取模型信息
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    
    try:
        # 使用YOLO加载模型
        yolo_model = YOLO(db_model.path)
        torch_model = yolo_model.model
        torch_model.eval()  # 确保模型处于评估模式
        
        # 分析模型结构
        structure_info = analyze_model_structure(torch_model)
        
        return {
            "success": True,
            "model_name": db_model.name,
            "model_type": db_model.type,
            "model_id": model_id,
            "structure": structure_info
        }
        
    except Exception as e:
        error_msg = "模型文件格式不正确，可能是损坏的或不支持的格式。请检查模型文件。"
        raise HTTPException(status_code=500, detail=f"获取模型结构失败: {error_msg}")


def analyze_model_structure(model, strict_pruning=True):
    """
    分析模型结构，返回可剪枝模块信息
    """
    import torch.nn as nn
    
    structure_info = {
        "modules": [],
        "total_params": 0,
        "prunable_modules": [],
        "total_modules": 0,
        "analysis": {}
    }
    
    def is_module_prunable(module, module_name, strict=True):
        """
        判断模块是否可剪枝
        strict: 是否启用严格模式
            - True: 严格模式，排除许多特殊层
            - False: 宽松模式，主要排除检测头等关键层
        """
        # 检查模块类型
        module_type = type(module).__name__
        
        if strict:
            # 严格模式：排除更多类型的层
            # 检查参数数量
            param_count = sum(p.numel() for p in module.parameters(recurse=False))
            if param_count == 0:
                return False  # 参数为0的模块不可剪枝
            
            # 检查是否为卷积层，如果是，检查步长
            if isinstance(module, nn.Conv2d):
                # 下采样层（stride > 1）不应被剪枝，因为它们改变了空间维度
                if module.stride[0] > 1 or module.stride[1] > 1:
                    return False
                # 深度可分离卷积也不应被剪枝
                if module.groups == module.in_channels and module.out_channels == module.groups:
                    return False
            
            # 激活函数通常不可剪枝
            if 'Activation' in module_type or 'activation' in module_type.lower():
                return False
            if any(act in module_type for act in ['ReLU', 'LeakyReLU', 'Sigmoid', 'Tanh', 'Softmax', 'SiLU', 'Hardswish']):
                return False
            
            # BatchNorm层一般不单独剪枝（虽然BN剪枝是可能的，但通常与卷积层一起考虑）
            if isinstance(module, (nn.BatchNorm1d, nn.BatchNorm2d, nn.BatchNorm3d)):
                return False
            
            # 检查模块名称中的关键词
            name_lower = module_name.lower()
            
            # Detect头通常不可剪枝
            if 'detect' in name_lower or 'detection' in name_lower:
                return False
            
            # Attention相关层不可剪枝
            if 'attn' in name_lower or 'attention' in name_lower:
                return False
            
            # QKV卷积层不可剪枝
            if 'qkv' in name_lower:
                return False
            
            # Position Embedding层不可剪枝
            if 'pe' in name_lower or 'pos_embed' in name_lower:
                return False
            
            # 输出相关层通常不可剪枝
            if 'output' in name_lower or 'proj' in name_lower:
                return False
            
            # 上采样层通常不可剪枝
            if 'upsample' in name_lower or 'upsampling' in name_lower or 'interpolate' in name_lower:
                return False
            
            # 激活函数层通常不可剪枝
            if any(act in name_lower for act in ['relu', 'leakyrelu', 'sigmoid', 'tanh', 'softmax', 'silu', 'swish', 'hardswish']):
                return False
            
            # 连接操作通常不可剪枝
            if 'concat' in name_lower or 'cat' in name_lower:
                return False
            
            # 跳连或残差连接通常不可剪枝
            if 'shortcut' in name_lower or 'residual' in name_lower or 'skip' in name_lower:
                return False
            
            # 其他通常不可剪枝的层
            if isinstance(module, (nn.AdaptiveAvgPool2d, nn.AvgPool2d, nn.MaxPool2d, nn.Dropout, nn.Dropout2d, nn.Identity)):
                return False
            
            # 默认情况下认为是可剪枝的
            return True
        else:
            # 宽松模式：只排除绝对不能剪枝的关键层
            name_lower = module_name.lower()
            
            # Detect头等关键层不能剪枝
            if any(keyword in name_lower for keyword in ['detect', 'dfl', 'cls', 'reg', 'segment', 'pose']):
                return False
            
            # 默认情况下认为是可剪枝的
            return True
    
    def get_module_info(module, name_prefix="", depth=0):
        module_info = {
            "name": name_prefix,
            "type": type(module).__name__,
            "depth": depth,
            "params": 0,
            "submodules": [],
            "prunable": False,  # 默认不可剪枝，后续根据规则判断
            "flops": 0,
            "input_shape": [],
            "output_shape": []
        }
        
        try:
            # 安全地计算参数数量
            param_count = sum(p.numel() for p in module.parameters(recurse=False))
            module_info["params"] = param_count
        except Exception as e:
            module_info["params"] = 0
        
        # 判断是否可剪枝
        module_info["prunable"] = is_module_prunable(module, name_prefix, strict=strict_pruning)
        
        # 如果可剪枝，添加到可剪枝列表
        if module_info["prunable"]:
            structure_info["prunable_modules"].append(name_prefix)
        
        structure_info["total_params"] += module_info["params"]
        structure_info["total_modules"] += 1
        
        # 递归处理子模块
        for child_name, child_module in module.named_children():
            full_name = f"{name_prefix}.{child_name}" if name_prefix else child_name
            child_info = get_module_info(child_module, full_name, depth + 1)
            module_info["submodules"].append(child_info)
        
        return module_info
    
    # 分析模型顶层模块
    for name, module in model.named_children():
        try:
            module_info = get_module_info(module, name, 0)
            structure_info["modules"].append(module_info)
        except Exception as e:
            continue
    
    # 添加模型分析数据
    structure_info["analysis"] = {
        "param_distribution": calculate_param_distribution(structure_info["modules"]),
        "memory_usage": structure_info["total_params"] * 4 / (1024 ** 2)  # 假设每个参数4字节，转换为MB
    }
    
    return structure_info


def calculate_param_distribution(modules):
    """
    计算参数分布
    """
    param_dist = []
    
    def traverse_modules(mods, path=""):
        for mod in mods:
            current_path = f"{path}.{mod['name']}" if path else mod['name']
            if mod['params'] > 0:
                param_dist.append({
                    "name": current_path,
                    "type": mod['type'],
                    "params": mod['params'],
                    "percentage": 0  # 稍后计算
                })
            if mod['submodules']:
                traverse_modules(mod['submodules'], current_path)
    
    traverse_modules(modules)
    
    # 计算百分比
    total_params = sum(item['params'] for item in param_dist)
    if total_params > 0:
        for item in param_dist:
            item['percentage'] = round((item['params'] / total_params) * 100, 2)
    
    return param_dist


class ModelAnalysisRequest(BaseModel):
    include_flops: bool = True
    include_memory: bool = True
    include_bottleneck: bool = True
    hardware_target: str = "auto"  # auto, cpu, gpu, npu


@router.post("/{model_id}/analyze")
def analyze_model(
    model_id: str,
    request: ModelAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    模型分析：计算FLOPs、内存使用、瓶颈分析等
    """
    from ultralytics import YOLO
    from app.crud.crud_model import model
    import torch
    
    # 获取模型信息
    db_model = model.get(db, id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="模型未找到")
    
    try:
        # 加载模型
        yolo_model = YOLO(db_model.path)
        torch_model = yolo_model.model
        
        # 确保模型处于评估模式
        torch_model.eval()
        
        analysis_result = {
            "model_id": model_id,
            "model_name": db_model.name,
            "analysis": {}
        }
        
        # 计算参数分布
        if request.include_flops:
            analysis_result["analysis"]["param_distribution"] = calculate_param_distribution(analyze_model_structure(torch_model)["modules"])
        
        # 内存使用分析
        if request.include_memory:
            total_params = sum(p.numel() for p in torch_model.parameters())
            analysis_result["analysis"]["memory_usage"] = {
                "total_params": total_params,
                "estimated_memory_mb": total_params * 4 / (1024 ** 2)  # 4字节/参数
            }
        
        # 硬件特定分析
        if request.hardware_target != "auto":
            analysis_result["analysis"]["hardware_target"] = request.hardware_target
        
        return analysis_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型分析失败: {str(e)}")

def simple_structured_pruning(model, modules_to_prune, prune_ratio):
    """
    简单的结构化剪枝 - 按用户指定的层进行剪枝（完全按照用户选择，不做额外限制）
    """
    import torch
    import torch.nn as nn
    import torch_pruning as tp
    import logging
    import copy
    
    logger = logging.getLogger(__name__)
    
    # 创建模型副本以避免污染原始模型
    pruned_model = copy.deepcopy(model)
    pruned_model = pruned_model.cpu()
    
    # 准备示例输入
    example_input = torch.randn(1, 3, 640, 640)
    
    # 构建依赖图，只忽略绝对不能剪枝的层（检测头等关键层）
    # 其他用户选择的层都应该被允许尝试剪枝
    ignored_layers = []
    
    for name, m in pruned_model.named_modules():
        name_lower = name.lower()
        
        # 只有检测头相关的层才被忽略，其他层都包含在依赖图中
        if any(keyword in name_lower for keyword in ['detect', 'dfl', 'cls', 'reg', 'segment', 'pose']):
            ignored_layers.append(m)
            continue
        
    # 构建依赖图
    try:
        dg = tp.DependencyGraph().build_dependency(
            pruned_model,
            example_inputs=example_input,
            ignored_layers=ignored_layers
        )
    except Exception as e:
        raise Exception(f"构建依赖图失败: {str(e)}")
    
    pruned_count = 0
    failed_layers = []
    successfully_pruned = []
    
    # 对用户指定的每个模块进行剪枝 - 完全按照用户选择，不做任何限制
    for module_path in modules_to_prune:
        try:
            # 获取指定的模块
            module = dict(pruned_model.named_modules())[module_path]
            
            # 检查模块是否为卷积层
            if not isinstance(module, nn.Conv2d):
                # 如果不是卷积层，跳过（因为结构化剪枝只能对卷积层操作）
                # 这是torch-pruning工具的限制，不是代码限制
                continue
            
            # 检查模块是否在依赖图中
            if module not in dg.module2node:
                # 模块不在依赖图中，无法安全剪枝
                failed_layers.append({"layer": module_path, "reason": "模块不在依赖图中"})
                continue
            
            # 检查模块是否满足剪枝条件
            out_channels = module.out_channels
            num_prune = int(out_channels * prune_ratio)
            
            if num_prune <= 0 or num_prune >= out_channels or out_channels <= 1:
                failed_layers.append({"layer": module_path, "reason": f"剪枝比例非法 (out_channels={out_channels}, prune_channels={num_prune})"})
                continue
            
            # 计算重要性（基于权重的L1范数）
            importance = torch.norm(module.weight.data.view(out_channels, -1), p=1, dim=1)
            
            # 获取要剪枝的通道索引
            prune_indices = torch.argsort(importance)[:num_prune].tolist()
            
            # 通过依赖图获取安全的剪枝组
            try:
                pruning_group = dg.get_pruning_group(
                    module, 
                    tp.prune_conv_out_channels, 
                    idxs=prune_indices
                )
            except Exception as e:
                failed_layers.append({"layer": module_path, "reason": f"获取剪枝组失败: {str(e)}"})
                continue
            
            # 检查并执行剪枝
            if pruning_group is not None and hasattr(pruning_group, '__len__') and len(pruning_group) > 0:
                if not hasattr(pruning_group, 'executable') or pruning_group.executable():
                    try:
                        pruning_group.prune()
                        pruned_count += 1
                        successfully_pruned.append({
                            "layer": module_path, 
                            "channels_pruned": num_prune, 
                            "original_channels": out_channels
                        })
                        logger.info(f"✅ 成功剪枝层: {module_path}，从 {out_channels} 通道剪到 {out_channels - num_prune} 通道")
                    except Exception as e:
                        failed_layers.append({"layer": module_path, "reason": f"执行剪枝失败: {str(e)}"})
                        logger.warning(f"执行剪枝失败 {module_path}: {e}")
                else:
                    failed_layers.append({"layer": module_path, "reason": "剪枝组不可执行"})
                    logger.warning(f"跳过 {module_path}: 剪枝组不可执行")
            else:
                failed_layers.append({"layer": module_path, "reason": "剪枝组为空或无效"})
                logger.warning(f"跳过 {module_path}: 剪枝组为空或无效")
        
        except Exception as e:
            failed_layers.append({"layer": module_path, "reason": f"处理剪枝时出错: {str(e)}"})
            logger.warning(f"处理剪枝 {module_path} 时出错: {e}")
            continue
    
    # 对于自定义剪枝，即使没有成功剪枝任何层，也正常返回结果
    # 因为用户可能选择了一些无法剪枝的层，这是用户的选择
    if pruned_count == 0 and modules_to_prune:
        logger.info(f"自定义结构化剪枝完成：共指定 {len(modules_to_prune)} 个层，但成功剪枝 0 层")
    
    logger.info(f"结构化剪枝完成: 成功 {pruned_count} 层，失败 {len(failed_layers)} 层")
    
    return pruned_model, successfully_pruned, failed_layers



