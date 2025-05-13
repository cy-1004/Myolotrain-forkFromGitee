"""
OpenCV API 端点 - 提供图像处理和计算机视觉功能的 API
"""
import os
import shutil
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.db.session import get_db
from app.core.config import settings
from app.services.opencv_service import opencv_service
from app.utils.file_utils import save_upload_file_temp, get_temp_file_path

router = APIRouter()

# 临时文件目录
TEMP_DIR = Path(settings.TEMP_DIR) / "opencv"
os.makedirs(TEMP_DIR, exist_ok=True)

# 处理后的图像目录
PROCESSED_DIR = Path(settings.STATIC_DIR) / "processed_images"
os.makedirs(PROCESSED_DIR, exist_ok=True)

# 数据集增强目录
AUGMENTED_DIR = Path(settings.STATIC_DIR) / "augmented_datasets"
os.makedirs(AUGMENTED_DIR, exist_ok=True)

# 高级数据增强目录
ADVANCED_AUG_DIR = Path(settings.STATIC_DIR) / "advanced_augmentations"
os.makedirs(ADVANCED_AUG_DIR, exist_ok=True)


@router.post("/preprocess", response_class=FileResponse)
async def preprocess_image(
    image: UploadFile = File(...),
    operations: str = Form("[]"),
    db: Session = Depends(get_db)
):
    """
    预处理图像

    操作格式:
    [
        {"name": "resize_image", "params": {"width": 640, "height": 480}},
        {"name": "denoise_image", "params": {"strength": 3}}
    ]
    """
    import json

    try:
        # 解析操作
        operations_list = json.loads(operations)

        # 保存上传的图像
        temp_file = await save_upload_file_temp(image, TEMP_DIR)

        # 读取图像
        img = opencv_service.read_image(temp_file)

        # 应用操作
        for operation in operations_list:
            op_name = operation["name"]
            op_params = operation.get("params", {})

            # 获取操作方法
            op_method = getattr(opencv_service, op_name, None)
            if op_method is None:
                raise HTTPException(status_code=400, detail=f"未知的操作: {op_name}")

            # 应用操作
            img = op_method(img, **op_params)

        # 保存处理后的图像
        output_filename = f"processed_{Path(image.filename).stem}.jpg"
        output_path = PROCESSED_DIR / output_filename
        opencv_service.save_image(img, output_path)

        # 返回处理后的图像
        return FileResponse(
            path=output_path,
            filename=output_filename,
            media_type="image/jpeg"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图像处理失败: {str(e)}")
    finally:
        # 清理临时文件
        if 'temp_file' in locals():
            try:
                os.remove(temp_file)
            except:
                pass


@router.post("/batch-process")
async def batch_process_images(
    images: List[UploadFile] = File(...),
    operations: str = Form("[]"),
    db: Session = Depends(get_db)
):
    """
    批量处理图像

    操作格式:
    [
        {"name": "resize_image", "params": {"width": 640, "height": 480}},
        {"name": "denoise_image", "params": {"strength": 3}}
    ]
    """
    import json
    import uuid

    try:
        # 解析操作
        operations_list = json.loads(operations)

        # 创建批处理目录
        batch_id = str(uuid.uuid4())
        batch_dir = TEMP_DIR / f"batch_{batch_id}"
        output_dir = PROCESSED_DIR / f"batch_{batch_id}"
        os.makedirs(batch_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        # 保存上传的图像
        temp_files = []
        for image in images:
            temp_file = await save_upload_file_temp(image, batch_dir)
            temp_files.append(temp_file)

        # 批量处理图像
        output_paths = opencv_service.batch_process_images(
            temp_files,
            str(output_dir),
            operations_list
        )

        # 返回处理结果
        return {
            "success": True,
            "message": f"成功处理 {len(output_paths)} 张图像",
            "batch_id": batch_id,
            "output_paths": [str(path) for path in output_paths]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量处理图像失败: {str(e)}")


@router.get("/processed/{batch_id}/{filename}")
async def get_processed_image(batch_id: str, filename: str):
    """获取处理后的图像"""
    file_path = PROCESSED_DIR / f"batch_{batch_id}" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="图像不存在")

    return FileResponse(path=file_path)


@router.post("/analyze-image")
async def analyze_image(
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """分析图像质量"""
    try:
        # 保存上传的图像
        temp_file = await save_upload_file_temp(image, TEMP_DIR)

        # 读取图像
        img = opencv_service.read_image(temp_file)

        # 分析图像质量
        is_blurry, blur_score = opencv_service.detect_blur(img)
        is_overexposed, overexposed_ratio = opencv_service.detect_overexposure(img)
        is_underexposed, underexposed_ratio = opencv_service.detect_underexposure(img)

        # 返回分析结果
        return {
            "filename": image.filename,
            "blur": {
                "is_blurry": is_blurry,
                "score": blur_score
            },
            "exposure": {
                "is_overexposed": is_overexposed,
                "overexposed_ratio": overexposed_ratio,
                "is_underexposed": is_underexposed,
                "underexposed_ratio": underexposed_ratio
            },
            "recommendations": [
                "图像模糊，建议使用更清晰的图像" if is_blurry else None,
                "图像过度曝光，建议降低曝光" if is_overexposed else None,
                "图像曝光不足，建议增加曝光" if is_underexposed else None
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析图像失败: {str(e)}")
    finally:
        # 清理临时文件
        if 'temp_file' in locals():
            try:
                os.remove(temp_file)
            except:
                pass


@router.post("/augment-dataset")
async def augment_dataset(
    background_tasks: BackgroundTasks,
    dataset_path: str = Form(...),
    augmentation_options: str = Form("{}"),
    multiplier: int = Form(2),
    db: Session = Depends(get_db)
):
    """
    增强数据集

    增强选项格式:
    {
        "flip": true,
        "rotate": {"angles": [90, 180, 270]},
        "noise": {"types": ["gaussian"], "amount": 0.05},
        "brightness_contrast": {"brightness": [-20, 20], "contrast": [0.8, 1.2]},
        "perspective": true,
        "perspective_strength": 0.2
    }
    """
    import json
    import uuid

    try:
        # 解析增强选项
        augmentation_options_dict = json.loads(augmentation_options)

        # 验证数据集路径
        dataset_dir = Path(dataset_path)
        if not dataset_dir.exists() or not dataset_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"数据集目录不存在: {dataset_path}")

        # 创建输出目录
        augmentation_id = str(uuid.uuid4())
        output_dir = AUGMENTED_DIR / augmentation_id
        os.makedirs(output_dir, exist_ok=True)

        # 在后台任务中增强数据集
        def augment_dataset_task():
            try:
                stats = opencv_service.augment_dataset(
                    str(dataset_dir),
                    str(output_dir),
                    augmentation_options_dict,
                    multiplier
                )

                # 保存统计信息
                with open(output_dir / "stats.json", "w") as f:
                    json.dump(stats, f, indent=2)

            except Exception as e:
                # 记录错误
                with open(output_dir / "error.txt", "w") as f:
                    f.write(f"增强数据集失败: {str(e)}")

        # 添加后台任务
        background_tasks.add_task(augment_dataset_task)

        # 返回任务信息
        return {
            "success": True,
            "message": "数据集增强任务已启动",
            "augmentation_id": augmentation_id,
            "output_dir": str(output_dir)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动数据集增强任务失败: {str(e)}")


@router.get("/augmentation-status/{augmentation_id}")
async def get_augmentation_status(augmentation_id: str):
    """获取数据集增强任务状态"""
    output_dir = AUGMENTED_DIR / augmentation_id

    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="增强任务不存在")

    # 检查是否有错误
    error_file = output_dir / "error.txt"
    if error_file.exists():
        with open(error_file, "r") as f:
            error_message = f.read()
        return {
            "status": "failed",
            "error": error_message
        }

    # 检查是否完成
    stats_file = output_dir / "stats.json"
    if stats_file.exists():
        with open(stats_file, "r") as f:
            import json
            stats = json.load(f)
        return {
            "status": "completed",
            "stats": stats
        }

    # 任务仍在进行中
    return {
        "status": "in_progress"
    }


@router.post("/compare-images")
async def compare_images(
    images: List[UploadFile] = File(...),
    titles: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """创建图像比较视图"""
    try:
        # 解析标题
        titles_list = titles.split(",") if titles else None

        # 保存上传的图像
        temp_files = []
        for image in images:
            temp_file = await save_upload_file_temp(image, TEMP_DIR)
            temp_files.append(temp_file)

        # 读取图像
        imgs = [opencv_service.read_image(file) for file in temp_files]

        # 创建比较图像
        comparison = opencv_service.create_comparison_image(imgs, titles_list)

        # 保存比较图像
        import uuid
        output_filename = f"comparison_{uuid.uuid4()}.jpg"
        output_path = PROCESSED_DIR / output_filename
        opencv_service.save_image(comparison, output_path)

        # 返回比较图像
        return FileResponse(
            path=output_path,
            filename=output_filename,
            media_type="image/jpeg"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建图像比较视图失败: {str(e)}")
    finally:
        # 清理临时文件
        for temp_file in locals().get('temp_files', []):
            try:
                os.remove(temp_file)
            except:
                pass


@router.post("/draw-boxes")
async def draw_bounding_boxes(
    image: UploadFile = File(...),
    boxes: str = Form(...),
    labels: Optional[str] = Form(None),
    confidences: Optional[str] = Form(None),
    color: Optional[str] = Form("0,255,0"),
    thickness: int = Form(2),
    db: Session = Depends(get_db)
):
    """
    在图像上绘制边界框

    边界框格式:
    [[x1, y1, x2, y2], [x1, y1, x2, y2], ...]
    或
    [[x, y, w, h, 1], [x, y, w, h, 1], ...] (最后一个1表示是xywh格式)
    """
    import json

    try:
        # 解析参数
        boxes_list = json.loads(boxes)
        labels_list = json.loads(labels) if labels else None
        confidences_list = json.loads(confidences) if confidences else None
        color_tuple = tuple(map(int, color.split(",")))

        # 保存上传的图像
        temp_file = await save_upload_file_temp(image, TEMP_DIR)

        # 读取图像
        img = opencv_service.read_image(temp_file)

        # 绘制边界框
        result = opencv_service.draw_bounding_boxes(
            img,
            boxes_list,
            labels_list,
            confidences_list,
            color_tuple,
            thickness
        )

        # 保存结果图像
        import uuid
        output_filename = f"boxes_{uuid.uuid4()}.jpg"
        output_path = PROCESSED_DIR / output_filename
        opencv_service.save_image(result, output_path)

        # 返回结果图像
        return FileResponse(
            path=output_path,
            filename=output_filename,
            media_type="image/jpeg"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"绘制边界框失败: {str(e)}")
    finally:
        # 清理临时文件
        if 'temp_file' in locals():
            try:
                os.remove(temp_file)
            except:
                pass


@router.post("/advanced-augmentation")
async def advanced_augmentation(
    background_tasks: BackgroundTasks,
    image1: Optional[UploadFile] = File(None),
    image2: Optional[UploadFile] = File(None),
    image3: Optional[UploadFile] = File(None),
    image4: Optional[UploadFile] = File(None),
    augmentation_type: str = Form(...),  # cutmix, mixup, mosaic, weather
    cutmix_alpha: Optional[float] = Form(None),
    mixup_alpha: Optional[float] = Form(None),
    weather_type: Optional[str] = Form(None),  # rain, snow, fog, etc.
    weather_intensity: Optional[float] = Form(None),
    db: Session = Depends(get_db)
):
    """
    高级数据增强

    支持的增强类型:
    - cutmix: 将两张图像按一定比例混合
    - mixup: 将两张图像按权重混合
    - mosaic: 将四张图像拼接成一张
    - weather: 模拟天气效果（雨、雪、雾等）
    """
    try:
        # 创建临时目录
        temp_dir = TEMP_DIR / f"advanced_aug_{uuid.uuid4()}"
        os.makedirs(temp_dir, exist_ok=True)

        # 保存上传的图像
        temp_files = []

        # 根据增强类型处理图像
        if augmentation_type == "cutmix":
            # CutMix需要两张图像
            if not image1 or not image2:
                raise HTTPException(status_code=400, detail="CutMix需要两张图像")

            # 保存图像
            temp_file1 = await save_upload_file_temp(image1, temp_dir)
            temp_file2 = await save_upload_file_temp(image2, temp_dir)
            temp_files.extend([temp_file1, temp_file2])

            # 读取图像
            img1 = opencv_service.read_image(temp_file1)
            img2 = opencv_service.read_image(temp_file2)

            # 应用CutMix
            alpha = cutmix_alpha or 0.5
            result = opencv_service.apply_cutmix(img1, img2, alpha)

        elif augmentation_type == "mixup":
            # MixUp需要两张图像
            if not image1 or not image2:
                raise HTTPException(status_code=400, detail="MixUp需要两张图像")

            # 保存图像
            temp_file1 = await save_upload_file_temp(image1, temp_dir)
            temp_file2 = await save_upload_file_temp(image2, temp_dir)
            temp_files.extend([temp_file1, temp_file2])

            # 读取图像
            img1 = opencv_service.read_image(temp_file1)
            img2 = opencv_service.read_image(temp_file2)

            # 应用MixUp
            alpha = mixup_alpha or 0.5
            result = opencv_service.apply_mixup(img1, img2, alpha)

        elif augmentation_type == "mosaic":
            # Mosaic需要四张图像
            if not image1 or not image2 or not image3 or not image4:
                raise HTTPException(status_code=400, detail="Mosaic需要四张图像")

            # 保存图像
            temp_file1 = await save_upload_file_temp(image1, temp_dir)
            temp_file2 = await save_upload_file_temp(image2, temp_dir)
            temp_file3 = await save_upload_file_temp(image3, temp_dir)
            temp_file4 = await save_upload_file_temp(image4, temp_dir)
            temp_files.extend([temp_file1, temp_file2, temp_file3, temp_file4])

            # 读取图像
            img1 = opencv_service.read_image(temp_file1)
            img2 = opencv_service.read_image(temp_file2)
            img3 = opencv_service.read_image(temp_file3)
            img4 = opencv_service.read_image(temp_file4)

            # 应用Mosaic
            result = opencv_service.apply_mosaic([img1, img2, img3, img4])

        elif augmentation_type == "weather":
            # Weather只需要一张图像
            if not image1:
                raise HTTPException(status_code=400, detail="Weather需要一张图像")

            # 保存图像
            temp_file1 = await save_upload_file_temp(image1, temp_dir)
            temp_files.append(temp_file1)

            # 读取图像
            img = opencv_service.read_image(temp_file1)

            # 检查天气类型
            if not weather_type:
                raise HTTPException(status_code=400, detail="请指定天气类型")

            # 应用天气效果
            intensity = weather_intensity or 0.5
            result = opencv_service.apply_weather_effect(img, weather_type, intensity)

        else:
            raise HTTPException(status_code=400, detail=f"不支持的增强类型: {augmentation_type}")

        # 保存结果图像
        output_filename = f"{augmentation_type}_{uuid.uuid4()}.jpg"
        output_path = ADVANCED_AUG_DIR / output_filename
        opencv_service.save_image(result, output_path)

        # 返回结果
        return {
            "success": True,
            "output_path": f"/static/advanced_augmentations/{output_filename}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"高级数据增强失败: {str(e)}")
    finally:
        # 清理临时文件
        for temp_file in locals().get('temp_files', []):
            try:
                os.remove(temp_file)
            except:
                pass

        # 清理临时目录
        if 'temp_dir' in locals():
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
