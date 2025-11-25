"""
进程监控服务 - 用于监控和更新训练进程状态
"""
import os
import time
import subprocess
import threading
import datetime
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.crud import training_task
from app.core.config import settings

class ProcessMonitor:
    """进程监控器，用于监控训练进程状态并更新数据库"""

    def __init__(self):
        self.running = False
        self.monitor_thread = None

    def start(self):
        """启动监控线程"""
        if self.running:
            return

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
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
                # 创建数据库会话
                db = SessionLocal()

                # 获取所有正在运行的训练任务
                running_tasks = training_task.get_multi_by_status(
                    db,
                    status=["running", "training", "downloading_model", "pending"]
                )

                # 检查每个任务的进程状态
                for task in running_tasks:
                    # 正确访问数据库模型的属性
                    process_id = getattr(task, 'process_id', None)
                    if process_id:
                        try:
                            pid = int(process_id)
                            is_running = self._is_process_running(pid)

                            # 如果进程不再运行，分析日志判断状态
                            if not is_running:
                                # 分析训练日志内容
                                status = self._analyze_training_log(task.id)

                                if status == "completed":
                                    # 日志中发现成功标记，训练成功
                                    print(f"训练任务 {task.id} 处理完成")
                                elif status == "failed":
                                    # 日志中发现失败标记，训练失败
                                    training_task.update(db, db_obj=task, obj_in={
                                        "status": "failed",
                                        "end_time": datetime.datetime.now()
                                    })
                                    print(f"训练任务 {task.id} 失败")
                                else:
                                    # 日志中没有明确标记，保持原状态
                                    print(f"训练任务 {task.id} 状态未知，保持原状态")
                        except Exception as e:
                            print(f"检查任务 {task.id} 状态时出错: {e}")

                # 关闭数据库会话
                db.close()

            except Exception as e:
                print(f"进程监控循环出错: {e}")

            # 每30秒检查一次
            time.sleep(30)

    def _is_process_running(self, pid):
        """检查进程是否在运行"""
        try:
            if os.name == 'nt':  # Windows
                # 使用tasklist命令检查进程
                output = subprocess.check_output(f'tasklist /FI "PID eq {pid}"', shell=True).decode()
                return str(pid) in output
            else:  # Unix/Linux
                # 使用ps命令检查进程
                try:
                    os.kill(pid, 0)
                    return True
                except OSError:
                    return False
        except:
            return False

    def _analyze_training_log(self, task_id):
        """分析训练日志，判断训练是否成功或失败

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
                    # 更新任务状态为已完成
                    from app.db.session import SessionLocal
                    from app.crud import training_task
                    db = SessionLocal()
                    try:
                        task = training_task.get(db, id=task_id)
                        if task and task.status in ["running", "training", "downloading_model", "pending"]:
                            training_task.update(db, db_obj=task, obj_in={
                                "status": "completed",
                                "end_time": datetime.datetime.now()
                            })
                            print(f"训练任务 {task_id} 状态已更新为已完成")
                    finally:
                        db.close()
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