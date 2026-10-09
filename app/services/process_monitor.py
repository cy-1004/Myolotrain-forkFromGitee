"""
进程监控服务 - 用于监控和更新训练进程状态

训练任务正常情况下由启动它的监控线程收尾（training_service.monitor_training_process）。
这里兜底处理"没有监控线程在等它"的任务，典型场景是服务重启：
  - 服务启动时巡检一次：上次运行留下的训练中任务，进程已不在的按产物和日志收尾；
  - 之后每 30 秒巡检一次，处理本进程之外启动的、或监控线程意外退出的任务。
"""
import datetime
import os
import threading
import time

import psutil

from app.core.config import settings
from app.crud import training_task
from app.db.session import SessionLocal

# 需要巡检的任务状态。pending 是建好但还没点开始的任务，没有进程，不属于巡检范围
ACTIVE_STATUSES = ["running", "training", "downloading_model"]

CHECK_INTERVAL_SECONDS = 30


def _parse_pid(process_id):
    try:
        return int(process_id) if process_id else None
    except (TypeError, ValueError):
        return None


def is_training_process_alive(pid: int, task_id) -> bool:
    """训练进程是否还在运行

    不能只看 PID 是否存在：服务重启（尤其容器重启）后 PID 会被系统复用，
    同一个 PID 可能已经是别的进程。训练进程的命令行里一定包含任务 ID
    （训练脚本路径 logs/tensorboard/<任务ID>/train_script.py，续训代码里的输出目录 training_<任务ID>），
    以此确认它就是这个任务的进程。
    """
    try:
        proc = psutil.Process(pid)
        if proc.status() == psutil.STATUS_ZOMBIE:
            return False
        cmdline = " ".join(proc.cmdline())
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        # AccessDenied：读不了命令行，说明是别的用户的进程，不可能是我们启动的训练进程
        return False
    return str(task_id) in cmdline


class ProcessMonitor:
    """进程监控器，用于监控训练进程状态并更新数据库"""

    def __init__(self):
        self.running = False
        self.monitor_thread = None

    def start(self):
        """启动监控：先同步巡检一次（处理服务重启前遗留的任务），再启动定期巡检线程"""
        if self.running:
            return

        try:
            self.sweep(startup=True)
        except Exception as e:
            print(f"启动巡检训练任务出错: {e}")

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, name="process-monitor")
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print("进程监控服务已启动")

    def stop(self):
        """停止监控线程"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            self.monitor_thread = None
        print("进程监控服务已停止")

    def _monitor_loop(self):
        """监控循环，定期检查所有训练进程状态"""
        while self.running:
            try:
                self.sweep(startup=False)
            except Exception as e:
                print(f"进程监控循环出错: {e}")

            # 分段睡眠，stop() 时能及时退出
            for _ in range(CHECK_INTERVAL_SECONDS):
                if not self.running:
                    break
                time.sleep(1)

    def sweep(self, startup: bool = False):
        """巡检一遍处于运行态的训练任务，给进程已经不在的任务收尾"""
        from app.services import training_service

        db = SessionLocal()
        try:
            tasks = training_task.get_multi_by_status(db, status=ACTIVE_STATUSES)
            for task in tasks:
                if training_service.is_task_watched(task.id):
                    continue  # 本进程的监控线程正在等它，交给监控线程收尾
                pid = _parse_pid(task.process_id)
                if pid is None:
                    # 没有 PID：还在下载基础模型等同步阶段，或者没来得及启动训练进程服务就退出了。
                    # 只在服务启动时处理——此刻本进程里不可能有进行中的同步阶段
                    if startup:
                        self._finalize(db, task)
                    continue
                if is_training_process_alive(pid, task.id):
                    continue
                self._finalize(db, task)
        finally:
            db.close()

    def _finalize(self, db, task):
        """训练进程已经不在、又没有监控线程知道它的返回码：根据日志和产物判断结果"""
        from app.services import training_service

        log_status = self._analyze_training_log(task.id)
        best_pt = training_service.get_training_output_dir(task) / "exp" / "weights" / "best.pt"
        now = datetime.datetime.now()

        if log_status == "completed" and best_pt.exists():
            training_task.update(db, db_obj=task, obj_in={"status": "completed", "end_time": now})
            print(f"训练任务 {task.id} 已完成（巡检收尾）")
            try:
                training_service.register_trained_model(db, task, "best")
            except Exception as e:
                print(f"训练任务 {task.id} 登记最佳模型失败: {e}")
        elif log_status == "failed":
            training_task.update(db, db_obj=task, obj_in={"status": "failed", "end_time": now})
            print(f"训练任务 {task.id} 失败（日志中有错误）")
        else:
            # 日志里既没有完成标记也没有报错：进程是被外力终止的（服务/容器重启、被系统杀掉）。
            # 标记为"已中断"而不是失败，用户可以从 last.pt 继续训练
            training_task.update(db, db_obj=task, obj_in={"status": "interrupted", "end_time": now})
            print(f"训练任务 {task.id} 已中断（进程已不在，可继续训练）")

    def _analyze_training_log(self, task_id):
        """分析训练日志，判断训练是否成功或失败（只读，不修改任务状态）

        参数:
            task_id: 训练任务ID

        返回:
            str: 'completed', 'failed', 或 'unknown'
        """
        base_log_dir = os.path.join(settings.TENSORBOARD_LOGS_DIR, str(task_id))
        resume_log_path = os.path.join(base_log_dir, "resume_training_log.txt")
        log_path = resume_log_path if os.path.exists(resume_log_path) else os.path.join(base_log_dir, "training_log.txt")

        if not os.path.exists(log_path):
            print(f"训练日志文件不存在: {log_path}")
            return "unknown"

        try:
            # 使用编码工具读取日志文件，支持跨平台编码兼容性
            from app.utils.encoding_utils import read_log_with_auto_encoding
            log_content = read_log_with_auto_encoding(log_path)

            # 检查成功标记
            success_markers = [
                "Training completed successfully",
                "training completed successfully",
                "Training completed",
                "training completed",
                "Results saved to",
                "results saved to",
                "results_dict"
            ]
            for marker in success_markers:
                if marker in log_content:
                    print(f"训练日志中发现成功标记: {marker}")
                    return "completed"

            # 检查失败标记
            failure_markers = [
                "Traceback (most recent call last)",
                "Error:",
                "Exception:",
                "CUDA out of memory",
                "CUDA error:",
                "RuntimeError:",
                "AssertionError:",
                "ValueError:"
            ]
            for marker in failure_markers:
                if marker in log_content:
                    print(f"训练日志中发现失败标记: {marker}")
                    return "failed"

            # 没有明确标记
            print(f"训练日志中没有发现明确的成功或失败标记")
            return "unknown"
        except Exception as e:
            print(f"分析训练日志出错: {e}")
            return "unknown"

# 创建全局进程监控器实例
process_monitor = ProcessMonitor()
