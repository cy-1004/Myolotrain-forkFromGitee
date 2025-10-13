#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试数据库初始化修复是否成功"""
import logging
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

# 确保使用正确的编码
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_db_fix")

def test_db_initialization():
    """测试数据库初始化"""
    try:
        logger.info("开始测试数据库初始化...")
        
        # 导入并调用init_db函数
        from app.db.init_db import init_db, create_initial_admin
        
        # 先尝试单独创建初始管理员，验证修复是否生效
        logger.info("测试创建初始管理员用户...")
        create_initial_admin()
        logger.info("初始管理员用户创建测试完成")
        
        # 然后运行完整的数据库初始化
        logger.info("运行完整的数据库初始化...")
        init_db()
        logger.info("数据库初始化测试成功！")
        return True
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_db_initialization()
    if success:
        logger.info("所有测试通过！数据库初始化问题已修复。")
        sys.exit(0)
    else:
        logger.error("测试失败，请查看错误信息。")
        sys.exit(1)