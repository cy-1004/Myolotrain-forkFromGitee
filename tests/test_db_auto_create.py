#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试数据库自动创建功能的脚本
此脚本用于验证在检测不到yolov8_platform数据库的情况下，系统是否能自动创建数据库
"""
import sys
import psycopg2
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def check_db_exists():
    """检查数据库是否存在"""
    db_params = {
        'user': 'postgres',
        'password': 'postgres',
        'host': 'localhost',
        'port': '5432',
        'database': 'postgres'
    }
    
    try:
        # 连接到默认数据库
        conn = psycopg2.connect(**db_params)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 检查数据库是否存在
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'yolov8_platform'")
        exists = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return exists is not None
    except Exception as e:
        logger.error(f"检查数据库时出错: {e}")
        return False

def drop_database():
    """删除数据库（如果存在）"""
    db_params = {
        'user': 'postgres',
        'password': 'postgres',
        'host': 'localhost',
        'port': '5432',
        'database': 'postgres'
    }
    
    try:
        conn = psycopg2.connect(**db_params)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 首先终止所有连接到该数据库的会话
        cursor.execute("""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = 'yolov8_platform'
              AND pid <> pg_backend_pid()
        """)
        
        # 删除数据库
        cursor.execute("DROP DATABASE IF EXISTS yolov8_platform")
        logger.info("已删除yolov8_platform数据库")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"删除数据库时出错: {e}")
        return False

def test_database_auto_creation():
    """测试数据库自动创建功能"""
    # 检查数据库是否存在
    db_exists = check_db_exists()
    logger.info(f"数据库存在状态: {db_exists}")
    
    # 如果数据库存在，先删除它
    if db_exists:
        logger.info("数据库已存在，尝试删除它...")
        if not drop_database():
            logger.error("无法删除数据库，测试失败")
            return False
    
    # 再次检查数据库是否存在
    db_exists = check_db_exists()
    if db_exists:
        logger.error("数据库删除失败，测试无法继续")
        return False
    
    logger.info("数据库已成功删除，现在尝试通过init_database函数创建它...")
    
    # 导入init_database函数
    try:
        sys.path.append(str(Path(__file__).resolve().parent))
        from init_db import init_database
        
        # 调用init_database函数创建数据库
        result = init_database()
        if result:
            logger.info("数据库创建成功！")
            
            # 验证数据库是否真的存在
            if check_db_exists():
                logger.info("验证成功：数据库确实存在")
                return True
            else:
                logger.error("验证失败：数据库仍然不存在")
                return False
        else:
            logger.error("数据库创建失败")
            return False
    except Exception as e:
        logger.error(f"导入或调用init_database函数时出错: {e}")
        return False

if __name__ == "__main__":
    logger.info("开始测试数据库自动创建功能...")
    success = test_database_auto_creation()
    
    if success:
        logger.info("测试通过！数据库自动创建功能正常工作")
        sys.exit(0)
    else:
        logger.error("测试失败！数据库自动创建功能不正常")
        sys.exit(1)