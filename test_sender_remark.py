#!/usr/bin/env python3
"""
测试发送者备注名功能
验证消息监控服务是否正确提取和使用sender_remark属性
"""

import sys
import os
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.simple_message_processor import SimpleMessageProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_simple_message_processor():
    """测试简化版消息处理器"""
    logger.info("开始测试简化版消息处理器...")
    
    processor = SimpleMessageProcessor()
    
    # 测试不带发送者名称的调用
    logger.info("测试1: 不带发送者名称")
    success, result = processor.process_message("买饮料，4块钱")
    logger.info(f"结果: 成功={success}, 消息={result}")
    
    # 测试带发送者名称的调用
    logger.info("测试2: 带发送者名称")
    success, result = processor.process_message("买饮料，4块钱", "张杰")
    logger.info(f"结果: 成功={success}, 消息={result}")
    
    # 测试带发送者备注名的调用
    logger.info("测试3: 带发送者备注名")
    success, result = processor.process_message("买饮料，4块钱", "小杰")
    logger.info(f"结果: 成功={success}, 消息={result}")

def create_mock_message():
    """创建模拟的FriendMessage对象"""
    class MockFriendMessage:
        def __init__(self, content, sender, sender_remark=None):
            self.type = 'friend'
            self.content = content
            self.sender = sender
            self.sender_remark = sender_remark
    
    return MockFriendMessage("买饮料，4块钱", "测试群", "张杰")

def test_message_extraction():
    """测试消息属性提取逻辑"""
    logger.info("开始测试消息属性提取逻辑...")
    
    # 创建模拟消息
    message = create_mock_message()
    
    # 模拟监控服务中的提取逻辑
    sender_name = None
    if hasattr(message, 'sender_remark') and message.sender_remark:
        sender_name = message.sender_remark
        logger.info(f"使用发送者备注名: {sender_name}")
    elif hasattr(message, 'sender') and message.sender:
        sender_name = message.sender
        logger.info(f"使用发送者名称: {sender_name}")
    else:
        sender_name = "未知发送者"
        logger.info(f"使用默认发送者名称: {sender_name}")
    
    logger.info(f"最终提取的发送者名称: {sender_name}")
    
    # 测试处理消息
    processor = SimpleMessageProcessor()
    success, result = processor.process_message(message.content, sender_name)
    logger.info(f"处理结果: 成功={success}, 消息={result}")

def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始测试发送者备注名功能")
    logger.info("=" * 50)
    
    try:
        # 测试简化版消息处理器
        test_simple_message_processor()
        
        print("\n" + "=" * 50)
        
        # 测试消息属性提取
        test_message_extraction()
        
        logger.info("=" * 50)
        logger.info("测试完成")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"测试过程中发生异常: {e}")
        import traceback
        logger.error(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
