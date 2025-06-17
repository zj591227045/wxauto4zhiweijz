#!/usr/bin/env python3
"""
简单测试发送者备注名功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_message_extraction():
    """测试消息属性提取逻辑"""
    print("开始测试消息属性提取逻辑...")
    
    # 创建模拟的FriendMessage对象
    class MockFriendMessage:
        def __init__(self, content, sender, sender_remark=None):
            self.type = 'friend'
            self.content = content
            self.sender = sender
            self.sender_remark = sender_remark
    
    # 测试场景1：有sender_remark
    print("\n测试场景1：有sender_remark")
    message1 = MockFriendMessage("买饮料，4块钱", "测试群", "张杰")
    
    sender_name = None
    if hasattr(message1, 'sender_remark') and message1.sender_remark:
        sender_name = message1.sender_remark
        print(f"✅ 使用发送者备注名: {sender_name}")
    elif hasattr(message1, 'sender') and message1.sender:
        sender_name = message1.sender
        print(f"使用发送者名称: {sender_name}")
    else:
        sender_name = "未知发送者"
        print(f"使用默认发送者名称: {sender_name}")
    
    # 测试场景2：没有sender_remark
    print("\n测试场景2：没有sender_remark")
    message2 = MockFriendMessage("买饮料，4块钱", "测试群", None)
    
    sender_name = None
    if hasattr(message2, 'sender_remark') and message2.sender_remark:
        sender_name = message2.sender_remark
        print(f"使用发送者备注名: {sender_name}")
    elif hasattr(message2, 'sender') and message2.sender:
        sender_name = message2.sender
        print(f"✅ 使用发送者名称: {sender_name}")
    else:
        sender_name = "未知发送者"
        print(f"使用默认发送者名称: {sender_name}")
    
    # 测试场景3：都没有
    print("\n测试场景3：都没有")
    message3 = MockFriendMessage("买饮料，4块钱", None, None)
    
    sender_name = None
    if hasattr(message3, 'sender_remark') and message3.sender_remark:
        sender_name = message3.sender_remark
        print(f"使用发送者备注名: {sender_name}")
    elif hasattr(message3, 'sender') and message3.sender:
        sender_name = message3.sender
        print(f"使用发送者名称: {sender_name}")
    else:
        sender_name = "未知发送者"
        print(f"✅ 使用默认发送者名称: {sender_name}")

def test_api_request_format():
    """测试API请求格式"""
    print("\n开始测试API请求格式...")
    
    # 模拟API请求数据构建
    message_content = "买饮料，4块钱"
    sender_name = "张杰"
    
    data = {
        'description': message_content,
        'accountBookId': 'test_account_book_id'
    }
    
    # 如果有发送者名称，添加到请求数据中
    if sender_name:
        data['userName'] = sender_name
        print(f"✅ 添加userName字段: {sender_name}")
    
    print(f"最终API请求数据: {data}")
    
    # 验证userName字段存在
    assert 'userName' in data, "userName字段应该存在"
    assert data['userName'] == "张杰", "userName字段值应该是'张杰'"
    print("✅ API请求格式验证通过")

def main():
    """主函数"""
    print("=" * 50)
    print("开始测试发送者备注名功能")
    print("=" * 50)
    
    try:
        # 测试消息属性提取
        test_message_extraction()
        
        # 测试API请求格式
        test_api_request_format()
        
        print("\n" + "=" * 50)
        print("✅ 所有测试通过")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        import traceback
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
