import os
import sys
import subprocess
import uvicorn
from pathlib import Path
from app.db.init_db import init_db

# 导入主初始化数据库函数
sys.path.append(str(Path(__file__).resolve().parent))
from init_db import init_database

def start_app():
    """启动YOLOv8训练与检测平台"""
    print("正在启动YOLOv8训练与检测平台...")
    
    # 确保数据库存在
    print("检查并初始化数据库...")
    if init_database():
        # 初始化数据库表结构
        print("初始化数据库表结构...")
        init_db()
        
        # 启动应用程序
        print("启动Web服务器...")
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        print("数据库初始化失败，无法启动应用程序。")
        sys.exit(1)

if __name__ == "__main__":
    # 确保在虚拟环境中运行
    if sys.prefix == sys.base_prefix:
        print("警告: 当前不在Python虚拟环境中运行")
        print("继续运行应用程序...")
    
    # 启动应用
    start_app()
