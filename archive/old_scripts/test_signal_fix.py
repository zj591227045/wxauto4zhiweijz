#!/usr/bin/env python3
"""
测试信号修复
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_enhanced_wechat_signals():
    """测试增强版微信管理器信号"""
    print("🔍 测试增强版微信管理器信号...")
    print("=" * 50)
    
    try:
        from app.utils.enhanced_async_wechat import async_wechat_manager
        
        # 检查信号是否存在
        signals_to_check = [
            'wechat_initialized',
            'wechat_ready', 
            'connection_status_changed',
            'status_changed',
            'message_sent',
            'messages_received'
        ]
        
        print("检查信号定义:")
        for signal_name in signals_to_check:
            if hasattr(async_wechat_manager, signal_name):
                signal = getattr(async_wechat_manager, signal_name)
                print(f"  ✅ {signal_name}: {type(signal)}")
            else:
                print(f"  ❌ {signal_name}: 不存在")
        
        # 测试信号连接
        print("\n测试信号连接:")
        
        def test_callback(success, message, info):
            print(f"  📡 wechat_initialized 信号触发: success={success}, message={message}")
        
        def test_status_callback(connected, message):
            print(f"  📡 connection_status_changed 信号触发: connected={connected}, message={message}")
        
        try:
            async_wechat_manager.wechat_initialized.connect(test_callback)
            print("  ✅ wechat_initialized 信号连接成功")
        except Exception as e:
            print(f"  ❌ wechat_initialized 信号连接失败: {e}")
        
        try:
            async_wechat_manager.connection_status_changed.connect(test_status_callback)
            print("  ✅ connection_status_changed 信号连接成功")
        except Exception as e:
            print(f"  ❌ connection_status_changed 信号连接失败: {e}")
        
        # 检查管理器状态
        print(f"\n管理器状态:")
        print(f"  运行状态: {'运行中' if async_wechat_manager.is_running() else '未运行'}")
        print(f"  连接状态: {'已连接' if async_wechat_manager.is_connected() else '未连接'}")
        
        stats = async_wechat_manager.get_stats()
        print(f"  统计信息: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_window_integration():
    """测试简约窗口集成"""
    print("\n🔍 测试简约窗口集成...")
    print("=" * 50)
    
    try:
        # 不启动GUI，只测试导入和信号连接
        from app.qt_ui.simple_main_window import SimpleMainWindow
        from app.utils.enhanced_async_wechat import async_wechat_manager
        
        print("✅ 模块导入成功")
        
        # 检查简约窗口是否有相关方法
        methods_to_check = [
            'setup_enhanced_wechat_integration',
            'on_enhanced_wechat_initialized',
            'on_enhanced_connection_status_changed'
        ]
        
        print("检查简约窗口方法:")
        for method_name in methods_to_check:
            if hasattr(SimpleMainWindow, method_name):
                print(f"  ✅ {method_name}: 存在")
            else:
                print(f"  ❌ {method_name}: 不存在")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🧪 信号修复验证测试")
    print("=" * 60)
    
    results = []
    
    # 测试1: 增强版微信管理器信号
    results.append(("增强版微信管理器信号", test_enhanced_wechat_signals()))
    
    # 测试2: 简约窗口集成
    results.append(("简约窗口集成", test_simple_window_integration()))
    
    # 显示测试结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    # 总结
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！信号修复成功")
        print("\n💡 现在可以正常启动程序:")
        print("   python start_simple_ui.py")
    elif passed > 0:
        print("⚠️ 部分测试通过，可能还有问题需要修复")
    else:
        print("💥 所有测试失败，需要进一步检查")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
