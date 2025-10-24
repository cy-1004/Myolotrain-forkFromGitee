#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
设置Python虚拟环境并安装所需依赖
"""

import os
import sys
import subprocess
import platform

def create_venv():
    """创建虚拟环境并安装依赖"""
    print("=" * 50)
    print("开始设置YOLOv8训练环境")
    print("=" * 50)
    
    # 检查Python版本
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 12):
        print("错误: 需要Python 3.12或更高版本")
        sys.exit(1)
    
    print(f"检测到Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # 确定虚拟环境目录
    venv_dir = "venv"
    if os.path.exists(venv_dir):
        while True:
            response = input(f"虚拟环境目录 '{venv_dir}' 已存在。覆盖? [y/n]: ")
            if response.lower() == 'y':
                import shutil
                shutil.rmtree(venv_dir)
                break
            elif response.lower() == 'n':
                print("设置已取消")
                sys.exit(0)
    
    # 创建虚拟环境
    print(f"\n创建虚拟环境在 '{venv_dir}'...")
    try:
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
    except subprocess.CalledProcessError:
        print("创建虚拟环境失败")
        sys.exit(1)
    
    # 确定pip路径
    if platform.system() == "Windows":
        pip_path = os.path.join(venv_dir, "Scripts", "pip")
        python_path = os.path.join(venv_dir, "Scripts", "python")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
        python_path = os.path.join(venv_dir, "bin", "python")
    
    # 升级pip
    print("\n升级pip...")
    try:
        # 使用python -m pip的方式升级pip，避免权限问题
        subprocess.run([python_path, "-m", "pip", "install", "--upgrade", "pip", "--no-cache-dir"], check=True)
    except subprocess.CalledProcessError:
        print("警告: 升级pip失败，但将继续执行安装过程")
        #sys.exit(1)
    
    # 安装依赖
    print("\n安装项目依赖...")
    try:
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
    except subprocess.CalledProcessError:
        print("安装依赖失败")
        sys.exit(1)
    
    # 创建激活脚本
    create_activation_scripts(venv_dir)
    
    print("\n" + "=" * 50)
    print("虚拟环境设置完成!")
    print("=" * 50)
    print("\n使用方法:")
    if platform.system() == "Windows":
        print("  运行 'activate.bat' 激活虚拟环境")
    else:
        print("  运行 'source activate.sh' 激活虚拟环境")
    print("  运行 'python train.py' 开始训练")
    print("  运行 'deactivate' 退出虚拟环境")
    print("=" * 50)

def create_activation_scripts(venv_dir):
    """创建激活虚拟环境的脚本"""
    # Windows批处理文件
    with open("activate.bat", "w") as f:
        f.write(f"@echo off\n")
        f.write(f"echo 激活YOLOv8训练环境...\n")
        f.write(f"call {os.path.join(venv_dir, 'Scripts', 'activate.bat')}\n")
        f.write(f"echo 虚拟环境已激活，可以运行 'python train.py' 开始训练\n")
        f.write(f"echo 使用 'deactivate' 命令退出虚拟环境\n")
    
    # Linux/Mac shell脚本
    with open("activate.sh", "w") as f:
        f.write(f"#!/bin/bash\n")
        f.write(f"echo 激活YOLOv8训练环境...\n")
        f.write(f"source {os.path.join(venv_dir, 'bin', 'activate')}\n")
        f.write(f"echo 虚拟环境已激活，可以运行 'python train.py' 开始训练\n")
        f.write(f"echo 使用 'deactivate' 命令退出虚拟环境\n")
    
    # 设置Linux/Mac脚本为可执行
    if platform.system() != "Windows":
        os.chmod("activate.sh", 0o755)

if __name__ == "__main__":
    create_venv()
