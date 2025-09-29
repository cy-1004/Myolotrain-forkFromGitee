# -*- coding: utf-8 -*-
"""
编码工具模块测试脚本
用于验证encoding_utils.py在不同编码场景下的功能
"""
import os
import sys
import platform

# 添加项目根目录到Python搜索路径，以便能够导入app模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.utils.encoding_utils import (
    get_encoding_handler,
    decode_log_bytes,
    read_log_with_auto_encoding,
    get_system_encoding_info
)

class EncodingTester:
    """编码工具测试类"""
    
    def __init__(self):
        self.test_dir = "encoding_test_files"
        self.handler = get_encoding_handler()
        
    def setup(self):
        """创建测试目录"""
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
            print(f"已创建测试目录: {self.test_dir}")
    
    def create_test_files(self):
        """创建不同编码的测试文件"""
        # 使用不同编码创建测试文件
        encodings = ["utf-8", "gbk", "utf-16"]
        file_contents = {
            "utf-8": "这是UTF-8编码的测试文本。This is a UTF-8 encoded test text.",
            "gbk": "这是GBK编码的测试文本。This is a GBK encoded test text.",
            "utf-16": "这是UTF-16编码的测试文本。This is a UTF-16 encoded test text."
        }
        
        test_files = []
        
        for encoding in encodings:
            file_path = os.path.join(self.test_dir, f"test_file_{encoding.replace('-', '_')}.txt")
            
            try:
                # 创建带有BOM的文件
                if encoding == "utf-8":
                    with open(file_path, "w", encoding="utf-8-sig") as f:
                        f.write(file_contents[encoding])
                else:
                    with open(file_path, "w", encoding=encoding) as f:
                        f.write(file_contents[encoding])
                
                test_files.append(file_path)
                print(f"已创建{encoding}编码的测试文件: {file_path}")
            except Exception as e:
                print(f"创建{encoding}编码文件失败: {e}")
        
        # 创建混合编码的二进制数据文件
        mixed_data_path = os.path.join(self.test_dir, "mixed_encoding.bin")
        try:
            # 混合UTF-8和GBK编码的字节
            mixed_data = (
                "UTF-8: 你好世界".encode("utf-8") + 
                b"\x00" + 
                "GBK: 测试数据".encode("gbk")
            )
            with open(mixed_data_path, "wb") as f:
                f.write(mixed_data)
            test_files.append(mixed_data_path)
            print(f"已创建混合编码的二进制测试文件: {mixed_data_path}")
        except Exception as e:
            print(f"创建混合编码文件失败: {e}")
        
        return test_files
    
    def test_read_log_with_auto_encoding(self, test_files):
        """测试read_log_with_auto_encoding函数"""
        print("\n===== 测试自动编码读取功能 =====")
        
        for file_path in test_files:
            print(f"\n测试文件: {file_path}")
            try:
                content = read_log_with_auto_encoding(file_path)
                print(f"读取成功。内容预览: {content[:50]}...")
            except Exception as e:
                print(f"读取失败: {e}")
    
    def test_decode_bytes(self, test_files):
        """测试decode_bytes函数"""
        print("\n===== 测试字节数据解码功能 =====")
        
        for file_path in test_files:
            if file_path.endswith(".bin"):
                print(f"\n测试二进制文件: {file_path}")
                try:
                    with open(file_path, "rb") as f:
                        data = f.read()
                    decoded = decode_log_bytes(data)
                    print(f"解码成功。内容: {decoded}")
                except Exception as e:
                    print(f"解码失败: {e}")
    
    def test_get_subprocess_encoding_args(self):
        """测试获取子进程编码参数功能"""
        print("\n===== 测试子进程编码参数功能 =====")
        
        subprocess_args = self.handler.get_subprocess_encoding_args()
        print(f"子进程编码参数: {subprocess_args}")
        
        # 测试运行一个简单的子进程
        import subprocess
        try:
            # 运行一个简单的命令显示系统信息
            if platform.system() == "Windows":
                cmd = ["cmd.exe", "/c", "echo", "这是测试子进程输出"]
            else:
                cmd = ["echo", "这是测试子进程输出"]
            
            result = subprocess.run(cmd, **subprocess_args)
            print(f"子进程执行成功，退出码: {result.returncode}")
        except Exception as e:
            print(f"子进程执行失败: {e}")
    
    def test_encoding_detection(self, test_files):
        """测试编码检测功能"""
        print("\n===== 测试编码检测功能 =====")
        
        for file_path in test_files:
            if not file_path.endswith(".bin"):  # 只测试文本文件
                print(f"\n检测文件编码: {file_path}")
                try:
                    with open(file_path, "rb") as f:
                        data = f.read()
                    detected_encoding, confidence = self.handler.detect_encoding(data)
                    print(f"检测到编码: {detected_encoding}，置信度: {confidence:.2f}")
                except Exception as e:
                    print(f"编码检测失败: {e}")
    
    def cleanup(self):
        """清理测试文件"""
        if os.path.exists(self.test_dir):
            for file in os.listdir(self.test_dir):
                file_path = os.path.join(self.test_dir, file)
                os.remove(file_path)
            os.rmdir(self.test_dir)
            print(f"\n已清理测试目录: {self.test_dir}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n===== 系统编码信息 =====")
        info = get_system_encoding_info()
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        try:
            self.setup()
            test_files = self.create_test_files()
            self.test_read_log_with_auto_encoding(test_files)
            self.test_decode_bytes(test_files)
            self.test_get_subprocess_encoding_args()
            self.test_encoding_detection(test_files)
            print("\n所有测试完成！")
        except Exception as e:
            print(f"\n测试过程中发生错误: {e}")
        finally:
            # 询问是否清理测试文件
            if input("\n是否清理测试文件？(y/n): ").lower() == "y":
                self.cleanup()
            else:
                print("测试文件保留在: {self.test_dir}")

if __name__ == "__main__":
    tester = EncodingTester()
    tester.run_all_tests()