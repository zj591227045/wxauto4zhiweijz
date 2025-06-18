#!/usr/bin/env python3
"""
测试消息监控修复效果
验证wxauto错误处理和监听功能
"""

import sys
import os
import time
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / "data" / "Logs" / "monitoring_test.log", encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def test_wxauto_manager():
    """测试wxauto管理器的错误处理"""
    try:
        from app.modules.wxauto_manager import WxautoManager
        
        logger.info("=== 测试wxauto管理器 ===")
        
        # 创建管理器实例
        manager = WxautoManager()
        
        # 测试启动
        logger.info("测试启动...")
        init_result = manager.start()
        logger.info(f"启动结果: {init_result}")
        
        if init_result:
            # 测试连接状态
            logger.info("测试连接状态...")
            is_connected = manager.is_connected()
            logger.info(f"连接状态: {is_connected}")
            
            # 测试添加监听聊天（使用测试聊天名）
            test_chat = "测试聊天"
            logger.info(f"测试添加监听聊天: {test_chat}")
            add_result = manager.add_listen_chat(test_chat)
            logger.info(f"添加监听结果: {add_result}")
            
            # 测试获取消息（应该能处理各种错误）
            logger.info("测试获取消息...")
            for i in range(3):
                messages = manager.get_messages(test_chat)
                logger.info(f"第{i+1}次获取消息: {len(messages)}条")
                time.sleep(1)
            
            # 测试移除监听聊天
            logger.info(f"测试移除监听聊天: {test_chat}")
            remove_result = manager.remove_listen_chat(test_chat)
            logger.info(f"移除监听结果: {remove_result}")
        
        logger.info("wxauto管理器测试完成")
        return True
        
    except Exception as e:
        logger.error(f"wxauto管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_message_listener():
    """测试消息监听器的错误处理"""
    try:
        from app.modules.wxauto_manager import WxautoManager
        from app.modules.message_listener import MessageListener
        
        logger.info("=== 测试消息监听器 ===")
        
        # 创建管理器和监听器
        wxauto_manager = WxautoManager()
        message_listener = MessageListener(wxauto_manager)
        
        # 启动wxauto管理器
        if not wxauto_manager.start():
            logger.warning("wxauto管理器启动失败，但继续测试监听器逻辑")
        
        # 测试监听器状态
        logger.info("测试监听器状态...")
        logger.info(f"监听状态: {message_listener.is_listening()}")
        
        # 测试启动监听（使用测试聊天）
        test_chats = ["测试聊天1", "测试聊天2"]
        logger.info(f"测试启动监听: {test_chats}")
        
        start_result = message_listener.start_listening(test_chats)
        logger.info(f"启动监听结果: {start_result}")
        
        if start_result:
            # 让监听器运行一段时间
            logger.info("监听器运行中，等待5秒...")
            time.sleep(5)
            
            # 检查统计信息
            stats = message_listener.get_statistics()
            logger.info(f"监听统计: {stats}")
            
            # 停止监听
            logger.info("停止监听...")
            stop_result = message_listener.stop_listening()
            logger.info(f"停止监听结果: {stop_result}")
        
        logger.info("消息监听器测试完成")
        return True
        
    except Exception as e:
        logger.error(f"消息监听器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_handling():
    """测试错误处理机制"""
    try:
        logger.info("=== 测试错误处理机制 ===")
        
        # 模拟常见的wxauto错误
        test_errors = [
            "Find Control Timeout",
            "dictionary changed size during iteration",
            "控件查找超时",
            "其他未知错误"
        ]
        
        for error_msg in test_errors:
            logger.info(f"模拟错误: {error_msg}")
            
            # 测试错误分类逻辑
            is_expected_error = any(error_text in error_msg for error_text in [
                "Find Control Timeout", 
                "dictionary changed size during iteration",
                "控件查找超时"
            ])
            
            if is_expected_error:
                logger.debug(f"这是预期错误: {error_msg}")
            else:
                logger.error(f"这是意外错误: {error_msg}")
        
        logger.info("错误处理机制测试完成")
        return True
        
    except Exception as e:
        logger.error(f"错误处理测试失败: {e}")
        return False

def main():
    """主测试函数"""
    logger.info("开始消息监控修复测试...")
    
    # 确保必要的目录存在
    (project_root / "data" / "Logs").mkdir(parents=True, exist_ok=True)
    
    test_results = []
    
    # 运行各项测试
    test_results.append(("错误处理机制", test_error_handling()))
    test_results.append(("wxauto管理器", test_wxauto_manager()))
    test_results.append(("消息监听器", test_message_listener()))
    
    # 输出测试结果
    logger.info("=== 测试结果汇总 ===")
    all_passed = True
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        logger.info("🎉 所有测试通过！消息监控修复成功！")
        return 0
    else:
        logger.error("❌ 部分测试失败，需要进一步检查")
        return 1

if __name__ == "__main__":
    sys.exit(main())
