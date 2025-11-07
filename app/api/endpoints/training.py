from typing import List, Optional, Dict, Any
import os
import subprocess
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import torch

from app.db.session import get_db
from app.schemas.training_task import TrainingTask
from app.services import training_service
from app.services.training_service import DeviceManager
from app.services.ascend_service import AscendDeviceManager
from app.services import model_service

router = APIRouter()

class TrainingRequest(BaseModel):
    model_type: str
    dataset_path: str
    epochs: int
    batch_size: int
    image_size: int
    device_type: str = 'auto'  # 'auto', 'cpu', 或 'gpu'
    gpu_memory: Optional[int] = None  # GPU显存限制（MB）

@router.post("/train")
async def start_training_api(request: TrainingRequest):
    try:
        from app.services.training_service import train_model

        result_path = train_model(
            model_type=request.model_type,
            dataset_path=request.dataset_path,
            epochs=request.epochs,
            batch_size=request.batch_size,
            image_size=request.image_size,
            device_type=request.device_type,
            gpu_memory=request.gpu_memory
        )

        return {"status": "success", "model_path": str(result_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
def create_training_task(
    name: str = Body(...),
    dataset_id: Optional[str] = Body(None),
    local_dataset_path: Optional[str] = Body(None),
    model_id: Optional[str] = Body(None),
    parameters: Dict[str, Any] = Body(...),
    hardware_config: Optional[Dict[str, Any]] = Body(None),
    db: Session = Depends(get_db)
):
    """
    Create a new training task
    """
    # 检查数据集参数
    if not dataset_id and not local_dataset_path:
        raise HTTPException(status_code=400, detail="必须提供 dataset_id 或 local_dataset_path")

    # 初始化设备信息
    gpu_info = None
    ascend_info = None
    recommended_memory = None

    # 如果选择了GPU设备，自动获取GPU信息
    if hardware_config and hardware_config.get("device_type") == "gpu":
        # 获取GPU信息
        gpus = DeviceManager.get_available_gpus()

        # 如果有可用的GPU
        if gpus:
            # 检查是否指定了GPU ID
            gpu_index = hardware_config.get("gpu_index", 0)

            # 查找指定的GPU
            for gpu in gpus:
                if gpu.get("index", 0) == gpu_index:
                    gpu_info = gpu
                    break

            # 如果没有找到指定的GPU，使用第一个GPU
            if not gpu_info and gpus:
                gpu_info = gpus[0]
                hardware_config["gpu_index"] = gpu_info.get("index", 0)
                print(f"指定的GPU ID {gpu_index} 不存在，使用GPU ID {hardware_config['gpu_index']}")

            if gpu_info:
                free_memory = gpu_info.get("memory_free", 0)

                if free_memory > 0:
                    # 计算推荐的显存设置（可用显存的80%）
                    recommended_memory = int(free_memory * 0.8)

                    # 如果没有设置显存限制，则使用推荐值
                    if not hardware_config.get("gpu_memory"):
                        hardware_config["gpu_memory"] = recommended_memory
                        print(f"自动设置GPU显存限制为: {hardware_config['gpu_memory']}MB")

    # 如果选择了昇腾NPU设备，自动获取昇腾NPU信息
    elif hardware_config and hardware_config.get("device_type") == "ascend":
        # 获取昇腾NPU信息
        ascends = AscendDeviceManager.get_available_ascends()

        # 如果有可用的昇腾NPU
        if ascends:
            # 检查是否指定了昇腾NPU ID
            ascend_index = hardware_config.get("ascend_index", 0)

            # 查找指定的昇腾NPU
            for ascend in ascends:
                if ascend.get("index", 0) == ascend_index:
                    ascend_info = ascend
                    break

            # 如果没有找到指定的昇腾NPU，使用第一个昇腾NPU
            if not ascend_info and ascends:
                ascend_info = ascends[0]
                hardware_config["ascend_index"] = ascend_info.get("index", 0)
                print(f"指定的昇腾NPU ID {ascend_index} 不存在，使用昇腾NPU ID {hardware_config['ascend_index']}")

            if ascend_info:
                free_memory = ascend_info.get("memory_free", 0)

                if free_memory > 0:
                    # 计算推荐的内存设置（可用内存的80%）
                    recommended_memory = int(free_memory * 0.8)

                    # 如果没有设置内存限制，则使用推荐值
                    if not hardware_config.get("ascend_memory"):
                        hardware_config["ascend_memory"] = recommended_memory
                        print(f"自动设置昇腾NPU内存限制为: {hardware_config['ascend_memory']}MB")

    # 创建训练任务
    task = training_service.create_training_task(
        db=db,
        name=name,
        dataset_id=dataset_id,
        local_dataset_path=local_dataset_path,
        model_id=model_id,
        parameters=parameters,
        hardware_config=hardware_config
    )

    # 将任务转换为字典，以便添加额外信息
    # 兼容Pydantic v1和v2的方式
    try:
        # Pydantic v2
        from app.schemas.training_task import TrainingTask as TrainingTaskSchema
        response_data = TrainingTaskSchema.model_validate(task).model_dump()
    except Exception:
        # 尝试其他方式
        try:
            # 另一种Pydantic v2方式
            from app.schemas.training_task import TrainingTask as TrainingTaskSchema
            response_data = TrainingTaskSchema.model_validate(task.__dict__).model_dump()
        except Exception:
            # 回退到Pydantic v1
            from app.schemas.training_task import TrainingTask as TrainingTaskSchema
            response_data = {k: v for k, v in task.__dict__.items() if not k.startswith('_')}

    # 添加GPU信息到响应中
    if gpu_info:
        response_data["gpu_info"] = {
            "has_gpu": True,
            "gpu_name": gpu_info.get("name", ""),
            "total_memory": gpu_info.get("memory", 0),
            "used_memory": gpu_info.get("memory_used", 0),
            "free_memory": gpu_info.get("memory_free", 0),
            "recommended_memory": recommended_memory,
            "gpu_index": gpu_info.get("index", 0)
        }

    # 添加昇腾NPU信息到响应中
    if ascend_info:
        response_data["ascend_info"] = {
            "has_ascend": True,
            "ascend_name": ascend_info.get("name", ""),
            "total_memory": ascend_info.get("memory", 0),
            "used_memory": ascend_info.get("memory_used", 0),
            "free_memory": ascend_info.get("memory_free", 0),
            "recommended_memory": recommended_memory,
            "ascend_index": ascend_info.get("index", 0)
        }

    return response_data

@router.post("/{task_id}/start", response_model=TrainingTask)
def start_training(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Start a training task
    """
    return training_service.start_training(db=db, task_id=task_id)

@router.post("/{task_id}/resume", response_model=TrainingTask)
def resume_training(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Resume a stopped training task
    """
    return training_service.resume_training(db=db, task_id=task_id)

@router.get("/", response_model=List[TrainingTask])
def read_training_tasks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve training tasks
    """
    tasks = training_service.get_training_tasks(db, skip=skip, limit=limit)
    return tasks

@router.get("/all-gpus-info", response_model=Dict)
def get_all_gpus_info():
    """获取所有可用的GPU信息，用于前端显示和选择"""
    response = {
        "has_gpu": False,
        "gpus": [],
        "current_device": None
    }

    try:
        if torch.cuda.is_available():
            response["has_gpu"] = True
            gpu_count = torch.cuda.device_count()

            for i in range(gpu_count):
                props = torch.cuda.get_device_properties(i)
                free_memory, total_memory = torch.cuda.mem_get_info(i)
                used_memory = total_memory - free_memory

                # 添加display_name字段用于显示
                gpu_info = {
                    "index": i,
                    "name": props.name,
                    "display_name": f"GPU {i}: {props.name}",  # 添加这行
                    "total_memory": int(total_memory / (1024 * 1024)),
                    "used_memory": int(used_memory / (1024 * 1024)),
                    "free_memory": int(free_memory / (1024 * 1024)),
                    "recommended_memory": int(free_memory * 0.8 / (1024 * 1024))
                }
                response["gpus"].append(gpu_info)

            # 即使只有一个GPU也应该返回
            if gpu_count > 0:
                current_device_index = torch.cuda.current_device()
                response["current_device"] = {
                    "index": current_device_index,
                    "name": torch.cuda.get_device_name(current_device_index)
                }

    except Exception as e:
        print(f"获取GPU信息失败: {str(e)}")
        return {"error": f"获取GPU信息失败: {str(e)}"}

    return response

@router.get("/gpu-memory-info", response_model=Dict)
def get_gpu_memory_info():
    """获取GPU显存信息，专门用于前端显示"""
    response = {
        "has_gpu": False,
        "gpu_name": "",
        "total_memory": 0,
        "used_memory": 0,
        "free_memory": 0,
        "recommended_memory": 0
    }

    try:
        if torch.cuda.is_available():
            response["has_gpu"] = True
            # 使用第一个GPU
            free_memory, total_memory = torch.cuda.mem_get_info(0)
            used_memory = total_memory - free_memory

            response.update({
                "gpu_name": torch.cuda.get_device_name(0),
                "total_memory": int(total_memory / (1024 * 1024)),  # 转换为MB
                "used_memory": int(used_memory / (1024 * 1024)),
                "free_memory": int(free_memory / (1024 * 1024)),
                "recommended_memory": int(free_memory * 0.8 / (1024 * 1024))
            })

    except Exception as e:
        print(f"获取GPU信息失败: {str(e)}")
        return {"error": f"获取GPU信息失败: {str(e)}"}

    return response

@router.get("/{task_id}", response_model=TrainingTask)
def read_training_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific training task by id"""
    task = training_service.get_training_task(db, task_id=task_id)
    return task

@router.post("/{task_id}/stop", response_model=TrainingTask)
def stop_training(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Stop a training task
    """
    return training_service.stop_training(db, task_id=task_id)

@router.get("/{task_id}/logs")
def get_training_logs(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the logs for a training task
    """
    return training_service.get_training_logs(db, task_id=task_id)

@router.get("/{task_id}/results")
def get_training_results(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the training results for a training task
    """
    return training_service.get_training_results(db, task_id=task_id)

@router.get("/{task_id}/tensorboard")
def get_tensorboard_url(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get the TensorBoard URL for a training task
    """
    # 导入TensorBoard管理器
    from app.services.tensorboard_service import tensorboard_manager

    # 确保TensorBoard服务正在运行
    if not tensorboard_manager.is_available():
        tensorboard_manager.start()

    logs_data = training_service.get_training_logs(db, task_id=task_id)

    # 获取原始TensorBoard URL
    tensorboard_url = logs_data["tensorboard_url"]

    # 替换localhost为当前请求的主机名
    if tensorboard_url and tensorboard_url.startswith("http://localhost:"):
        # 获取当前请求的主机名
        host = request.headers.get("host", "localhost")
        # 如果主机名包含端口，只取主机部分
        if ":" in host:
            host = host.split(":")[0]
        # 替换URL中的localhost
        tensorboard_url = tensorboard_url.replace("http://localhost:", f"http://{host}:")

    return {"url": tensorboard_url}

@router.get("/{task_id}/logs-folder")
def open_logs_folder(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    打开TensorBoard日志目录
    """
    # 获取训练任务
    task = training_service.get_training_task(db, task_id=task_id)

    # 检查任务是否存在
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")

    # 构建日志目录路径
    import json
    parameters = {}
    if hasattr(task, 'parameters') and task.parameters is not None:
        parameters = task.parameters if isinstance(task.parameters, dict) else {}
        # 如果parameters是字符串，尝试解析为JSON
        if isinstance(task.parameters, str):
            try:
                parameters = json.loads(task.parameters)
            except json.JSONDecodeError:
                parameters = {}
    
    if isinstance(parameters, dict) and "output_dir" in parameters:
        output_dir = parameters["output_dir"]
        exp_dir = os.path.join(str(output_dir), "exp")

        # 检查目录是否存在
        if os.path.exists(exp_dir):
            # 使用系统命令打开文件夹
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(exp_dir)
                else:  # Linux/Mac
                    subprocess.Popen(['xdg-open', exp_dir])

                return {"success": True, "path": exp_dir}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"打开日志目录失败: {str(e)}")
        else:
            raise HTTPException(status_code=404, detail="日志目录不存在")
    else:
        raise HTTPException(status_code=404, detail="训练任务没有输出目录信息")


@router.get("/{task_id}/logs/download")
def download_training_logs(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    下载训练日志文件
    """
    # 获取训练任务
    task = training_service.get_training_task(db, task_id=task_id)

    # 检查任务是否存在
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")

    # 检查TensorBoard日志目录
    tensorboard_path = None
    if hasattr(task, 'tensorboard_path'):
        tensorboard_path = str(task.tensorboard_path) if task.tensorboard_path is not None else None
    if not tensorboard_path:
        raise HTTPException(status_code=404, detail="日志文件不存在")

    # 构建日志文件路径
    from pathlib import Path
    tensorboard_dir = Path(tensorboard_path)
    log_path = tensorboard_dir / "training_log.txt"

    # 检查日志文件是否存在
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="日志文件不存在")

    # 返回日志文件下载响应
    return FileResponse(
        path=str(log_path),
        filename=f"training_logs_{task_id}.txt",
        media_type="text/plain"
    )

@router.post("/restart-tensorboard")
def restart_tensorboard():
    """
    重启TensorBoard服务
    """
    from app.services.tensorboard_service import tensorboard_manager

    # 重启TensorBoard服务
    success = tensorboard_manager.restart()

    if success:
        return {"success": True, "message": "TensorBoard服务已重启"}
    else:
        return {"success": False, "message": "TensorBoard服务重启失败"}

@router.delete("/{task_id}")
def delete_training_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a training task and its associated files
    """
    training_service.delete_training_task(db, task_id=task_id)
    return {"success": True, "message": "Training task deleted successfully"}

@router.get("/device-info")
def get_device_info():
    """获取设备信息，包括可用的GPU列表及其显存大小"""
    gpus = DeviceManager.get_available_gpus()
    ascends = AscendDeviceManager.get_available_ascends()
    recommended_memory = None
    current_device = None
    gpu_info = None
    ascend_info = None

    # 如果有可用的GPU
    if gpus:
        gpu_info = gpus[0]  # 使用第一个GPU的信息

        # 计算推荐的显存设置（可用显存的80%）
        free_memory = gpu_info.get("memory_free", 0)
        if free_memory > 0:
            recommended_memory = int(free_memory * 0.8)

        # 获取当前活跃的GPU设备
        try:
            if torch.cuda.is_available():
                current_device_index = torch.cuda.current_device()
                current_device = {
                    "index": current_device_index,
                    "name": torch.cuda.get_device_name(current_device_index)
                }
        except Exception as e:
            print(f"获取当前活跃GPU设备失败: {str(e)}")

    # 如果有可用的昇腾NPU
    if ascends:
        ascend_info = ascends[0]  # 使用第一个昇腾NPU的信息

    return {
        "gpus": gpus,
        "ascends": ascends,
        "has_cuda": torch.cuda.is_available(),
        "has_ascend": len(ascends) > 0,
        "recommended_memory": recommended_memory,
        "current_device": current_device,
        "gpu_info": gpu_info,
        "ascend_info": ascend_info
    }

class GPUMemoryValidationRequest(BaseModel):
    gpu_memory: int
    gpu_index: Optional[int] = 0

@router.post("/validate-gpu-memory")
def validate_gpu_memory(request: GPUMemoryValidationRequest):
    """验证GPU显存设置是否合理"""
    # 获取指定GPU的信息
    gpus = DeviceManager.get_available_gpus()

    # 初始化变量
    is_valid = False
    message = "GPU不可用"
    total_memory = 0
    free_memory = 0
    used_memory = 0
    recommended_memory = None
    gpu_name = ""
    has_gpu = False

    # 检查指定的GPU是否存在
    gpu_info = None
    for gpu in gpus:
        if gpu.get("index", 0) == request.gpu_index:
            gpu_info = gpu
            break

    if gpu_info and torch.cuda.is_available():
        has_gpu = True
        gpu_name = gpu_info.get("name", "")
        total_memory = gpu_info.get("memory", 0)
        free_memory = gpu_info.get("memory_free", 0)
        used_memory = gpu_info.get("memory_used", 0)

        # 计算推荐的显存设置（可用显存的80%）
        if free_memory > 0:
            recommended_memory = int(free_memory * 0.8)

        # 验证请求的显存是否合理
        if request.gpu_memory <= 0:
            is_valid = False
            message = f"请求的显存必须大于0MB"
        elif request.gpu_memory > total_memory:
            is_valid = False
            message = f"请求的显存({request.gpu_memory}MB)超过了GPU最大显存({total_memory}MB)"
        elif request.gpu_memory > free_memory:
            is_valid = False
            message = f"请求的显存({request.gpu_memory}MB)超过了当前可用显存({free_memory}MB)"
        elif recommended_memory and request.gpu_memory > recommended_memory:
            is_valid = False
            message = f"建议使用不超过{recommended_memory}MB显存（当前可用显存{free_memory}MB）"
        else:
            is_valid = True
            message = "显存设置有效"

    return {
        "valid": is_valid,
        "message": message,
        "total_memory": total_memory,
        "free_memory": free_memory,
        "used_memory": used_memory,
        "recommended_memory": recommended_memory,
        "gpu_name": gpu_name,
        "has_gpu": has_gpu,
        "gpu_index": request.gpu_index
    }

class AscendMemoryValidationRequest(BaseModel):
    ascend_memory: int
    ascend_index: Optional[int] = 0

@router.post("/validate-ascend-memory")
def validate_ascend_memory(request: AscendMemoryValidationRequest):
    """验证昇腾NPU内存设置是否合理"""
    # 验证请求的内存是否合理
    is_valid, message, total_memory = AscendDeviceManager.validate_ascend_memory(
        requested_memory=request.ascend_memory,
        ascend_index=request.ascend_index if request.ascend_index is not None else 0
    )

    # 获取昇腾NPU信息
    ascends = AscendDeviceManager.get_available_ascends()

    # 初始化变量
    free_memory = 0
    used_memory = 0
    recommended_memory = None
    ascend_name = ""
    has_ascend = False

    # 检查指定的昇腾NPU是否存在
    ascend_info = None
    for ascend in ascends:
        if ascend.get("index", 0) == request.ascend_index:
            ascend_info = ascend
            break

    if ascend_info:
        has_ascend = True
        ascend_name = ascend_info.get("name", "")
        total_memory = ascend_info.get("memory", 0)
        free_memory = ascend_info.get("memory_free", 0)
        used_memory = ascend_info.get("memory_used", 0)

        # 计算推荐的内存设置（可用内存的80%）
        if free_memory > 0:
            recommended_memory = int(free_memory * 0.8)

    return {
        "valid": is_valid,
        "message": message,
        "total_memory": total_memory,
        "free_memory": free_memory,
        "used_memory": used_memory,
        "recommended_memory": recommended_memory,
        "ascend_name": ascend_name,
        "has_ascend": has_ascend,
        "ascend_index": request.ascend_index
    }

@router.get("/ascend-info", response_model=Dict)
def get_ascend_info():
    """获取所有可用的昇腾NPU信息，用于前端显示和选择"""
    ascends = AscendDeviceManager.get_available_ascends()

    response = {
        "has_ascend": len(ascends) > 0,
        "ascends": [],
        "current_device": None
    }

    # 如果有可用的昇腾NPU，添加到响应中
    if ascends:
        for i, ascend in enumerate(ascends):
            # 添加display_name字段用于显示
            ascend_info = {
                "index": ascend.get("index", i),
                "name": ascend.get("name", f"Ascend NPU {i}"),
                "display_name": f"NPU {i}: {ascend.get('name', 'Unknown')}",
                "total_memory": ascend.get("memory", 0),
                "used_memory": ascend.get("memory_used", 0),
                "free_memory": ascend.get("memory_free", 0),
                "recommended_memory": ascend.get("recommended_memory", 0)
            }
            response["ascends"].append(ascend_info)

        # 设置当前设备为第一个昇腾NPU
        response["current_device"] = {
            "index": ascends[0].get("index", 0),
            "name": ascends[0].get("name", "Unknown")
        }

    return response

@router.get("/{task_id}/download-model/{model_type}")
def download_model_file(
    task_id: str,
    model_type: str,  # 'best' 或 'last'
    db: Session = Depends(get_db)
):
    """
    下载训练任务的模型文件 (best.pt 或 last.pt)
    """
    # 获取训练任务
    task = training_service.get_training_task(db, task_id=task_id)
    
    # 检查任务是否存在
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    
    # 检查任务是否已完成
    task_status = getattr(task, 'status', None)
    if task_status != "completed":
        raise HTTPException(status_code=400, detail="训练任务尚未完成")
    
    # 获取输出目录
    import json
    parameters = {}
    if hasattr(task, 'parameters') and task.parameters is not None:
        parameters = task.parameters if isinstance(task.parameters, dict) else {}
        # 如果parameters是字符串，尝试解析为JSON
        if isinstance(task.parameters, str):
            try:
                parameters = json.loads(task.parameters)
            except json.JSONDecodeError:
                parameters = {}
    
    if isinstance(parameters, dict) and "output_dir" in parameters:
        output_dir = parameters["output_dir"]
        exp_weights_dir = os.path.join(str(output_dir), "exp", "weights")
        
        # 确定模型文件路径
        if model_type == "best":
            model_file_path = os.path.join(exp_weights_dir, "best.pt")
            filename = f"{task.name}_best.pt"
        elif model_type == "last":
            model_file_path = os.path.join(exp_weights_dir, "last.pt")
            filename = f"{task.name}_last.pt"
        else:
            raise HTTPException(status_code=400, detail="无效的模型类型，必须是 'best' 或 'last'")
        
        # 检查模型文件是否存在
        if not os.path.exists(model_file_path):
            raise HTTPException(status_code=404, detail=f"模型文件不存在: {model_file_path}")
        
        # 返回文件下载响应
        return FileResponse(
            path=model_file_path,
            filename=filename,
            media_type="application/octet-stream"
        )
    else:
        raise HTTPException(status_code=404, detail="训练任务没有输出目录信息")


@router.post("/{task_id}/upload-model/{model_type}")
def upload_model_to_management(
    task_id: str,
    model_type: str,  # 'best' 或 'last'
    db: Session = Depends(get_db)
):
    """
    将训练任务的模型文件上传到模型管理
    """
    # 获取训练任务
    task = training_service.get_training_task(db, task_id=task_id)
    
    # 检查任务是否存在
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    
    # 检查任务是否已完成
    task_status = getattr(task, 'status', None)
    if task_status != "completed":
        raise HTTPException(status_code=400, detail="训练任务尚未完成")
    
    # 获取输出目录
    import json
    parameters = {}
    if hasattr(task, 'parameters') and task.parameters is not None:
        parameters = task.parameters if isinstance(task.parameters, dict) else {}
        # 如果parameters是字符串，尝试解析为JSON
        if isinstance(task.parameters, str):
            try:
                parameters = json.loads(task.parameters)
            except json.JSONDecodeError:
                parameters = {}
    
    if isinstance(parameters, dict) and "output_dir" in parameters:
        output_dir = parameters["output_dir"]
        exp_weights_dir = os.path.join(str(output_dir), "exp", "weights")
        
        # 确定模型文件路径
        if model_type == "best":
            model_file_path = os.path.join(exp_weights_dir, "best.pt")
            model_name = f"{task.name}_最佳模型"
        elif model_type == "last":
            model_file_path = os.path.join(exp_weights_dir, "last.pt")
            model_name = f"{task.name}_最后模型"
        else:
            raise HTTPException(status_code=400, detail="无效的模型类型，必须是 'best' 或 'last'")
        
        # 检查模型文件是否存在
        if not os.path.exists(model_file_path):
            raise HTTPException(status_code=404, detail=f"模型文件不存在: {model_file_path}")
        
        # 创建模型记录
        from app.schemas.model import ModelCreate
        from app.crud import model as model_crud
        
        # 准备模型数据
        model_data = ModelCreate(
            name=model_name,
            description=f"由训练任务 '{task.name}' 生成的{ '最佳' if model_type == 'best' else '最后' }模型",
            type="yolov8",  # 默认模型类型
            task="detect",  # 默认任务类型
            path=model_file_path,
            source="training"
        )
        
        # 创建模型
        try:
            db_model = model_crud.create(db, obj_in=model_data)
            return {"success": True, "model_id": str(db_model.id), "message": "模型已成功上传到模型管理"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"创建模型记录失败: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="训练任务没有输出目录信息")
