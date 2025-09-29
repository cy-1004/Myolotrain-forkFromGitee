# -*- coding: utf-8 -*-
"""
编码处理工具模块
提供跨平台的字符集兼容性支持，解决Windows、Linux和macOS上的日志编码问题
"""
import sys
import os
import platform
import locale
from typing import Optional, BinaryIO, TextIO, Union, Tuple

class EncodingHandler:
    """编码处理工具类，提供跨平台的编码解决方案"""
    
    def __init__(self):
        # 获取当前系统信息
        self.system = platform.system()
        self.python_version = sys.version_info
        # 获取系统默认编码
        self.system_encoding = locale.getpreferredencoding(False)
        
        # 根据操作系统设置推荐编码
        if self.system == 'Windows':
            # Windows系统通常使用GBK或cp936
            self.recommended_encoding = 'utf-8'  # 优先使用UTF-8以确保跨平台兼容性
            self.fallback_encodings = ['gbk', 'cp936', 'utf-8-sig']
        elif self.system in ['Linux', 'Darwin']:  # Darwin是macOS
            # Linux和macOS通常使用UTF-8
            self.recommended_encoding = 'utf-8'
            self.fallback_encodings = ['utf-8-sig', 'latin-1']
        else:
            # 其他系统默认使用UTF-8
            self.recommended_encoding = 'utf-8'
            self.fallback_encodings = ['utf-8-sig', 'latin-1']
        
    def get_encoding_info(self) -> dict:
        """获取当前系统的编码信息"""
        return {
            'system': self.system,
            'python_version': f"{self.python_version.major}.{self.python_version.minor}.{self.python_version.micro}",
            'system_encoding': self.system_encoding,
            'recommended_encoding': self.recommended_encoding,
            'fallback_encodings': self.fallback_encodings
        }
        
    def decode_bytes(self, data: bytes, errors: str = 'replace') -> str:
        """
        智能解码字节数据，尝试多种编码
        :param data: 要解码的字节数据
        :param errors: 解码错误处理方式
        :return: 解码后的字符串
        """
        # 首先尝试推荐编码
        try:
            return data.decode(self.recommended_encoding, errors=errors)
        except UnicodeDecodeError:
            # 如果失败，尝试所有回退编码
            for encoding in self.fallback_encodings:
                if encoding != self.recommended_encoding:  # 避免重复尝试
                    try:
                        return data.decode(encoding, errors=errors)
                    except UnicodeDecodeError:
                        continue
            # 所有编码都失败，使用replace策略强制解码
            return data.decode(self.recommended_encoding, errors='replace')
    
    def open_log_file(self, file_path: str, mode: str = 'r', **kwargs) -> Union[TextIO, BinaryIO]:
        """
        打开日志文件，根据模式和系统选择合适的编码
        :param file_path: 文件路径
        :param mode: 文件打开模式
        :param kwargs: 其他传递给open函数的参数
        :return: 文件对象
        """
        # 如果是二进制模式，不需要编码
        if 'b' in mode:
            return open(file_path, mode, **kwargs)
        
        # 文本模式，添加编码参数
        if 'encoding' not in kwargs:
            kwargs['encoding'] = self.recommended_encoding
        
        if 'errors' not in kwargs:
            kwargs['errors'] = 'replace'
        
        return open(file_path, mode, **kwargs)
    
    def get_subprocess_encoding_args(self) -> dict:
        """
        获取subprocess.Popen的编码参数，确保跨平台兼容性
        :return: 包含编码参数的字典
        """
        if self.python_version >= (3, 7):
            # Python 3.7+ 支持text=True和encoding参数
            return {
                'text': True,
                'encoding': self.recommended_encoding,
                'errors': 'replace'
            }
        else:
            # Python 3.6及以下版本，使用universal_newlines=True
            return {
                'universal_newlines': True
            }
    
    def read_log_file(self, file_path: str) -> str:
        """
        读取日志文件内容，自动处理不同编码
        :param file_path: 日志文件路径
        :return: 日志内容
        """
        try:
            # 首先尝试使用推荐编码读取
            with self.open_log_file(file_path, 'r') as f:
                return f.read()
        except UnicodeDecodeError:
            # 如果失败，尝试二进制读取并使用智能解码
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                    return self.decode_bytes(content)
            except Exception as e:
                return f"读取日志文件时出错: {str(e)}"
    
    def detect_encoding(self, data: bytes, confidence: float = 0.8) -> Tuple[str, float]:
        """
        尝试检测字节数据的编码
        :param data: 要检测的字节数据
        :param confidence: 置信度阈值
        :return: (检测到的编码, 置信度)
        """
        # 简单的编码检测算法
        # 检查BOM标记
        if data.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig', 0.99
        if data.startswith(b'\xff\xfe'):
            return 'utf-16-le', 0.99
        if data.startswith(b'\xfe\xff'):
            return 'utf-16-be', 0.99
        
        # 统计可解码字符的比例来判断编码
        best_encoding = self.recommended_encoding
        best_score = 0.0
        
        # 只检查前10KB数据来提高效率
        sample_data = data[:10240] if len(data) > 10240 else data
        
        # 尝试所有可能的编码
        for encoding in [self.recommended_encoding] + self.fallback_encodings:
            try:
                # 计算可解码的字符数
                decoded = sample_data.decode(encoding)
                # 简单评分：非控制字符的比例
                valid_chars = sum(1 for c in decoded if c.isprintable() or c.isspace())
                score = valid_chars / len(decoded)
                
                if score > best_score:
                    best_score = score
                    best_encoding = encoding
                    
                # 如果置信度足够高，直接返回
                if score > confidence:
                    return encoding, score
                    
            except UnicodeDecodeError:
                continue
        
        return best_encoding, best_score

# 创建全局实例，方便使用
global_encoding_handler = EncodingHandler()

def get_encoding_handler() -> EncodingHandler:
    """获取全局编码处理器实例"""
    return global_encoding_handler

# 便捷函数
def decode_log_bytes(data: bytes, errors: str = 'replace') -> str:
    """便捷函数：解码日志字节数据"""
    return global_encoding_handler.decode_bytes(data, errors)


def read_log_with_auto_encoding(file_path: str) -> str:
    """便捷函数：自动编码读取日志文件"""
    return global_encoding_handler.read_log_file(file_path)


def get_system_encoding_info() -> dict:
    """便捷函数：获取系统编码信息"""
    return global_encoding_handler.get_encoding_info()

if __name__ == "__main__":
    # 演示编码处理工具的使用
    handler = get_encoding_handler()
    info = get_system_encoding_info()
    
    print("系统编码信息:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # 创建一个测试日志文件
    test_log_path = "test_encoding_log.txt"
    with handler.open_log_file(test_log_path, "w") as f:
        f.write("这是一个测试日志文件，包含中英文混合内容。\n")
        f.write("This is a test log file with mixed Chinese and English content.\n")
    
    print(f"\n已创建测试日志文件: {test_log_path}")
    
    # 读取测试日志文件
    log_content = read_log_with_auto_encoding(test_log_path)
    print("\n读取的日志内容:")
    print(log_content)
    
    # 清理测试文件
    if os.path.exists(test_log_path):
        os.remove(test_log_path)
        print(f"\n已删除测试日志文件: {test_log_path}")