#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动PyQt6界面的脚本
只为记账-微信助手
"""

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def setup_logging():
    """设置日志"""
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "qt_ui.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def check_dependencies():
    """检查依赖项"""
    try:
        import PyQt6
        print("[OK] PyQt6 已安装")
    except ImportError:
        print("[ERROR] PyQt6 未安装，请运行: pip install PyQt6")
        return False

    try:
        import requests
        print("[OK] requests 已安装")
    except ImportError:
        print("[ERROR] requests 未安装，请运行: pip install requests")
        return False

    return True

def main():
    """主函数"""
    print("=" * 50)
    print("只为记账-微信助手 (完整版)")
    print("=" * 50)

    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # 检查依赖项
        if not check_dependencies():
            print("\n请安装缺失的依赖项后重试")
            input("按回车键退出...")
            return 1

        # 添加app目录到路径，但避免导入app包
        app_dir = os.path.join(project_root, "app")
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)

        # 导入并启动主界面（带自动监控功能）
        print("DEBUG: 开始导入主窗口模块")
        from app.qt_ui.main_window_with_startup import MainWindowWithStartup
        print("DEBUG: 主窗口模块导入成功")

        print("正在启动PyQt6界面（完整版）...")
        logger.info("启动PyQt6界面（完整版）...")
        print("DEBUG: 开始调用主窗口main函数")
        
        # 创建应用程序
        app = QApplication(sys.argv)
        
        # 创建主窗口
        window = MainWindowWithStartup()
        window.show()
        
        # 运行应用程序
        sys.exit(app.exec())

    except ImportError as e:
        error_msg = f"导入模块失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        logger.error(error_msg)
        print("\n请确保所有依赖项已正确安装")
        input("按回车键退出...")
        return 1
    except Exception as e:
        error_msg = f"启动失败: {str(e)}"
        print(f"[ERROR] {error_msg}")
        logger.error(error_msg, exc_info=True)
        input("按回车键退出...")
        return 1

if __name__ == "__main__":
    sys.exit(main())
