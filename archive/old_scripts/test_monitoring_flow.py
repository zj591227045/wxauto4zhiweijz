#!/usr/bin/env python3
"""
测试监控启动流程
"""

import sys
import os
import time

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_monitoring_flow():
    """测试监控启动流程"""
    print("🔍 测试监控启动流程...")
    print("=" * 50)
    
    try:
        # 测试增强版微信管理器初始化
        from app.utils.enhanced_async_wechat import async_wechat_manager
        
        print("1. 测试增强版微信管理器状态:")
        print(f"   运行状态: {'运行中' if async_wechat_manager.is_running() else '未运行'}")
        print(f"   连接状态: {'已连接' if async_wechat_manager.is_connected() else '未连接'}")
        
        # 如果未连接，尝试初始化
        if not async_wechat_manager.is_connected():
            print("\n2. 尝试初始化微信...")
            
            init_success = False
            init_message = ""
            
            def on_init_result(success, result, message):
                nonlocal init_success, init_message
                init_success = success
                init_message = message
                print(f"   初始化结果: {'成功' if success else '失败'}")
                print(f"   消息: {message}")
                if result:
                    print(f"   详细信息: {result}")
            
            # 异步初始化微信
            async_wechat_manager.initialize_wechat(callback=on_init_result)
            
            # 等待初始化完成
            print("   等待初始化完成...")
            time.sleep(10)
            
            if init_success:
                print("   ✅ 微信初始化成功")
            else:
                print(f"   ❌ 微信初始化失败: {init_message}")
                return False
        else:
            print("   ✅ 微信已经连接")
        
        # 测试消息监控器
        print("\n3. 测试消息监控器:")
        from app.services.enhanced_zero_history_monitor import EnhancedZeroHistoryMonitor
        
        monitor = EnhancedZeroHistoryMonitor()
        print("   ✅ 消息监控器创建成功")
        
        # 检查微信实例
        if monitor.wx_instance:
            print("   ✅ 消息监控器有微信实例")
        else:
            print("   ❌ 消息监控器没有微信实例")
            # 尝试初始化
            if monitor._initialize_wechat():
                print("   ✅ 消息监控器微信实例初始化成功")
            else:
                print("   ❌ 消息监控器微信实例初始化失败")
                return False
        
        # 测试添加监控目标
        print("\n4. 测试添加监控目标:")
        test_chat = "张杰"
        
        try:
            result = monitor.add_chat_target(test_chat)
            if result:
                print(f"   ✅ 成功添加监控目标: {test_chat}")
            else:
                print(f"   ⚠️ 监控目标可能已存在: {test_chat}")
        except Exception as e:
            print(f"   ❌ 添加监控目标失败: {e}")
            return False
        
        # 测试启动监控
        print("\n5. 测试启动监控:")
        try:
            result = monitor.start_chat_monitoring(test_chat)
            if result:
                print(f"   ✅ 成功启动监控: {test_chat}")
            else:
                print(f"   ⚠️ 监控可能已经启动: {test_chat}")
        except Exception as e:
            print(f"   ❌ 启动监控失败: {e}")
            return False
        
        # 清理
        print("\n6. 清理测试:")
        try:
            monitor.stop_monitoring()
            print("   ✅ 监控已停止")
        except Exception as e:
            print(f"   ⚠️ 停止监控时出现异常: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_window_methods():
    """测试简约窗口方法"""
    print("\n🔍 测试简约窗口方法...")
    print("=" * 50)
    
    try:
        from app.qt_ui.simple_main_window import SimpleMainWindow
        
        # 检查关键方法
        methods_to_check = [
            'check_wechat_and_start_monitoring',
            'initialize_wechat_and_wait',
            'on_enhanced_wechat_initialized',
            'add_listeners_and_start_monitoring'
        ]
        
        print("检查关键方法:")
        for method_name in methods_to_check:
            if hasattr(SimpleMainWindow, method_name):
                print(f"  ✅ {method_name}: 存在")
            else:
                print(f"  ❌ {method_name}: 不存在")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🧪 监控启动流程测试")
    print("=" * 60)
    print("时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    results = []
    
    # 测试1: 监控启动流程
    results.append(("监控启动流程", test_monitoring_flow()))
    
    # 测试2: 简约窗口方法
    results.append(("简约窗口方法", test_simple_window_methods()))
    
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
        print("🎉 所有测试通过！监控启动流程修复成功")
        print("\n💡 现在可以正常启动程序并开始监听:")
        print("   python start_simple_ui.py")
        print("   点击'开始监听'按钮")
    elif passed > 0:
        print("⚠️ 部分测试通过，可能还有问题需要修复")
    else:
        print("💥 所有测试失败，需要进一步检查")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
