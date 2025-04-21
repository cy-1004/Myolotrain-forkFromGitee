import os
import time
import uuid
import asyncio
import zipfile
import shutil
from typing import Dict, Optional, List, Any
from fastapi import UploadFile, HTTPException
from pathlib import Path

# 上传状态跟踪
class UploadStatus:
    def __init__(self, file_id: str, filename: str, total_size: int):
        self.file_id = file_id
        self.filename = filename
        self.total_size = total_size
        self.uploaded_size = 0
        self.upload_speed = 0  # 字节/秒
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.status = "uploading"  # uploading, extracting, validating, completed, failed
        self.progress = 0  # 0-100
        self.message = "上传中..."
        self.error = None
        self.result_path = None

    def update_progress(self, uploaded_size: int):
        """更新上传进度"""
        now = time.time()
        time_diff = now - self.last_update_time

        if time_diff > 0.5:  # 每0.5秒更新一次速度
            size_diff = uploaded_size - self.uploaded_size
            self.upload_speed = size_diff / time_diff if time_diff > 0 else 0
            self.last_update_time = now

        self.uploaded_size = uploaded_size
        if self.total_size > 0:
            # 对于大文件，使用更精确的进度计算
            # 保留两位小数以提供更平滑的进度更新
            progress_value = (self.uploaded_size / self.total_size) * 100
            # 如果进度接近100%但还未完成，保持在99%
            if progress_value >= 99.5 and progress_value < 100:
                self.progress = 99
            else:
                self.progress = min(99, int(progress_value))

    def set_extracting(self):
        """设置为解压状态"""
        self.status = "extracting"
        self.message = "解压文件中..."
        self.progress = 99  # 保持在99%，表示还有工作要做

    def set_validating(self):
        """设置为验证状态"""
        self.status = "validating"
        self.message = "验证数据集结构..."
        self.progress = 99  # 保持在99%

    def set_completed(self, result_path: str):
        """设置为完成状态"""
        self.status = "completed"
        self.message = "处理完成"
        self.progress = 100
        self.result_path = result_path

    def set_failed(self, error: str):
        """设置为失败状态"""
        self.status = "failed"
        self.message = "处理失败"
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        elapsed_time = time.time() - self.start_time
        estimated_time = 0

        if self.status == "uploading" and self.upload_speed > 0 and self.total_size > self.uploaded_size:
            estimated_time = (self.total_size - self.uploaded_size) / self.upload_speed

        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "total_size": self.total_size,
            "uploaded_size": self.uploaded_size,
            "upload_speed": self.upload_speed,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "elapsed_time": elapsed_time,
            "estimated_time": estimated_time,
            "result_path": self.result_path
        }


class UploadManager:
    def __init__(self):
        self.uploads: Dict[str, UploadStatus] = {}

    def create_upload(self, filename: str, total_size: int) -> str:
        """创建新的上传任务"""
        file_id = str(uuid.uuid4())
        self.uploads[file_id] = UploadStatus(file_id, filename, total_size)
        return file_id

    def get_status(self, file_id: str) -> Optional[Dict[str, Any]]:
        """获取上传状态"""
        if file_id in self.uploads:
            return self.uploads[file_id].to_dict()
        return None

    def update_progress(self, file_id: str, uploaded_size: int):
        """更新上传进度"""
        if file_id in self.uploads:
            self.uploads[file_id].update_progress(uploaded_size)

    def set_extracting(self, file_id: str):
        """设置为解压状态"""
        if file_id in self.uploads:
            self.uploads[file_id].set_extracting()

    def set_validating(self, file_id: str):
        """设置为验证状态"""
        if file_id in self.uploads:
            self.uploads[file_id].set_validating()

    def set_completed(self, file_id: str, result_path: str):
        """设置为完成状态"""
        if file_id in self.uploads:
            self.uploads[file_id].set_completed(result_path)

    def set_failed(self, file_id: str, error: str):
        """设置为失败状态"""
        if file_id in self.uploads:
            self.uploads[file_id].set_failed(error)

    def clean_old_uploads(self, max_age: int = 3600):
        """清理旧的上传记录（默认1小时）"""
        now = time.time()
        to_remove = []

        for file_id, status in self.uploads.items():
            if now - status.start_time > max_age:
                to_remove.append(file_id)

        for file_id in to_remove:
            del self.uploads[file_id]


# 全局上传管理器实例
upload_manager = UploadManager()


# 定期清理旧的上传记录
async def cleanup_task():
    while True:
        await asyncio.sleep(3600)  # 每小时清理一次
        upload_manager.clean_old_uploads()


# 启动清理任务
def start_cleanup():
    asyncio.create_task(cleanup_task())


# 处理数据集文件名（重命名过长或包含特殊字符的文件）
def process_dataset_files(dataset_dir: Path) -> List[str]:
    """处理数据集中的文件名，返回重命名的文件列表"""
    renamed_files = []

    for root, _, files in os.walk(dataset_dir):
        for filename in files:
            file_path = os.path.join(root, filename)

            # 检查文件名是否过长或包含特殊字符
            if len(filename) > 200 or any(c in filename for c in r'<>:"/\|?*'):
                # 生成新的文件名
                base, ext = os.path.splitext(filename)
                new_filename = f"{base[:50]}_{uuid.uuid4().hex[:8]}{ext}"
                new_file_path = os.path.join(root, new_filename)

                # 重命名文件
                os.rename(file_path, new_file_path)
                renamed_files.append(f"{filename} -> {new_filename}")

    return renamed_files
