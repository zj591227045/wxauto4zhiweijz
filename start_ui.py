#!/usr/bin/env python3
"""
新UI启动脚本
使用新的UI样式（参考图片风格），集成最新的模块化架构
包含蓝色圆形按钮、优化的统计卡片和查看日志功能
"""

import sys
import logging
from pathlib import Path

# 检测是否为打包后的exe文件
if getattr(sys, 'frozen', False):
    # 打包后的exe文件
    project_root = Path(sys.executable).parent
else:
    # 开发环境
    project_root = Path(__file__).parent

sys.path.insert(0, str(project_root))

def setup_logging():
    """设置日志系统，处理打包后的路径问题"""
    try:
        # 确保日志目录存在
        log_dir = project_root / "data" / "Logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # 设置日志文件路径
        log_file = log_dir / "legacy_app.log"

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file, encoding='utf-8')
            ]
        )
        return True
    except Exception as e:
        # 如果无法创建日志文件，只使用控制台输出
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        print(f"警告：无法创建日志文件，仅使用控制台输出: {e}")
        return False

# 初始化日志系统
setup_logging()

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
        logger.info("启动新UI（集成新模块化架构）...")
        
        # 设置环境
        if not setup_environment():
            logger.error("环境设置失败，退出程序")
            return 1
        
        # 导入并启动旧版UI主窗口
        from app.qt_ui.legacy_ui_with_modules import main as run_legacy_window
        
        logger.info("启动新UI主窗口...")
        return run_legacy_window()
        
    except Exception as e:
        logger.error(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
