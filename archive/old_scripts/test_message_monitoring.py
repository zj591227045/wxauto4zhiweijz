#!/usr/bin/env python3
"""
测试消息监控功能
"""

import sys
import os
import time
from PyQt6.QtCore import QCoreApplication

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_enhanced_zero_history_monitor():
    """测试增强版零历史消息监控器"""
    print("🔍 测试增强版零历史消息监控器...")
    print("=" * 50)
    
    try:
        from app.services.enhanced_zero_history_monitor import EnhancedZeroHistoryMonitor
        
        # 创建监控器
        monitor = EnhancedZeroHistoryMonitor()
        print("✅ 监控器创建成功")
        
        # 检查微信实例
        if monitor.wx_instance:
            print("✅ 微信实例已初始化")
        else:
            print("❌ 微信实例未初始化，尝试初始化...")
            if monitor._initialize_wechat():
                print("✅ 微信实例初始化成功")
            else:
                print("❌ 微信实例初始化失败")
                return False
        
        # 设置消息接收回调
        message_received_count = 0
        
        def on_message_received(chat_name, content, sender):
            nonlocal message_received_count
            message_received_count += 1
            print(f"📨 收到消息 #{message_received_count}: {chat_name} - {sender}: {content[:30]}...")
        
        monitor.message_received.connect(on_message_received)
        print("✅ 消息接收回调已设置")
        
        # 添加监控目标
        test_chat = "张杰"
        print(f"\n添加监控目标: {test_chat}")
        
        if monitor.add_chat_target(test_chat):
            print(f"✅ 成功添加监控目标: {test_chat}")
        else:
            print(f"❌ 添加监控目标失败: {test_chat}")
            return False
        
        # 启动监控
        print(f"\n启动监控: {test_chat}")
        if monitor.start_chat_monitoring(test_chat):
            print(f"✅ 成功启动监控: {test_chat}")
        else:
            print(f"❌ 启动监控失败: {test_chat}")
            return False
        
        # 检查监控状态
        print(f"\n监控状态检查:")
        print(f"  运行状态: {'运行中' if monitor.is_running else '未运行'}")
        print(f"  连接状态: {'健康' if monitor.connection_healthy else '异常'}")
        print(f"  监控聊天: {monitor.monitored_chats}")
        print(f"  活跃线程: {len(monitor.monitor_threads)}")
        
        # 等待消息
        print(f"\n等待消息（30秒）...")
        print("请在微信中向监控对象发送测试消息...")
        
        start_time = time.time()
        while time.time() - start_time < 30:
            # 处理Qt事件
            QCoreApplication.processEvents()
            time.sleep(0.1)
            
            # 每5秒显示一次状态
            if int(time.time() - start_time) % 5 == 0:
                print(f"  等待中... 已收到 {message_received_count} 条消息")
                time.sleep(1)  # 避免重复打印
        
        print(f"\n测试结果:")
        print(f"  总共收到消息: {message_received_count} 条")
        
        # 停止监控
        print(f"\n停止监控...")
        if monitor.stop_monitoring():
            print("✅ 监控停止成功")
        else:
            print("❌ 监控停止失败")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_signal_connection():
    """测试信号连接"""
    print("\n🔍 测试信号连接...")
    print("=" * 50)
    
    try:
        from app.services.enhanced_zero_history_monitor import EnhancedZeroHistoryMonitor
        
        monitor = EnhancedZeroHistoryMonitor()
        
        # 检查信号是否存在
        signals_to_check = [
            'message_received',
            'accounting_result',
            'status_changed',
            'connection_lost',
            'connection_restored',
            'error_occurred'
        ]
        
        print("检查信号定义:")
        for signal_name in signals_to_check:
            if hasattr(monitor, signal_name):
                signal = getattr(monitor, signal_name)
                print(f"  ✅ {signal_name}: {type(signal)}")
            else:
                print(f"  ❌ {signal_name}: 不存在")
        
        # 测试信号连接
        print("\n测试信号连接:")
        
        def test_message_callback(chat_name, content, sender):
            print(f"  📡 message_received 信号触发: {chat_name} - {sender}: {content[:20]}...")
        
        def test_status_callback(status):
            print(f"  📡 status_changed 信号触发: {status}")
        
        try:
            monitor.message_received.connect(test_message_callback)
            print("  ✅ message_received 信号连接成功")
        except Exception as e:
            print(f"  ❌ message_received 信号连接失败: {e}")
        
        try:
            monitor.status_changed.connect(test_status_callback)
            print("  ✅ status_changed 信号连接成功")
        except Exception as e:
            print(f"  ❌ status_changed 信号连接失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🧪 消息监控功能测试")
    print("=" * 60)
    print("时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    # 创建Qt应用（用于信号处理）
    app = QCoreApplication(sys.argv)
    
    results = []
    
    # 测试1: 信号连接
    results.append(("信号连接测试", test_signal_connection()))
    
    # 测试2: 消息监控
    results.append(("消息监控测试", test_enhanced_zero_history_monitor()))
    
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
        print("🎉 所有测试通过！消息监控功能正常")
        print("\n💡 现在可以正常使用消息监控功能:")
        print("   1. 启动程序: python start_simple_ui.py")
        print("   2. 点击'开始监听'按钮")
        print("   3. 在微信中发送消息进行测试")
    elif passed > 0:
        print("⚠️ 部分测试通过，可能还有问题需要修复")
    else:
        print("💥 所有测试失败，需要进一步检查")
    
    print("\n📝 使用说明:")
    print("- 确保微信已启动并登录")
    print("- 确保有名为'张杰'的微信联系人（或修改测试代码中的联系人名称）")
    print("- 测试时请向监控对象发送消息")
    print("- 观察控制台输出的消息接收情况")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
