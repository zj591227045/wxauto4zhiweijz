"""
App模块初始化
模块化版本的简化初始化
"""

import os
import sys
import logging

# 确保当前目录在Python路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 确保父目录在Python路径中
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 模块化版本不需要Flask相关的导入
logger = logging.getLogger(__name__)
logger.info("App模块初始化完成（模块化版本）")