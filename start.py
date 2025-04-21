import os
import sys
import subprocess
import uvicorn
from app.db.init_db import init_db

def start_app():
    """启动YOLOv8训练与检测平台"""
    print("正在启动YOLOv8训练与检测平台...")
    
    # 初始化数据库
    print("初始化数据库...")
    init_db()
    
    # 启动应用程序
    print("启动Web服务器...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    # 确保在虚拟环境中运行
    if sys.prefix == sys.base_prefix:
        print("警告: 当前不在Python虚拟环境中运行")
        response = input("是否继续? [y/n]: ")
        if response.lower() not in ['y', 'yes']:
            sys.exit(0)
    
    # 启动应用
    start_app()
