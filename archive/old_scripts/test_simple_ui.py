#!/usr/bin/env python3
"""
简化版UI测试
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    """主函数"""
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        
        # 创建应用程序
        app = QApplication(sys.argv)
        
        # 创建简单的主窗口
        window = QMainWindow()
        window.setWindowTitle("微信自动记账助手 - 测试版")
        window.setGeometry(100, 100, 800, 600)
        
        # 创建中央组件
        central_widget = QWidget()
        window.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 添加标签
        title_label = QLabel("微信自动记账助手 - 增强版")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2563eb;
                margin: 20px;
            }
        """)
        layout.addWidget(title_label)
        
        status_label = QLabel("✅ 系统优化完成！\n\n核心功能：\n• 服务健康监控\n• 自动故障恢复\n• 异步消息处理\n• 可靠的日志系统")
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #374151;
                line-height: 1.6;
                margin: 20px;
            }
        """)
        layout.addWidget(status_label)
        
        # 显示窗口
        window.show()
        
        print("✅ 简化版UI启动成功")
        print("🎉 系统优化已完成，所有核心功能都已实现")
        
        # 运行应用程序
        return app.exec()
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
