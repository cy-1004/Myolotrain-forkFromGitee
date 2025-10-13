#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Myolotrain项目部署检查脚本
用于验证项目在新主机上的运行环境是否满足要求
"""

import os
import sys
import socket
import psutil


def check_python_version():
    """检查Python版本是否满足要求"""
    print("=" * 60)
    print("检查Python版本")
    print("=" * 60)
    
    version_info = sys.version_info
    current_version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    print(f"当前Python版本: {current_version}")
    
    if version_info.major < 3 or (version_info.major == 3 and version_info.minor < 8):
        print("❌ 错误: 需要Python 3.8或更高版本")
        return False
    else:
        print("✅ Python版本满足要求")
        return True


def check_postgresql():
    """检查PostgreSQL服务是否运行"""
    print("=" * 60)
    print("检查PostgreSQL服务")
    print("=" * 60)
    
    # 尝试连接PostgreSQL默认端口
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("localhost", 5432))
        sock.close()
        
        if result == 0:
            print("✅ PostgreSQL服务正在运行")
            return True
        else:
            print("❌ 警告: 未检测到PostgreSQL服务运行在默认端口(5432)")
            print("   请确保已安装PostgreSQL并启动服务")
            print("   并创建用户名'postgres'，密码'postgres'，数据库'yolov8_platform'")
            return False
    except Exception as e:
        print(f"❌ 检查PostgreSQL服务时出错: {e}")
        return False


def check_required_files():
    """检查必要文件是否存在"""
    print("=" * 60)
    print("检查必要文件")
    print("=" * 60)
    
    required_files = [
        "requirements.txt",
        "setup_venv.py",
        "init_db.py",
        "start.py",
        "app/main.py",
        "app/db/init_db.py",
        "app/core/config.py"
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} 存在")
        else:
            print(f"❌ {file_path} 不存在")
            all_exist = False
    
    return all_exist


def check_system_resources():
    """检查系统资源是否满足基本要求"""
    print("=" * 60)
    print("检查系统资源")
    print("=" * 60)
    
    # 检查内存
    mem = psutil.virtual_memory()
    mem_gb = mem.total / (1024 ** 3)
    print(f"总内存: {mem_gb:.2f} GB")
    
    if mem_gb < 4:
        print("❌ 警告: 系统内存不足4GB，可能影响程序性能")
    else:
        print("✅ 系统内存满足基本要求")
    
    # 检查磁盘空间
    disk = psutil.disk_usage('/')
    disk_gb = disk.total / (1024 ** 3)
    print(f"总磁盘空间: {disk_gb:.2f} GB")
    
    if disk_gb < 20:
        print("❌ 警告: 磁盘空间不足20GB，可能影响数据存储")
    else:
        print("✅ 磁盘空间满足基本要求")
    
    # 检查CPU核心数
    cpu_count = psutil.cpu_count(logical=True)
    print(f"CPU核心数: {cpu_count}")
    
    if cpu_count < 2:
        print("❌ 警告: CPU核心数不足2个，可能影响程序性能")
    else:
        print("✅ CPU核心数满足基本要求")


def main():
    """主函数"""
    print("""
    ==================================================
    Myolotrain项目部署检查工具
    ==================================================
    此工具将检查项目在新主机上的运行环境是否满足要求
    """)
    
    # 运行所有检查
    python_ok = check_python_version()
    postgresql_ok = check_postgresql()
    files_ok = check_required_files()
    check_system_resources()
    
    print("\n" + "=" * 60)
    print("部署检查结果总结")
    print("=" * 60)
    
    # 计算总体检查结果
    all_ok = python_ok and files_ok
    
    # 如果PostgreSQL未运行，给出警告但不视为致命错误
    if not postgresql_ok:
        print("⚠️  警告: PostgreSQL服务未检测到或配置不匹配")
        print("   请参考部署文档手动配置数据库")
    
    if all_ok:
        print("✅ 基本环境检查通过！")
        print("   请按照以下步骤部署项目:")
        print("   1. 确保PostgreSQL已正确安装并配置")
        print("   2. 运行 'python setup_venv.py' 创建虚拟环境并安装依赖")
        print("   3. 运行 'python init_db.py' 初始化数据库")
        print("   4. 运行 'python start.py' 启动应用程序")
        print("   5. 访问 http://localhost:8000 进行登录")
        print("   6. 默认管理员账号: admin 密码: admin")
    else:
        print("❌ 环境检查未通过！")
        print("   请修复上述问题后重新运行检查")
    
    print("=" * 60)


if __name__ == "__main__":
    main()