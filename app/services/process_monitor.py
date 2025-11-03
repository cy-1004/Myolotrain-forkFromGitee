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
                                    print(f"训练任务 {task.id} 已完成，正在注册输出模型")
                                    
                                    # 查找并注册输出模型
                                    try:
                                        # 获取输出目录
                                        parameters = getattr(task, 'parameters', None)
                                        output_dir = parameters.get("output_dir") if parameters else None
                                        if output_dir:
                                            # 查找最佳模型文件
                                            best_model_path = None
                                            possible_weights_paths = [
                                                os.path.join(output_dir, "exp", "weights", "best.pt"),  # 标准路径
                                                os.path.join(output_dir, "weights", "best.pt"),          # 另一种可能的路径
                                                os.path.join(output_dir, "best.pt")                        # 直接在输出目录下
                                            ]

                                            # 尝试每个可能的路径
                                            for model_path in possible_weights_paths:
                                                if os.path.exists(model_path):
                                                    best_model_path = model_path
                                                    print(f"找到最佳模型文件: {best_model_path}")
                                                    break

                                            # 如果找到模型文件，注册到数据库
                                            if best_model_path:
                                                # 导入必要的模块
                                                from app.crud import model
                                                from app.schemas.model import ModelCreate
                                                
                                                # 获取模型名称和类型
                                                model_name = f"{task.name}_best"
                                                model_filename = os.path.basename(best_model_path)
                                                
                                                # 确定模型类型和任务类型
                                                model_type = "yolov8"  # 默认为yolov8
                                                model_task = "detect"  # 默认为检测任务
                                                
                                                # 从训练参数中获取任务类型
                                                if parameters and "task" in parameters:
                                                    model_task = parameters["task"]
                                                else:
                                                    # 从模型文件名中提取任务类型
                                                    if "segment" in best_model_path.lower():
                                                        model_task = "segment"
                                                    elif "classify" in best_model_path.lower():
                                                        model_task = "classify"
                                                    elif "pose" in best_model_path.lower():
                                                        model_task = "pose"

                                                # 从模型文件名中推断模型类型
                                                if "yolov8" in best_model_path.lower():
                                                    # 提取yolov8n, yolov8s等
                                                    import re
                                                    match = re.search(r'yolov8[a-z]\d*', best_model_path.lower())
                                                    if match:
                                                        model_type = match.group(0)
                                                elif "yolov5" in best_model_path.lower():
                                                    model_type = "yolov5"
                                                elif "yolov10" in best_model_path.lower():
                                                    model_type = "yolov10"
                                                elif "yolo11" in best_model_path.lower():
                                                    model_type = "yolo11"

                                                # 创建模型记录
                                                model_in = ModelCreate(
                                                    name=model_name,
                                                    description=f"{task.name} 训练生成的最佳模型",
                                                    type=model_type,
                                                    task=model_task,
                                                    path=best_model_path,
                                                    source="training"
                                                )
                                                
                                                # 添加到数据库
                                                db_model = model.create(db, obj_in=model_in)
                                                print(f"成功注册模型: {model_name} (ID: {db_model.id})")
                                                
                                                # 更新训练任务，关联输出模型
                                                update_data = {
                                                    "status": "completed",
                                                    "end_time": datetime.datetime.now(),
                                                    "output_model_id": str(db_model.id)  # 确保使用字符串格式的UUID而不是对象
                                                }
                                                updated_task = training_task.update(db, db_obj=task, obj_in=update_data)
                                                print(f"成功更新训练任务 {task.id}，关联输出模型 {db_model.id}")
                                                print(f"更新后的任务状态: {updated_task.status}")
                                                print(f"更新后的输出模型ID: {getattr(updated_task, 'output_model_id', None)}")
                                            else:
                                                print(f"警告: 未找到训练输出的模型文件")
                                                # 即使没有找到模型文件，也更新任务状态，但不设置output_model_id
                                                training_task.update(db, db_obj=task, obj_in={
                                                    "status": "completed",
                                                    "end_time": datetime.datetime.now()
                                                    # 不设置output_model_id字段，保持为NULL
                                                })
                                    except Exception as e:
                                        print(f"注册输出模型时出错: {e}")
                                        # 即使注册模型失败，也更新任务状态，但不设置output_model_id
                                        training_task.update(db, db_obj=task, obj_in={
                                            "status": "completed",
                                            "end_time": datetime.datetime.now()
                                            # 不设置output_model_id字段，保持为NULL
                                        })
                                    
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
                "results_dict",  # 新增：训练结果字典输出
                "best.pt",
                "last.pt"
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