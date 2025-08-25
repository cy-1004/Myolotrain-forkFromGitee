"""
流媒体服务模块 - 支持RTSP和RTMP流处理
"""
import cv2
import threading
import time
import logging
from typing import Optional, Callable, Dict, Any
from urllib.parse import urlparse
import numpy as np

logger = logging.getLogger(__name__)

class StreamService:
    """流媒体服务类，支持RTSP、RTMP和本地摄像头"""
    
    def __init__(self):
        self.active_streams: Dict[str, 'StreamHandler'] = {}
        self._stream_counter = 0
    
    def create_stream(self, source: str, stream_type: str = "auto") -> str:
        """
        创建新的流处理器
        
        Args:
            source: 流源地址或摄像头ID
            stream_type: 流类型 (rtsp, rtmp, webcam, auto)
        
        Returns:
            str: 流ID
        """
        stream_id = f"stream_{self._stream_counter}"
        self._stream_counter += 1
        
        # 自动检测流类型
        if stream_type == "auto":
            stream_type = self._detect_stream_type(source)
        
        handler = StreamHandler(stream_id, source, stream_type)
        self.active_streams[stream_id] = handler
        
        logger.info(f"Created stream {stream_id} for source {source} (type: {stream_type})")
        return stream_id
    
    def start_stream(self, stream_id: str) -> bool:
        """启动流"""
        if stream_id in self.active_streams:
            return self.active_streams[stream_id].start()
        return False
    
    def stop_stream(self, stream_id: str) -> bool:
        """停止流"""
        if stream_id in self.active_streams:
            result = self.active_streams[stream_id].stop()
            del self.active_streams[stream_id]
            return result
        return False
    
    def get_frame(self, stream_id: str) -> Optional[np.ndarray]:
        """获取最新帧"""
        if stream_id in self.active_streams:
            return self.active_streams[stream_id].get_frame()
        return None
    
    def get_stream_info(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """获取流信息"""
        if stream_id in self.active_streams:
            return self.active_streams[stream_id].get_info()
        return None
    
    def list_streams(self) -> Dict[str, Dict[str, Any]]:
        """列出所有活动流"""
        return {
            stream_id: handler.get_info() 
            for stream_id, handler in self.active_streams.items()
        }
    
    def _detect_stream_type(self, source: str) -> str:
        """自动检测流类型"""
        if isinstance(source, int) or source.isdigit():
            return "webcam"
        
        parsed = urlparse(source)
        if parsed.scheme.lower() == "rtsp":
            return "rtsp"
        elif parsed.scheme.lower() == "rtmp":
            return "rtmp"
        elif source.startswith("http"):
            return "http"
        else:
            return "file"


class StreamHandler:
    """单个流处理器"""
    
    def __init__(self, stream_id: str, source: str, stream_type: str):
        self.stream_id = stream_id
        self.source = source
        self.stream_type = stream_type
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.current_frame: Optional[np.ndarray] = None
        self.frame_lock = threading.Lock()
        self.error_count = 0
        self.max_errors = 10
        self.reconnect_delay = 5  # 秒
        
        # 流信息
        self.fps = 0
        self.width = 0
        self.height = 0
        self.frame_count = 0
        self.start_time = None
        
    def start(self) -> bool:
        """启动流处理"""
        if self.is_running:
            return True
        
        try:
            # 根据流类型配置VideoCapture
            if self.stream_type == "webcam":
                self.cap = cv2.VideoCapture(int(self.source))
            else:
                self.cap = cv2.VideoCapture(self.source)
                
                # 为网络流设置缓冲区和超时
                if self.stream_type in ["rtsp", "rtmp", "http"]:
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open stream: {self.source}")
                return False
            
            # 获取流信息
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self.is_running = True
            self.start_time = time.time()
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            
            logger.info(f"Stream {self.stream_id} started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting stream {self.stream_id}: {e}")
            return False
    
    def stop(self) -> bool:
        """停止流处理"""
        self.is_running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        logger.info(f"Stream {self.stream_id} stopped")
        return True
    
    def get_frame(self) -> Optional[np.ndarray]:
        """获取最新帧"""
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None
    
    def get_info(self) -> Dict[str, Any]:
        """获取流信息"""
        runtime = time.time() - self.start_time if self.start_time else 0
        return {
            "stream_id": self.stream_id,
            "source": self.source,
            "type": self.stream_type,
            "is_running": self.is_running,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "frame_count": self.frame_count,
            "runtime": runtime,
            "error_count": self.error_count
        }
    
    def _capture_loop(self):
        """帧捕获循环"""
        consecutive_errors = 0
        
        while self.is_running:
            try:
                if not self.cap or not self.cap.isOpened():
                    if not self._reconnect():
                        time.sleep(self.reconnect_delay)
                        continue
                
                ret, frame = self.cap.read()
                
                if ret and frame is not None:
                    with self.frame_lock:
                        self.current_frame = frame
                    self.frame_count += 1
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    if consecutive_errors > 5:
                        logger.warning(f"Stream {self.stream_id}: Multiple consecutive read failures")
                        if not self._reconnect():
                            time.sleep(self.reconnect_delay)
                        consecutive_errors = 0
                
                # 控制帧率
                if self.fps > 0:
                    time.sleep(1.0 / self.fps)
                else:
                    time.sleep(0.033)  # ~30 FPS
                    
            except Exception as e:
                self.error_count += 1
                logger.error(f"Error in capture loop for stream {self.stream_id}: {e}")
                
                if self.error_count > self.max_errors:
                    logger.error(f"Too many errors for stream {self.stream_id}, stopping")
                    self.is_running = False
                    break
                
                time.sleep(self.reconnect_delay)
    
    def _reconnect(self) -> bool:
        """重新连接流"""
        try:
            if self.cap:
                self.cap.release()
            
            logger.info(f"Attempting to reconnect stream {self.stream_id}")
            
            if self.stream_type == "webcam":
                self.cap = cv2.VideoCapture(int(self.source))
            else:
                self.cap = cv2.VideoCapture(self.source)
                
                if self.stream_type in ["rtsp", "rtmp", "http"]:
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            if self.cap.isOpened():
                logger.info(f"Stream {self.stream_id} reconnected successfully")
                return True
            else:
                logger.error(f"Failed to reconnect stream {self.stream_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error reconnecting stream {self.stream_id}: {e}")
            return False


# 全局流服务实例
stream_service = StreamService()