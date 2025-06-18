#!/usr/bin/env python3
"""
智能消息监控测试 - 自动检测可用联系人
"""

import sys
import os
import time
from PyQt6.QtCore import QCoreApplication

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def get_available_contacts():
    """获取可用的微信联系人"""
    try:
        import wxauto
        wx = wxauto.WeChat()
        
        if not wx:
            print("❌ 无法创建微信实例")
            return []
        
        # 获取聊天列表
        chat_list = wx.GetSessionList()
        if not chat_list:
            print("❌ 无法获取聊天列表")
            return []
        
        print(f"📋 找到 {len(chat_list)} 个聊天对象:")

        # 安全地显示聊天列表
        display_count = min(10, len(chat_list))
        for i in range(display_count):
            try:
                chat_name = str(chat_list[i])
                print(f"  {i+1}. {chat_name}")
            except Exception as e:
                print(f"  {i+1}. [显示错误: {e}]")

        return chat_list
        
    except Exception as e:
        print(f"❌ 获取联系人失败: {e}")
        return []

def test_monitoring_with_real_contact():
    """使用真实联系人测试监控"""
    print("🔍 智能消息监控测试...")
    print("=" * 50)
    
    try:
        # 获取可用联系人
        contacts = get_available_contacts()
        if not contacts:
            print("❌ 没有可用的联系人进行测试")
            return False
        
        # 选择第一个联系人作为测试目标
        test_chat = contacts[0]
        print(f"\n🎯 选择测试目标: {test_chat}")
        
        from app.services.enhanced_zero_history_monitor import EnhancedZeroHistoryMonitor
        
        # 创建监控器
        monitor = EnhancedZeroHistoryMonitor()
        print("✅ 监控器创建成功")
        
        # 检查微信实例
        if not monitor.wx_instance:
            if monitor._initialize_wechat():
                print("✅ 微信实例初始化成功")
            else:
                print("❌ 微信实例初始化失败")
                return False
        else:
            print("✅ 微信实例已就绪")
        
        # 设置消息接收回调
        message_received_count = 0
        received_messages = []
        
        def on_message_received(chat_name, content, sender):
            nonlocal message_received_count
            message_received_count += 1
            received_messages.append({
                'chat': chat_name,
                'content': content,
                'sender': sender,
                'time': time.strftime("%H:%M:%S")
            })
            print(f"📨 [{time.strftime('%H:%M:%S')}] {chat_name} - {sender}: {content[:50]}...")
        
        monitor.message_received.connect(on_message_received)
        print("✅ 消息接收回调已设置")
        
        # 添加监控目标
        print(f"\n📡 添加监控目标: {test_chat}")
        if monitor.add_chat_target(test_chat):
            print(f"✅ 成功添加监控目标")
        else:
            print(f"❌ 添加监控目标失败")
            return False
        
        # 启动监控
        print(f"\n🚀 启动监控...")
        if monitor.start_chat_monitoring(test_chat):
            print(f"✅ 监控启动成功")
        else:
            print(f"❌ 监控启动失败")
            return False
        
        # 显示监控状态
        print(f"\n📊 监控状态:")
        print(f"  运行状态: {'运行中' if monitor.is_running else '未运行'}")
        print(f"  连接状态: {'健康' if monitor.connection_healthy else '异常'}")
        print(f"  监控聊天: {monitor.monitored_chats}")
        print(f"  活跃线程: {len(monitor.monitor_threads)}")
        
        # 等待消息
        print(f"\n⏰ 等待消息（15秒）...")
        print(f"💡 请在微信中向 '{test_chat}' 发送测试消息")
        print("   建议发送: '测试记账 支出 10 午餐'")
        
        start_time = time.time()
        last_status_time = 0
        
        while time.time() - start_time < 15:
            # 处理Qt事件
            QCoreApplication.processEvents()
            time.sleep(0.1)
            
            # 每3秒显示一次状态
            current_time = time.time() - start_time
            if int(current_time) > last_status_time and int(current_time) % 3 == 0:
                last_status_time = int(current_time)
                print(f"  ⏳ 等待中... 已收到 {message_received_count} 条消息 ({int(current_time)}/15秒)")
        
        # 显示测试结果
        print(f"\n📈 测试结果:")
        print(f"  总共收到消息: {message_received_count} 条")
        
        if received_messages:
            print(f"  消息详情:")
            for i, msg in enumerate(received_messages, 1):
                print(f"    {i}. [{msg['time']}] {msg['sender']}: {msg['content'][:30]}...")
        else:
            print(f"  💡 没有收到消息，可能的原因:")
            print(f"     - 测试时间内没有发送消息")
            print(f"     - 消息被过滤（如系统消息）")
            print(f"     - 监控目标不正确")
        
        # 停止监控
        print(f"\n🛑 停止监控...")
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

def test_monitoring_status():
    """测试监控状态功能"""
    print("\n🔍 测试监控状态功能...")
    print("=" * 50)
    
    try:
        from app.services.enhanced_zero_history_monitor import EnhancedZeroHistoryMonitor
        
        monitor = EnhancedZeroHistoryMonitor()
        
        # 获取状态信息
        status_info = monitor.get_status_info()
        
        print("📊 监控器状态信息:")
        for key, value in status_info.items():
            print(f"  {key}: {value}")
        
        # 获取微信信息
        wechat_info = monitor.get_wechat_info()
        
        print("\n📱 微信连接信息:")
        for key, value in wechat_info.items():
            print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🧪 智能消息监控测试")
    print("=" * 60)
    print("时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    # 创建Qt应用（用于信号处理）
    app = QCoreApplication(sys.argv)
    
    results = []
    
    # 测试1: 监控状态
    results.append(("监控状态测试", test_monitoring_status()))
    
    # 测试2: 实际监控
    results.append(("智能监控测试", test_monitoring_with_real_contact()))
    
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
        print("⚠️ 部分测试通过，监控功能基本正常")
        print("💡 建议检查失败的测试项目")
    else:
        print("💥 所有测试失败，需要进一步检查")
    
    print("\n📝 使用建议:")
    print("- 确保微信已启动并登录")
    print("- 选择有消息记录的联系人进行测试")
    print("- 发送包含记账关键词的消息进行测试")
    print("- 观察程序日志了解详细运行情况")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
