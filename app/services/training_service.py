"""Training service module"""
import os
import sys
import time
import subprocess
import platform
import uuid
import json
import threading
import torch
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
import re

from app.core.config import settings
from app.core.paths import resolve_stored
from app.crud import training_task, dataset, model
from app.models.training_task import TrainingTask
from app.schemas.training_task import TrainingTaskCreate, TrainingTaskUpdate
from app.services.ascend_service import AscendDeviceManager

# UUID验证正则表达式
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

def is_valid_uuid(uuid_str):
    """验证字符串是否为有效的UUID格式"""
    if not isinstance(uuid_str, str):
        return False
    return bool(UUID_PATTERN.match(uuid_str))

# 屏蔽 NVIDIA 特有 API
# 昇腾环境禁用CUDA显存限制函数，改由环境变量或CANN层级控制显存
try:
    import torch
    if not hasattr(torch, 'npu') or not torch.npu.is_available():
        # 只有在非昇腾环境下才执行CUDA相关的代码
        torch.cuda.empty_cache()  # 仅在CUDA环境下清理缓存
except AttributeError:
    # torch.npu不存在，说明不是昇腾环境
    pass

# 设置TensorBoard为True
# 用 Ultralytics 的 Python API 而不是 `yolo settings` 子进程：后者要求 yolo 命令在 PATH 上，
# 找不到时抛 FileNotFoundError（原先只捕获了 CalledProcessError），会让整个应用在导入阶段崩溃
try:
    from ultralytics import settings as _yolo_settings
    _yolo_settings.update({"tensorboard": True})
except Exception as e:
    print(f"警告: 设置TensorBoard时出错: {e}")
    # 继续执行，即使设置失败


# 基础模型名只允许这些字符：它会被拼进文件路径，不能含路径分隔符
_BASE_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# 历史约定：model_type 只传尺寸字母时表示 YOLOv8（"n" -> "yolov8n"）
_YOLOV8_SIZE_LETTERS = {"n", "s", "m", "l", "x"}


def resolve_base_weights(model_type: str) -> Path:
    """把训练参数里的 model_type 解析为基础权重文件路径（文件不一定已存在）

    - "n"/"s"/... -> yolov8n.pt（兼容旧前端）；"yolov8n"、"yolo11n"、"yolo11n.pt" 按原名
      （原先的逻辑会把 "yolo11n" 拼成 "yolov8yolo11n"，导致 YOLO11 只能通过上传模型训练）
    - 查找顺序：WEIGHTS_DIR（Docker 中为预置权重目录）→ 项目下的 models/（旧版本下载位置）
    - 都不存在时返回 WEIGHTS_DIR 下的路径，由调用方决定是否下载

    Raises:
        ValueError: model_type 不是合法的模型名
    """
    name = (model_type or "").strip()
    if name.endswith(".pt"):
        name = name[:-3]
    if name in _YOLOV8_SIZE_LETTERS:
        name = f"yolov8{name}"
    if not _BASE_MODEL_NAME_RE.match(name):
        raise ValueError(f"不合法的模型类型: {model_type!r}")

    filename = f"{name}.pt"
    candidates = [Path(settings.WEIGHTS_DIR) / filename, settings.BASE_DIR / "models" / filename]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def download_base_weights(model_file: Path) -> Path:
    """下载 Ultralytics 官方基础权重到指定路径

    直接下载到目标路径；原先用 YOLO("xxx.pt") 触发下载，文件会落在当前目录或
    Ultralytics 自己的权重目录，而不是后面训练脚本要读取的 models_dir。
    """
    from ultralytics.utils.downloads import attempt_download_asset

    model_file.parent.mkdir(parents=True, exist_ok=True)
    attempt_download_asset(str(model_file))
    if not model_file.exists():
        raise FileNotFoundError(f"下载后仍找不到权重文件: {model_file}（{model_file.name} 可能不是官方发布的模型名）")
    return model_file


# 允许通过 parameters.extra_train_args 传给 Ultralytics 的训练参数及其类型。
# 值会以 Python 字面量写进生成的训练脚本，所以只放行基本类型，字符串只允许枚举值
_EXTRA_TRAIN_ARGS = {
    "patience": int, "seed": int, "close_mosaic": int, "save_period": int, "workers": int,
    "deterministic": bool, "cos_lr": bool, "amp": bool, "plots": bool, "val": bool,
    "lr0": float, "lrf": float, "mosaic": float, "mixup": float, "fliplr": float, "flipud": float,
    "degrees": float, "translate": float, "scale": float, "hsv_h": float, "hsv_s": float, "hsv_v": float,
}
_EXTRA_TRAIN_ENUMS = {
    "optimizer": {"auto", "SGD", "Adam", "AdamW", "NAdam", "RAdam", "RMSProp"},
    "cache": {"ram", "disk"},
}


def sanitize_extra_train_args(extra) -> Dict[str, Any]:
    if not isinstance(extra, dict):
        return {}
    clean = {}
    for key, value in extra.items():
        if key in _EXTRA_TRAIN_ARGS:
            typ = _EXTRA_TRAIN_ARGS[key]
            if typ is bool and isinstance(value, bool):
                clean[key] = value
            elif typ is int and isinstance(value, int) and not isinstance(value, bool):
                clean[key] = value
            elif typ is float and isinstance(value, (int, float)) and not isinstance(value, bool):
                clean[key] = float(value)
        elif key in _EXTRA_TRAIN_ENUMS and value in _EXTRA_TRAIN_ENUMS[key]:
            clean[key] = value
    return clean


def _training_subprocess_env() -> Dict[str, str]:
    """训练子进程的环境变量（首次训练与续训共用）"""
    env = os.environ.copy()
    env['ULTRALYTICS_SKIP_DOWNLOAD'] = '1'
    env['ULTRALYTICS_SKIP_AMP_CHECK'] = '1'
    env['ULTRALYTICS_TENSORBOARD'] = '1'
    # 子进程的输出直接写进日志文件描述符，编码由子进程决定：中文 Windows 上默认是 GBK，
    # 与日志读取端约定的 UTF-8 不一致会乱码。这里强制子进程按 UTF-8 输出
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    return env


# 用户主动停止后的状态。训练进程被杀时返回码非 0，监控线程不能把它们改写成 failed
_USER_STOPPED_STATUSES = {"cancelled", "stopped"}

# 当前进程内有监控线程在等待的训练任务。process_monitor 的定期巡检跳过这些任务，
# 避免两边同时给同一个任务收尾
_watched_task_ids = set()
_watched_lock = threading.Lock()


def is_task_watched(task_id) -> bool:
    with _watched_lock:
        return str(task_id) in _watched_task_ids


def monitor_training_process(training_process, task_id) -> None:
    """等待训练子进程结束并更新任务状态（在后台线程中运行）

    必须自己创建数据库会话：原先复用的是发起训练那个请求的会话，请求结束后会话已关闭，
    跨线程使用 SQLAlchemy 会话本身也不安全，导致训练结束后状态更新经常失败、任务一直停在 training。
    """
    from app.db.session import SessionLocal

    with _watched_lock:
        _watched_task_ids.add(str(task_id))
    try:
        training_process.wait()
    except Exception as e:
        print(f"\n=== 监控训练进程时出错: {e} ===")
    return_code = training_process.returncode

    db = SessionLocal()
    try:
        db_task = training_task.get(db, id=task_id)
        if not db_task:
            return
        if db_task.status in _USER_STOPPED_STATUSES:
            print(f"\n=== 训练任务 {task_id} 已被用户停止（返回码 {return_code}） ===")
            return

        best_pt = get_training_output_dir(db_task) / "exp" / "weights" / "best.pt"
        if return_code == 0 and best_pt.exists():
            training_task.update(db, db_obj=db_task, obj_in={
                "status": "completed",
                "end_time": datetime.now()
            })
            print(f"\n=== 训练任务 {task_id} 已成功完成 ===")
            # 自动登记最佳模型并回填 output_model_id，不再需要手动点"上传到模型管理"
            try:
                db_model = register_trained_model(db, db_task, "best")
                print(f"\n=== 已登记最佳模型: {db_model.id} ===")
            except Exception as e:
                print(f"\n=== 登记最佳模型失败（可在训练列表中手动上传）: {e} ===")
        else:
            # 返回码为 0 但没有 best.pt：训练脚本吞掉了异常，同样视为失败
            reason = f"返回码 {return_code}" if return_code != 0 else "未生成 best.pt"
            training_task.update(db, db_obj=db_task, obj_in={
                "status": "failed",
                "end_time": datetime.now()
            })
            print(f"\n=== 训练任务 {task_id} 失败（{reason}） ===")
    except Exception as e:
        print(f"\n=== 更新训练任务 {task_id} 状态时出错: {e} ===")
    finally:
        db.close()
        with _watched_lock:
            _watched_task_ids.discard(str(task_id))


def _task_parameters(db_task) -> Dict[str, Any]:
    """训练参数统一转成 dict（历史数据里有存成 JSON 字符串的）"""
    params = db_task.parameters
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            params = {}
    return params if isinstance(params, dict) else {}


def get_training_output_dir(db_task) -> Path:
    """训练输出目录。训练脚本以 project=<该目录>, name='exp' 运行，产物在 <该目录>/exp/ 下"""
    output_dir = resolve_stored(_task_parameters(db_task).get("output_dir"))
    if not output_dir:
        output_dir = os.path.join(settings.STATIC_DIR, "models", f"training_{db_task.id}")
    return Path(output_dir)


def _trained_model_type(db: Session, db_task, params: Dict[str, Any]) -> str:
    """训练产物的模型类型：沿用基础模型的类型（如 yolo11n），而不是一律写成 yolov8"""
    if db_task.model_id:
        base = model.get(db, id=db_task.model_id)
        if base and base.type:
            return base.type
    name = str(params.get("model_type") or "").strip()
    if name.endswith(".pt"):
        name = name[:-3]
    if name in _YOLOV8_SIZE_LETTERS:
        name = f"yolov8{name}"
    return name if _BASE_MODEL_NAME_RE.match(name or "") else "yolov8"


def register_trained_model(db: Session, db_task, which: str = "best"):
    """把训练产出的 best.pt / last.pt 登记到模型管理，best 同时回填到任务的 output_model_id

    幂等：同一个权重文件只登记一次，重复调用返回已有记录。
    训练成功后由监控线程自动调用；"上传到模型管理"按钮也走这里。

    Raises:
        ValueError: which 不是 best/last
        FileNotFoundError: 权重文件不存在
    """
    from app.models.model import Model as ModelORM
    from app.schemas.model import ModelCreate

    if which not in ("best", "last"):
        raise ValueError("无效的模型类型，必须是 'best' 或 'last'")
    weights_file = get_training_output_dir(db_task) / "exp" / "weights" / f"{which}.pt"
    if not weights_file.exists():
        raise FileNotFoundError(f"模型文件不存在: {weights_file}")

    db_model = db.query(ModelORM).filter(ModelORM.path == str(weights_file)).first()
    if db_model is None:
        params = _task_parameters(db_task)
        label = "最佳" if which == "best" else "最后"
        db_model = model.create(db, obj_in=ModelCreate(
            name=f"{db_task.name}_{label}模型",
            description=f"由训练任务 '{db_task.name}' 生成的{label}模型",
            type=_trained_model_type(db, db_task, params),
            task=params.get("task_type", "detect"),
            path=str(weights_file),
            source="training",
        ))

    if which == "best" and db_task.output_model_id != db_model.id:
        training_task.update(db, db_obj=db_task, obj_in={"output_model_id": db_model.id})
    return db_model


def read_results_csv(db_task) -> List[Dict[str, Any]]:
    """读取训练的逐 epoch 指标（Ultralytics 写的 exp/results.csv），文件不存在时返回空列表

    Ultralytics 的列名带有对齐用的空格（如 "      metrics/mAP50(B)"），这里统一去掉；
    数值转 float，无法解析的保持原样。
    """
    import csv

    csv_path = get_training_output_dir(db_task) / "exp" / "results.csv"
    if not csv_path.exists():
        return []
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row = {}
            for key, value in raw.items():
                if key is None:
                    continue
                value = (value or "").strip()
                try:
                    row[key.strip()] = float(value)
                except ValueError:
                    row[key.strip()] = value
            if row:
                rows.append(row)
    return rows


# 单次最多返回的日志字节数，防止前端一次拉取几十 MB 的日志把页面卡死
LOG_CHUNK_MAX_BYTES = 256 * 1024


def get_training_log_path(db_task) -> Path:
    tensorboard_dir = db_task.tensorboard_path or os.path.join(settings.TENSORBOARD_LOGS_DIR, str(db_task.id))
    return Path(tensorboard_dir) / "training_log.txt"


def read_training_log_chunk(db_task, offset: int = 0, limit: int = 64 * 1024) -> Dict[str, Any]:
    """按字节偏移增量读取训练日志

    前端轮询时带上上次返回的 next_offset，只拿新增内容；原先的 /logs 接口每 5 秒返回整个日志文件。
    offset < 0 表示从文件末尾往前取 |offset| 字节（打开日志弹窗时先看最近的内容）。
    切块位置会对齐到 UTF-8 字符边界，避免中文被截成半个字符。

    Returns:
        {"text", "offset"（本次实际起点）, "next_offset", "size"（文件当前大小）, "exists"}
    """
    limit = max(1, min(int(limit), LOG_CHUNK_MAX_BYTES))
    log_path = get_training_log_path(db_task)
    if not log_path.exists():
        return {"text": "", "offset": 0, "next_offset": 0, "size": 0, "exists": False}

    size = log_path.stat().st_size
    start = size + offset if offset < 0 else offset
    # 日志被重新开始训练覆盖后会变短，旧偏移量越界时从头读
    if start < 0 or start > size:
        start = 0

    with open(log_path, "rb") as f:
        f.seek(start)
        data = f.read(limit)

    # 起点落在多字节字符中间（UTF-8 续字节为 10xxxxxx）：跳过残缺的前缀
    head = 0
    if start > 0:
        while head < len(data) and head < 4 and (data[head] & 0xC0) == 0x80:
            head += 1
    # 终点截断了多字节字符：把残缺的尾巴留给下一次读取
    tail = len(data)
    if start + len(data) < size:
        back = 0
        while back < 4 and back < tail and (data[tail - 1 - back] & 0xC0) == 0x80:
            back += 1
        if back < tail:
            lead = data[tail - 1 - back]
            # 前导字节声明的字符长度：110xxxxx=2、1110xxxx=3、11110xxx=4
            expected = 2 if (lead & 0xE0) == 0xC0 else 3 if (lead & 0xF0) == 0xE0 else 4 if (lead & 0xF8) == 0xF0 else 1
            if lead >= 0xC0 and back + 1 < expected:
                tail -= back + 1

    chunk = data[head:tail]
    return {
        "text": chunk.decode("utf-8", errors="replace"),
        "offset": start + head,
        "next_offset": start + tail,
        "size": size,
        "exists": True,
    }

# 导入可能需要的PyTorch和Ultralytics模型类
try:
    # 导入PyTorch核心类
    from torch.nn.modules.container import Sequential
    from torch.nn import Module, ModuleList, ModuleDict

    # 导入Ultralytics模型类
    from ultralytics.nn.tasks import DetectionModel, SegmentationModel, ClassificationModel, PoseModel

    # 导入Ultralytics模块类
    from ultralytics.nn.modules import conv
    from ultralytics.nn.modules import block
    from ultralytics.nn.modules import head

    # 添加PyTorch核心类到安全全局变量
    torch.serialization.add_safe_globals([Sequential, Module, ModuleList, ModuleDict])

    # 添加Ultralytics模型类到安全全局变量
    torch.serialization.add_safe_globals([DetectionModel, SegmentationModel, ClassificationModel, PoseModel])

    # 添加Ultralytics模块类
    torch.serialization.add_safe_globals([conv.Conv])

    # 添加所有Ultralytics模块类
    for module in [conv, block, head]:
        for name in dir(module):
            if name[0].isupper():  # 类名通常以大写字母开头
                try:
                    cls = getattr(module, name)
                    if isinstance(cls, type):  # 确保是类
                        torch.serialization.add_safe_globals([cls])
                except Exception as e:
                    print(f"Could not add {module.__name__}.{name} to safe globals: {e}")
except ImportError as e:
    print(f"Warning: Could not import required classes: {e}")

class DeviceManager:
    @staticmethod
    def get_available_gpus() -> list:
        """
        获取所有可用的GPU信息
        :return: GPU信息列表 [{'index': 0, 'name': 'GPU名称', 'memory': 显存大小(MB), 'memory_used': 已用显存(MB), 'memory_free': 可用显存(MB)}]
        """
        gpus = []
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                total_memory = int(props.total_memory / (1024 * 1024))  # 转换为MB

                # 尝试获取当前显存使用情况
                memory_used = 0
                memory_free = total_memory
                try:
                    # 如果支持torch.cuda.memory_stats，则使用它获取当前显存使用情况
                    if hasattr(torch.cuda, 'memory_stats'):
                        stats = torch.cuda.memory_stats(i)
                        memory_used = int(stats.get('allocated_bytes.all.current', 0) / (1024 * 1024))
                        memory_free = total_memory - memory_used
                    # 如果支持torch.cuda.memory.memory_reserved，则使用它获取当前显存使用情况
                    elif hasattr(torch.cuda.memory, 'memory_reserved'):
                        memory_used = int(torch.cuda.memory.memory_reserved(i) / (1024 * 1024))
                        memory_free = total_memory - memory_used
                    # 如果支持torch.cuda.memory.mem_get_info，则使用它获取当前显存使用情况
                    elif hasattr(torch.cuda.memory, 'mem_get_info'):
                        memory_free = int(torch.cuda.memory.mem_get_info(i)[0] / (1024 * 1024))
                        memory_used = total_memory - memory_free
                except Exception as e:
                    print(f"获取GPU {i} 显存使用情况失败: {str(e)}")

                gpus.append({
                    'index': i,
                    'name': props.name,
                    'memory': total_memory,
                    'memory_used': memory_used,
                    'memory_free': memory_free
                })
        return gpus

    @staticmethod
    def validate_gpu_memory(requested_memory: int) -> tuple[bool, str, int]:
        """
        验证请求的GPU显存是否合理
        :param requested_memory: 请求的显存大小(MB)
        :return: (是否有效, 提示信息, 总显存大小)
        """
        if not torch.cuda.is_available():
            return False, "GPU不可用，请使用CPU模式训练", 0

        # 获取GPU信息
        gpus = DeviceManager.get_available_gpus()
        if not gpus:
            return False, "GPU信息获取失败，请使用CPU模式训练", 0

        gpu_info = gpus[0]
        total_memory = gpu_info.get("memory", 0)
        free_memory = gpu_info.get("memory_free", 0)
        used_memory = gpu_info.get("memory_used", 0)

        if requested_memory <= 0:
            return False, f"请求的显存必须大于0MB", total_memory

        if requested_memory > total_memory:
            return False, f"请求的显存({requested_memory}MB)超过了GPU最大显存({total_memory}MB)", total_memory

        # 检查是否超过可用显存
        if requested_memory > free_memory:
            return False, f"请求的显存({requested_memory}MB)超过了当前可用显存({free_memory}MB)", total_memory

        # 建议最多使用可用显存的90%
        recommended_memory = int(free_memory * 0.9)
        if requested_memory > recommended_memory:
            return False, f"建议使用不超过{recommended_memory}MB显存（当前可用显存{free_memory}MB）", total_memory

        return True, "显存设置有效", total_memory

    @staticmethod
    def get_device_info(device_type: str = 'auto', gpu_memory: Optional[int] = None, gpu_index: int = 0,
                        gpu_indices: Optional[List[int]] = None, auto_select_gpu: bool = False,
                        ascend_memory: Optional[int] = None, ascend_index: int = 0) -> dict:
        """
        获取设备信息并配置训练设备
        :param device_type: 'cpu', 'gpu', 'ascend' 或 'auto'
        :param gpu_memory: GPU显存限制（MB）
        :param gpu_index: GPU索引，默认为0
        :param gpu_indices: 多个GPU索引列表
        :param auto_select_gpu: 是否自动选择空闲GPU
        :param ascend_memory: 昇腾NPU内存限制（MB）
        :param ascend_index: 昇腾NPU索引，默认为0
        :return: 设备配置信息
        """
        # 获取所有可用的GPU和昇腾NPU
        available_gpus = DeviceManager.get_available_gpus()
        available_ascends = AscendDeviceManager.get_available_ascends()

        device_info = {
            'device_type': device_type,
            'device': 'cpu',
            'gpu_memory': None,
            'gpu_index': gpu_index,
            'gpu_indices': gpu_indices,
            'auto_select_gpu': auto_select_gpu,
            'ascend_memory': None,
            'ascend_index': ascend_index,
            'cpu_cores': None,
            'available_gpus': available_gpus,
            'available_ascends': available_ascends
        }

        # 检测是否有可用的GPU和昇腾NPU
        has_cuda = torch.cuda.is_available()
        has_ascend = len(available_ascends) > 0

        # 自动模式下，优先使用昇腾NPU，其次是GPU，最后是CPU
        if device_type == 'auto':
            if has_ascend:
                device_type = 'ascend'
            elif has_cuda:
                device_type = 'gpu'
            else:
                device_type = 'cpu'
            device_info['device_type'] = device_type

        # 处理昇腾NPU设备
        if device_type == 'ascend':
            if not has_ascend:
                print('\n=== 警告: 昇腾NPU不可用，将尝试使用GPU训练 ===')
                if has_cuda:
                    device_type = 'gpu'
                    device_info['device_type'] = 'gpu'
                else:
                    device_type = 'cpu'
                    device_info['device_type'] = 'cpu'
            else:
                # 使用昇腾NPU设备管理器获取设备信息
                ascend_device_info = AscendDeviceManager.get_device_info(
                    ascend_memory=ascend_memory,
                    ascend_index=ascend_index
                )

                # 更新设备信息
                device_info.update({
                    'device': ascend_device_info['device'],
                    'ascend_memory': ascend_device_info['ascend_memory'],
                    'ascend_index': ascend_device_info['ascend_index']
                })

                # 如果昇腾NPU不可用，回退到其他设备
                if ascend_device_info['device_type'] != 'ascend':
                    device_type = ascend_device_info['device_type']
                    device_info['device_type'] = device_type

        # 处理GPU设备
        if device_type == 'gpu':
            if not has_cuda:
                print('\n=== 警告: GPU不可用，将使用CPU训练 ===')
                device_type = 'cpu'
                device_info['device_type'] = 'cpu'
            else:
                # 处理自动选择GPU情况
                if auto_select_gpu:
                    # 自动选择最空闲的GPU
                    if available_gpus:
                        # 按可用显存排序，选择最空闲的GPU
                        sorted_gpus = sorted(available_gpus, key=lambda x: x.get('memory_free', 0), reverse=True)
                        selected_gpu = sorted_gpus[0]
                        
                        # 使用-1表示自动选择GPU
                        device_info['device'] = [-1]
                        device_info['gpu_indices'] = [-1]
                        device_info['gpu_index'] = -1
                        print(f"\n=== 自动选择GPU: {selected_gpu.get('name')} (索引: {selected_gpu.get('index')}) ===")
                        
                        # 显存设置为None表示自动
                        device_info['gpu_memory'] = None
                    else:
                        print('\n=== 警告: 没有可用的GPU，将使用CPU训练 ===')
                        device_type = 'cpu'
                        device_info['device_type'] = 'cpu'
                # 处理多GPU情况
                elif gpu_indices and len(gpu_indices) > 1:
                    # 多GPU训练
                    selected_gpus = []
                    for idx in gpu_indices:
                        for gpu in available_gpus:
                            if gpu.get("index", 0) == idx:
                                selected_gpus.append(gpu)
                                break
                    
                    if selected_gpus:
                        # 设置多GPU设备
                        device_info['device'] = gpu_indices
                        device_info['gpu_indices'] = gpu_indices
                        print(f"\n=== 使用多GPU训练: {gpu_indices} ===")
                        
                        # 设置GPU显存限制（应用于所有GPU）
                        if gpu_memory and gpu_memory > 0:
                            # 对于多GPU，我们使用总的显存限制
                            print(f"\n=== 多GPU总显存限制为 {gpu_memory}MB ===")
                            device_info['gpu_memory'] = gpu_memory
                        else:
                            # 自动显存限制
                            device_info['gpu_memory'] = None
                    else:
                        print('\n=== 警告: 指定的GPU不存在，将使用单GPU训练 ===')
                        # 回退到单GPU模式
                        gpu_indices = None
                        device_info['gpu_indices'] = None
                
                # 处理单GPU情况
                if not auto_select_gpu and (not gpu_indices or len(gpu_indices) <= 1):
                    # 检查指定的GPU是否存在
                    selected_gpu = None
                    for gpu in available_gpus:
                        if gpu.get("index", 0) == gpu_index:
                            selected_gpu = gpu
                            break

                    # 如果没有找到指定的GPU，使用第一个GPU
                    if not selected_gpu and available_gpus:
                        selected_gpu = available_gpus[0]
                        gpu_index = selected_gpu.get("index", 0)
                        device_info['gpu_index'] = gpu_index
                        print(f"\n=== 警告: 指定的GPU ID {gpu_index} 不存在，使用GPU ID {gpu_index} ===")

                    if selected_gpu:
                        # 设置当前设备
                        try:
                            torch.cuda.set_device(gpu_index)
                            device_info['device'] = f'cuda:{gpu_index}'
                        except Exception as e:
                            print(f'\n=== 警告: 无法设置当前GPU设备: {str(e)} ===')
                            device_info['device'] = 'cuda'

                        # 设置GPU显存限制
                        if gpu_memory:
                            # 获取选定的GPU信息
                            total_memory = selected_gpu.get("memory", 0)
                            free_memory = selected_gpu.get("memory_free", 0)

                            # 验证GPU显存设置
                            if gpu_memory <= 0:
                                print(f"\n=== 警告: 请求的显存必须大于0MB ===")
                                # 使用推荐的显存大小（80%的可用显存）
                                gpu_memory = int(free_memory * 0.8)
                            elif gpu_memory > total_memory:
                                print(f"\n=== 警告: 请求的显存({gpu_memory}MB)超过了GPU最大显存({total_memory}MB) ===")
                                # 使用推荐的显存大小（80%的可用显存）
                                gpu_memory = int(free_memory * 0.8)
                            elif gpu_memory > free_memory:
                                print(f"\n=== 警告: 请求的显存({gpu_memory}MB)超过了当前可用显存({free_memory}MB) ===")
                                # 使用推荐的显存大小（80%的可用显存）
                                gpu_memory = int(free_memory * 0.8)

                            print(f"\n=== 设置GPU {gpu_index} 显存限制为 {gpu_memory}MB ===")

                            # 设置GPU显存限制
                            try:
                                torch.cuda.set_per_process_memory_fraction(gpu_memory / total_memory)
                                device_info['gpu_memory'] = gpu_memory
                            except Exception as e:
                                print(f'\n=== 警告: 无法设置GPU显存限制: {str(e)} ===')
                    else:
                        print('\n=== 警告: 没有可用的GPU，将使用CPU训练 ===')
                        device_type = 'cpu'
                        device_info['device_type'] = 'cpu'
                        device_info['device'] = 'cpu'

        # 处理CPU设备
        if device_type == 'cpu':
            # 获取CPU核心数
            physical_cores = psutil.cpu_count(logical=False) or os.cpu_count() // 2
            if physical_cores:
                device_info['cpu_cores'] = physical_cores


        return device_info


def resolve_cpu_cores(requested_cores: Optional[int]) -> int:
    """
    统一的CPU核心数裁决逻辑，确保安全有效的CPU使用
    """
    import os
    import psutil

    logical = psutil.cpu_count(logical=True)
    physical = psutil.cpu_count(logical=False) or logical // 2

    # 规则 1：不能超过物理核
    max_safe = physical

    # 规则 2：最少 1 核，如果requested_cores为None则使用默认值
    if requested_cores is None:
        requested = max(1, os.cpu_count() or 1)
    else:
        requested = max(1, int(requested_cores))

    # 规则 3：最终裁决
    final_cores = min(requested, max_safe)

    return final_cores

def train_model(
    model_type: str,
    dataset_path: str,
    epochs: int,
    batch_size: int,
    image_size: int,
    task_type: str = 'detect',  # 任务类型: detect, segment, pose, obb
    device_type: str = 'auto',
    gpu_memory: Optional[int] = None,
    gpu_index: int = 0,
    gpu_indices: Optional[List[int]] = None,
    auto_select_gpu: bool = False,
    ascend_memory: Optional[int] = None,
    ascend_index: int = 0,
    **kwargs
) -> Path:
    """
    训练模型的主函数
    """
    # 获取设备配置
    device_info = DeviceManager.get_device_info(
        device_type=device_type,
        gpu_memory=gpu_memory,
        gpu_index=gpu_index,
        gpu_indices=gpu_indices,
        auto_select_gpu=auto_select_gpu,
        ascend_memory=ascend_memory,
        ascend_index=ascend_index
    )

    # 打印设备信息
    if device_info['device_type'] == 'cpu':
        print(f"\n=== 使用 CPU 训练，线程数: {device_info['cpu_cores']} ===")
    elif device_info['device_type'] == 'gpu':
        print(f"\n=== 使用 GPU 训练，显存限制: {device_info['gpu_memory']}MB ===")
    elif device_info['device_type'] == 'ascend':
        print(f"\n=== 使用 昇腾NPU 训练，内存限制: {device_info['ascend_memory']}MB ===")

    # 配置训练参数
    train_args = {
        'model': model_type,
        'data': dataset_path,
        'epochs': epochs,
        'batch': batch_size,
        'imgsz': image_size,
        'task': task_type,  # 使用指定的任务类型
        **kwargs
    }
    
    # 设置设备参数
    if device_info['device_type'] == 'gpu':
        # 处理自动选择GPU
        if device_info.get('auto_select_gpu', False):
            # 使用-1表示自动选择最空闲的GPU
            train_args['device'] = [-1] if len(device_info.get('available_gpus', [])) > 1 else -1
        # 处理多GPU训练
        elif 'gpu_indices' in device_info and device_info['gpu_indices']:
            train_args['device'] = device_info['gpu_indices']
        else:
            # 单GPU训练
            train_args['device'] = device_info['device']
    else:
        # 非GPU设备
        train_args['device'] = device_info['device']

    # 开始训练
    try:
        from ultralytics import YOLO
        model = YOLO(model_type)

        # 如果是昇腾NPU设备，需要进行特殊处理
        if device_info['device_type'] == 'ascend':
            # 这里需要根据实际的昇腾NPU API进行实现
            try:
                import torch_npu
                # 设置环境变量
                os.environ['ASCEND_VISIBLE_DEVICES'] = str(device_info['ascend_index'])
                # 其他昇腾NPU特定的设置
                # ...
            except ImportError:
                print("\n=== 警告: 无法导入torch_npu，将尝试使用其他设备 ===")
                # 回退到CPU
                train_args['device'] = 'cpu'

        # 执行训练
        results = model.train(**train_args)

        # 返回训练后的模型路径
        return Path(results.save_dir) / 'weights' / 'best.pt'
    except Exception as e:
        print(f"\n=== 训练过程中出现错误: {str(e)} ===")
        raise

def create_training_task(
    db: Session,
    name: str,
    dataset_id: Optional[str] = None,
    local_dataset_path: Optional[str] = None,
    model_id: Optional[str] = None,
    parameters: Dict[str, Any] = None,
    hardware_config: Optional[Dict[str, Any]] = None
) -> TrainingTask:
    """
    创建训练任务
    支持使用注册数据集或本地数据集路径
    """
    # 初始化参数
    if parameters is None:
        parameters = {}

    # 检查数据集参数
    if dataset_id:
        # 使用注册数据集
        db_dataset = dataset.get(db, id=dataset_id)
        if not db_dataset:
            raise HTTPException(
                status_code=404,
                detail="Dataset not found",
            )
        # 将数据集路径添加到参数中
        parameters["dataset_path"] = str(Path(db_dataset.path) / "dataset.yaml")
    elif local_dataset_path:
        # 使用本地数据集路径
        dataset_path = Path(local_dataset_path)
        if not dataset_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"本地数据集地址'{local_dataset_path}' 不存在",
            )

        # 检查并创建必要的目录结构
        train_images_dir = dataset_path / "train" / "images"
        val_images_dir = dataset_path / "val" / "images"
        test_images_dir = dataset_path / "test" / "images"
        train_labels_dir = dataset_path / "train" / "labels"
        val_labels_dir = dataset_path / "val" / "labels"
        test_labels_dir = dataset_path / "test" / "labels"
        classes_file = dataset_path / "classes.txt"
        dataset_yaml_file = dataset_path / "dataset.yaml"

        # 创建必要的目录
        os.makedirs(train_images_dir, exist_ok=True)
        os.makedirs(val_images_dir, exist_ok=True)
        os.makedirs(test_images_dir, exist_ok=True)
        os.makedirs(train_labels_dir, exist_ok=True)
        os.makedirs(val_labels_dir, exist_ok=True)
        os.makedirs(test_labels_dir, exist_ok=True)

        # 创建默认的classes.txt文件（如果不存在）
        if not classes_file.exists():
            with open(classes_file, "w", encoding="utf-8") as f:
                f.write("object\n")

        # 创建或更新dataset.yaml文件
        classes = []
        try:
            with open(classes_file, "r", encoding="utf-8") as f:
                classes = [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            print(f"Error reading classes file: {e}")
            classes = ["object"]

        # 如果类别列表为空，使用默认类别
        if not classes:
            classes = ["object"]
            with open(classes_file, "w", encoding="utf-8") as f:
                f.write("object\n")

        # 创建或更新dataset.yaml文件
        dataset_yaml = {
            "path": str(dataset_path),
            "train": "train/images",
            "val": "val/images",
            "test": "test/images",
            "nc": len(classes),
            "names": classes
        }

        try:
            import yaml
            with open(dataset_yaml_file, "w", encoding="utf-8") as f:
                yaml.dump(dataset_yaml, f, default_flow_style=False)
        except Exception as e:
            print(f"Error creating dataset.yaml: {e}")
            # 备用方法
            with open(dataset_yaml_file, "w", encoding="utf-8") as f:
                f.write(f"path: {str(dataset_path)}\n")
                f.write("train: train/images\n")
                f.write("val: val/images\n")
                f.write("test: test/images\n")
                f.write(f"nc: {len(classes)}\n")
                f.write(f"names: {str(classes)}\n")

        # 将数据集路径添加到参数中
        parameters["dataset_path"] = str(dataset_yaml_file)
    else:
        raise HTTPException(
            status_code=400,
            detail="Either dataset_id or local_dataset_path must be provided",
        )

    # 检查模型是否存在（如果提供）
    if model_id:
        db_model = model.get(db, id=model_id)
        if not db_model:
            raise HTTPException(
                status_code=404,
                detail="模型未找到",
            )

    # 处理硬件配置中的自动选择GPU选项
    processed_hardware_config = hardware_config.copy() if hardware_config else {}
    
    # 如果启用了自动选择GPU，确保相关参数正确设置
    if processed_hardware_config.get('auto_select_gpu', False):
        # 确保GPU索引为-1表示自动选择
        processed_hardware_config['gpu_index'] = -1
        # 显存设置为-1表示自动
        if processed_hardware_config.get('gpu_memory') == '自动':
            processed_hardware_config['gpu_memory'] = -1
    
    # 创建训练任务
    task_in = TrainingTaskCreate(
        name=name,
        dataset_id=dataset_id,  # 如果使用本地数据集，这里会是None
        model_id=model_id,
        parameters=parameters,
        hardware_config=processed_hardware_config
    )

    return training_task.create(db, obj_in=task_in)

def get_training_task(db: Session, task_id: str) -> TrainingTask:
    """
    获取训练任务
    """
    # 验证task_id是否为有效的UUID格式
    if not is_valid_uuid(task_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid task ID format. Expected a valid UUID.",
        )
    
    db_task = training_task.get(db, id=task_id)
    if not db_task:
        raise HTTPException(
            status_code=404,
            detail="Training task not found",
        )
    return db_task

def get_training_tasks(db: Session, skip: int = 0, limit: int = 100) -> List[TrainingTask]:
    """
    获取所有训练任务
    """
    return training_task.get_multi(db, skip=skip, limit=limit)

def delete_training_task(db: Session, task_id: str) -> TrainingTask:
    """
    删除训练任务
    """
    # 验证task_id是否为有效的UUID格式
    if not is_valid_uuid(task_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid task ID format. Expected a valid UUID.",
        )
    
    db_task = training_task.get(db, id=task_id)
    if not db_task:
        raise HTTPException(
            status_code=404,
            detail="Training task not found",
        )

    # 如果任务正在运行，先停止它
    if db_task.status in ["running", "training", "downloading_model", "pending"]:
        try:
            stop_training(db, task_id)
        except Exception as e:
            print(f"停止训练任务失败: {e}")

    # 删除任务相关文件
    try:
        # 删除输出目录
        if db_task.parameters and "output_dir" in db_task.parameters:
            output_dir = resolve_stored(db_task.parameters["output_dir"])
            if output_dir:
                output_path = Path(output_dir)
                if output_path.exists():
                    import shutil
                    shutil.rmtree(output_path)

        # 删除TensorBoard日志
        if db_task.tensorboard_path:
            tensorboard_path = Path(db_task.tensorboard_path)
            if tensorboard_path.exists():
                import shutil
                shutil.rmtree(tensorboard_path)
    except Exception as e:
        print(f"Error deleting task files: {e}")

    # 删除数据库记录
    return training_task.remove(db, id=task_id)

def start_training(db: Session, task_id: str) -> TrainingTask:
    """
    启动训练任务
    """
    # 验证task_id是否为有效的UUID格式
    if not is_valid_uuid(task_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid task ID format. Expected a valid UUID.",
        )
    
    db_task = training_task.get(db, id=task_id)
    if not db_task:
        raise HTTPException(
            status_code=404,
            detail="训练任务未找到",
        )

    # 检查任务状态
    if db_task.status in ["running", "training", "downloading_model"]:
        raise HTTPException(
            status_code=400,
            detail="正在训练中",
        )

    # Get model if provided
    weights_path = ""
    if db_task.model_id:
        db_model = model.get(db, id=db_task.model_id)
        if not db_model:
            raise HTTPException(
                status_code=404,
                detail="模型未找到",
            )
        weights_path = db_model.path

    # 更新任务状态
    db_task = training_task.update(db, db_obj=db_task, obj_in={
        "status": "pending",
        "start_time": datetime.now(),
        "end_time": None
    })

    # 准备训练参数
    model_type = db_task.parameters.get("model_type", "yolov8n")
    epochs = db_task.parameters.get("epochs", 10)
    batch_size = db_task.parameters.get("batch_size", 16)
    img_size = db_task.parameters.get("img_size", 640)

    # 获取数据集路径
    dataset_yaml = None

    # 如果有数据集ID，使用注册数据集
    if db_task.dataset_id:
        db_dataset = dataset.get(db, id=db_task.dataset_id)
        if not db_dataset:
            raise HTTPException(
                status_code=404,
                detail="数据集未找到",
            )
        dataset_yaml = Path(db_dataset.path) / "dataset.yaml"
    # 如果没有数据集ID，使用参数中的数据集路径
    elif "dataset_path" in db_task.parameters:
        dataset_yaml = Path(resolve_stored(db_task.parameters["dataset_path"]))
    else:
        raise HTTPException(
            status_code=400,
            detail="未指定用于训练的数据集",
        )

    # 检查数据集YAML文件是否存在
    if not dataset_yaml.exists():
        raise HTTPException(
            status_code=404,
            detail=f"数据集yaml文件未找到: {dataset_yaml}",
        )

    # 创建输出目录
    output_dir = os.path.join(settings.STATIC_DIR, "models", f"training_{task_id}")
    os.makedirs(output_dir, exist_ok=True)

    # 创建TensorBoard日志目录
    tensorboard_dir = os.path.join(settings.TENSORBOARD_LOGS_DIR, str(task_id))
    os.makedirs(tensorboard_dir, exist_ok=True)

    # 启动TensorBoard
    from app.services.tensorboard_service import tensorboard_manager

    # 确保TensorBoard已启动
    if not tensorboard_manager.is_available():
        if tensorboard_manager.start():
            print(f"TensorBoard已启动，可访问: {tensorboard_manager.get_url()}")
        else:
            print("TensorBoard启动失败，请检查日志")
    else:
        print(f"TensorBoard已在运行，可访问: {tensorboard_manager.get_url()}")

    # 设置训练参数
    epochs = db_task.parameters.get("epochs", 10)
    batch_size = db_task.parameters.get("batch_size", 16)
    model_type = db_task.parameters.get("model_type", "yolov8n")

    # 处理图像大小参数
    img_size = db_task.parameters.get("img_size", 640)

    # 检查是否启用矩形训练
    rect_training = db_task.parameters.get("rect", False)

    # 获取硬件配置
    hardware_config = db_task.hardware_config or {}
    device_type = hardware_config.get("device_type", "cpu")
    raw_cpu_cores = hardware_config.get("cpu_cores", os.cpu_count())
    cpu_cores = resolve_cpu_cores(raw_cpu_cores)
    # 更新硬件配置，确保使用经过裁决的CPU核心数
    hardware_config["cpu_cores"] = cpu_cores
    gpu_memory = hardware_config.get("gpu_memory", 4096)  # 默认 4GB
    memory_limit = hardware_config.get("memory", 8192)  # 默认 8GB

    # 检查模型文件是否存在
    if weights_path and os.path.exists(weights_path):
        model_file = Path(weights_path)
        print(f"\n=== 使用用户上传的模型文件: {model_file} ===")
    else:
        # 如果指定了模型文件但不存在，记录错误
        if weights_path:
            print(f"\n=== 警告: 用户指定的模型文件不存在: {weights_path}, 将使用默认模型 ===")

        try:
            model_file = resolve_base_weights(model_type)
        except ValueError as e:
            training_task.update(db, db_obj=db_task, obj_in={"status": "failed", "end_time": datetime.now()})
            raise HTTPException(status_code=400, detail=str(e))

        # 如果模型文件不存在，则下载
        if not model_file.exists():
            print(f"\n=== 模型文件不存在，将下载: {model_file} ===")

            # 更新任务状态为下载模型
            db_task = training_task.update(db, db_obj=db_task, obj_in={
                "status": "downloading_model"
            })

            try:
                download_base_weights(model_file)
                print(f"\n=== 模型下载完成: {model_file} ===")
            except Exception as e:
                print(f"\n=== 模型下载失败: {e} ===")
                # 更新任务状态为失败
                db_task = training_task.update(db, db_obj=db_task, obj_in={
                    "status": "failed",
                    "end_time": datetime.now()
                })
                raise HTTPException(
                    status_code=500,
                    detail=f"Error downloading model: {str(e)}",
                )

    # 确保路径是绝对路径
    dataset_yaml_abs = Path(dataset_yaml).absolute()
    output_dir_abs = Path(output_dir).absolute()
    model_file_abs = model_file.absolute()

    # 创建训练脚本
    script_path = os.path.join(tensorboard_dir, "train_script.py")

    # 使用模板文件生成脚本内容
    template_path = os.path.join(settings.BASE_DIR, 'app', 'templates', 'train_script_template.py')
    with open(template_path, 'r', encoding='utf-8') as f:
        script_content = f.read()

    # 获取任务类型，默认为'detect'
    task_type = db_task.parameters.get('task_type', 'detect')
    
    # 格式化脚本内容
    script_content = script_content.format(
        cpu_cores,  # 为模板开头的CPU核心数设置添加的参数
        os.path.join(settings.BASE_DIR, 'app', 'static', 'fonts', 'Arial.Unicode.ttf'),
        device_type,
        gpu_memory,
        memory_limit,
        model_type,
        dataset_yaml_abs,
        epochs,
        batch_size,
        img_size,
        rect_training,
        output_dir_abs,
        model_file_abs,
        task_type
    )

    # 修改双花括号为单花括号，因为在这里我们不需要转义
    script_content = script_content.replace("train_args = {{", "train_args = {")
    script_content = script_content.replace("}}", "}")

    # 额外的 Ultralytics 训练参数（如流水线传入的 patience），只接受白名单内、类型正确的值
    extra_train_args = sanitize_extra_train_args(db_task.parameters.get("extra_train_args"))
    if extra_train_args:
        marker = "        # 如果启用矩形训练，添加rect参数"
        if marker in script_content:
            script_content = script_content.replace(
                marker, f"        train_args.update({extra_train_args!r})\n{marker}", 1)
        else:
            print("\n=== 警告: 训练脚本模板中找不到插入点，额外训练参数未生效 ===")

    # 添加多GPU支持
    gpu_indices = hardware_config.get("gpu_indices", None)
    if gpu_indices and isinstance(gpu_indices, list):
        # 设置GPU索引环境变量
        gpu_indices_str = ",".join(str(idx) for idx in gpu_indices)
        script_content = script_content.replace(
            "os.environ['ULTRALYTICS_TENSORBOARD'] = '1'", 
            f"os.environ['ULTRALYTICS_TENSORBOARD'] = '1'\n        os.environ['GPU_INDICES'] = '{gpu_indices_str}'"
        )

    # 写入脚本文件
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    # 更新任务状态为训练中
    db_task = training_task.update(db, db_obj=db_task, obj_in={
        "status": "training",
        "parameters": {
            **db_task.parameters,
            "output_dir": output_dir
        },
        "tensorboard_path": tensorboard_dir
    })

    # 创建日志文件
    log_file_path = os.path.join(tensorboard_dir, "training_log.txt")
    # 使用utf-8编码写入日志文件，以确保中文显示正确
    log_file = open(log_file_path, "w", encoding="utf-8", errors="replace")

    # 启动训练进程
    print(f"\n=== 等待训练进程启动... ===")
    try:
        # 显式传递环境变量，确保子进程环境一致性
        env = _training_subprocess_env()
        
        # 如果是昇腾NPU设备，添加昇腾相关环境变量
        if device_type == 'ascend' or device_type == 'npu':
            # 如果用户已经在系统环境里配好了，不覆盖
            
            # 1. 处理 ASCEND_HOME (CANN 根目录)
            if 'ASCEND_HOME' not in os.environ:
                env['ASCEND_HOME'] = '/usr/local/Ascend/ascend-toolkit/latest'
            
            # 2. 处理运行时的关键变量 (LD_LIBRARY_PATH 等通常在用户的 set_env.sh 里)
            # 提示：如果用户执行过 source /path/to/ascend/set_env.sh，
            # 那么 os.environ.copy() 已经包含了所有的库路径。
            
            # 3. 必须注入的动态变量 (因为这是前端用户在界面选的，必须由代码控制)
            # 就算用户在系统里设了 DEVICE_ID=0，但如果他在网页选了 NPU 1，
            # 这里的代码必须强制覆盖为 1，否则点击就没意义了。
            ascend_idx = str(hardware_config.get('ascend_index', '0'))
            env['ASCEND_VISIBLE_DEVICES'] = ascend_idx
            env['DEVICE_ID'] = ascend_idx
            
            # 4. 协议实现 (Ultralytics 在 NPU 上建议设置这个)
            env['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'cpp'
        
        training_process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=log_file,
            stderr=log_file,
            text=True,
            cwd=os.getcwd(),  # 使用当前工作目录
            env=env  # 显式传递环境变量
        )

        # 等待一段时间，检查进程是否立即退出
        time.sleep(2)
        return_code = training_process.poll()

        if return_code is not None:
            # 进程已退出，获取错误信息
            _, error_message = training_process.communicate()

            # 更新任务状态为失败
            db_task = training_task.update(db, db_obj=db_task, obj_in={
                "status": "failed",
                "end_time": datetime.now()
            })

            raise Exception(f"训练中断 {return_code}. 错误信息: {error_message}")

        # 保存进程ID
        db_task = training_task.update(db, db_obj=db_task, obj_in={
            "process_id": str(training_process.pid)
        })

        print(f"\n=== 训练进程已启动，PID: {training_process.pid} ===")

        # 启动一个线程来监控训练进程的状态
        monitor_thread = threading.Thread(
            target=monitor_training_process,
            args=(training_process, task_id),
            name=f"train-monitor-{task_id}",
        )
        monitor_thread.daemon = True
        monitor_thread.start()

        return db_task
    except Exception as e:
        # 更新任务状态为失败
        db_task = training_task.update(db, db_obj=db_task, obj_in={
            "status": "failed",
            "end_time": datetime.now()
        })

        raise HTTPException(
            status_code=500,
            detail=f"Error starting training process: {str(e)}",
        )

def stop_training(db: Session, task_id: str) -> TrainingTask:
    """
    停止训练任务
    """
    # 验证task_id是否为有效的UUID格式
    if not is_valid_uuid(task_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid task ID format. Expected a valid UUID.",
        )
    
    db_task = training_task.get(db, id=task_id)
    if not db_task:
        raise HTTPException(
            status_code=404,
            detail="训练任务未找到",
        )

    # 检查任务状态
    if db_task.status not in ["running", "training", "downloading_model", "pending"]:
        raise HTTPException(
            status_code=400,
            detail="训练未开始",
        )

    # 尝试终止进程
    if db_task.process_id:
        try:
            pid = int(db_task.process_id)

            # 在Windows上使用taskkill
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], check=False)
            # 在Unix/Linux上使用kill
            else:
                try:
                    import signal
                    os.kill(pid, signal.SIGTERM)
                except ImportError:
                    # 如果无法导入signal，尝试使用subprocess
                    subprocess.run(['kill', str(pid)], check=False)

            print(f"\n=== 已终止训练进程，PID: {pid} ===")
        except Exception as e:
            print(f"停止训练任务出错: {e}")

    # 检查是否有最新的检查点文件
    last_checkpoint = None
    if db_task.parameters and "output_dir" in db_task.parameters:
        output_dir = resolve_stored(db_task.parameters["output_dir"])
        if output_dir:
            # 检查可能的检查点路径
            possible_weights_dirs = [
                os.path.join(output_dir, "exp", "weights"),  # 标准路径
                os.path.join(output_dir, "weights")          # 另一种可能的路径
            ]

            # 尝试每个可能的路径
            for weights_dir in possible_weights_dirs:
                if os.path.exists(weights_dir):
                    print(f"\n=== 检查检查点目录: {weights_dir} ===")
                    # 查找最新的检查点文件
                    checkpoint_files = [f for f in os.listdir(weights_dir) if f.endswith(".pt") and not f.startswith("best")]
                    if checkpoint_files:
                        # 按文件名排序，获取最新的检查点
                        checkpoint_files.sort()
                        last_checkpoint = os.path.join(weights_dir, checkpoint_files[-1])
                        print(f"\n=== 找到最新检查点: {last_checkpoint} ===")
                        break  # 找到检查点后退出循环

            # 如果上面的路径都没有找到检查点，尝试直接在输出目录下查找
            if not last_checkpoint:
                # 直接在输出目录下查找所有pt文件
                for root, _, files in os.walk(output_dir):
                    pt_files = [f for f in files if f.endswith(".pt") and not f.startswith("best")]
                    if pt_files:
                        pt_files.sort()
                        last_checkpoint = os.path.join(root, pt_files[-1])
                        print(f"\n=== 在目录{root} 中找到检查点: {last_checkpoint} ===")
                        break

    # 更新任务状态为已取消
    update_data = {
        "status": "cancelled",
        "end_time": datetime.now()
    }

    # 如果有最新的检查点，更新last_checkpoint字段
    if last_checkpoint:
        update_data["last_checkpoint"] = last_checkpoint

    db_task = training_task.update(db, db_obj=db_task, obj_in=update_data)

    return db_task

def resume_training(db: Session, task_id: str) -> TrainingTask:
    """
    恢复训练任务
    """
    # 验证task_id是否为有效的UUID格式
    if not is_valid_uuid(task_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid task ID format. Expected a valid UUID.",
        )
    
    # 获取训练任务
    db_task = training_task.get(db, id=task_id)
    if not db_task:
        raise HTTPException(
            status_code=404,
            detail="训练任务未找到",
        )

    # 检查任务状态
    if db_task.status not in ["completed", "failed", "cancelled", "interrupted"]:
        raise HTTPException(
            status_code=400,
            detail="只有中断、失败的任务才能继续训练",
        )

    # 检查输出目录
    if not db_task.parameters or "output_dir" not in db_task.parameters:
        raise HTTPException(
            status_code=400,
            detail="找不到输出目录",
        )

    output_dir = resolve_stored(db_task.parameters["output_dir"])
    if not output_dir or not os.path.exists(output_dir):
        raise HTTPException(
            status_code=400,
            detail="输出目录不存在",
        )

    print(f"\n=== 使用YOLOv8内置恢复训练机制，输出目录 {output_dir} ===")

    # 更新任务状态
    db_task = training_task.update(db, db_obj=db_task, obj_in={
        "status": "pending",
        "start_time": datetime.now(),
        "end_time": None
    })

    # 获取数据集路径
    dataset_yaml = None

    # 如果有数据集ID，使用注册数据集
    if db_task.dataset_id:
        db_dataset = dataset.get(db, id=db_task.dataset_id)
        if not db_dataset:
            raise HTTPException(
                status_code=404,
                detail="Dataset not found",
            )
        dataset_yaml = Path(db_dataset.path) / "dataset.yaml"
    # 如果没有数据集ID，使用参数中的数据集路径
    elif "dataset_path" in db_task.parameters:
        dataset_yaml = Path(resolve_stored(db_task.parameters["dataset_path"]))
    else:
        raise HTTPException(
            status_code=400,
            detail="未指定用于训练的数据集",
        )

    # 检查数据集YAML文件是否存在
    if not dataset_yaml.exists():
        raise HTTPException(
            status_code=404,
            detail=f"yaml文件未找到: {dataset_yaml}",
        )

    # 准备训练参数
    model_type = db_task.parameters.get("model_type", "yolov8n")
    epochs = db_task.parameters.get("epochs", 10)
    batch_size = db_task.parameters.get("batch_size", 16)
    img_size = db_task.parameters.get("img_size", 640)

    # 使用原来的输出目录
    output_dir = resolve_stored(db_task.parameters.get("output_dir"))
    if not output_dir:
        output_dir = os.path.join(settings.STATIC_DIR, "models", f"training_{task_id}")
        os.makedirs(output_dir, exist_ok=True)

    # 使用原来的TensorBoard日志目录
    tensorboard_dir = db_task.tensorboard_path
    if not tensorboard_dir:
        tensorboard_dir = os.path.join(settings.TENSORBOARD_LOGS_DIR, str(task_id))
        os.makedirs(tensorboard_dir, exist_ok=True)

    # 启动TensorBoard
    from app.services.tensorboard_service import tensorboard_manager

    # 确保TensorBoard已启动
    if not tensorboard_manager.is_available():
        if tensorboard_manager.start():
            print(f"TensorBoard已启动，可访问: {tensorboard_manager.get_url()}")
        else:
            print("TensorBoard启动失败，请检查日志")
    else:
        print(f"TensorBoard已在运行，可访问: {tensorboard_manager.get_url()}")

    # 准备YOLOv8训练命令
    # dataset_yaml 已在前面获取

    # 检查是否启用矩形训练
    rect_training = db_task.parameters.get("rect", False)

    # 获取硬件配置
    hardware_config = db_task.hardware_config or {}
    device_type = hardware_config.get("device_type", "cpu")
    raw_cpu_cores = hardware_config.get("cpu_cores", os.cpu_count())
    cpu_cores = resolve_cpu_cores(raw_cpu_cores)
    # 更新硬件配置，确保使用经过裁决的CPU核心数
    hardware_config["cpu_cores"] = cpu_cores
    gpu_memory = hardware_config.get("gpu_memory", 4096)  # 默认 4GB
    memory_limit = hardware_config.get("memory", 8192)  # 默认 8GB

    # 确保路径是绝对路径
    dataset_yaml_abs = Path(dataset_yaml).absolute()
    output_dir_abs = Path(output_dir).absolute()

    # 获取原始模型路径（用于恢复训练）
    model_path = ""
    if db_task.model_id:
        db_model = model.get(db, id=db_task.model_id)
        if db_model:
            model_path = db_model.path

    # 在恢复训练时，优先使用检查点文件
    last_checkpoint = getattr(db_task, 'last_checkpoint', None)
    if last_checkpoint and os.path.exists(last_checkpoint):
        # 使用检查点文件进行恢复训练
        model_file_abs = Path(last_checkpoint)
        print(f"\n=== 使用检查点文件进行恢复训练: {model_file_abs} ===")
    else:
        # 如果没有检查点文件，回退到原始模型文件
        model_file_abs = Path(model_path) if model_path else Path(model_type)
        print(f"\n=== 没有找到检查点文件，使用原始模型文件: {model_file_abs} ===")

    # 准备训练参数字典
    task_type = db_task.parameters.get('task_type', 'detect')
    train_args = {
        'data': str(dataset_yaml_abs),
        'epochs': epochs,
        'batch': batch_size,
        'imgsz': img_size,
        'task': task_type,  # 使用指定的任务类型
        'project': str(output_dir_abs),
        'name': 'exp',
        'exist_ok': True,
        'workers': 0,  # 禁用多进程数据加载，避免多进程问题
        'amp': False,  # 禁用自动混合精度，避免下载额外模型
        'resume': True  # 启用恢复训练
    }

    # 添加设备参数
    if device_type == 'gpu':
        # 检查是否有GPU索引环境变量
        gpu_indices = hardware_config.get("gpu_indices", None)
        if gpu_indices and isinstance(gpu_indices, list):
            # 使用指定的GPU索引
            gpu_list = [int(idx) for idx in gpu_indices]
            train_args['device'] = gpu_list
            print(f"\n=== 设置设备为多GPU: {gpu_list} ===")
        elif gpu_memory == -1:
            # 自动选择GPU，使用特殊值-1
            train_args['device'] = -1
            print("\n=== 设置设备为自动选择GPU ===")
        else:
            # 使用默认GPU设备
            train_args['device'] = 0
            print("\n=== 设置设备为GPU 0 ===")
    else:
        # 使用CPU设备
        train_args['device'] = 'cpu'
        print("\n=== 设置设备为CPU ===")

    # 如果启用矩形训练，添加rect参数
    if rect_training:
        train_args['rect'] = True
        print("\n=== 已启用矩形训练模型===")

    # 更新任务状态为训练中
    db_task = training_task.update(db, db_obj=db_task, obj_in={
        "status": "training",
        "parameters": {
            **db_task.parameters,
            "output_dir": output_dir,
            "resume": True
        },
        "tensorboard_path": tensorboard_dir
    })

    # 使用与start_training相同的日志文件路径
    log_file_path = os.path.join(tensorboard_dir, "training_log.txt")
    # 以追加模式续写同一个日志文件。编码必须与首次训练一致（UTF-8），
    # 原先这里用 GBK，续训后的日志在页面上中英文混杂地乱码
    log_file = open(log_file_path, "a", encoding="utf-8", errors="replace")

    print(f"\n=== 调用YOLO恢复训练... ===")
    
    # 构造要执行的Python代码
    python_code = f"""
import os
import sys
import torch

# ====== CPU 并行强制配置（最前）======
cpu_cores = {cpu_cores}

os.environ["OMP_NUM_THREADS"] = str(cpu_cores)
os.environ["MKL_NUM_THREADS"] = str(cpu_cores)
os.environ["OPENBLAS_NUM_THREADS"] = str(cpu_cores)
os.environ["NUMEXPR_NUM_THREADS"] = str(cpu_cores)

torch.set_num_threads(cpu_cores)
torch.set_num_interop_threads(cpu_cores)

print(f"[CPU CONFIG] cores={cpu_cores}")
# =====================================

from ultralytics import YOLO

# 设置环境变量
os.environ['ULTRALYTICS_SKIP_DOWNLOAD'] = '1'
os.environ['ULTRALYTICS_SKIP_AMP_CHECK'] = '1'
os.environ['ULTRALYTICS_TENSORBOARD'] = '1'

# 加载模型
model_file = r'{model_file_abs}'
print(f"加载模型: {{model_file}}")
model = YOLO(model_file)

# 训练参数
train_args = {train_args}

# 为CPU训练更新workers参数
if train_args.get('device') == 'cpu':
    train_args['workers'] = max(1, {cpu_cores} // 2)

print(f"开始恢复训练，参数: {{train_args}}")

# 开始训练
results = model.train(**train_args)

print("\\n训练完成")
print(f"结果摘要: {{results}}")
"""

    # 启动训练进程
    try:
        training_process = subprocess.Popen(
            [sys.executable, "-c", python_code],
            stdout=log_file,
            stderr=log_file,
            text=True,
            cwd=os.getcwd(),  # 使用当前工作目录
            env=_training_subprocess_env()
        )

        # 等待一段时间，检查进程是否立即退出
        time.sleep(2)
        return_code = training_process.poll()

        if return_code is not None:
            # 进程已退出，获取错误信息
            _, error_message = training_process.communicate()

            # 更新任务状态为失败
            db_task = training_task.update(db, db_obj=db_task, obj_in={
                "status": "failed",
                "end_time": datetime.now()
            })

            raise Exception(f"Resume training process exited immediately with code {return_code}. Error: {error_message}")

        # 保存进程ID
        db_task = training_task.update(db, db_obj=db_task, obj_in={
            "process_id": str(training_process.pid)
        })

        print(f"\n=== 继续训练进程已启动，PID: {training_process.pid} ===")

        # 与首次训练一样启动监控线程；原先续训没有监控，结束后状态一直停在 training
        monitor_thread = threading.Thread(
            target=monitor_training_process,
            args=(training_process, task_id),
            name=f"train-monitor-{task_id}",
        )
        monitor_thread.daemon = True
        monitor_thread.start()

        return db_task
    except Exception as e:
        # 更新任务状态为失败
        db_task = training_task.update(db, db_obj=db_task, obj_in={
            "status": "failed",
            "end_time": datetime.now()
        })

        raise HTTPException(
            status_code=500,
            detail=f"Error starting resume training process: {str(e)}",
        )

def get_training_logs(db: Session, task_id: str) -> Dict[str, Any]:
    """
    获取训练日志
    """
    db_task = training_task.get(db, id=task_id)
    if not db_task:
        raise HTTPException(
            status_code=404,
            detail="训练任务未找到",
        )

    # 检查TensorBoard日志目录
    if not db_task.tensorboard_path:
        return {
            "logs": "No logs available",
            "tensorboard_url": None
        }

    tensorboard_dir = Path(db_task.tensorboard_path)

    # 检查训练日志输出
    log_output = ""
    log_path = tensorboard_dir / "training_log.txt"

    # 如果日志文件不存在，尝试创建一个
    if not log_path.exists():
        try:
            # 检查进程是否在运行
            if db_task.process_id:
                pid = int(db_task.process_id)
                is_running = False

                # 在Windows上检查进程
                if os.name == 'nt':
                    import subprocess
                    try:
                        subprocess.check_output(f'tasklist /FI "PID eq {pid}"', shell=True)
                        output = subprocess.check_output(f'tasklist /FI "PID eq {pid}"', shell=True).decode()
                        if str(pid) in output:
                            is_running = True
                    except:
                        pass
                # 在Unix/Linux上检查进程
                else:
                    try:
                        # 尝试使用subprocess检查进程
                        result = subprocess.run(['ps', '-p', str(pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if result.returncode == 0:
                            is_running = True
                    except:
                        pass

                if is_running:
                    log_output = f"训练进程正在运行 (PID: {pid})，但尚未生成日志文件。请稍后再查看"
                else:
                    # 更新任务状态为失败
                    if db_task.status in ["running", "training", "downloading_model", "pending"]:
                        training_task.update(db, db_obj=db_task, obj_in={
                            "status": "failed",
                            "end_time": datetime.now()
                        })
                    log_output = "训练进程已结束，但未生成日志文件。可能是训练过程中出现了错误"
            else:
                log_output = "未找到训练日志文件，且没有关联的进程ID"
        except Exception as e:
            log_output = f"检查训练进程时出错: {e}"
    else:
        # 读取日志文件
        try:
            # 使用编码工具读取日志文件，支持跨平台编码兼容性
            from app.utils.encoding_utils import read_log_with_auto_encoding
            log_output = read_log_with_auto_encoding(log_path)
        except Exception as e:
            log_output = f"读取日志文件时出错: {e}"

    # 检查训练脚本输出（作为备用）
    script_path = tensorboard_dir / "train_script.py"
    if script_path.exists() and not log_output:
        try:
            with open(script_path, "r", encoding="utf-8", errors="replace") as f:
                script_content = f.read()
            log_output += "\n\n=== 训练脚本内容 ===\n" + script_content
        except Exception as e:
            log_output += f"\n\n读取训练脚本时出错 {e}"

    # 返回日志信息
    # 获取TensorBoard URL
    tensorboard_url = f"http://localhost:{settings.TENSORBOARD_PORT}"

    # 如果有输出目录，添加到URL
    if db_task.parameters and "output_dir" in db_task.parameters:
        output_dir = resolve_stored(db_task.parameters["output_dir"])
        if output_dir:
            # 从输出目录中提取任务ID
            task_id_part = os.path.basename(output_dir)
            if task_id_part.startswith("training_"):
                task_id = task_id_part.replace("training_", "")

                # 检查TensorBoard日志文件是否存在
                exp_dir = os.path.join(settings.MODELS_DIR, f"training_{task_id}/exp")

                # 检查目录是否存在
                if os.path.exists(exp_dir):
                    # 检查是否有events.out.tfevents文件
                    has_events_file = False
                    for file in os.listdir(exp_dir):
                        if file.startswith("events.out.tfevents"):
                            has_events_file = True
                            break

                    if has_events_file:
                        print(f"找到TensorBoard日志文件: {exp_dir}")
                    else:
                        print(f"警告: 目录存在但未找到TensorBoard日志文件: {exp_dir}")
                else:
                    print(f"警告: TensorBoard日志目录不存在: {exp_dir}")

                # 用 run 过滤把 URL 定位到本次任务。
                # 之前只返回根路径，TensorBoard 会把历史上所有训练的曲线一起画出来，
                # 而 run 名是 training_{uuid}\exp 这种，肉眼分不出哪条是刚跑的，
                # 看上去就像"打开还是上次的数据"。
                # regexInput 是 TensorBoard 前端的 run 过滤正则（hash 参数，不发给服务端）。
                tensorboard_url = f"{tensorboard_url}/#scalars&regexInput=training_{task_id}"

                # 打印日志，帮助调试
                print(f"生成的TensorBoard URL: {tensorboard_url}")
                print(f"对应的本地路径: {exp_dir}")

    return {
        "logs": log_output,
        "tensorboard_url": tensorboard_url
    }

def get_training_results(db: Session, task_id: str) -> Dict[str, Any]:
    """
    获取训练结果
    """
    # 验证task_id是否为有效的UUID格式
    if not is_valid_uuid(task_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid task ID format. Expected a valid UUID.",
        )
    
    db_task = training_task.get(db, id=task_id)
    if not db_task:
        raise HTTPException(
            status_code=404,
            detail="Training task not found",
        )

    # 检查任务状态
    if db_task.status != "completed":
        return {
            "status": db_task.status,
            "message": "Training task is not completed",
            "results": None
        }

    # 检查输出模型
    if not db_task.output_model_id:
        return {
            "status": "completed",
            "message": "Training completed but no output model found",
            "results": None
        }

    # 获取输出模型
    db_model = model.get(db, id=db_task.output_model_id)
    if not db_model:
        return {
            "status": "completed",
            "message": "Training completed but output model not found in database",
            "results": None
        }

    # 返回结果
    return {
        "status": "completed",
        "message": "Training completed successfully",
        "results": {
            "model_id": str(db_model.id),
            "model_name": db_model.name,
            "model_path": db_model.path
        }
    }