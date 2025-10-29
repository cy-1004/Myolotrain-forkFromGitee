from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import psutil
import time
from datetime import datetime

from app.db.session import get_db
from app.services.monitoring_service import system_monitor

router = APIRouter()

@router.get("/system-resources")
def get_system_resources():
    """获取当前系统资源使用情况"""
    try:
        # CPU信息
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count(logical=True)
        
        # 内存信息
        memory = psutil.virtual_memory()
        memory_info = {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent
        }
        
        # 磁盘信息
        disk = psutil.disk_usage('/')
        disk_info = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": (disk.used / disk.total) * 100 if disk.total > 0 else 0
        }
        
        # 网络信息
        net_io = psutil.net_io_counters()
        network_info = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv
        }
        
        # GPU信息（如果有）
        gpu_info = []
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                gpu_name = pynvml.nvmlDeviceGetName(handle)
                
                # GPU使用率
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                
                # GPU内存信息
                gpu_memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                
                # 确保数值类型正确
                memory_total = int(gpu_memory_info.total)
                memory_used = int(gpu_memory_info.used)
                memory_free = int(gpu_memory_info.free)
                memory_percent = (memory_used / memory_total) * 100 if memory_total > 0 else 0
                
                gpu_info.append({
                    "index": i,
                    "name": gpu_name.decode('utf-8') if isinstance(gpu_name, bytes) else str(gpu_name),
                    "utilization": int(utilization.gpu),
                    "memory_total": memory_total,
                    "memory_used": memory_used,
                    "memory_free": memory_free,
                    "memory_percent": memory_percent
                })
        except Exception as e:
            # 如果没有GPU或无法获取GPU信息，则忽略
            pass
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count
            },
            "memory": memory_info,
            "disk": disk_info,
            "network": network_info,
            "gpu": gpu_info
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/system-resources/history")
def get_system_resources_history(minutes: int = 60):
    """获取历史系统资源使用情况（默认最近60分钟）"""
    try:
        # 从监控服务获取历史数据
        history_data = system_monitor.get_recent_data(minutes)
        
        # 如果没有历史数据，生成示例数据
        if not history_data:
            # 生成示例历史数据
            history_data = []
            current_time = time.time()
            
            for i in range(minutes):
                timestamp = current_time - (minutes - i) * 60
                history_data.append({
                    "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_percent": (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100
                })
        
        return {
            "data": history_data,
            "period": f"Last {minutes} minutes"
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/system-resources/control/status")
def get_system_monitoring_status():
    """获取系统监控服务状态"""
    try:
        return {"enabled": system_monitor.is_enabled()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/system-resources/control")
def control_system_monitoring(action: str):
    """控制系统监控服务的启用/禁用"""
    try:
        if action == "enable":
            system_monitor.enable()
            return {"message": "系统监控服务已启用"}
        elif action == "disable":
            system_monitor.disable()
            return {"message": "系统监控服务已禁用"}
        elif action == "status":
            return {"enabled": system_monitor.is_enabled()}
        else:
            raise HTTPException(status_code=400, detail="无效的操作，支持的操作: enable, disable, status")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))