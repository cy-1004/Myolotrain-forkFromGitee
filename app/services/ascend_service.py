"""Ascend NPU service module"""
import os
import sys
import platform
from typing import List, Dict, Any, Optional

class AscendDeviceManager:
    """华为昇腾NPU设备管理器"""

    @staticmethod
    def get_available_ascends() -> list:
        """
        获取所有可用的昇腾NPU信息
        :return: NPU信息列表 [{'index': 0, 'name': 'NPU名称', 'memory': 内存大小(MB), 'memory_used': 已用内存(MB), 'memory_free': 可用内存(MB)}]
        """
        ascends = []

        try:
            # 尝试导入昇腾相关库
            # 注意：实际使用时需要安装相关依赖
            # 尝试导入昇腾相关库
            import torch_npu
            import acl

            # 获取NPU数量
            device_count = torch_npu.npu.device_count()

            if device_count == 0:
                # 没有检测到昇腾NPU设备
                print("未检测到昇腾NPU设备")
                return []

            # 获取所有昇腾NPU信息
            for i in range(device_count):
                # 获取NPU属性
                props = torch_npu.npu.get_device_properties(i)
                total_memory = int(props.total_memory / (1024 * 1024))  # 转换为MB

                # 获取内存使用情况
                memory_used = int(torch_npu.npu.memory_used(i) / (1024 * 1024))
                memory_free = total_memory - memory_used

                ascends.append({
                    'index': i,
                    'name': props.name,
                    'memory': total_memory,
                    'memory_used': memory_used,
                    'memory_free': memory_free,
                    'recommended_memory': int(memory_free * 0.8)  # 推荐使用80%的可用内存
                })
        except Exception as e:
            print(f"获取昇腾NPU信息失败: {str(e)}")

        return ascends

    @staticmethod
    def validate_ascend_memory(requested_memory: int, ascend_index: int = 0) -> tuple[bool, str, int]:
        """
        验证请求的昇腾NPU内存是否合理
        :param requested_memory: 请求的内存大小(MB)
        :param ascend_index: 昇腾NPU索引，默认为0
        :return: (是否有效, 提示信息, 总内存大小)
        """
        # 获取昇腾NPU信息
        ascends = AscendDeviceManager.get_available_ascends()
        if not ascends:
            return False, "昇腾NPU不可用，请使用其他模式训练", 0

        # 查找指定的昇腾NPU
        ascend_info = None
        for ascend in ascends:
            if ascend.get("index", 0) == ascend_index:
                ascend_info = ascend
                break

        # 如果没有找到指定的昇腾NPU，使用第一个
        if not ascend_info and ascends:
            ascend_info = ascends[0]

        if not ascend_info:
            return False, "昇腾NPU信息获取失败，请使用其他模式训练", 0

        total_memory = ascend_info.get("memory", 0)
        free_memory = ascend_info.get("memory_free", 0)
        used_memory = ascend_info.get("memory_used", 0)

        if requested_memory <= 0:
            return False, f"请求的内存必须大于0MB", total_memory

        if requested_memory > total_memory:
            return False, f"请求的内存({requested_memory}MB)超过了昇腾NPU最大内存({total_memory}MB)", total_memory

        # 检查是否超过可用内存
        if requested_memory > free_memory:
            return False, f"请求的内存({requested_memory}MB)超过了当前可用内存({free_memory}MB)", total_memory

        # 建议最多使用可用内存的90%
        recommended_memory = int(free_memory * 0.9)
        if requested_memory > recommended_memory:
            return False, f"建议使用不超过{recommended_memory}MB内存（当前可用内存{free_memory}MB）", total_memory

        return True, "内存设置有效", total_memory

    @staticmethod
    def get_device_info(ascend_memory: Optional[int] = None, ascend_index: int = 0) -> dict:
        """
        获取昇腾NPU设备信息
        :param ascend_memory: 昇腾NPU内存限制（MB）
        :param ascend_index: 昇腾NPU索引，默认为0
        :return: 设备配置信息
        """
        # 获取所有可用的昇腾NPU
        available_ascends = AscendDeviceManager.get_available_ascends()

        device_info = {
            'device_type': 'ascend',
            'device': 'cpu',  # 默认使用CPU，如果昇腾NPU可用则会更新
            'ascend_memory': None,
            'ascend_index': ascend_index,
            'available_ascends': available_ascends
        }

        # 检查是否有可用的昇腾NPU
        has_ascend = len(available_ascends) > 0

        if not has_ascend:
            print('\n=== 警告: 昇腾NPU不可用，将使用CPU训练 ===')
            device_info['device_type'] = 'cpu'
            return device_info

        # 检查指定的昇腾NPU是否存在
        selected_ascend = None
        for ascend in available_ascends:
            if ascend.get("index", 0) == ascend_index:
                selected_ascend = ascend
                break

        # 如果没有找到指定的昇腾NPU，使用第一个
        if not selected_ascend and available_ascends:
            selected_ascend = available_ascends[0]
            ascend_index = selected_ascend.get("index", 0)
            device_info['ascend_index'] = ascend_index
            print(f"\n=== 警告: 指定的昇腾NPU ID {ascend_index} 不存在，使用昇腾NPU ID {ascend_index} ===")

        if selected_ascend:
            # 设置当前设备
            try:
                # 这里需要根据实际的昇腾NPU API进行实现
                # 以下是示例代码，实际使用时需要替换为真实的API调用
                # torch_npu.npu.set_device(ascend_index)
                device_info['device'] = f'npu:{ascend_index}'
            except Exception as e:
                print(f'\n=== 警告: 无法设置当前昇腾NPU设备: {str(e)} ===')
                device_info['device'] = 'npu'  # 使用默认昇腾NPU

            # 设置昇腾NPU内存限制
            if ascend_memory:
                # 获取选定的昇腾NPU信息
                total_memory = selected_ascend.get("memory", 0)
                free_memory = selected_ascend.get("memory_free", 0)

                # 验证昇腾NPU内存设置
                if ascend_memory <= 0:
                    print(f"\n=== 警告: 请求的内存必须大于0MB ===")
                    # 使用推荐的内存大小（80%的可用内存）
                    ascend_memory = int(free_memory * 0.8)
                elif ascend_memory > total_memory:
                    print(f"\n=== 警告: 请求的内存({ascend_memory}MB)超过了昇腾NPU最大内存({total_memory}MB) ===")
                    # 使用推荐的内存大小（80%的可用内存）
                    ascend_memory = int(free_memory * 0.8)
                elif ascend_memory > free_memory:
                    print(f"\n=== 警告: 请求的内存({ascend_memory}MB)超过了当前可用内存({free_memory}MB) ===")
                    # 使用推荐的内存大小（80%的可用内存）
                    ascend_memory = int(free_memory * 0.8)

                print(f"\n=== 设置昇腾NPU {ascend_index} 内存限制为 {ascend_memory}MB ===")

                # 设置昇腾NPU内存限制
                try:
                    # 这里需要根据实际的昇腾NPU API进行实现
                    # 以下是示例代码，实际使用时需要替换为真实的API调用
                    # torch_npu.npu.set_memory_limit(ascend_memory * 1024 * 1024)  # 转换为字节
                    device_info['ascend_memory'] = ascend_memory
                except Exception as e:
                    print(f'\n=== 警告: 无法设置昇腾NPU内存限制: {str(e)} ===')
        else:
            print('\n=== 警告: 没有可用的昇腾NPU，将使用CPU训练 ===')
            device_info['device_type'] = 'cpu'
            device_info['device'] = 'cpu'

        return device_info
