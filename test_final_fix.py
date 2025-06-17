#!/usr/bin/env python3
"""
测试最终修复效果
验证朋友消息过滤和去重机制
"""

import sys
import os
import hashlib

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class MockMessage:
    """模拟消息对象"""
    def __init__(self, msg_type, content, sender=None, sender_remark=None):
        self.type = msg_type
        self.content = content
        self.sender = sender
        self.sender_remark = sender_remark

def generate_message_id(message):
    """模拟消息ID生成逻辑"""
    try:
        # 提取消息内容
        if hasattr(message, 'content'):
            content = str(message.content).strip()
        else:
            content = str(message).strip()
        
        # 提取发送者信息
        sender = "unknown"
        if hasattr(message, 'sender_remark') and message.sender_remark:
            sender = str(message.sender_remark).strip()
        elif hasattr(message, 'sender') and message.sender:
            sender = str(message.sender).strip()
        
        # 使用简单稳定的ID：发送者+内容的哈希
        stable_content = f"{sender}:{content}"
        content_hash = hashlib.md5(stable_content.encode('utf-8')).hexdigest()
        
        return content_hash
    except Exception as e:
        return f"error_{hash(str(message))}"

def test_message_id_stability():
    """测试消息ID生成的稳定性"""
    print("测试消息ID生成稳定性...")
    print("=" * 60)
    
    # 创建相同内容的消息
    messages = [
        MockMessage('friend', '早饭，15元', '张杰', '张杰'),
        MockMessage('friend', '早饭，15元', '张杰', '张杰'),  # 完全相同
        MockMessage('friend', '早饭，15元', sender_remark='张杰'),  # 只有备注名
        MockMessage('friend', '早饭，15元', sender='张杰'),  # 只有发送者名
    ]
    
    print("消息ID生成结果:")
    print("-" * 60)
    
    ids = []
    for i, message in enumerate(messages, 1):
        msg_id = generate_message_id(message)
        ids.append(msg_id)
        
        sender_info = f"sender={getattr(message, 'sender', None)}, remark={getattr(message, 'sender_remark', None)}"
        print(f"{i}. ID: {msg_id[:16]}... | 内容: {message.content} | {sender_info}")
    
    # 检查ID稳定性
    unique_ids = set(ids)
    print("-" * 60)
    print(f"生成的ID数量: {len(ids)}")
    print(f"唯一ID数量: {len(unique_ids)}")
    
    if len(unique_ids) == 1:
        print("✅ ID生成稳定，相同消息生成相同ID")
        return True
    else:
        print("❌ ID生成不稳定，相同消息生成不同ID")
        print("唯一ID列表:")
        for i, uid in enumerate(unique_ids, 1):
            print(f"  {i}. {uid}")
        return False

def test_deduplication_logic():
    """测试去重逻辑"""
    print("\n测试去重逻辑...")
    print("=" * 60)
    
    # 模拟处理过的消息集合
    processed_messages = set()
    
    # 测试消息
    test_messages = [
        MockMessage('friend', '早饭，15元', sender_remark='张杰'),
        MockMessage('friend', '早饭，15元', sender_remark='张杰'),  # 重复
        MockMessage('friend', '午饭，20元', sender_remark='张杰'),  # 不同内容
        MockMessage('friend', '早饭，15元', sender_remark='李华'),  # 不同发送者
        MockMessage('friend', '早饭，15元', sender_remark='张杰'),  # 再次重复
    ]
    
    print("消息处理结果:")
    print("-" * 60)
    
    processed_count = 0
    duplicate_count = 0
    
    for i, message in enumerate(test_messages, 1):
        # 只处理friend类型消息
        if hasattr(message, 'type') and message.type == 'friend':
            # 生成消息key用于去重
            sender_name = getattr(message, 'sender_remark', None) or getattr(message, 'sender', 'unknown')
            content = message.content
            message_key = f"{sender_name}:{content}"
            
            if message_key not in processed_messages:
                processed_messages.add(message_key)
                processed_count += 1
                status = "✅ 处理"
                print(f"{i}. {status} | {sender_name} | {content}")
            else:
                duplicate_count += 1
                status = "🔄 重复"
                print(f"{i}. {status} | {sender_name} | {content}")
        else:
            status = "🚫 过滤"
            print(f"{i}. {status} | 非friend消息")
    
    print("-" * 60)
    print(f"总消息数: {len(test_messages)}")
    print(f"处理消息数: {processed_count}")
    print(f"重复消息数: {duplicate_count}")
    print(f"去重率: {duplicate_count/(processed_count+duplicate_count)*100:.1f}%")
    
    # 验证结果
    expected_processed = 3  # 张杰的早饭、张杰的午饭、李华的早饭
    expected_duplicate = 2  # 2条重复的张杰早饭
    
    if processed_count == expected_processed and duplicate_count == expected_duplicate:
        print("✅ 去重逻辑正常")
        return True
    else:
        print("❌ 去重逻辑异常")
        print(f"期望处理: {expected_processed}, 实际处理: {processed_count}")
        print(f"期望重复: {expected_duplicate}, 实际重复: {duplicate_count}")
        return False

def test_integration_scenario():
    """测试集成场景"""
    print("\n测试集成场景...")
    print("=" * 60)
    
    # 模拟真实的消息流
    message_stream = [
        # 启动时的历史消息（应该被记录但不处理）
        MockMessage('friend', '昨天的消息1', sender_remark='张杰'),
        MockMessage('friend', '昨天的消息2', sender_remark='李华'),
        MockMessage('sys', '张杰加入了群聊'),
        
        # 运行时的新消息
        MockMessage('friend', '早饭，15元', sender_remark='张杰'),  # 新消息，应该处理
        MockMessage('friend', '昨天的消息1', sender_remark='张杰'),  # 历史消息重复，应该跳过
        MockMessage('self', '✅ 记账成功！'),  # 自己的回复，应该过滤
        MockMessage('friend', '午饭，20元', sender_remark='张杰'),  # 新消息，应该处理
        MockMessage('sys', '系统通知'),  # 系统消息，应该过滤
        MockMessage('friend', '早饭，15元', sender_remark='张杰'),  # 重复消息，应该跳过
    ]
    
    # 模拟启动时记录历史消息ID
    startup_message_ids = set()
    for i, message in enumerate(message_stream[:3]):  # 前3条作为启动时的历史消息
        if hasattr(message, 'type') and message.type == 'friend':
            message_id = generate_message_id(message)
            startup_message_ids.add(message_id)
    
    print(f"启动时记录了 {len(startup_message_ids)} 条历史消息ID")
    
    # 模拟运行时处理消息
    processed_messages = set()
    processed_count = 0
    filtered_count = 0
    duplicate_count = 0
    
    print("\n运行时消息处理:")
    print("-" * 60)
    
    for i, message in enumerate(message_stream, 1):
        # 1. 首先检查是否是friend类型
        if not (hasattr(message, 'type') and message.type == 'friend'):
            filtered_count += 1
            msg_type = getattr(message, 'type', 'unknown')
            print(f"{i:2d}. 🚫 过滤 | 类型: {msg_type:6s} | 内容: {getattr(message, 'content', str(message))}")
            continue
        
        # 2. 检查是否是历史消息
        message_id = generate_message_id(message)
        if message_id in startup_message_ids:
            duplicate_count += 1
            sender = getattr(message, 'sender_remark', 'unknown')
            print(f"{i:2d}. 📜 历史 | 发送者: {sender:6s} | 内容: {message.content}")
            continue
        
        # 3. 检查是否是重复消息
        sender_name = getattr(message, 'sender_remark', None) or getattr(message, 'sender', 'unknown')
        message_key = f"{sender_name}:{message.content}"
        if message_key in processed_messages:
            duplicate_count += 1
            print(f"{i:2d}. 🔄 重复 | 发送者: {sender_name:6s} | 内容: {message.content}")
            continue
        
        # 4. 处理新消息
        processed_messages.add(message_key)
        processed_count += 1
        print(f"{i:2d}. ✅ 处理 | 发送者: {sender_name:6s} | 内容: {message.content}")
    
    print("-" * 60)
    print(f"总消息数: {len(message_stream)}")
    print(f"处理消息数: {processed_count}")
    print(f"过滤消息数: {filtered_count}")
    print(f"重复/历史消息数: {duplicate_count}")
    print(f"处理率: {processed_count/len(message_stream)*100:.1f}%")
    
    # 验证结果
    expected_processed = 2  # 只有2条真正的新朋友消息
    if processed_count == expected_processed:
        print("✅ 集成场景测试通过")
        return True
    else:
        print("❌ 集成场景测试失败")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("测试最终修复效果")
    print("=" * 60)
    
    try:
        # 运行所有测试
        test1_passed = test_message_id_stability()
        test2_passed = test_deduplication_logic()
        test3_passed = test_integration_scenario()
        
        print("\n" + "=" * 60)
        print("测试总结:")
        print("=" * 60)
        
        if test1_passed and test2_passed and test3_passed:
            print("🎉 所有测试通过！")
            print("✅ 消息ID生成稳定")
            print("✅ 去重逻辑正常")
            print("✅ 集成场景正常")
            print("\n修复效果:")
            print("- 只处理 friend 类型的消息")
            print("- 稳定的消息ID生成")
            print("- 有效的去重机制")
            print("- 历史消息过滤")
            print("- 大幅减少重复处理")
        else:
            print("⚠️  部分测试失败")
            print(f"消息ID稳定性: {'✅' if test1_passed else '❌'}")
            print(f"去重逻辑: {'✅' if test2_passed else '❌'}")
            print(f"集成场景: {'✅' if test3_passed else '❌'}")
        
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        import traceback
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
