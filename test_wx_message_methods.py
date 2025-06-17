#!/usr/bin/env python3
"""
测试微信消息获取方法的实际行为
验证GetListenMessage、GetAllMessage等方法是否符合预期
"""

import sys
import os
import time
import threading
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_wx_message_methods():
    """测试微信消息获取方法"""
    print("=" * 80)
    print("测试微信消息获取方法的实际行为")
    print("=" * 80)
    
    try:
        # 直接导入wxauto
        import wxauto
        wx = wxauto.WeChat()

        if not wx:
            print("❌ 无法获取微信实例")
            return False

        print(f"✅ 微信实例获取成功")
        
        # 测试目标
        chat_name = "测试test"
        
        print(f"\n开始测试聊天对象: {chat_name}")
        print("-" * 80)
        
        # 1. 测试AddListenChat
        print("1. 测试AddListenChat...")
        try:
            wx.AddListenChat(chat_name)
            print(f"✅ 成功添加监听对象: {chat_name}")
        except Exception as e:
            print(f"❌ 添加监听对象失败: {e}")
            return False
        
        # 2. 测试GetAllMessage
        print("\n2. 测试GetAllMessage...")
        try:
            all_messages = wx.GetAllMessage(chat_name)
            if all_messages:
                print(f"📊 GetAllMessage返回 {len(all_messages)} 条消息")
                print("最近5条消息:")
                for i, msg in enumerate(all_messages[-5:], 1):
                    msg_type = getattr(msg, 'type', 'unknown')
                    content = getattr(msg, 'content', str(msg))
                    sender = getattr(msg, 'sender_remark', None) or getattr(msg, 'sender', 'unknown')
                    print(f"  {i}. 类型:{msg_type:6s} | 发送者:{sender:8s} | 内容:{content[:30]}...")
            else:
                print("📊 GetAllMessage返回空列表")
        except Exception as e:
            print(f"❌ GetAllMessage失败: {e}")
        
        # 3. 测试GetListenMessage（初始状态）
        print("\n3. 测试GetListenMessage（初始状态）...")
        try:
            listen_messages = wx.GetListenMessage(chat_name)
            if listen_messages:
                print(f"📊 GetListenMessage返回 {len(listen_messages)} 条消息")
                print("消息列表:")
                for i, msg in enumerate(listen_messages, 1):
                    msg_type = getattr(msg, 'type', 'unknown')
                    content = getattr(msg, 'content', str(msg))
                    sender = getattr(msg, 'sender_remark', None) or getattr(msg, 'sender', 'unknown')
                    print(f"  {i}. 类型:{msg_type:6s} | 发送者:{sender:8s} | 内容:{content[:30]}...")
            else:
                print("📊 GetListenMessage返回空列表")
        except Exception as e:
            print(f"❌ GetListenMessage失败: {e}")
        
        # 4. 等待新消息并测试
        print("\n4. 等待新消息测试...")
        print("请在微信中发送一条新消息到测试群，然后等待10秒...")
        
        # 记录开始时间
        start_time = datetime.now()
        
        # 监控循环
        for i in range(10):
            time.sleep(1)
            try:
                new_messages = wx.GetListenMessage(chat_name)
                if new_messages:
                    current_time = datetime.now()
                    elapsed = (current_time - start_time).total_seconds()
                    
                    print(f"\n⏰ {elapsed:.1f}秒后检测到 {len(new_messages)} 条新消息:")
                    for j, msg in enumerate(new_messages, 1):
                        msg_type = getattr(msg, 'type', 'unknown')
                        content = getattr(msg, 'content', str(msg))
                        sender = getattr(msg, 'sender_remark', None) or getattr(msg, 'sender', 'unknown')
                        print(f"  {j}. 类型:{msg_type:6s} | 发送者:{sender:8s} | 内容:{content[:50]}...")
                    
                    # 分析消息类型
                    type_counts = {}
                    for msg in new_messages:
                        msg_type = getattr(msg, 'type', 'unknown')
                        type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
                    
                    print(f"📈 消息类型统计: {type_counts}")
                    break
                else:
                    print(f"⏳ {i+1}/10 秒 - 暂无新消息")
            except Exception as e:
                print(f"❌ 第{i+1}次检查失败: {e}")
        
        # 5. 再次测试GetListenMessage
        print("\n5. 再次测试GetListenMessage...")
        try:
            listen_messages_2 = wx.GetListenMessage(chat_name)
            if listen_messages_2:
                print(f"📊 第二次GetListenMessage返回 {len(listen_messages_2)} 条消息")
                
                # 检查是否返回了相同的消息
                if listen_messages and listen_messages_2:
                    same_count = 0
                    for msg1 in listen_messages:
                        content1 = getattr(msg1, 'content', str(msg1))
                        for msg2 in listen_messages_2:
                            content2 = getattr(msg2, 'content', str(msg2))
                            if content1 == content2:
                                same_count += 1
                                break
                    
                    print(f"🔍 重复消息数量: {same_count}")
                    if same_count > 0:
                        print("⚠️  GetListenMessage返回了重复的消息！")
                    else:
                        print("✅ GetListenMessage没有返回重复消息")
            else:
                print("📊 第二次GetListenMessage返回空列表")
        except Exception as e:
            print(f"❌ 第二次GetListenMessage失败: {e}")
        
        # 6. 对比测试结论
        print("\n" + "=" * 80)
        print("测试结论:")
        print("=" * 80)
        
        print("1. GetAllMessage行为:")
        print("   - 返回聊天的所有历史消息")
        print("   - 包含各种类型的消息（friend、sys、time、self等）")
        print("   - 适合获取历史记录，不适合实时监控")
        
        print("\n2. GetListenMessage行为:")
        print("   - 理论上只返回新消息")
        print("   - 实际测试中可能返回重复消息")
        print("   - 需要进一步验证是否真的只返回新消息")
        
        print("\n3. 建议:")
        print("   - 如果GetListenMessage确实返回重复消息，需要强化去重机制")
        print("   - 考虑使用消息时间戳或其他唯一标识进行去重")
        print("   - 可能需要结合多种方法来实现真正的新消息监控")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        import traceback
        print(f"异常详情: {traceback.format_exc()}")
        return False

def test_message_uniqueness():
    """测试消息唯一性标识"""
    print("\n" + "=" * 80)
    print("测试消息唯一性标识")
    print("=" * 80)
    
    try:
        import wxauto
        wx = wxauto.WeChat()
        
        chat_name = "测试test"
        
        # 获取消息
        messages = wx.GetListenMessage(chat_name)
        if not messages:
            print("📊 没有消息可供测试")
            return
        
        print(f"📊 分析 {len(messages)} 条消息的唯一性标识...")
        
        # 分析消息属性
        for i, msg in enumerate(messages[:5], 1):  # 只分析前5条
            print(f"\n消息 {i}:")
            print(f"  类型: {type(msg)}")
            print(f"  属性: {dir(msg)}")
            
            # 检查常见属性
            attrs_to_check = ['content', 'sender', 'sender_remark', 'type', 'time', 'timestamp', 'id', 'msgid']
            for attr in attrs_to_check:
                if hasattr(msg, attr):
                    value = getattr(msg, attr)
                    print(f"  {attr}: {value}")
        
        # 检查是否有时间戳或ID属性
        sample_msg = messages[0]
        has_timestamp = any(hasattr(sample_msg, attr) for attr in ['time', 'timestamp', 'created_at', 'send_time'])
        has_id = any(hasattr(sample_msg, attr) for attr in ['id', 'msgid', 'message_id'])
        
        print(f"\n📈 消息唯一性分析:")
        print(f"  有时间戳属性: {has_timestamp}")
        print(f"  有ID属性: {has_id}")
        
        if not has_timestamp and not has_id:
            print("⚠️  消息对象缺少时间戳和ID属性，去重可能困难")
            print("💡 建议使用内容+发送者的组合进行去重")
        
    except Exception as e:
        print(f"❌ 消息唯一性测试失败: {e}")

def main():
    """主函数"""
    print("开始测试微信消息获取方法...")
    
    # 基本方法测试
    success = test_wx_message_methods()
    
    if success:
        # 消息唯一性测试
        test_message_uniqueness()
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)
    
    if success:
        print("✅ 基本测试完成，请查看上述结果分析")
        print("💡 根据测试结果调整消息处理策略")
    else:
        print("❌ 测试失败，请检查微信连接状态")

if __name__ == "__main__":
    main()
