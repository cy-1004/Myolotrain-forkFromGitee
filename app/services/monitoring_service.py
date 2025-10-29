"""
系统资源监控服务
用于定期收集和存储系统资源使用情况
"""
import psutil
import time
import threading
import json
import os
from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

class SystemMonitor:
    """系统资源监控器"""

    def __init__(self):
        self.running = False
        self.enabled = True  # 监控服务默认启用
        self.monitor_thread = None
        self.data_storage = []
        self.max_storage_size = 1000  # 最大存储数据点数
        self.storage_file = "logs/system_monitor_data.json"

    def start(self):
        """启动监控线程"""
        if self.running or not self.enabled:
            return

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print("系统资源监控服务已启动")

    def stop(self):
        """停止监控线程"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            self.monitor_thread = None
        print("系统资源监控服务已停止")

    def enable(self):
        """启用监控服务"""
        self.enabled = True
        print("系统资源监控服务已启用")

    def disable(self):
        """禁用监控服务"""
        self.enabled = False
        if self.running:
            self.stop()
        print("系统资源监控服务已禁用")

    def is_enabled(self):
        """检查监控服务是否启用"""
        return self.enabled

    def _monitor_loop(self):
        """监控循环，定期收集系统资源信息"""
        while self.running and self.enabled:
            try:
                # 收集系统资源信息
                resource_data = self._collect_system_resources()
                
                # 存储数据
                self._store_data(resource_data)
                
                # 每5秒收集一次数据
                time.sleep(5)
            except Exception as e:
                print(f"系统资源监控循环出错: {e}")
                time.sleep(5)

    def _collect_system_resources(self) -> Dict:
        """收集系统资源信息"""
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
                    gpu_name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                    
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
            print(f"收集系统资源信息时出错: {e}")
            return {}

    def _store_data(self, data: Dict):
        """存储数据"""
        if not data:
            return
            
        # 添加到内存存储
        self.data_storage.append(data)
        
        # 限制存储大小
        if len(self.data_storage) > self.max_storage_size:
            self.data_storage = self.data_storage[-self.max_storage_size:]
        
        # 定期保存到文件（每100个数据点保存一次）
        if len(self.data_storage) % 100 == 0:
            self._save_to_file()

    def _save_to_file(self):
        """保存数据到文件"""
        try:
            # 确保日志目录存在
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            
            # 读取现有数据
            existing_data = []
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            
            # 合并数据（保留最新的数据）
            combined_data = existing_data + self.data_storage
            if len(combined_data) > self.max_storage_size:
                combined_data = combined_data[-self.max_storage_size:]
            
            # 保存到文件
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(combined_data, f, ensure_ascii=False, indent=2)
                
            # 清空内存存储
            self.data_storage = []
        except Exception as e:
            print(f"保存监控数据到文件时出错: {e}")

    def get_recent_data(self, count: int = 100) -> List[Dict]:
        """获取最近的监控数据"""
        try:
            # 从文件读取数据
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                return file_data[-count:]
            else:
                return self.data_storage[-count:]
        except Exception as e:
            print(f"读取监控数据时出错: {e}")
            return self.data_storage[-count:]

    def get_data_by_time_range(self, start_time: str, end_time: str) -> List[Dict]:
        """根据时间范围获取监控数据"""
        try:
            # 从文件读取数据
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
            else:
                file_data = self.data_storage
            
            # 过滤时间范围内的数据
            filtered_data = []
            for data in file_data:
                if start_time <= data['timestamp'] <= end_time:
                    filtered_data.append(data)
            
            return filtered_data
        except Exception as e:
            print(f"根据时间范围读取监控数据时出错: {e}")
            return []

# 创建全局系统监控器实例
system_monitor = SystemMonitor()