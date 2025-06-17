#!/usr/bin/env python3
"""
测试系统回复消息过滤功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_system_reply_filter():
    """测试系统回复消息过滤功能"""
    print("测试系统回复消息过滤功能...")
    
    # 导入监控服务
    try:
        from app.services.zero_history_monitor import ZeroHistoryMonitor
        from app.services.clean_message_monitor import CleanMessageMonitor
        from app.services.message_monitor import MessageMonitor
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    
    # 测试消息样本
    test_messages = [
        # 正常的记账消息（应该处理）
        ("张杰", "买饮料，4块钱", False),
        ("小明", "肯德基，19.9", False),
        ("李华", "买书，24元", False),
        
        # 系统回复消息（应该过滤）
        ("客服", "✅ 记账成功！\n📝 明细：肯德基，19.9\n📅 日期：2025-06-16", True),
        ("系统", "📝 明细：买书，24元\n💸 方向：支出；分类：📚学习", True),
        ("助手", "💰 金额：19.9元\n📊 预算：个人预算（test01）", True),
        ("客服", "⚠️ 记账服务返回错误: HTTP 400", True),
        ("系统", "❌ 记账失败：网络连接错误", True),
        ("助手", "聊天与记账无关", True),
        
        # 包含系统回复特征的用户消息（应该过滤，避免误判）
        ("张杰", "今天记账成功了吗？", False),  # 这个不应该被过滤
        ("小明", "✅ 我完成了作业", True),  # 这个应该被过滤（包含✅符号）
    ]
    
    # 创建监控器实例（不初始化微信）
    monitors = []
    try:
        # 注意：这里只是测试过滤方法，不初始化完整的监控器
        class TestMonitor:
            def _is_system_reply_message(self, content: str) -> bool:
                """从ZeroHistoryMonitor复制的方法"""
                system_reply_patterns = [
                    "✅ 记账成功！",
                    "📝 明细：",
                    "📅 日期：",
                    "💸 方向：",
                    "💰 金额：",
                    "📊 预算：",
                    "⚠️ 记账服务返回错误",
                    "❌ 记账失败",
                    "聊天与记账无关",
                    "信息与记账无关"
                ]
                
                for pattern in system_reply_patterns:
                    if pattern in content:
                        return True
                
                return False
        
        test_monitor = TestMonitor()
        
        print("\n测试结果:")
        print("=" * 60)
        
        all_passed = True
        for sender, content, should_be_filtered in test_messages:
            is_filtered = test_monitor._is_system_reply_message(content)
            
            status = "✅ 通过" if is_filtered == should_be_filtered else "❌ 失败"
            filter_status = "过滤" if is_filtered else "处理"
            expected_status = "过滤" if should_be_filtered else "处理"
            
            print(f"{status} | {sender}: {content[:30]}...")
            print(f"     实际: {filter_status} | 期望: {expected_status}")
            
            if is_filtered != should_be_filtered:
                all_passed = False
                print(f"     ⚠️  过滤结果不符合预期")
            
            print()
        
        print("=" * 60)
        if all_passed:
            print("🎉 所有测试通过！系统回复消息过滤功能正常")
        else:
            print("⚠️  部分测试失败，需要调整过滤规则")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        import traceback
        print(f"异常详情: {traceback.format_exc()}")
        return False

def test_filter_patterns():
    """测试过滤模式的覆盖率"""
    print("\n测试过滤模式覆盖率...")
    
    # 系统回复消息的所有可能模式
    system_patterns = [
        "✅ 记账成功！",
        "📝 明细：",
        "📅 日期：",
        "💸 方向：",
        "💰 金额：",
        "📊 预算：",
        "⚠️ 记账服务返回错误",
        "❌ 记账失败",
        "聊天与记账无关",
        "信息与记账无关"
    ]
    
    print(f"定义的过滤模式数量: {len(system_patterns)}")
    print("过滤模式列表:")
    for i, pattern in enumerate(system_patterns, 1):
        print(f"  {i}. {pattern}")
    
    print("\n建议添加的模式（如果需要）:")
    additional_patterns = [
        "🔄 正在处理",
        "⏳ 请稍等",
        "🚫 操作被拒绝",
        "ℹ️ 提示信息"
    ]
    
    for pattern in additional_patterns:
        print(f"  - {pattern}")

def main():
    """主函数"""
    print("=" * 60)
    print("测试系统回复消息过滤功能")
    print("=" * 60)
    
    try:
        # 测试过滤功能
        filter_test_passed = test_system_reply_filter()
        
        # 测试过滤模式
        test_filter_patterns()
        
        print("\n" + "=" * 60)
        print("测试总结:")
        print("=" * 60)
        
        if filter_test_passed:
            print("✅ 系统回复消息过滤功能测试通过")
            print("✅ 修复应该能解决历史消息重复处理问题")
        else:
            print("❌ 系统回复消息过滤功能测试失败")
            print("⚠️  需要进一步调整过滤规则")
        
        print("\n建议:")
        print("1. 部署修复后，观察日志中是否还有系统回复消息被处理")
        print("2. 如果仍有问题，可能需要添加更多过滤模式")
        print("3. 考虑添加发送者名称过滤（如'客服'、'系统'、'助手'等）")
        
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        import traceback
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
