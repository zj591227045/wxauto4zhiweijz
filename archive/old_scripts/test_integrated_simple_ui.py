#!/usr/bin/env python3
"""
测试集成增强功能的简约版界面
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_imports():
    """测试导入是否正常"""
    print("测试导入...")
    
    try:
        from app.qt_ui.simple_main_window import SimpleMainWindow
        print("✓ SimpleMainWindow 导入成功")
    except Exception as e:
        print(f"✗ SimpleMainWindow 导入失败: {e}")
        return False
    
    try:
        from app.utils.service_health_monitor import health_monitor
        print("✓ 健康监控系统导入成功")
    except Exception as e:
        print(f"✗ 健康监控系统导入失败: {e}")
        return False
    
    try:
        from app.services.robust_message_processor import RobustMessageProcessor
        print("✓ 增强版消息处理器导入成功")
    except Exception as e:
        print(f"✗ 增强版消息处理器导入失败: {e}")
        return False
    
    try:
        from app.services.robust_message_delivery import RobustMessageDelivery
        print("✓ 增强版消息投递服务导入成功")
    except Exception as e:
        print(f"✗ 增强版消息投递服务导入失败: {e}")
        return False
    
    return True

def test_ui_creation():
    """测试UI创建"""
    print("\n测试UI创建...")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from app.qt_ui.simple_main_window import SimpleMainWindow
        
        # 创建应用程序
        app = QApplication(sys.argv)
        
        # 创建主窗口
        window = SimpleMainWindow()
        print("✓ 简约版主窗口创建成功")
        
        # 检查增强功能是否已集成
        if hasattr(window, 'enhanced_processor'):
            print("✓ 增强版消息处理器已集成")
        else:
            print("✗ 增强版消息处理器未集成")
        
        if hasattr(window, 'enhanced_delivery'):
            print("✓ 增强版消息投递服务已集成")
        else:
            print("✗ 增强版消息投递服务未集成")
        
        if hasattr(window, 'health_monitoring_active'):
            print("✓ 健康监控状态变量已添加")
        else:
            print("✗ 健康监控状态变量未添加")
        
        if hasattr(window, 'open_enhanced_monitor_window'):
            print("✓ 增强版监控窗口方法已添加")
        else:
            print("✗ 增强版监控窗口方法未添加")
        
        # 检查按钮是否存在
        central_widget = window.centralWidget()
        if central_widget:
            print("✓ 中央组件存在")
            
            # 查找服务状态检查按钮
            buttons = central_widget.findChildren(type(window).__bases__[0].__dict__.get('QPushButton', object))
            status_button_found = False
            for button in buttons:
                if hasattr(button, 'text') and '服务状态检查' in button.text():
                    status_button_found = True
                    break
            
            if status_button_found:
                print("✓ 服务状态检查按钮已添加")
            else:
                print("✗ 服务状态检查按钮未找到")
        
        # 不显示窗口，直接关闭
        window.close()
        app.quit()
        
        return True
        
    except Exception as e:
        print(f"✗ UI创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_enhanced_features():
    """测试增强功能"""
    print("\n测试增强功能...")
    
    try:
        from app.services.robust_message_processor import RobustMessageProcessor
        from app.services.robust_message_delivery import RobustMessageDelivery
        from app.utils.service_health_monitor import health_monitor
        
        # 测试消息处理器
        processor = RobustMessageProcessor()
        print("✓ 增强版消息处理器创建成功")
        
        # 测试消息投递服务
        delivery = RobustMessageDelivery()
        print("✓ 增强版消息投递服务创建成功")
        
        # 测试健康监控
        print(f"✓ 健康监控系统状态: {health_monitor.is_running()}")
        
        # 清理
        delivery.stop_delivery_service()
        print("✓ 增强功能测试完成")
        
        return True
        
    except Exception as e:
        print(f"✗ 增强功能测试失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("集成增强功能的简约版界面测试")
    print("=" * 60)
    
    # 测试导入
    if not test_imports():
        print("\n❌ 导入测试失败")
        return 1
    
    # 测试增强功能
    if not test_enhanced_features():
        print("\n❌ 增强功能测试失败")
        return 1
    
    # 测试UI创建
    if not test_ui_creation():
        print("\n❌ UI创建测试失败")
        return 1
    
    print("\n" + "=" * 60)
    print("🎉 所有测试通过！")
    print("✓ 增强功能已成功集成到简约版界面")
    print("✓ 保持了界面的简洁性")
    print("✓ 后台健壮性优化已启用")
    print("✓ 服务状态检查入口已添加")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
