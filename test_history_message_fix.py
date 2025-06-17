#!/usr/bin/env python3
"""
测试历史消息处理修复方案
验证启动时历史消息记录和后续新消息处理
"""

import sys
import os
import time
import threading
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_startup_message_recording():
    """测试启动时历史消息记录"""
    print("=" * 80)
    print("测试启动时历史消息记录")
    print("=" * 80)
    
    try:
        # 导入微信实例
        import wxauto
        wx = wxauto.WeChat()
        
        chat_name = "测试test"
        
        print(f"开始测试聊天对象: {chat_name}")
        print("-" * 80)
        
        # 添加监听
        wx.AddListenChat(chat_name)
        print(f"✅ 已添加监听对象: {chat_name}")
        
        # 模拟启动时历史消息记录过程
        startup_message_ids = set()
        max_attempts = 5  # 减少测试时间
        total_messages = 0
        
        print(f"\n开始记录历史消息（最多{max_attempts}次尝试）...")
        
        for attempt in range(max_attempts):
            print(f"\n第{attempt + 1}次获取历史消息...")
            
            # 获取消息
            messages = wx.GetListenMessage(chat_name)
            
            if messages and isinstance(messages, list):
                batch_count = 0
                new_messages = []
                
                for message in messages:
                    # 生成简单的消息ID
                    content = getattr(message, 'content', str(message))
                    sender = getattr(message, 'sender_remark', None) or getattr(message, 'sender', 'unknown')
                    msg_type = getattr(message, 'type', 'unknown')
                    
                    message_id = f"{sender}:{content}"
                    
                    if message_id not in startup_message_ids:
                        startup_message_ids.add(message_id)
                        batch_count += 1
                        new_messages.append({
                            'type': msg_type,
                            'sender': sender,
                            'content': content[:50] + ('...' if len(content) > 50 else '')
                        })
                
                total_messages += batch_count
                print(f"  获取到{len(messages)}条消息，其中{batch_count}条为新消息")
                
                # 显示新消息详情
                if new_messages:
                    print("  新消息详情:")
                    for i, msg in enumerate(new_messages[:5], 1):  # 只显示前5条
                        print(f"    {i}. [{msg['type']}] {msg['sender']}: {msg['content']}")
                    if len(new_messages) > 5:
                        print(f"    ... 还有{len(new_messages) - 5}条消息")
                
                # 如果这次没有新消息，说明历史消息已经全部获取完毕
                if batch_count == 0:
                    print(f"  ✅ 历史消息获取完毕，共记录{total_messages}条历史消息")
                    break
            else:
                print(f"  第{attempt + 1}次获取到空消息列表")
            
            # 等待1秒再次获取
            print("  等待1秒...")
            time.sleep(1)
        
        print(f"\n📊 历史消息记录统计:")
        print(f"  总尝试次数: {attempt + 1}")
        print(f"  记录的历史消息数: {len(startup_message_ids)}")
        print(f"  累计处理消息数: {total_messages}")
        
        # 额外等待，确保微信内部状态稳定
        print("\n等待3秒，确保微信内部状态稳定...")
        time.sleep(3)
        
        # 测试后续消息获取
        print("\n测试后续消息获取...")
        subsequent_messages = wx.GetListenMessage(chat_name)
        
        if subsequent_messages:
            print(f"⚠️  后续获取到{len(subsequent_messages)}条消息（应该为0或很少）")
            for i, msg in enumerate(subsequent_messages[:3], 1):
                content = getattr(msg, 'content', str(msg))
                sender = getattr(msg, 'sender_remark', None) or getattr(msg, 'sender', 'unknown')
                msg_type = getattr(msg, 'type', 'unknown')
                print(f"  {i}. [{msg_type}] {sender}: {content[:50]}...")
        else:
            print("✅ 后续获取为空，历史消息处理正常")
        
        return startup_message_ids
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        print(f"异常详情: {traceback.format_exc()}")
        return None

def test_new_message_detection(startup_message_ids):
    """测试新消息检测"""
    print("\n" + "=" * 80)
    print("测试新消息检测")
    print("=" * 80)
    
    if not startup_message_ids:
        print("❌ 没有历史消息ID，跳过新消息检测测试")
        return
    
    try:
        import wxauto
        wx = wxauto.WeChat()
        
        chat_name = "测试test"
        
        print(f"历史消息ID数量: {len(startup_message_ids)}")
        print("请在微信中发送一条新消息，然后等待10秒...")
        
        # 监控新消息
        for i in range(10):
            time.sleep(1)
            messages = wx.GetListenMessage(chat_name)
            
            if messages:
                print(f"\n⏰ {i+1}秒后检测到{len(messages)}条消息:")
                
                new_message_count = 0
                history_message_count = 0
                
                for j, message in enumerate(messages, 1):
                    content = getattr(message, 'content', str(message))
                    sender = getattr(message, 'sender_remark', None) or getattr(message, 'sender', 'unknown')
                    msg_type = getattr(message, 'type', 'unknown')
                    
                    message_id = f"{sender}:{content}"
                    
                    if message_id in startup_message_ids:
                        history_message_count += 1
                        status = "📜 历史"
                    else:
                        new_message_count += 1
                        status = "🆕 新消息"
                    
                    print(f"  {j}. {status} | [{msg_type}] {sender}: {content[:50]}...")
                
                print(f"\n📊 消息分类统计:")
                print(f"  新消息: {new_message_count}")
                print(f"  历史消息: {history_message_count}")
                print(f"  过滤率: {history_message_count/(new_message_count+history_message_count)*100:.1f}%")
                
                if new_message_count > 0:
                    print("✅ 检测到新消息，历史消息过滤正常工作")
                    break
            else:
                print(f"⏳ {i+1}/10 秒 - 暂无消息")
        
    except Exception as e:
        print(f"❌ 新消息检测测试失败: {e}")

def test_message_type_filtering():
    """测试消息类型过滤"""
    print("\n" + "=" * 80)
    print("测试消息类型过滤")
    print("=" * 80)
    
    try:
        import wxauto
        wx = wxauto.WeChat()
        
        chat_name = "测试test"
        
        # 获取一些消息进行类型分析
        messages = wx.GetListenMessage(chat_name)
        
        if not messages:
            print("📊 没有消息可供分析")
            return
        
        print(f"📊 分析{len(messages)}条消息的类型分布:")
        
        type_stats = {}
        friend_messages = []
        
        for message in messages:
            msg_type = getattr(message, 'type', 'unknown')
            type_stats[msg_type] = type_stats.get(msg_type, 0) + 1
            
            if msg_type == 'friend':
                content = getattr(message, 'content', str(message))
                sender = getattr(message, 'sender_remark', None) or getattr(message, 'sender', 'unknown')
                friend_messages.append({
                    'sender': sender,
                    'content': content[:50] + ('...' if len(content) > 50 else '')
                })
        
        print("\n消息类型统计:")
        for msg_type, count in sorted(type_stats.items()):
            percentage = count / len(messages) * 100
            print(f"  {msg_type:8s}: {count:3d} 条 ({percentage:5.1f}%)")
        
        print(f"\n只处理friend类型消息的效果:")
        print(f"  总消息数: {len(messages)}")
        print(f"  friend消息数: {type_stats.get('friend', 0)}")
        print(f"  过滤掉的消息数: {len(messages) - type_stats.get('friend', 0)}")
        print(f"  过滤率: {(len(messages) - type_stats.get('friend', 0))/len(messages)*100:.1f}%")
        
        if friend_messages:
            print(f"\nfriend类型消息示例（前5条）:")
            for i, msg in enumerate(friend_messages[:5], 1):
                print(f"  {i}. {msg['sender']}: {msg['content']}")
        
    except Exception as e:
        print(f"❌ 消息类型过滤测试失败: {e}")

def main():
    """主函数"""
    print("开始测试历史消息处理修复方案...")
    
    # 1. 测试启动时历史消息记录
    startup_message_ids = test_startup_message_recording()
    
    # 2. 测试新消息检测
    if startup_message_ids:
        test_new_message_detection(startup_message_ids)
    
    # 3. 测试消息类型过滤
    test_message_type_filtering()
    
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    print("修复方案要点:")
    print("1. 启动时多次调用GetListenMessage，记录所有历史消息ID")
    print("2. 运行时跳过已记录的历史消息ID")
    print("3. 只处理friend类型的消息，过滤sys、time、self等类型")
    print("4. 使用简单的发送者+内容组合进行去重")
    
    print("\n预期效果:")
    print("- 启动时不处理任何历史消息")
    print("- 运行时只处理真正的新朋友消息")
    print("- 大幅减少重复处理和系统回复循环")
    print("- 提高系统稳定性和性能")

if __name__ == "__main__":
    main()
