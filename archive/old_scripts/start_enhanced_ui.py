#!/usr/bin/env python3
"""
启动增强版微信自动记账程序
集成了服务健康监控和自动恢复功能
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def check_dependencies():
    """检查依赖项"""
    missing_deps = []
    
    try:
        import PyQt6
        print("✅ PyQt6 已安装")
    except ImportError:
        missing_deps.append("PyQt6")
        print("❌ PyQt6 未安装")
    
    try:
        import requests
        print("✅ requests 已安装")
    except ImportError:
        missing_deps.append("requests")
        print("❌ requests 未安装")
    
    try:
        import wxauto
        print("✅ wxauto 已安装")
    except ImportError:
        print("⚠️  wxauto 未安装（可选，用于微信自动化）")
    
    try:
        import psutil
        print("✅ psutil 已安装")
    except ImportError:
        print("⚠️  psutil 未安装（可选，用于系统监控）")
    
    if missing_deps:
        print(f"\n❌ 缺少必要依赖: {', '.join(missing_deps)}")
        print("请运行以下命令安装:")
        for dep in missing_deps:
            print(f"  pip install {dep}")
        return False
    
    return True

def setup_environment():
    """设置环境"""
    try:
        # 确保数据目录存在
        data_dir = Path(project_root) / "data"
        data_dir.mkdir(exist_ok=True)
        
        logs_dir = data_dir / "Logs"
        logs_dir.mkdir(exist_ok=True)
        
        print(f"✅ 数据目录已准备: {data_dir}")
        
        # 设置日志级别
        os.environ.setdefault('LOG_LEVEL', 'INFO')
        
        return True
        
    except Exception as e:
        print(f"❌ 环境设置失败: {e}")
        return False

def main():
    """主函数"""
    print("微信自动记账程序 - 增强版")
    print("=" * 50)
    print("版本: 2.0.0")
    print("功能: 集成服务健康监控和自动恢复")
    print("=" * 50)
    
    # 检查依赖
    print("\n🔍 检查依赖项...")
    if not check_dependencies():
        print("\n❌ 依赖检查失败，程序退出")
        return 1
    
    # 设置环境
    print("\n🔧 设置环境...")
    if not setup_environment():
        print("\n❌ 环境设置失败，程序退出")
        return 1
    
    # 初始化日志系统
    print("\n📝 初始化日志系统...")
    try:
        from app.logs import logger
        logger.info("增强版程序启动")
        print("✅ 日志系统初始化成功")
    except Exception as e:
        print(f"❌ 日志系统初始化失败: {e}")
        return 1
    
    # 启动主界面
    print("\n🚀 启动主界面...")
    try:
        from PyQt6.QtWidgets import QApplication
        from app.qt_ui.enhanced_main_window import EnhancedMainWindow
        
        # 创建应用程序
        app = QApplication(sys.argv)
        app.setApplicationName("微信自动记账助手")
        app.setApplicationVersion("2.0.0")
        app.setOrganizationName("智微记账")
        
        # 设置应用程序样式
        app.setStyleSheet("""
            QApplication {
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
            }
        """)
        
        # 创建主窗口
        window = EnhancedMainWindow()
        window.show()
        
        print("✅ 主界面启动成功")
        print("\n🎉 程序已启动，请在界面中进行操作")
        print("💡 提示: 可以在'服务健康监控'面板中启动监控服务")
        
        # 运行应用程序
        return app.exec()
        
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
        print("请确保所有依赖都已正确安装")
        return 1
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        logger.error(f"程序启动异常: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
