import os
import shutil
import zipfile
import uuid
import hashlib
import re
import asyncio
import json
import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import dataset
from app.models.dataset import Dataset
from app.schemas.dataset import DatasetCreate, DatasetUpdate
from app.services.upload_service import upload_manager, process_dataset_files as upload_process_dataset_files

# 导入目录路径
IMPORT_DIR = Path("datasets_import")

# 允许浏览的根目录
ALLOWED_ROOTS = [
    Path("C:/"),  # Windows C盘
    Path("D:/"),  # Windows D盘
    Path("E:/"),  # Windows E盘
    Path("F:/"),  # Windows F盘
    Path("G:/"),  # Windows G盘
    Path("H:/"),  # Windows H盘
    Path("I:/"),  # Windows I盘
    Path("J:/"),  # Windows J盘
    Path("K:/"),  # Windows K盘
    Path("L:/"),  # Windows L盘
    Path("M:/"),  # Windows M盘
    Path("N:/"),  # Windows N盘
    Path("O:/"),  # Windows O盘
    Path("P:/"),  # Windows P盘
    Path("Q:/"),  # Windows Q盘
    Path("R:/"),  # Windows R盘
    Path("S:/"),  # Windows S盘
    Path("T:/"),  # Windows T盘
    Path("U:/"),  # Windows U盘
    Path("V:/"),  # Windows V盘
    Path("W:/"),  # Windows W盘
    Path("X:/"),  # Windows X盘
    Path("Y:/"),  # Windows Y盘
    Path("Z:/"),  # Windows Z盘
    Path("/"),    # Linux/Mac根目录
    Path.home(),  # 用户主目录
]

# 最大文件名长度（Windows限制为260个字符，但我们设置更小的值以确保安全）
MAX_FILENAME_LENGTH = 200
# 非法字符正则表达式（Windows不允许的字符）
ILLEGAL_CHARS_PATTERN = r'[<>:"/\\|?*\x00-\x1F]'

def sanitize_filename(filename: str) -> str:
    """
    处理文件名，移除非法字符并确保长度不超过限制
    """
    # 移除非法字符
    sanitized = re.sub(ILLEGAL_CHARS_PATTERN, '_', filename)

    # 获取文件扩展名
    base, ext = os.path.splitext(sanitized)

    # 如果文件名仍然太长，使用哈希值替换
    if len(sanitized) > MAX_FILENAME_LENGTH:
        # 使用原始文件名的哈希值作为新文件名
        hashed_name = hashlib.md5(filename.encode('utf-8')).hexdigest()
        sanitized = f"{hashed_name}{ext}"

    return sanitized

def process_dataset_files(dataset_dir: Path) -> Dict[str, str]:
    """
    处理数据集中的所有文件，重命名过长或包含特殊字符的文件名
    返回一个字典，键为原始文件路径，值为新文件路径
    """
    renamed_files = {}

    # 处理训练、验证和测试图像目录
    for image_dir in [dataset_dir / "train" / "images", dataset_dir / "val" / "images", dataset_dir / "test" / "images"]:
        if not image_dir.exists():
            continue

        for img_file in image_dir.glob("*.*"):
            # 检查文件名是否需要处理
            filename = img_file.name
            sanitized = sanitize_filename(filename)

            # 如果文件名已更改，则重命名文件
            if sanitized != filename:
                new_path = img_file.parent / sanitized
                try:
                    # 重命名文件
                    shutil.move(str(img_file), str(new_path))
                    renamed_files[str(img_file)] = str(new_path)
                    print(f"Renamed file: {img_file} -> {new_path}")

                    # 同时处理对应的标签文件（如果存在）
                    label_file = (img_file.parent.parent / "labels" / filename).with_suffix(".txt")
                    if label_file.exists():
                        new_label_path = (new_path.parent.parent / "labels" / sanitized).with_suffix(".txt")
                        # 确保标签目录存在
                        os.makedirs(new_label_path.parent, exist_ok=True)
                        shutil.move(str(label_file), str(new_label_path))
                        renamed_files[str(label_file)] = str(new_label_path)
                        print(f"Renamed label file: {label_file} -> {new_label_path}")
                except Exception as e:
                    print(f"Error renaming file {img_file}: {str(e)}")

    return renamed_files

def process_dataset_structure(dataset_dir: Path) -> Dict[str, Any]:
    """
    处理数据集结构，确保train、val和test目录存在
    """
    # 检查并创建必要的目录
    train_images_dir = dataset_dir / "train" / "images"
    val_images_dir = dataset_dir / "val" / "images"
    test_images_dir = dataset_dir / "test" / "images"

    os.makedirs(train_images_dir, exist_ok=True)
    os.makedirs(val_images_dir, exist_ok=True)
    os.makedirs(test_images_dir, exist_ok=True)

    # 确保标签目录存在
    os.makedirs(dataset_dir / "train" / "labels", exist_ok=True)
    os.makedirs(dataset_dir / "val" / "labels", exist_ok=True)
    os.makedirs(dataset_dir / "test" / "labels", exist_ok=True)

    # 统计图像数量
    train_images = list(train_images_dir.glob("*.*"))
    val_images = list(val_images_dir.glob("*.*"))
    test_images = list(test_images_dir.glob("*.*"))

    return {
        "train_count": len(train_images),
        "val_count": len(val_images),
        "test_count": len(test_images),
        "total_count": len(train_images) + len(val_images) + len(test_images)
    }

def move_image_and_label(img_path: Path, target_img_dir: Path, target_label_dir: Path, src_set: str = "train"):
    """移动图像和对应的标签文件"""
    try:
        # 检查源图像是否存在
        if not img_path.exists():
            print(f"Warning: Source image does not exist: {img_path}")
            return

        # 检查是否是图像文件
        if img_path.suffix.lower() not in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
            print(f"Warning: Not an image file: {img_path}")
            return

        # 确保目标目录存在
        os.makedirs(target_img_dir, exist_ok=True)
        os.makedirs(target_label_dir, exist_ok=True)

        # 移动图像
        img_filename = img_path.name
        target_img_path = target_img_dir / img_filename

        print(f"Copying image from {img_path} to {target_img_path}")
        shutil.copy2(str(img_path), str(target_img_path))

        # 只有在成功复制后才删除源文件
        if target_img_path.exists():
            try:
                os.remove(img_path)
            except Exception as e:
                print(f"Warning: Could not remove source image {img_path}: {e}")

        # 移动对应的标签
        src_label_dir = img_path.parent.parent / "labels"
        label_path = None

        # 直接匹配与图像文件同名的.txt或.TXT文件（忽略文件名中的任何中间部分）
        label_name = img_path.stem + '.txt'  # 保持原始文件名，仅替换扩展名
        label_path = src_label_dir / label_name
        if not label_path.exists():
            # 尝试匹配.TXT后缀
            label_path = src_label_dir / (img_path.stem + '.TXT')

        if label_path:
            # 统一使用小写文件名处理（避免Windows大小写问题）
            target_label_path = target_label_dir / label_path.name.lower().replace('.txt', '.txt')
            print(f"Copying label from {label_path} to {target_label_path}")
            shutil.copy2(str(label_path), str(target_label_path))

            # 只有在成功复制后才删除源文件
            if target_label_path.exists():
                try:
                    # 确保删除操作使用原始路径（兼容大小写）
                    os.remove(str(label_path))
                except Exception as e:
                    print(f"Warning: Could not remove source label {label_path}: {e}")
        else:
            print(f"Warning: No label file found for {img_path} in {src_label_dir}")

        return True  # 返回成功标志
    except Exception as e:
        print(f"Error moving image and label: {e}")
        # 不抛出异常，让处理继续进行
        return False  # 返回失败标志

def split_dataset(
    dataset_dir: Path,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42,
    mode: str = "from_train"  # "from_train" 或 "redistribute"
) -> Dict[str, int]:
    """
    分割数据集为训练集、验证集和测试集

    Args:
        dataset_dir: 数据集目录
        train_ratio: 训练集比例
        val_ratio: 验证集比例
        test_ratio: 测试集比例
        random_seed: 随机种子
        mode: 分割模式，"from_train"从训练集分割，"redistribute"重新分配所有图像

    Returns:
        包含各集合图像数量的字典
    """
    print(f"Starting dataset split with mode={mode}, train_ratio={train_ratio}, val_ratio={val_ratio}, test_ratio={test_ratio}")

    import random
    random.seed(random_seed)

    # 确保目录存在
    train_images_dir = dataset_dir / "train" / "images"
    val_images_dir = dataset_dir / "val" / "images"
    test_images_dir = dataset_dir / "test" / "images"

    train_labels_dir = dataset_dir / "train" / "labels"
    val_labels_dir = dataset_dir / "val" / "labels"
    test_labels_dir = dataset_dir / "test" / "labels"

    os.makedirs(train_images_dir, exist_ok=True)
    os.makedirs(val_images_dir, exist_ok=True)
    os.makedirs(test_images_dir, exist_ok=True)
    os.makedirs(train_labels_dir, exist_ok=True)
    os.makedirs(val_labels_dir, exist_ok=True)
    os.makedirs(test_labels_dir, exist_ok=True)

    # 定义图像文件后缀
    image_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]

    # 获取所有图像文件
    def get_image_files(directory):
        if not directory.exists():
            return []
        return [f for f in directory.glob("*.*")
                if f.is_file() and f.suffix.lower() in image_extensions]

    # 根据模式执行不同的分割逻辑
    if mode == "from_train":
        # 从训练集分割出验证集和测试集
        train_images = get_image_files(train_images_dir)
        print(f"Found {len(train_images)} images in train directory")

        # 计算要移动的图像数量
        total_images = len(train_images)
        if total_images == 0:
            print("Warning: No images found in train directory")
            return {
                "train": 0,
                "val": 0,
                "test": 0,
                "total": 0
            }

        num_val = int(total_images * val_ratio / (1 - test_ratio))
        num_test = int(total_images * test_ratio / (1 - test_ratio))

        # 确保不超过总数
        num_val = min(num_val, total_images - 1)  # 至少保留一张图片在训练集
        num_test = min(num_test, total_images - num_val - 1)

        print(f"Will move {num_val} images to val and {num_test} images to test")

        # 随机选择验证集和测试集图像
        if num_val + num_test > 0:
            images_to_move = random.sample(train_images, num_val + num_test)
            val_images = images_to_move[:num_val]
            test_images = images_to_move[num_val:]

            # 移动验证集图像和标签
            val_success = 0
            for img_path in val_images:
                if move_image_and_label(img_path, val_images_dir, val_labels_dir):
                    val_success += 1
            print(f"Successfully moved {val_success}/{len(val_images)} images to val set")

            # 移动测试集图像和标签
            test_success = 0
            for img_path in test_images:
                if move_image_and_label(img_path, test_images_dir, test_labels_dir):
                    test_success += 1
            print(f"Successfully moved {test_success}/{len(test_images)} images to test set")

    else:  # "redistribute"
        # 收集所有图像
        train_images = get_image_files(train_images_dir)
        val_images = get_image_files(val_images_dir)
        test_images = get_image_files(test_images_dir)

        print(f"Found {len(train_images)} train images, {len(val_images)} val images, {len(test_images)} test images")

        # 创建包含源集信息的列表
        all_images = []
        all_images.extend([(img, "train") for img in train_images])
        all_images.extend([(img, "val") for img in val_images])
        all_images.extend([(img, "test") for img in test_images])

        # 随机打乱
        random.shuffle(all_images)

        # 计算每个集合的图像数量
        total_images = len(all_images)
        if total_images == 0:
            print("Warning: No images found in dataset")
            return {
                "train": 0,
                "val": 0,
                "test": 0,
                "total": 0
            }

        num_train = max(1, int(total_images * train_ratio))  # 至少一张图片
        num_val = max(1, int(total_images * val_ratio))      # 至少一张图片

        # 确保总数不超过
        if num_train + num_val >= total_images:
            num_train = max(1, int(total_images * 0.7))  # 默认值
            num_val = max(1, int(total_images * 0.15))   # 默认值
            if num_train + num_val >= total_images:
                num_train = max(1, total_images - 2)  # 至少留两张给其他集合
                num_val = 1

        print(f"Will redistribute: {num_train} to train, {num_val} to val, {total_images - num_train - num_val} to test")

        # 分配图像
        new_train = all_images[:num_train]
        new_val = all_images[num_train:num_train+num_val]
        new_test = all_images[num_train+num_val:]

        # 创建临时目录来存储所有图像
        temp_dir = dataset_dir / "temp"
        temp_images_dir = temp_dir / "images"
        temp_labels_dir = temp_dir / "labels"
        os.makedirs(temp_images_dir, exist_ok=True)
        os.makedirs(temp_labels_dir, exist_ok=True)

        # 先将所有图像移动到临时目录
        for img_path, src_set in all_images:
            try:
                # 复制图像到临时目录
                temp_img_path = temp_images_dir / img_path.name
                shutil.copy2(str(img_path), str(temp_img_path))

                # 复制标签到临时目录（文件名与图像严格匹配，仅替换后缀为 .txt）
                src_label_dir = img_path.parent.parent / "labels"
                label_name = img_path.name.replace(img_path.suffix, '.txt')
                label_path = src_label_dir / label_name
                if label_path.exists():
                    temp_label_path = temp_labels_dir / label_name
                    shutil.copy2(str(label_path), str(temp_label_path))
                else:
                    # 兼容大小写不敏感的标签文件（如 .TXT）
                    for ext in [".txt", ".TXT"]:
                        label_path = (src_label_dir / img_path.stem).with_suffix(ext)
                        if label_path.exists():
                            temp_label_path = temp_labels_dir / label_path.name
                            shutil.copy2(str(label_path), str(temp_label_path))
                            break
                    else:
                        print(f"Warning: Label file not found: {src_label_dir / label_name}")
            except Exception as e:
                print(f"Error copying to temp directory: {e}")

        # 检查临时目录中的文件是否完整
        temp_files = list(temp_images_dir.glob("*.*"))
        temp_labels = list(temp_labels_dir.glob("*.*"))
        if not temp_files:
            print("Error: No files found in temp directory. Aborting redistribution.")
            return {"train": 0, "val": 0, "test": 0, "total": 0}

        # 清空现有目录（仅在临时文件验证通过后执行）
        for dir_path in [train_images_dir, train_labels_dir, val_images_dir, val_labels_dir, test_images_dir, test_labels_dir]:
            try:
                for file_path in dir_path.glob("*.*"):
                    if file_path.is_file():
                        os.remove(file_path)
            except Exception as e:
                print(f"Error clearing directory {dir_path}: {e}")
                # 不中断流程，但记录错误

        # 从临时目录移动图像和标签到目标目录
        train_success = 0
        for img_path, _ in new_train:
            temp_img_path = temp_images_dir / img_path.name
            if temp_img_path.exists():
                try:
                    # 复制图像
                    target_img_path = train_images_dir / img_path.name
                    shutil.copy2(str(temp_img_path), str(target_img_path))

                    # 复制标签（使用原始文件名匹配）
                    label_name = img_path.name.replace(img_path.suffix, '.txt')
                    temp_label_path = temp_labels_dir / label_name
                    if temp_label_path.exists():
                        target_label_path = train_labels_dir / label_name
                        shutil.copy2(str(temp_label_path), str(target_label_path))
                    else:
                        print(f"Warning: Label file not found in temp directory: {temp_label_path}")

                    train_success += 1
                except Exception as e:
                    print(f"Error moving to train set: {e}")

        val_success = 0
        for img_path, _ in new_val:
            temp_img_path = temp_images_dir / img_path.name
            if temp_img_path.exists():
                try:
                    # 复制图像
                    target_img_path = val_images_dir / img_path.name
                    shutil.copy2(str(temp_img_path), str(target_img_path))

                    # 复制标签（使用原始文件名匹配）
                    label_name = img_path.name.replace(img_path.suffix, '.txt')
                    temp_label_path = temp_labels_dir / label_name
                    if temp_label_path.exists():
                        target_label_path = val_labels_dir / label_name
                        shutil.copy2(str(temp_label_path), str(target_label_path))
                        print(f"Copied label: {temp_label_path} -> {target_label_path}")
                    else:
                        print(f"Warning: Label file not found in temp directory: {temp_label_path}")

                    val_success += 1
                except Exception as e:
                    print(f"Error moving to val set: {e}")

        test_success = 0
        for img_path, _ in new_test:
            temp_img_path = temp_images_dir / img_path.name
            if temp_img_path.exists():
                try:
                    # 复制图像
                    target_img_path = test_images_dir / img_path.name
                    shutil.copy2(str(temp_img_path), str(target_img_path))

                    # 复制标签（使用原始文件名匹配）
                    label_name = img_path.name.replace(img_path.suffix, '.txt')
                    temp_label_path = temp_labels_dir / label_name
                    if temp_label_path.exists():
                        target_label_path = test_labels_dir / label_name
                        shutil.copy2(str(temp_label_path), str(target_label_path))
                        print(f"Copied label to test: {temp_label_path} -> {target_label_path}")
                    else:
                        print(f"Warning: Test label file not found in temp directory: {temp_label_path}")

                    test_success += 1
                except Exception as e:
                    print(f"Error moving to test set: {e}")

        print(f"Successfully redistributed: {train_success} to train, {val_success} to val, {test_success} to test")

        # 删除临时目录
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error removing temp directory: {e}")

    # 更新dataset.yaml
    update_dataset_yaml(dataset_dir)

    # 获取分割后的图像数量
    final_train_images = get_image_files(train_images_dir)
    final_val_images = get_image_files(val_images_dir)
    final_test_images = get_image_files(test_images_dir)

    # 返回分割结果
    result = {
        "train": len(final_train_images),
        "val": len(final_val_images),
        "test": len(final_test_images),
        "total": len(final_train_images) + len(final_val_images) + len(final_test_images)
    }

    print(f"Final dataset split result: {result}")
    return result

def update_dataset_yaml(dataset_dir: Path):
    """更新dataset.yaml文件，添加test路径"""
    yaml_path = dataset_dir / "dataset.yaml"
    if not yaml_path.exists():
        return

    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 添加test路径
        data["test"] = "test/images"

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False)
    except Exception as e:
        print(f"Error updating dataset.yaml: {e}")

async def create_dataset(
    db: Session,
    name: str,
    description: Optional[str],
    file: UploadFile,
    file_id: Optional[str] = None,
    split_dataset_enabled: bool = False,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42
) -> Dataset:
    """
    Create a new dataset from an uploaded ZIP file
    """
    # Check if dataset with the same name already exists
    db_dataset = dataset.get_by_name(db, name=name)
    if db_dataset:
        if file_id:
            upload_manager.set_failed(file_id, "Dataset with this name already exists")
        raise HTTPException(
            status_code=400,
            detail="Dataset with this name already exists",
        )

    # Generate unique ID for the dataset
    dataset_id = str(uuid.uuid4())
    dataset_dir = settings.DATASETS_DIR / dataset_id
    os.makedirs(dataset_dir, exist_ok=True)

    # Save the uploaded file
    upload_path = settings.UPLOADS_DIR / f"{dataset_id}.zip"

    # 如果提供了file_id，使用上传状态跟踪
    if file_id:
        # 更新状态为保存文件
        upload_manager.update_progress(file_id, 0)

        # 分块读取并写入文件，同时更新进度
        # 对于大文件，使用更大的块大小以提高性能
        chunk_size = 4 * 1024 * 1024  # 4MB chunks
        total_size = 0

        with open(upload_path, "wb") as buffer:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                buffer.write(chunk)
                total_size += len(chunk)
                upload_manager.update_progress(file_id, total_size)
    else:
        # 不使用状态跟踪，直接复制文件
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    try:
        # 更新状态为解压文件
        if file_id:
            upload_manager.set_extracting(file_id)

        # Extract the ZIP file
        # 使用更高效的解压方式，对大文件进行优化
        with zipfile.ZipFile(upload_path, 'r') as zip_ref:
            # 获取文件列表
            file_list = zip_ref.namelist()
            total_files = len(file_list)
            extracted_files = 0

            # 分批解压文件，每批100个文件
            batch_size = 100
            for i in range(0, total_files, batch_size):
                batch = file_list[i:i + batch_size]
                zip_ref.extractall(dataset_dir, members=batch)
                extracted_files += len(batch)

                # 更新解压进度
                if file_id and total_files > 0:
                    progress = min(99, int((extracted_files / total_files) * 100))
                    # 更新状态消息
                    upload_manager.set_extracting(file_id)
                    # 更新进度条
                    upload_manager.update_progress(file_id, int(file.size * (progress / 100)))

 
        # --- 新增的核心逻辑：处理冗余的顶层目录 ---
        print(f"Post-extraction check for redundant top-level directory in {dataset_dir}")

        # 获取 dataset_dir 下的所有顶级条目
        extracted_items_at_root = list(dataset_dir.iterdir())

        # 过滤出可能是冗余目录的项：
        # 1. 必须是目录
        # 2. 不是预期的 'train', 'val', 'test' 目录名（这些是数据集的核心结构）
        # 3. 排除 '__MACOSX' 这种操作系统生成的隐藏目录
        potential_redundant_dirs = [
            item for item in extracted_items_at_root
            if item.is_dir()
            and item.name not in ["train", "val", "test", "test_images", "train_images", "val_images"] # 额外排除一些常见的图片目录名
            and item.name != "__MACOSX"
            and not item.name.startswith(".") # 排除其他隐藏目录
        ]

        print(len(potential_redundant_dirs))
        # 如果正好有一个潜在的冗余目录被检测到
        if len(potential_redundant_dirs) == 1:
            redundant_top_dir = potential_redundant_dirs[0]
            print(f"Found a single potential redundant top-level directory: {redundant_top_dir.name}. Attempting to move its contents up.")

            # 为了避免文件覆盖冲突（例如 dataset_dir 根部和 redundant_top_dir 内部都有 classes.txt）
            # 我们先将 redundant_top_dir 中的内容移动到 dataset_dir 的临时子目录
            # 然后清空 dataset_dir 根部，再将临时子目录内容移回 dataset_dir
            # 这种方法更安全，确保嵌套层的数据优先
            temp_move_dir = dataset_dir / f"temp_move_{uuid.uuid4().hex}"
            os.makedirs(temp_move_dir)

            # 将 redundant_top_dir 的所有内容移动到 temp_move_dir
            for item_in_redundant in redundant_top_dir.iterdir():
                try:
                    shutil.move(str(item_in_redundant), str(temp_move_dir / item_in_redundant.name))
                    print(f"Moved '{item_in_redundant.name}' from '{redundant_top_dir.name}' to temp.")
                except Exception as e:
                    print(f"Error moving '{item_in_redundant.name}' from redundant dir to temp: {e}")

            # 删除空的冗余目录
            try:
                shutil.rmtree(redundant_top_dir)
                print(f"Removed empty redundant directory: {redundant_top_dir.name}")
            except Exception as e:
                print(f"Warning: Could not remove redundant directory {redundant_top_dir}: {e}")

            # 清空 dataset_dir 根部可能存在的旧文件和目录（除了 temp_move_dir）
            for item in dataset_dir.iterdir():
                if item != temp_move_dir:
                    if item.is_file():
                        try:
                        	os.remove(item)
                        	print(f"Removed old root file: {item.name}")
                        except Exception as e:
                            print(f"Warning: Could not remove old root file {item.name}: {e}")
                    elif item.is_dir():
                        try:
                            shutil.rmtree(item)
                            print(f"Removed old root directory: {item.name}")
                        except Exception as e:
                            print(f"Warning: Could not remove old root directory {item.name}: {e}")

            # 将 temp_move_dir 中的内容移动回 dataset_dir 根部
            for item_in_temp in temp_move_dir.iterdir():
                try:
                    shutil.move(str(item_in_temp), str(dataset_dir / item_in_temp.name))
                    print(f"Moved '{item_in_temp.name}' from temp to dataset_dir root.")
                except Exception as e:
                    print(f"Error moving '{item_in_temp.name}' from temp to root: {e}")

            # 删除临时目录
            try:
                shutil.rmtree(temp_move_dir)
                print(f"Removed temporary directory: {temp_move_dir.name}")
            except Exception as e:
                print(f"Warning: Could not remove temporary directory {temp_move_dir}: {e}")

        else:
            print(f"No single redundant top-level directory detected after extraction. Extracted items at root: {[item.name for item in extracted_items_at_root]}")
        # --- 核心逻辑结束 ---


        # 更新状态为验证数据集
        if file_id:
            upload_manager.set_validating(file_id)


        # 处理数据集中的文件名（重命名过长或包含特殊字符的文件）
        try:
            renamed_files = process_dataset_files(dataset_dir)
            if renamed_files:
                print(f"Renamed {len(renamed_files)} files with problematic filenames")
        except Exception as e:
            print(f"Warning: Error processing filenames: {str(e)}")
            # 继续处理，不中断流程

        # 验证数据集结构
        train_images_dir = dataset_dir / "train" / "images"
        val_images_dir = dataset_dir / "val" / "images"
        classes_file = dataset_dir / "classes.txt"

        # 检查目录结构
        if not train_images_dir.exists():
            # 尝试创建目录
            os.makedirs(train_images_dir, exist_ok=True)
            print(f"Created missing directory: {train_images_dir}")

        if not val_images_dir.exists():
            # 尝试创建目录
            os.makedirs(val_images_dir, exist_ok=True)
            print(f"Created missing directory: {val_images_dir}")

        # 如果缺少classes.txt文件，则创建一个默认的
        if not classes_file.exists():
            # 尝试从数据集中推断类别
            print(f"Missing classes.txt file, creating a default one")
            with open(classes_file, "w", encoding="utf-8") as f:
                f.write("object\n")  # 默认类别

        # Read classes
        try:
            # 尝试使用UTF-8编码读取
            with open(classes_file, "r", encoding="utf-8") as f:
                classes = [line.strip() for line in f.readlines()]
        except UnicodeDecodeError:
            # 如果失败，尝试使用其他编码
            try:
                with open(classes_file, "r", encoding="latin-1") as f:
                    classes = [line.strip() for line in f.readlines()]
            except Exception as e:
                # 如果还是失败，创建一个新的文件
                print(f"Error reading classes.txt: {e}, creating a new one")
                with open(classes_file, "w", encoding="utf-8") as f:
                    f.write("object\n")  # 默认类别
                classes = ["object"]

        # Count images - 使用异常处理来确保即使某些文件有问题也能继续
        train_images = []
        val_images = []
        try:
            train_images = list(train_images_dir.glob("*.*"))
        except Exception as e:
            print(f"Warning: Error listing training images: {str(e)}")

        try:
            val_images = list(val_images_dir.glob("*.*"))
        except Exception as e:
            print(f"Warning: Error listing validation images: {str(e)}")

        image_count = len(train_images) + len(val_images)

        # 如果没有找到图像，这可能是一个问题，但我们不会中断处理
        if image_count == 0:
            print("Warning: No images found in the dataset. This might indicate a problem with the dataset structure.")

        # 如果启用自动分割，执行分割
        if split_dataset_enabled:
            # 检查比例总和是否为1
            if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.001:
                raise HTTPException(
                    status_code=400,
                    detail="分割比例总和必须为1.0",
                )

            split_result = split_dataset(
                dataset_dir,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
                test_ratio=test_ratio,
                random_seed=random_seed,
                mode="redistribute"  # 对新导入的数据集重新分配所有图像
            )

            # 更新图像计数
            image_count = split_result["total"]
        else:
            # 处理数据集结构，确保目录存在
            structure_info = process_dataset_structure(dataset_dir)
            image_count = structure_info["total_count"]

        # Create dataset.yaml file
        dataset_yaml = {
            "path": str(dataset_dir),
            "train": "train/images",
            "val": "val/images",
            "test": "test/images",  # 添加test路径
            "nc": len(classes),
            "names": classes
        }

        try:
            with open(dataset_dir / "dataset.yaml", "w", encoding="utf-8") as f:
                import yaml
                yaml.dump(dataset_yaml, f, default_flow_style=False)
        except Exception as e:
            print(f"Error creating dataset.yaml: {e}")
            # 如果失败，尝试使用其他方式
            with open(dataset_dir / "dataset.yaml", "w", encoding="latin-1") as f:
                f.write(f"path: {str(dataset_dir)}\n")
                f.write("train: train/images\n")
                f.write("val: val/images\n")
                f.write(f"nc: {len(classes)}\n")
                f.write(f"names: {str(classes)}\n")

        # 创建数据库记录
        # 注意：我们不能直接使用DatasetCreate，因为它不包含path字段
        # 我们需要直接创建一个完整的数据库记录

        # 创建数据集对象
        obj_in_data = {
            "name": name,
            "description": description or "",
            "path": str(dataset_dir),  # 设置path字段
            "classes": classes,
            "image_count": image_count,
            "status": "available"
        }

        # 创建数据库记录
        db_dataset = dataset.create_with_fields(db, obj_in=obj_in_data)

        # 更新上传状态为完成
        if file_id:
            upload_manager.set_completed(file_id, str(dataset_dir))

        return db_dataset

    except HTTPException as e:
        # 如果是我们抛出的HTTP异常，则直接重新抛出
        # Clean up in case of error
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir)
        if upload_path.exists():
            os.remove(upload_path)

        # 更新上传状态为失败
        if file_id:
            upload_manager.set_failed(file_id, str(e.detail))

        # 添加更详细的错误信息
        raise HTTPException(
            status_code=e.status_code,
            detail=f"{e.detail}\n\n请确保上传的数据集符合以下结构:\n- train/images/: 训练图像目录\n- val/images/: 验证图像目录\n- classes.txt: 类别列表文件",
        )
    except UnicodeDecodeError as e:
        # 编码错误
        # Clean up in case of error
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir)
        if upload_path.exists():
            os.remove(upload_path)

        # 更新上传状态为失败
        if file_id:
            upload_manager.set_failed(file_id, f"编码错误: {str(e)}. 请确保所有文本文件使用UTF-8编码。")

        # 记录详细错误
        import traceback
        error_details = traceback.format_exc()
        print(f"Encoding error processing dataset: {str(e)}\n{error_details}")

        raise HTTPException(
            status_code=500,
            detail=f"Encoding error processing dataset: {str(e)}. Please ensure all text files are UTF-8 encoded.",
        )
    except Exception as e:
        # 其他异常
        # Clean up in case of error
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir)
        if upload_path.exists():
            os.remove(upload_path)

        # 记录详细错误
        import traceback
        error_details = traceback.format_exc()
        print(f"Error processing dataset: {str(e)}\n{error_details}")

        # 检查是否是文件名过长问题
        error_msg = str(e)
        error_detail = ""
        if "No such file or directory" in error_msg and len(error_msg) > 200:
            # 这可能是文件名过长问题
            error_detail = "数据集包含文件名过长或特殊字符的文件。请在上传前重命名您的文件。"

            # 更新上传状态为失败
            if file_id:
                upload_manager.set_failed(file_id, error_detail)

            raise HTTPException(
                status_code=500,
                detail=f"Error processing dataset: {error_detail}",
            )
        else:
            error_detail = f"处理数据集时出错: {str(e)}"

            # 更新上传状态为失败
            if file_id:
                upload_manager.set_failed(file_id, error_detail)

            raise HTTPException(
                status_code=500,
                detail=error_detail,
            )
    finally:
        # Remove the ZIP file
        if upload_path.exists():
            os.remove(upload_path)

def get_dataset(db: Session, dataset_id: str) -> Dataset:
    """
    Get a dataset by ID
    """
    db_dataset = dataset.get(db, id=dataset_id)
    if not db_dataset:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found",
        )
    return db_dataset

def get_datasets(db: Session, skip: int = 0, limit: int = 100) -> List[Dataset]:
    """
    Get all datasets
    """
    datasets_list = dataset.get_multi(db, skip=skip, limit=limit)

    # 添加训练集/验证集/测试集图像数量
    for ds in datasets_list:
        try:
            dataset_path = Path(ds.path)
            train_images_dir = dataset_path / "train" / "images"
            val_images_dir = dataset_path / "val" / "images"
            test_images_dir = dataset_path / "test" / "images"

            train_count = len(list(train_images_dir.glob("*.*"))) if train_images_dir.exists() else 0
            val_count = len(list(val_images_dir.glob("*.*"))) if val_images_dir.exists() else 0
            test_count = len(list(test_images_dir.glob("*.*"))) if test_images_dir.exists() else 0

            # 添加到数据集对象
            ds.train_count = train_count
            ds.val_count = val_count
            ds.test_count = test_count
        except Exception as e:
            print(f"Error counting images for dataset {ds.id}: {e}")
            ds.train_count = 0
            ds.val_count = 0
            ds.test_count = 0

    return datasets_list

def get_directory_info(directory_name: str) -> Dict[str, Any]:
    """
    获取指定目录的信息
    """
    # 确保导入目录存在
    if not IMPORT_DIR.exists():
        os.makedirs(IMPORT_DIR, exist_ok=True)
        raise HTTPException(
            status_code=404,
            detail=f"Import directory does not exist"
        )

    # 检查目录是否存在
    dir_path = IMPORT_DIR / directory_name
    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Directory '{directory_name}' not found"
        )

    return get_dataset_directory_info(dir_path)

def get_dataset_directory_info(dir_path: Path) -> Dict[str, Any]:
    """
    获取数据集目录的信息，可以是内部目录或外部目录
    """
    # 检查目录结构是否符合要求
    train_images_dir = dir_path / "train" / "images"
    val_images_dir = dir_path / "val" / "images"
    test_images_dir = dir_path / "test" / "images"
    classes_file = dir_path / "classes.txt"

    # 计算图像数量
    train_images_count = 0
    val_images_count = 0
    test_images_count = 0

    if train_images_dir.exists():
        # 使用更精确的方式计算图像数量
        image_files = [f for f in train_images_dir.glob("*.*")
                      if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]
        train_images_count = len(image_files)
        print(f"Found {train_images_count} images in train directory")

    if val_images_dir.exists():
        image_files = [f for f in val_images_dir.glob("*.*")
                      if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]
        val_images_count = len(image_files)
        print(f"Found {val_images_count} images in val directory")

    if test_images_dir.exists():
        image_files = [f for f in test_images_dir.glob("*.*")
                      if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]
        test_images_count = len(image_files)
        print(f"Found {test_images_count} images in test directory")

    # 获取类别信息
    classes = []
    if classes_file.exists():
        try:
            with open(classes_file, "r", encoding="utf-8") as f:
                classes = [line.strip() for line in f.readlines() if line.strip()]
        except UnicodeDecodeError:
            try:
                with open(classes_file, "r", encoding="latin-1") as f:
                    classes = [line.strip() for line in f.readlines() if line.strip()]
            except Exception:
                classes = ["object"]

    # 返回目录信息
    return {
        "name": dir_path.name,
        "path": str(dir_path),
        "train_images": train_images_count,
        "val_images": val_images_count,
        "test_images": test_images_count,
        "total_images": train_images_count + val_images_count + test_images_count,
        "classes": classes,
        "classes_count": len(classes),
        "valid_structure": train_images_dir.exists() and val_images_dir.exists()
    }

def browse_filesystem(path: Optional[str] = None) -> Dict[str, Any]:
    """
    浏览本地文件系统
    """
    # 如果没有提供路径，返回可用的根目录
    if not path:
        # 过滤出实际存在的根目录
        available_roots = []
        for root in ALLOWED_ROOTS:
            try:
                if root.exists():
                    available_roots.append({
                        "name": str(root),
                        "path": str(root),
                        "is_dir": True
                    })
            except Exception as e:
                print(f"Error checking root {root}: {e}")

        return {
            "current_path": "",
            "parent_path": "",
            "items": available_roots
        }

    # 将路径转换为Path对象
    try:
        path_obj = Path(path)
        # 规范化路径，解决相对路径问题
        path_obj = path_obj.resolve()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid path: {str(e)}"
        )

    # 检查路径是否存在
    if not path_obj.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Path '{path}' does not exist"
        )

    # 检查路径是否是目录
    if not path_obj.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path '{path}' is not a directory"
        )

    # 检查路径是否在允许的范围内
    allowed = False
    for root in ALLOWED_ROOTS:
        try:
            # 检查path_obj是否是root或者是root的子目录
            if str(path_obj).startswith(str(root)):
                allowed = True
                break
        except Exception:
            continue

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Access to path '{path}' is not allowed"
        )

    # 获取父目录
    parent_path = str(path_obj.parent) if path_obj.parent != path_obj else ""

    # 获取目录内容
    items = []
    try:
        # 首先添加目录
        for item in path_obj.iterdir():
            if item.is_dir():
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": True
                })

        # 按名称排序
        items.sort(key=lambda x: x["name"])
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing directory: {str(e)}"
        )

    return {
        "current_path": str(path_obj),
        "parent_path": parent_path,
        "items": items
    }

def validate_external_directory(path: str) -> Dict[str, Any]:
    """
    验证外部数据集目录是否有效
    简化版：只检查目录是否存在，不做其他限制
    """
    try:
        path_obj = Path(path)
        # 规范化路径，解决相对路径问题
        path_obj = path_obj.resolve()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid path: {str(e)}"
        )

    # 检查路径是否存在
    if not path_obj.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Path '{path}' does not exist"
        )

    # 检查路径是否是目录
    if not path_obj.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path '{path}' is not a directory"
        )

    # 获取目录信息（仅供参考）
    dir_info = {
        "path": str(path_obj),
        "train_images": 0,
        "val_images": 0,
        "test_images": 0,
        "total_images": 0,
        "classes_count": 0,
        "classes": ["object"]
    }

    # 检查目录结构（仅供参考）
    train_images_dir = path_obj / "train" / "images"
    val_images_dir = path_obj / "val" / "images"
    test_images_dir = path_obj / "test" / "images"
    classes_file = path_obj / "classes.txt"

    # 如果存在这些目录，尝试获取信息
    if train_images_dir.exists() or val_images_dir.exists() or test_images_dir.exists():
        try:
            dir_info = get_dataset_directory_info(path_obj)
        except Exception as e:
            print(f"Error getting directory info: {e}")

    # 返回验证结果（始终返回有效）
    return {
        "valid": True,  # 始终返回有效
        "missing_dirs": [],
        "has_classes_file": classes_file.exists(),
        "directory_info": dir_info,
        "can_be_fixed": True,
        "message": "Directory is valid"
    }

def get_available_local_datasets() -> List[Dict[str, Any]]:
    """
    获取可用的本地数据集目录列表
    注意: 不再验证目录内容，只返回目录列表，以提高启动速度
    """
    available_datasets = []

    # 确保导入目录存在
    if not IMPORT_DIR.exists():
        os.makedirs(IMPORT_DIR, exist_ok=True)
        return available_datasets

    # 遍历导入目录中的子目录，只返回目录名称和路径，不验证内容
    for dir_path in IMPORT_DIR.iterdir():
        if dir_path.is_dir() and dir_path.name != '__pycache__':
            try:
                # 创建简化的目录信息，不验证内容
                # 但保持与前端期望的数据结构一致
                dataset_info = {
                    "name": dir_path.name,
                    "path": str(dir_path),
                    "train_images": 0,
                    "val_images": 0,
                    "test_images": 0,
                    "total_images": 0,
                    "classes": [],
                    "classes_count": 0,
                    "valid_structure": True  # 默认认为有效，在需要时才验证
                }
                available_datasets.append(dataset_info)
            except Exception as e:
                print(f"Error processing directory {dir_path.name}: {e}")
                # 继续处理下一个目录

    return available_datasets

def register_external_dataset(
    db: Session,
    name: str,
    description: Optional[str],
    external_path: str,
    split_dataset_enabled: bool = False,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42
) -> Dataset:
    """
    注册外部数据集目录
    简化版：直接注册外部目录，不做验证
    """
    # 检查数据集名称是否已存在
    db_dataset = dataset.get_by_name(db, name=name)
    if db_dataset:
        raise HTTPException(
            status_code=400,
            detail="Dataset with this name already exists",
        )

    # 简单验证路径是否存在且是目录
    path_obj = Path(external_path)
    if not path_obj.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Path '{external_path}' does not exist"
        )
    if not path_obj.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path '{external_path}' is not a directory"
        )

    # 创建必要的目录结构
    train_dir = path_obj / "train" / "images"
    val_dir = path_obj / "val" / "images"
    test_dir = path_obj / "test" / "images"

    os.makedirs(train_dir, exist_ok=True)
    os.makedirs(val_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)
    os.makedirs(path_obj / "train" / "labels", exist_ok=True)
    os.makedirs(path_obj / "val" / "labels", exist_ok=True)
    os.makedirs(path_obj / "test" / "labels", exist_ok=True)

    # 创建默认的classes.txt文件（如果不存在）
    classes_file = path_obj / "classes.txt"
    classes = ["object"]
    if classes_file.exists():
        try:
            with open(classes_file, "r", encoding="utf-8") as f:
                file_classes = [line.strip() for line in f.readlines() if line.strip()]
                if file_classes:
                    classes = file_classes
        except Exception:
            pass

    # 确保类别文件存在
    with open(classes_file, "w", encoding="utf-8") as f:
        for cls in classes:
            f.write(f"{cls}\n")

    # 创建dataset.yaml文件
    dataset_yaml = {
        "path": str(path_obj),
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "nc": len(classes),
        "names": classes
    }

    try:
        with open(path_obj / "dataset.yaml", "w", encoding="utf-8") as f:
            import yaml
            yaml.dump(dataset_yaml, f, default_flow_style=False)
    except Exception as e:
        print(f"Error creating dataset.yaml: {e}")
        with open(path_obj / "dataset.yaml", "w", encoding="utf-8") as f:
            f.write(f"path: {str(path_obj)}\n")
            f.write("train: train/images\n")
            f.write("val: val/images\n")
            f.write("test: test/images\n")
            f.write(f"nc: {len(classes)}\n")
            f.write(f"names: {str(classes)}\n")

    # 创建数据库记录
    obj_in_data = {
        "name": name,
        "description": description or "",
        "path": str(path_obj),
        "classes": classes,
        "image_count": 0,  # 初始化为0，在训练时会自动计算
        "status": "available",
        "is_external": True  # 标记为外部数据集
    }

    # 创建数据库记录
    db_dataset = dataset.create_with_fields(db, obj_in=obj_in_data)

    return db_dataset

def import_local_dataset(
    db: Session,
    name: str,
    description: Optional[str],
    directory_name: str,
    split_dataset_enabled: bool = False,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42
) -> Dataset:
    """
    从本地目录导入数据集
    修改后的版本：不再复制数据集文件，而是直接引用datasets_import目录中的原始数据集
    """
    # 检查数据集名称是否已存在
    db_dataset = dataset.get_by_name(db, name=name)
    if db_dataset:
        raise HTTPException(
            status_code=400,
            detail="Dataset with this name already exists",
        )

    # 检查源目录是否存在
    source_dir = IMPORT_DIR / directory_name
    if not source_dir.exists() or not source_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Directory '{directory_name}' not found in import directory",
        )

    try:
        # 获取绝对路径
        source_dir_abs = source_dir.resolve()

        # 读取classes.txt文件
        classes_file = source_dir / "classes.txt"
        classes = ["object"]
        if classes_file.exists():
            try:
                with open(classes_file, "r", encoding="utf-8") as f:
                    file_classes = [line.strip() for line in f.readlines() if line.strip()]
                    if file_classes:
                        classes = file_classes
            except Exception as e:
                print(f"Error reading classes file: {e}")
        else:
            # 如果类别文件不存在，创建一个默认的
            with open(classes_file, "w", encoding="utf-8") as f:
                f.write("object\n")
                classes = ["object"]

        # 如果启用自动分割，执行分割
        if split_dataset_enabled:
            # 检查比例总和是否为1
            if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.001:
                raise HTTPException(
                    status_code=400,
                    detail="分割比例总和必须为1.0",
                )

            split_result = split_dataset(
                source_dir,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
                test_ratio=test_ratio,
                random_seed=random_seed,
                mode="redistribute"  # 对导入的数据集重新分配所有图像
            )

            # 获取图像计数
            train_images_count = split_result["train"]
            val_images_count = split_result["val"]
            test_images_count = split_result["test"]
            total_images_count = split_result["total"]

            print(f"After splitting, counted images: train={train_images_count}, val={val_images_count}, test={test_images_count}, total={total_images_count}")
            image_count = total_images_count
        else:
            # 手动计算图像数量
            train_dir = source_dir / "train" / "images"
            val_dir = source_dir / "val" / "images"
            test_dir = source_dir / "test" / "images"

            train_images_count = len([f for f in train_dir.glob("*.*")
                                    if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]) if train_dir.exists() else 0
            val_images_count = len([f for f in val_dir.glob("*.*")
                                  if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]) if val_dir.exists() else 0
            test_images_count = len([f for f in test_dir.glob("*.*")
                                   if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]) if test_dir.exists() else 0
            total_images_count = train_images_count + val_images_count + test_images_count
            image_count = total_images_count

        # 检查是否存在dataset.yaml文件
        yaml_file = source_dir / "dataset.yaml"
        yaml_data = None

        # 获取绝对路径
        source_dir_abs = source_dir.resolve()

        if yaml_file.exists():
            # 如果存在，读取并验证
            try:
                import yaml
                with open(yaml_file, "r", encoding="utf-8") as f:
                    yaml_data = yaml.safe_load(f)
                print(f"Found existing dataset.yaml: {yaml_data}")

                # 验证yaml文件是否包含必要的字段
                required_fields = ["path", "train", "val", "nc", "names"]
                missing_fields = [field for field in required_fields if field not in yaml_data]

                if missing_fields:
                    print(f"Dataset.yaml is missing required fields: {missing_fields}")
                    yaml_data = None  # 强制重新生成
                elif yaml_data["nc"] != len(classes) or set(yaml_data["names"]) != set(classes):
                    print("Dataset.yaml has incorrect class information, updating...")
                    yaml_data["nc"] = len(classes)
                    yaml_data["names"] = classes
            except Exception as e:
                print(f"Error reading dataset.yaml: {e}")
                yaml_data = None  # 如果读取出错，重新生成

        # 如果需要，创建或更新dataset.yaml文件
        if yaml_data is None:
            # 创建新的dataset.yaml文件
            yaml_data = {
                "path": str(source_dir_abs),  # 使用绝对路径
                "train": str(source_dir_abs / "train" / "images"),  # 使用完整路径
                "val": str(source_dir_abs / "val" / "images"),      # 使用完整路径
                "test": str(source_dir_abs / "test" / "images"),    # 使用完整路径
                "nc": len(classes),
                "names": classes
            }

            try:
                import yaml
                with open(yaml_file, "w", encoding="utf-8") as f:
                    yaml.dump(yaml_data, f, default_flow_style=False)
                print(f"Created new dataset.yaml file: {yaml_data}")
            except Exception as e:
                print(f"Error creating dataset.yaml: {e}")
                # 如果使用yaml库失败，尝试手动写入
                with open(yaml_file, "w", encoding="utf-8") as f:
                    f.write(f"path: {str(source_dir_abs)}\n")
                    f.write(f"train: {str(source_dir_abs / 'train' / 'images')}\n")
                    f.write(f"val: {str(source_dir_abs / 'val' / 'images')}\n")
                    f.write(f"test: {str(source_dir_abs / 'test' / 'images')}\n")
                    f.write(f"nc: {len(classes)}\n")
                    f.write(f"names: {str(classes)}\n")

        # 创建数据库记录
        obj_in_data = {
            "name": name,
            "description": description or "",
            "path": str(source_dir),  # 直接使用原始目录路径
            "classes": classes,
            "image_count": image_count,
            "status": "available",
            "is_external": True  # 标记为外部数据集
        }

        # 创建数据库记录
        db_dataset = dataset.create_with_fields(db, obj_in=obj_in_data)

        return db_dataset

    except Exception as e:
        # 记录详细错误
        import traceback
        error_details = traceback.format_exc()
        print(f"Error importing local dataset: {str(e)}\n{error_details}")

        raise HTTPException(
            status_code=500,
            detail=f"Error importing local dataset: {str(e)}",
        )

def delete_dataset(db: Session, dataset_id: str) -> Dataset:
    """
    Delete a dataset
    """
    db_dataset = dataset.get(db, id=dataset_id)
    if not db_dataset:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found",
        )

    # 检查是否有训练任务正在使用该数据集
    from app.crud import training_task

    # 查询使用该数据集的训练任务
    tasks = db.query(training_task.model).filter(training_task.model.dataset_id == dataset_id).all()

    if tasks:
        # 检查是否有正在运行的训练任务
        running_tasks = [task for task in tasks if task.status in ["running", "training", "downloading_model", "pending"]]

        if running_tasks:
            # 如果有正在运行的训练任务，拒绝删除
            task_ids = [str(task.id) for task in running_tasks]
            raise HTTPException(
                status_code=400,
                detail=f"无法删除数据集，因为有训练任务正在使用它: {', '.join(task_ids)}",
            )

        # 如果有已完成或失败的训练任务，列出它们
        completed_tasks = [task for task in tasks if task.status not in ["running", "training", "downloading_model", "pending"]]
        if completed_tasks:
            task_ids = [str(task.id) for task in completed_tasks]
            print(f"警告: 删除数据集 {dataset_id} 将影响以下训练任务: {', '.join(task_ids)}")

    # 检查是否是外部数据集
    is_external = getattr(db_dataset, 'is_external', False)

    # 如果不是外部数据集，则删除数据集目录
    if not is_external:
        dataset_dir = Path(db_dataset.path)
        if dataset_dir.exists():
            try:
                shutil.rmtree(dataset_dir)
                print(f"Deleted dataset directory: {dataset_dir}")
            except Exception as e:
                print(f"Warning: Could not delete dataset directory {dataset_dir}: {e}")
    else:
        print(f"Not deleting external dataset directory: {db_dataset.path}")

    # Delete dataset from database
    return dataset.remove(db, id=dataset_id)

# 我们使用browse-filesystem API来浏览文件系统

def import_external_dataset(
    db: Session,
    name: str,
    description: Optional[str],
    directory_path: str,
    split_dataset_enabled: bool = False,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42
) -> Dataset:
    """
    从外部目录导入数据集
    与register_external_dataset不同，此函数不会移动数据集文件，而是直接引用外部目录
    """
    # 检查数据集名称是否已存在
    db_dataset = dataset.get_by_name(db, name=name)
    if db_dataset:
        raise HTTPException(
            status_code=400,
            detail="Dataset with this name already exists",
        )

    # 验证路径是否存在且是目录
    path_obj = Path(directory_path)
    if not path_obj.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Path '{directory_path}' does not exist"
        )
    if not path_obj.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path '{directory_path}' is not a directory"
        )

    try:
        # 创建必要的目录结构（如果不存在）
        train_dir = path_obj / "train" / "images"
        val_dir = path_obj / "val" / "images"
        test_dir = path_obj / "test" / "images"

        os.makedirs(train_dir, exist_ok=True)
        os.makedirs(val_dir, exist_ok=True)
        os.makedirs(test_dir, exist_ok=True)
        os.makedirs(path_obj / "train" / "labels", exist_ok=True)
        os.makedirs(path_obj / "val" / "labels", exist_ok=True)
        os.makedirs(path_obj / "test" / "labels", exist_ok=True)

        # 创建或读取classes.txt文件
        classes_file = path_obj / "classes.txt"
        classes = ["object"]
        if classes_file.exists():
            try:
                with open(classes_file, "r", encoding="utf-8") as f:
                    file_classes = [line.strip() for line in f.readlines() if line.strip()]
                    if file_classes:
                        classes = file_classes
            except Exception as e:
                print(f"Error reading classes file: {e}")

        # 确保类别文件存在
        with open(classes_file, "w", encoding="utf-8") as f:
            for cls in classes:
                f.write(f"{cls}\n")

        # 如果启用自动分割，执行分割
        if split_dataset_enabled:
            # 检查比例总和是否为1
            if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.001:
                raise HTTPException(
                    status_code=400,
                    detail="分割比例总和必须为1.0",
                )

            split_result = split_dataset(
                path_obj,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
                test_ratio=test_ratio,
                random_seed=random_seed,
                mode="redistribute"  # 对导入的数据集重新分配所有图像
            )

            # 获取图像计数
            train_images_count = split_result["train"]
            val_images_count = split_result["val"]
            test_images_count = split_result["test"]
            total_images_count = split_result["total"]

            print(f"After splitting, counted images: train={train_images_count}, val={val_images_count}, test={test_images_count}, total={total_images_count}")
            image_count = total_images_count
        else:
            # 手动计算图像数量
            train_images_count = len([f for f in train_dir.glob("*.*")
                                    if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]) if train_dir.exists() else 0
            val_images_count = len([f for f in val_dir.glob("*.*")
                                  if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]) if val_dir.exists() else 0
            test_images_count = len([f for f in test_dir.glob("*.*")
                                   if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]) if test_dir.exists() else 0
            total_images_count = train_images_count + val_images_count + test_images_count
            image_count = total_images_count

        # 检查是否存在dataset.yaml文件
        yaml_file = path_obj / "dataset.yaml"
        yaml_data = None

        # 获取绝对路径
        path_obj_abs = path_obj.resolve()

        if yaml_file.exists():
            # 如果存在，读取并验证
            try:
                import yaml
                with open(yaml_file, "r", encoding="utf-8") as f:
                    yaml_data = yaml.safe_load(f)
                print(f"Found existing dataset.yaml: {yaml_data}")

                # 验证yaml文件是否包含必要的字段
                required_fields = ["path", "train", "val", "nc", "names"]
                missing_fields = [field for field in required_fields if field not in yaml_data]

                if missing_fields:
                    print(f"Dataset.yaml is missing required fields: {missing_fields}")
                    yaml_data = None  # 强制重新生成
                elif yaml_data["nc"] != len(classes) or set(yaml_data["names"]) != set(classes):
                    print("Dataset.yaml has incorrect class information, updating...")
                    yaml_data["nc"] = len(classes)
                    yaml_data["names"] = classes
            except Exception as e:
                print(f"Error reading dataset.yaml: {e}")
                yaml_data = None  # 如果读取出错，重新生成

        # 如果需要，创建或更新dataset.yaml文件
        if yaml_data is None:
            # 创建新的dataset.yaml文件
            yaml_data = {
                "path": str(path_obj_abs),  # 使用绝对路径
                "train": str(path_obj_abs / "train" / "images"),  # 使用完整路径
                "val": str(path_obj_abs / "val" / "images"),      # 使用完整路径
                "test": str(path_obj_abs / "test" / "images"),    # 使用完整路径
                "nc": len(classes),
                "names": classes
            }

            try:
                import yaml
                with open(yaml_file, "w", encoding="utf-8") as f:
                    yaml.dump(yaml_data, f, default_flow_style=False)
                print(f"Created new dataset.yaml file: {yaml_data}")
            except Exception as e:
                print(f"Error creating dataset.yaml: {e}")
                # 如果使用yaml库失败，尝试手动写入
                with open(yaml_file, "w", encoding="utf-8") as f:
                    f.write(f"path: {str(path_obj_abs)}\n")
                    f.write(f"train: {str(path_obj_abs / 'train' / 'images')}\n")
                    f.write(f"val: {str(path_obj_abs / 'val' / 'images')}\n")
                    f.write(f"test: {str(path_obj_abs / 'test' / 'images')}\n")
                    f.write(f"nc: {len(classes)}\n")
                    f.write(f"names: {str(classes)}\n")

        # 创建数据库记录
        obj_in_data = {
            "name": name,
            "description": description or "",
            "path": str(path_obj),  # 直接使用原始目录路径
            "classes": classes,
            "image_count": image_count,
            "status": "available",
            "is_external": True  # 标记为外部数据集
        }

        # 创建数据库记录
        db_dataset = dataset.create_with_fields(db, obj_in=obj_in_data)

        return db_dataset

    except Exception as e:
        # 记录详细错误
        import traceback
        error_details = traceback.format_exc()
        print(f"Error importing external dataset: {str(e)}\n{error_details}")

        raise HTTPException(
            status_code=500,
            detail=f"Error importing external dataset: {str(e)}",
        )

def convert_coco_to_yolo(json_path, output_dir, split_enabled=True, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15, random_seed=42):
    """
    将COCO格式的JSON文件转换为YOLO格式的标签文件

    Args:
        json_path: COCO格式JSON文件路径
        output_dir: 输出目录
        split_enabled: 是否分割数据集
        train_ratio: 训练集比例
        val_ratio: 验证集比例
        test_ratio: 测试集比例
        random_seed: 随机种子

    Returns:
        result: 转换结果
    """
    # 读取COCO格式的JSON文件
    with open(json_path, "r", encoding="utf-8") as f:
        coco_data = json.load(f)

    # 验证COCO格式
    if "images" not in coco_data or "annotations" not in coco_data or "categories" not in coco_data:
        raise ValueError("无效的COCO格式JSON文件，缺少必要的字段")

    # 创建类别ID到索引的映射
    class_mapping = {}
    classes = []
    for i, category in enumerate(coco_data["categories"]):
        class_mapping[category["id"]] = i
        classes.append(category["name"])

    # 创建图像ID到文件名的映射（处理带有路径的文件名）
    image_id_to_filename = {}
    for image in coco_data["images"]:
        # 提取文件名（去除路径部分）
        file_name = image["file_name"]
        # 如果文件名包含路径分隔符，只保留文件名部分
        if '/' in file_name or '\\' in file_name:
            file_name = os.path.basename(file_name)
        image_id_to_filename[image["id"]] = file_name

    # 创建图像ID到尺寸的映射
    image_id_to_size = {image["id"]: (image["width"], image["height"]) for image in coco_data["images"]}

    # 按图像ID分组标注
    annotations_by_image = {}
    for annotation in coco_data["annotations"]:
        image_id = annotation["image_id"]
        if image_id not in annotations_by_image:
            annotations_by_image[image_id] = []
        annotations_by_image[image_id].append(annotation)

    # 获取所有图像ID
    image_ids = list(image_id_to_filename.keys())

    # 如果启用分割，则分割数据集
    if split_enabled:
        # 设置随机种子
        np.random.seed(random_seed)

        # 随机打乱图像ID
        np.random.shuffle(image_ids)

        # 计算分割点
        train_end = int(len(image_ids) * train_ratio)
        val_end = train_end + int(len(image_ids) * val_ratio)

        # 分割数据集
        train_ids = set(image_ids[:train_end])
        val_ids = set(image_ids[train_end:val_end])
        test_ids = set(image_ids[val_end:])

        # 创建训练集、验证集和测试集的目录
        train_dir = os.path.join(output_dir, "train", "labels")
        val_dir = os.path.join(output_dir, "val", "labels")
        test_dir = os.path.join(output_dir, "test", "labels")

        os.makedirs(train_dir, exist_ok=True)
        os.makedirs(val_dir, exist_ok=True)
        os.makedirs(test_dir, exist_ok=True)

        # 转换标注
        train_count = 0
        val_count = 0
        test_count = 0

        for image_id, annotations in annotations_by_image.items():
            # 获取图像文件名和尺寸
            filename = image_id_to_filename[image_id]
            width, height = image_id_to_size[image_id]

            # 提取文件名（不包含扩展名）
            base_filename = os.path.splitext(filename)[0]

            # 确定目标目录
            if image_id in train_ids:
                output_file = os.path.join(train_dir, f"{base_filename}.txt")
                train_count += 1
            elif image_id in val_ids:
                output_file = os.path.join(val_dir, f"{base_filename}.txt")
                val_count += 1
            elif image_id in test_ids:
                output_file = os.path.join(test_dir, f"{base_filename}.txt")
                test_count += 1
            else:
                continue  # 跳过未分配的图像

            # 创建YOLO格式的标注文件
            with open(output_file, "w") as f:
                for annotation in annotations:
                    # 获取类别索引
                    category_id = annotation["category_id"]
                    if category_id not in class_mapping:
                        continue
                    class_idx = class_mapping[category_id]

                    # 获取边界框坐标
                    bbox = annotation["bbox"]  # [x, y, width, height]

                    # 转换为YOLO格式（归一化的中心点坐标和宽高）
                    x_center = (bbox[0] + bbox[2] / 2) / width
                    y_center = (bbox[1] + bbox[3] / 2) / height
                    bbox_width = bbox[2] / width
                    bbox_height = bbox[3] / height

                    # 写入文件
                    f.write(f"{class_idx} {x_center:.6f} {y_center:.6f} {bbox_width:.6f} {bbox_height:.6f}\n")

        # 返回结果
        return {
            "classes": classes,
            "file_count": {
                "total": train_count + val_count + test_count,
                "train": train_count,
                "val": val_count,
                "test": test_count
            },
            "annotation_count": len(coco_data["annotations"])
        }
    else:
        # 不分割数据集，直接转换
        labels_dir = os.path.join(output_dir, "labels")
        os.makedirs(labels_dir, exist_ok=True)

        # 转换标注
        file_count = 0

        for image_id, annotations in annotations_by_image.items():
            # 获取图像文件名和尺寸
            filename = image_id_to_filename[image_id]
            width, height = image_id_to_size[image_id]

            # 提取文件名（不包含扩展名）
            base_filename = os.path.splitext(filename)[0]

            # 创建YOLO格式的标注文件
            output_file = os.path.join(labels_dir, f"{base_filename}.txt")

            with open(output_file, "w") as f:
                for annotation in annotations:
                    # 获取类别索引
                    category_id = annotation["category_id"]
                    if category_id not in class_mapping:
                        continue
                    class_idx = class_mapping[category_id]

                    # 获取边界框坐标
                    bbox = annotation["bbox"]  # [x, y, width, height]

                    # 转换为YOLO格式（归一化的中心点坐标和宽高）
                    x_center = (bbox[0] + bbox[2] / 2) / width
                    y_center = (bbox[1] + bbox[3] / 2) / height
                    bbox_width = bbox[2] / width
                    bbox_height = bbox[3] / height

                    # 写入文件
                    f.write(f"{class_idx} {x_center:.6f} {y_center:.6f} {bbox_width:.6f} {bbox_height:.6f}\n")

            file_count += 1

        # 返回结果
        return {
            "classes": classes,
            "file_count": {
                "total": file_count,
                "train": file_count,
                "val": 0,
                "test": 0
            },
            "annotation_count": len(coco_data["annotations"])
        }

def coco_to_yolo(coco_bbox, img_width, img_height):
    """
    将COCO格式的边界框转换为YOLO格式

    COCO格式: [x_min, y_min, width, height]
    YOLO格式: [x_center, y_center, width, height] (归一化到0-1)

    Args:
        coco_bbox: COCO格式的边界框 [x_min, y_min, width, height]
        img_width: 图像宽度
        img_height: 图像高度

    Returns:
        YOLO格式的边界框 [x_center, y_center, width, height]
    """
    x_min, y_min, width, height = coco_bbox

    # 计算中心点坐标
    x_center = x_min + width / 2
    y_center = y_min + height / 2

    # 归一化坐标
    x_center /= img_width
    y_center /= img_height
    width /= img_width
    height /= img_height

    return [x_center, y_center, width, height]

async def import_coco_dataset(
    db: Session,
    name: str,
    description: Optional[str],
    file: UploadFile,
    file_id: Optional[str] = None,
    split_dataset_enabled: bool = False,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42
) -> Dataset:
    """
    从COCO格式的JSON文件导入数据集

    Args:
        db: 数据库会话
        name: 数据集名称
        description: 数据集描述
        file: 上传的COCO JSON文件
        file_id: 上传文件ID（用于状态跟踪）
        split_dataset_enabled: 是否启用数据集分割
        train_ratio: 训练集比例
        val_ratio: 验证集比例
        test_ratio: 测试集比例
        random_seed: 随机种子

    Returns:
        Dataset: 创建的数据集对象
    """
    # 检查数据集名称是否已存在
    db_dataset = dataset.get_by_name(db, name=name)
    if db_dataset:
        if file_id:
            upload_manager.set_failed(file_id, "Dataset with this name already exists")
        raise HTTPException(
            status_code=400,
            detail="Dataset with this name already exists",
        )

    # 生成唯一ID
    dataset_id = str(uuid.uuid4())
    dataset_dir = settings.DATASETS_DIR / dataset_id
    os.makedirs(dataset_dir, exist_ok=True)

    # 创建必要的目录结构
    train_dir = dataset_dir / "train" / "images"
    val_dir = dataset_dir / "val" / "images"
    test_dir = dataset_dir / "test" / "images"
    train_labels_dir = dataset_dir / "train" / "labels"
    val_labels_dir = dataset_dir / "val" / "labels"
    test_labels_dir = dataset_dir / "test" / "labels"

    os.makedirs(train_dir, exist_ok=True)
    os.makedirs(val_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)
    os.makedirs(train_labels_dir, exist_ok=True)
    os.makedirs(val_labels_dir, exist_ok=True)
    os.makedirs(test_labels_dir, exist_ok=True)

    # 保存上传的JSON文件
    json_path = dataset_dir / "coco_annotations.json"

    try:
        # 读取JSON文件内容
        content = await file.read()

        # 保存JSON文件
        with open(json_path, "wb") as f:
            f.write(content)

        # 解析JSON文件
        coco_data = json.loads(content)

        # 验证COCO格式
        required_fields = ["images", "annotations", "categories"]
        for field in required_fields:
            if field not in coco_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid COCO format: missing '{field}' field"
                )

        # 提取类别信息
        categories = coco_data["categories"]
        classes = [category["name"] for category in sorted(categories, key=lambda x: x["id"])]

        # 创建类别ID到索引的映射
        category_id_to_index = {category["id"]: i for i, category in enumerate(sorted(categories, key=lambda x: x["id"]))}

        # 创建图像ID到文件名的映射（处理带有路径的文件名）
        image_id_to_filename = {}
        for image in coco_data["images"]:
            # 提取文件名（去除路径部分）
            file_name = image["file_name"]
            # 如果文件名包含路径分隔符，只保留文件名部分
            if '/' in file_name or '\\' in file_name:
                file_name = os.path.basename(file_name)
            image_id_to_filename[image["id"]] = file_name

        # 创建图像ID到尺寸的映射
        image_id_to_size = {image["id"]: (image["width"], image["height"]) for image in coco_data["images"]}

        # 创建图像ID到注释的映射
        image_id_to_annotations = {}
        for annotation in coco_data["annotations"]:
            image_id = annotation["image_id"]
            if image_id not in image_id_to_annotations:
                image_id_to_annotations[image_id] = []
            image_id_to_annotations[image_id].append(annotation)

        # 将图像分配到训练集、验证集和测试集
        all_image_ids = list(image_id_to_filename.keys())

        # 如果启用分割，则按比例分配
        if split_dataset_enabled:
            import random
            random.seed(random_seed)
            random.shuffle(all_image_ids)

            # 计算每个集合的图像数量
            total_images = len(all_image_ids)
            train_count = int(total_images * train_ratio)
            val_count = int(total_images * val_ratio)

            # 分配图像ID
            train_image_ids = all_image_ids[:train_count]
            val_image_ids = all_image_ids[train_count:train_count + val_count]
            test_image_ids = all_image_ids[train_count + val_count:]
        else:
            # 默认全部放入训练集
            train_image_ids = all_image_ids
            val_image_ids = []
            test_image_ids = []

        # 处理图像和标签
        for image_id in all_image_ids:
            # 获取图像文件名和尺寸
            filename = image_id_to_filename[image_id]
            img_width, img_height = image_id_to_size[image_id]

            # 确定目标目录
            if image_id in train_image_ids:
                target_img_dir = train_dir
                target_label_dir = train_labels_dir
            elif image_id in val_image_ids:
                target_img_dir = val_dir
                target_label_dir = val_labels_dir
            else:
                target_img_dir = test_dir
                target_label_dir = test_labels_dir

            # 创建YOLO格式的标签文件
            if image_id in image_id_to_annotations:
                annotations = image_id_to_annotations[image_id]

                # 创建标签文件
                label_path = target_label_dir / f"{Path(filename).stem}.txt"

                with open(label_path, "w") as f:
                    for annotation in annotations:
                        # 获取类别索引
                        category_id = annotation["category_id"]
                        class_index = category_id_to_index[category_id]

                        # 获取边界框
                        bbox = annotation["bbox"]

                        # 转换为YOLO格式
                        yolo_bbox = coco_to_yolo(bbox, img_width, img_height)

                        # 写入标签文件
                        f.write(f"{class_index} {yolo_bbox[0]:.6f} {yolo_bbox[1]:.6f} {yolo_bbox[2]:.6f} {yolo_bbox[3]:.6f}\n")

        # 创建classes.txt文件
        classes_file = dataset_dir / "classes.txt"
        with open(classes_file, "w", encoding="utf-8") as f:
            for cls in classes:
                f.write(f"{cls}\n")

        # 创建dataset.yaml文件
        dataset_yaml = {
            "path": str(dataset_dir),
            "train": "train/images",
            "val": "val/images",
            "test": "test/images",
            "nc": len(classes),
            "names": classes
        }

        try:
            import yaml
            with open(dataset_dir / "dataset.yaml", "w", encoding="utf-8") as f:
                yaml.dump(dataset_yaml, f, default_flow_style=False)
        except Exception as e:
            print(f"Error creating dataset.yaml: {e}")
            with open(dataset_dir / "dataset.yaml", "w", encoding="utf-8") as f:
                f.write(f"path: {str(dataset_dir)}\n")
                f.write("train: train/images\n")
                f.write("val: val/images\n")
                f.write("test: test/images\n")
                f.write(f"nc: {len(classes)}\n")
                f.write(f"names: {str(classes)}\n")

        # 创建数据库记录
        obj_in_data = {
            "name": name,
            "description": description or "",
            "path": str(dataset_dir),
            "classes": classes,
            "image_count": len(all_image_ids),
            "status": "available"
        }

        # 创建数据库记录
        db_dataset = dataset.create_with_fields(db, obj_in=obj_in_data)

        return db_dataset

    except Exception as e:
        # 清理临时文件
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir)

        # 记录详细错误
        import traceback
        error_details = traceback.format_exc()
        print(f"Error importing COCO dataset: {str(e)}\n{error_details}")

        raise HTTPException(
            status_code=500,
            detail=f"Error importing COCO dataset: {str(e)}",
        )

