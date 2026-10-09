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
from app.api.deps import forbid_in_external_mode, get_current_active_user
from app.models.dataset import Dataset as DatasetModel
from app.models.annotation import AnnotationProject as AnnotationProjectModel
from app.models.mosaic import MosaicCandidate as MosaicCandidateModel, MOSAIC_PENDING_LIMIT
from app.models.user import User
from app.services.opencv_service import opencv_service
from app.services.batch_process_service import batch_process_service
from app.services.mosaic_service import mosaic_service
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

# 批量处理任务目录：每个任务一个子目录，内含 status.json / manifest.json / result.zip
BATCH_DIR = Path(settings.STATIC_DIR) / "batch_tasks"
os.makedirs(BATCH_DIR, exist_ok=True)

# 拼图候选（待审核）目录
MOSAIC_DIR = Path(settings.STATIC_DIR) / "mosaic_candidates"
os.makedirs(MOSAIC_DIR, exist_ok=True)


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
    background_tasks: BackgroundTasks,
    images: List[UploadFile] = File(...),
    operations: str = Form("[]"),
    db: Session = Depends(get_db)
):
    """
    批量处理上传的图像（异步）

    立即返回 task_id，用 /opencv/batch-status/{task_id} 轮询进度，
    完成后用 /opencv/batch-download/{task_id} 下载打包结果。

    操作格式:
    [
        {"name": "resize_image", "params": {"width": 640, "height": 480}},
        {"name": "denoise_image", "params": {"strength": 3}}
    ]
    """
    import json

    try:
        operations_list = json.loads(operations)
        if not operations_list:
            raise HTTPException(status_code=400, detail="请至少选择一个处理操作")
        warnings = batch_process_service.validate_operations(operations_list)

        task_id = str(uuid.uuid4())
        input_dir = TEMP_DIR / f"batch_{task_id}"
        output_dir = BATCH_DIR / task_id
        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        # 保留原始文件名，方便处理完之后和源文件对得上
        # （save_upload_file_temp 会把文件名换成 uuid）
        pairs = []
        used_names = set()
        for image in images:
            raw_name = os.path.basename(image.filename or "image.jpg")
            name = raw_name
            stem, ext = os.path.splitext(raw_name)
            dup = 1
            while name in used_names:
                name = f"{stem}_{dup}{ext}"
                dup += 1
            used_names.add(name)

            dest = input_dir / name
            with open(dest, "wb") as f:
                shutil.copyfileobj(image.file, f)
            pairs.append((str(dest), None))

        if not pairs:
            raise HTTPException(status_code=400, detail="没有收到任何图像")

        batch_process_service.write_status(
            str(output_dir), status="pending", total=len(pairs), processed=0,
            failed=0, warnings=warnings,
        )
        batch_process_service.write_manifest(str(output_dir), {
            "source": "upload",
            "operations": operations_list,
            "selected": [os.path.basename(pth) for pth, _lab in pairs],
        })

        background_tasks.add_task(
            _run_batch_task, task_id, pairs, str(output_dir),
            operations_list, str(input_dir), warnings, str(input_dir),
        )

        return {
            "success": True,
            "message": f"已提交 {len(pairs)} 张图像的批量处理任务",
            "task_id": task_id,
            "total": len(pairs),
            "warnings": warnings,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交批量处理任务失败: {str(e)}")


@router.post("/batch-process-directory")
async def batch_process_directory(
    background_tasks: BackgroundTasks,
    source: str = Form("dataset"),          # dataset | annotation_project | path
    source_id: Optional[str] = Form(None),
    source_path: Optional[str] = Form(None),
    split: str = Form("all"),               # train | val | test | all
    sample_mode: str = Form("all"),         # all | ratio | count
    sample_value: float = Form(1.0),        # ratio 时是 0~1，count 时是张数
    sample_seed: Optional[int] = Form(None),
    operations: str = Form("[]"),
    db: Session = Depends(get_db)
):
    """
    直接处理服务器上已有的图片，不必经浏览器上传

    支持从数据集 / 标注项目里按比例或按张数随机抽样，
    比如"从这个数据集里随机取 20% 做降噪"。
    抽样种子会记进 manifest.json，保证结果可复现、可复查。

    注意：不提供就地覆盖 —— 覆盖原图不可逆，结果一律写到新目录，
    需要的话再自行替换。
    """
    import json

    try:
        operations_list = json.loads(operations)
        if not operations_list:
            raise HTTPException(status_code=400, detail="请至少选择一个处理操作")
        warnings = batch_process_service.validate_operations(operations_list)

        # 解析源目录
        if source == "dataset":
            if not source_id:
                raise HTTPException(status_code=400, detail="请指定数据集")
            ds = db.query(DatasetModel).filter(DatasetModel.id == source_id).first()
            if not ds:
                raise HTTPException(status_code=404, detail="数据集不存在")
            root = str(ds.path)
            source_name = ds.name
        elif source == "annotation_project":
            if not source_id:
                raise HTTPException(status_code=400, detail="请指定标注项目")
            proj = db.query(AnnotationProjectModel).filter(
                AnnotationProjectModel.id == source_id).first()
            if not proj:
                raise HTTPException(status_code=404, detail="标注项目不存在")
            root = str(proj.image_directory)
            source_name = proj.name
        elif source == "path":
            # 任意服务器路径作为来源，对外部署时等同于开放文件系统读取
            forbid_in_external_mode()
            if not source_path:
                raise HTTPException(status_code=400, detail="请指定目录路径")
            root = source_path
            source_name = os.path.basename(source_path.rstrip("/\\")) or "directory"
        else:
            raise HTTPException(status_code=400, detail=f"不支持的来源: {source}")

        all_pairs = batch_process_service.collect_images(root, split)
        if not all_pairs:
            raise HTTPException(status_code=404, detail=f"目录里没有找到图片: {root}")

        pairs, seed = batch_process_service.sample(
            all_pairs, sample_mode, sample_value, sample_seed)

        labeled = sum(1 for _img, lab in pairs if lab)
        if labeled and any(op.get("name") in batch_process_service.LABEL_APPROX
                           for op in operations_list):
            warnings.append(f"本次有 {labeled} 张图带标注，请留意上面的标签精度提示")

        task_id = str(uuid.uuid4())
        output_dir = BATCH_DIR / task_id
        os.makedirs(output_dir, exist_ok=True)

        batch_process_service.write_status(
            str(output_dir), status="pending", total=len(pairs), processed=0,
            failed=0, warnings=warnings,
        )
        batch_process_service.write_manifest(str(output_dir), {
            "source": source,
            "source_id": source_id,
            "source_name": source_name,
            "source_root": root,
            "split": split,
            "operations": operations_list,
            # seed 和选中清单必须落盘：抽样不可复现的话，
            # 事后没法查是哪一批图被改了
            "sample": {"mode": sample_mode, "value": sample_value, "seed": seed},
            "candidate_count": len(all_pairs),
            "selected_count": len(pairs),
            "labeled_count": labeled,
            "selected": [os.path.relpath(pth, root) for pth, _lab in pairs],
        })

        background_tasks.add_task(
            _run_batch_task, task_id, pairs, str(output_dir),
            operations_list, root, warnings, None,
        )

        return {
            "success": True,
            "message": f"已从 {len(all_pairs)} 张中抽取 {len(pairs)} 张提交处理",
            "task_id": task_id,
            "total": len(pairs),
            "candidate_count": len(all_pairs),
            "labeled_count": labeled,
            "seed": seed,
            "warnings": warnings,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交批量处理任务失败: {str(e)}")


def _run_batch_task(task_id, pairs, output_dir, operations_list,
                    source_root, warnings, cleanup_dir):
    """后台批量处理任务：边跑边写进度，跑完打包成 zip"""
    total = len(pairs)
    try:
        batch_process_service.write_status(
            output_dir, status="running", total=total, processed=0,
            failed=0, warnings=warnings,
        )

        # 每 5 张或最后一张写一次进度，避免频繁写盘
        def on_progress(processed, failed, total_count):
            if processed % 5 == 0 or processed + failed >= total_count:
                batch_process_service.write_status(
                    output_dir, status="running", total=total_count,
                    processed=processed, failed=failed, warnings=warnings,
                )

        stats = batch_process_service.run(
            pairs, output_dir, operations_list,
            source_root=source_root, progress_cb=on_progress,
        )

        zip_path = os.path.join(output_dir, "result.zip")
        batch_process_service.make_zip(output_dir, zip_path)

        batch_process_service.write_status(
            output_dir, status="completed", warnings=warnings,
            download_url=f"/api/opencv/batch-download/{task_id}", **stats,
        )
    except Exception as e:
        batch_process_service.write_status(
            output_dir, status="failed", total=total, processed=0,
            failed=total, error=str(e), warnings=warnings,
        )
    finally:
        if cleanup_dir:
            batch_process_service.cleanup(cleanup_dir)


@router.get("/batch-status/{task_id}")
async def get_batch_status(task_id: str):
    """轮询批量处理任务进度"""
    output_dir = BATCH_DIR / task_id
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="任务不存在")

    status = batch_process_service.read_status(str(output_dir))
    if status is None:
        return {"status": "pending"}

    total = status.get("total") or 0
    done = (status.get("processed") or 0) + (status.get("failed") or 0)
    status["progress"] = round(done / total * 100, 1) if total else 0.0
    return status


@router.get("/batch-download/{task_id}")
async def download_batch_result(task_id: str):
    """下载批量处理结果压缩包"""
    zip_path = BATCH_DIR / task_id / "result.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="结果尚未生成或任务不存在")
    return FileResponse(path=str(zip_path), filename=f"batch_{task_id}.zip",
                        media_type="application/zip")


@router.get("/batch-manifest/{task_id}")
async def get_batch_manifest(task_id: str):
    """查看这次任务实际选中了哪些文件、用的什么随机种子"""
    import json
    manifest_path = BATCH_DIR / task_id / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="任务不存在")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/batch-file/{task_id}/{file_path:path}")
async def get_batch_file(task_id: str, file_path: str):
    """取批量处理结果中的单个文件（前端用来渲染缩略图）"""
    base = (BATCH_DIR / task_id).resolve()
    target = (base / file_path).resolve()
    # 防止 ../ 穿越到任务目录之外
    if base != target and base not in target.parents:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path=str(target))


@router.post("/create-grid")
async def create_grid(
    images: List[UploadFile] = File(...),
    rows: int = Form(2),
    cols: int = Form(2),
    cell_width: Optional[int] = Form(None),
    cell_height: Optional[int] = Form(None),
    shuffle: bool = Form(False),
    seed: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    把多张图片拼成 rows x cols 的网格（联系表）

    纯预览用途，不产出标注，适合快速看一批抽帧结果或增强效果。
    需要进训练集的四合一拼图请用 /opencv/mosaic/generate。
    """
    import random as _random

    temp_dir = TEMP_DIR / f"grid_{uuid.uuid4()}"
    try:
        os.makedirs(temp_dir, exist_ok=True)

        temp_files = []
        for image in images:
            temp_files.append(await save_upload_file_temp(image, temp_dir))

        if not temp_files:
            raise HTTPException(status_code=400, detail="没有收到任何图像")

        if shuffle:
            rng = _random.Random(seed if seed is not None else _random.randrange(1, 2 ** 31 - 1))
            rng.shuffle(temp_files)

        imgs = [opencv_service.read_image(pth) for pth in temp_files]

        cell_size = None
        if cell_width and cell_height:
            cell_size = (int(cell_width), int(cell_height))

        grid = opencv_service.create_grid_image(imgs, int(rows), int(cols), cell_size)
        if grid is None:
            raise HTTPException(status_code=400, detail="创建网格失败")

        output_filename = f"grid_{uuid.uuid4()}.jpg"
        output_path = ADVANCED_AUG_DIR / output_filename
        opencv_service.save_image(grid, output_path)

        return {
            "success": True,
            "output_path": f"/static/advanced_augmentations/{output_filename}",
            "used": min(len(imgs), int(rows) * int(cols)),
            "supplied": len(imgs),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建网格失败: {str(e)}")
    finally:
        batch_process_service.cleanup(str(temp_dir))


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


# ==================== Mosaic 拼图候选（生成 -> 人工审核 -> 进训练集） ====================

@router.post("/mosaic/generate")
def generate_mosaic_candidates(
    dataset_id: str = Form(...),
    count: int = Form(20),
    split: str = Form("train"),
    seed: Optional[int] = Form(None),
    output_size: int = Form(640),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    批量随机生成拼图候选

    每张拼图随机取 4 张带标注的源图拼成，标注框跟着一起变换。
    产物先落在待定区，需要人工逐张审核（采纳 / 丢弃 / 暂留）后才进训练集。
    待审核数量有上限，超了会截断并在返回里说明。
    """
    dataset = db.query(DatasetModel).filter(DatasetModel.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    try:
        result = mosaic_service.generate(
            db, dataset, count=count, split=split, seed=seed,
            output_size=output_size, user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成拼图失败: {str(e)}")

    result["success"] = True
    return result


@router.get("/mosaic/candidates")
def list_mosaic_candidates(
    status: str = "pending",
    dataset_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """列出拼图候选，默认只看待审核的"""
    query = db.query(MosaicCandidateModel)
    if status and status != "all":
        query = query.filter(MosaicCandidateModel.status == status)
    if dataset_id:
        query = query.filter(MosaicCandidateModel.source_dataset_id == dataset_id)

    total = query.count()
    rows = (query.order_by(MosaicCandidateModel.created_at, MosaicCandidateModel.id)
            .offset(skip).limit(limit).all())

    return {
        "total": total,
        "pending_total": mosaic_service.pending_count(db),
        "pending_limit": MOSAIC_PENDING_LIMIT,
        "items": [mosaic_service.to_dict(row) for row in rows],
    }


@router.post("/mosaic/{candidate_id}/accept")
def accept_mosaic_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """采纳：写入 {源数据集名}_mosaic 数据集的 train 子集"""
    candidate = db.query(MosaicCandidateModel).filter(
        MosaicCandidateModel.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选不存在")
    try:
        result = mosaic_service.accept(db, candidate)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"采纳失败: {str(e)}")
    result["success"] = True
    return result


@router.post("/mosaic/{candidate_id}/discard")
def discard_mosaic_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """丢弃：删除待定区文件并标记状态。暂留则不调用任何接口，保持 pending 即可"""
    candidate = db.query(MosaicCandidateModel).filter(
        MosaicCandidateModel.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选不存在")
    try:
        result = mosaic_service.discard(db, candidate)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    result["success"] = True
    return result
