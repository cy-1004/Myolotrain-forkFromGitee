"""
目标追踪服务模块 - 提供基于自注意力机制的目标追踪功能
"""
import numpy as np
import torch
from typing import List, Dict, Any, Tuple, Optional
import logging
from fastapi import HTTPException

from app.nn.modules.enhanced_attention_tracker import EnhancedAttentionTracker

logger = logging.getLogger(__name__)

class TrackingService:
    """
    目标追踪服务类，提供基于自注意力机制的目标追踪功能
    """

    def __init__(self):
        """初始化追踪服务 - 不保存任何本地文件"""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"初始化追踪服务，使用设备: {self.device}")

        # 初始化追踪器
        self.tracker = EnhancedAttentionTracker(
            max_age=30,
            min_hits=3,
            iou_threshold=0.3,
            feature_similarity_weight=0.7,
            motion_weight=0.3,
            device=self.device
        )

    def reset_tracker(self):
        """重置追踪器状态"""
        self.tracker.reset()

    def set_single_target_mode(self, enable: bool, target_id: Optional[int] = None, target_class_id: Optional[int] = None):
        """
        设置单目标追踪模式

        参数:
            enable (bool): 是否启用单目标模式
            target_id (int, optional): 要追踪的目标ID
            target_class_id (int, optional): 要追踪的目标类别ID
        """
        logger.info(f"设置单目标追踪模式: enable={enable}, target_id={target_id}, target_class_id={target_class_id}")
        self.tracker.set_single_target_mode(enable, target_id, target_class_id)

    # 视频追踪功能已移除，仅保留摄像头追踪功能

    def track_frame(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        target_class_id: Optional[int] = None,
        enable_tracking: bool = False,
        cancel_tracking: bool = False
    ) -> List[Dict[str, Any]]:
        """
        追踪单帧中的目标 - 不保存任何本地文件

        参数:
            frame: 输入帧
            detections: 检测结果列表
            target_class_id: 要追踪的目标类别ID
            enable_tracking: 是否启用追踪特定类别
            cancel_tracking: 是否取消追踪

        返回:
            List[Dict]: 追踪结果列表
        """
        """
        追踪单帧中的目标 - 不保存任何本地文件

        参数:
            frame: 输入帧
            detections: 检测结果列表
            target_class_id: 要追踪的目标类别ID
            enable_tracking: 是否启用追踪特定类别
            cancel_tracking: 是否取消追踪

        返回:
            List[Dict]: 追踪结果列表
        """
        try:
            # 记录请求参数
            logger.info(f"追踪帧参数: target_class_id={target_class_id}, enable_tracking={enable_tracking}, cancel_tracking={cancel_tracking}")

            # 验证输入参数
            if frame is None:
                raise ValueError("输入帧不能为空")
            
            if detections is None:
                detections = []
            
            # 处理追踪模式切换
            if cancel_tracking:
                # 取消追踪 - 禁用单目标模式
                logger.info("取消追踪，禁用单目标模式")
                self.tracker.set_single_target_mode(False)
            elif enable_tracking and target_class_id is not None:
                # 启用追踪特定类别
                logger.info(f"启用追踪类别ID: {target_class_id}")
                # 确保target_class_id是整数
                try:
                    target_class_id_int = int(target_class_id)
                    self.tracker.set_single_target_mode(True, target_class_id=target_class_id_int)
                except (ValueError, TypeError) as e:
                    logger.warning(f"无法将target_class_id转换为整数: {e}")
                    # 尝试直接使用原始值
                    self.tracker.set_single_target_mode(True, target_class_id=target_class_id)

            # 更新追踪器 - 确保不保存任何本地文件
            tracks = self.tracker.update(frame, detections)

            # 记录追踪结果
            logger.info(f"追踪结果: {len(tracks)} 个目标")

            # 如果启用了追踪特定类别，但没有找到目标，尝试再次查找
            if enable_tracking and target_class_id is not None and len(tracks) == 0:
                logger.info(f"未找到类别ID为 {target_class_id} 的目标，尝试再次查找")

                # 查找检测结果中是否有目标类别
                for det in detections:
                    if det.get('class_id') == target_class_id:
                        logger.info(f"在检测结果中找到类别ID为 {target_class_id} 的目标，重新设置追踪模式")
                        self.tracker.set_single_target_mode(True, target_class_id=target_class_id)

                        # 重新更新追踪器 - 确保不保存任何本地文件
                        tracks = self.tracker.update(frame, detections)
                        logger.info(f"重新追踪结果: {len(tracks)} 个目标")
                        break

            return tracks

        except Exception as e:
            logger.error(f"帧追踪失败: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"帧追踪失败: {str(e)}")

    # 追踪报告功能已移除

    def _get_color_by_id(self, track_id: int) -> Tuple[int, int, int]:
        """
        根据轨迹ID生成颜色

        参数:
            track_id: 轨迹ID

        返回:
            Tuple[int, int, int]: BGR颜色
        """
        # 使用固定的颜色列表
        colors = [
            (0, 0, 255),    # 红色
            (0, 255, 0),    # 绿色
            (255, 0, 0),    # 蓝色
            (0, 255, 255),  # 黄色
            (255, 0, 255),  # 紫色
            (255, 255, 0),  # 青色
            (128, 0, 0),    # 深蓝色
            (0, 128, 0),    # 深绿色
            (0, 0, 128),    # 深红色
            (128, 128, 0),  # 深青色
        ]

        # 使用ID取模选择颜色
        return colors[track_id % len(colors)]


# 创建服务实例
tracking_service = TrackingService()
