"""
TensorBoard服务 - 管理TensorBoard实例
"""
import os
import sys
import subprocess
import threading
import time
import logging
from pathlib import Path
from typing import Optional, Dict

from app.core.config import settings

logger = logging.getLogger(__name__)

class TensorBoardManager:
    """TensorBoard管理器，用于管理TensorBoard实例"""

    def __init__(self):
        self.tensorboard_process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.lock = threading.Lock()
        # 使用两个日志目录：系统配置的日志目录和模型输出目录
        self.log_dir = settings.TENSORBOARD_LOGS_DIR
        self.models_dir = settings.MODELS_DIR
        self.port = settings.TENSORBOARD_PORT

    def start(self) -> bool:
        """
        启动TensorBoard服务

        返回:
            bool: 是否成功启动
        """
        with self.lock:
            # 如果已经在运行，直接返回True
            if self.is_running and self.tensorboard_process and self.tensorboard_process.poll() is None:
                logger.info("TensorBoard已经在运行中")
                return True

            # 确保日志目录存在
            os.makedirs(self.log_dir, exist_ok=True)

            try:
                # 启动TensorBoard进程，直接监控模型输出目录
                # YOLOv8在训练时会将TensorBoard日志写入到模型输出目录下的exp目录中
                self.tensorboard_process = subprocess.Popen(
                    [sys.executable, "-m", "tensorboard.main", "--logdir", str(self.models_dir),
                     "--port", str(self.port), "--bind_all"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                # 等待一段时间，确保TensorBoard启动成功
                time.sleep(2)

                # 检查进程是否仍在运行
                if self.tensorboard_process.poll() is None:
                    self.is_running = True
                    logger.info(f"TensorBoard已启动，PID: {self.tensorboard_process.pid}, 端口: {self.port}")
                    return True
                else:
                    # 进程已退出，获取错误信息
                    _, error = self.tensorboard_process.communicate()
                    logger.error(f"TensorBoard启动失败: {error}")
                    self.is_running = False
                    return False

            except Exception as e:
                logger.error(f"启动TensorBoard时出错: {e}")
                self.is_running = False
                return False

    def stop(self) -> bool:
        """
        停止TensorBoard服务

        返回:
            bool: 是否成功停止
        """
        with self.lock:
            if not self.is_running or not self.tensorboard_process:
                return True

            try:
                # 尝试终止进程
                self.tensorboard_process.terminate()

                # 等待进程终止
                try:
                    self.tensorboard_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 如果超时，强制终止
                    self.tensorboard_process.kill()

                self.is_running = False
                logger.info("TensorBoard已停止")
                return True

            except Exception as e:
                logger.error(f"停止TensorBoard时出错: {e}")
                return False

    def restart(self) -> bool:
        """
        重启TensorBoard服务

        返回:
            bool: 是否成功重启
        """
        self.stop()
        return self.start()

    def get_url(self) -> str:
        """
        获取TensorBoard URL

        返回:
            str: TensorBoard URL
        """
        return f"http://localhost:{self.port}"

    def is_available(self) -> bool:
        """
        检查TensorBoard是否可用

        返回:
            bool: 是否可用
        """
        with self.lock:
            if not self.is_running or not self.tensorboard_process:
                return False

            # 检查进程是否仍在运行
            return self.tensorboard_process.poll() is None

# 创建全局TensorBoard管理器实例
tensorboard_manager = TensorBoardManager()
