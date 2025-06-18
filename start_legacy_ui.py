#!/usr/bin/env python3
"""
旧版UI启动脚本
使用旧版UI界面和操作逻辑，集成最新的模块化架构
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / "data" / "Logs" / "legacy_app.log", encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def setup_environment():
    """设置环境"""
    try:
        # 确保必要的目录存在
        directories = [
            "data",
            "data/Logs", 
            "data/backup",
            "data/temp"
        ]
        
        for directory in directories:
            dir_path = project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("环境设置完成")
        return True
        
    except Exception as e:
        logger.error(f"环境设置失败: {e}")
        return False

def main():
    """主函数"""
    try:
        logger.info("启动旧版UI（集成新模块化架构）...")
        
        # 设置环境
        if not setup_environment():
            logger.error("环境设置失败，退出程序")
            return 1
        
        # 导入并启动旧版UI主窗口
        from app.qt_ui.legacy_ui_with_modules import main as run_legacy_window
        
        logger.info("启动旧版UI主窗口...")
        return run_legacy_window()
        
    except Exception as e:
        logger.error(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
