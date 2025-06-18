#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Token管理器测试脚本
用于验证token管理器是否正常工作
"""

import sys
import os
import json

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_token_manager():
    """测试token管理器"""
    print("=" * 50)
    print("Token管理器测试")
    print("=" * 50)
    
    try:
        # 导入必要的模块
        from app.utils.state_manager import state_manager
        from app.utils.token_manager import init_token_manager
        
        print("✓ 模块导入成功")
        
        # 检查配置文件
        config_file = "data/app_state.json"
        if not os.path.exists(config_file):
            print(f"✗ 配置文件不存在: {config_file}")
            return False
        
        # 读取配置
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        accounting_config = config.get('accounting_service', {})
        username = accounting_config.get('username', '')
        password = accounting_config.get('password', '')
        server_url = accounting_config.get('server_url', '')
        
        print(f"✓ 配置文件读取成功")
        print(f"  - 服务器: {server_url}")
        print(f"  - 用户名: {username}")
        print(f"  - 密码: {'***' if password else '未设置'}")
        
        if not all([username, password, server_url]):
            print("✗ 配置不完整，请先在界面中配置记账服务")
            return False
        
        # 初始化token管理器
        print("\n正在初始化token管理器...")
        token_manager = init_token_manager(state_manager)
        
        if not token_manager:
            print("✗ Token管理器初始化失败")
            return False
        
        print("✓ Token管理器初始化成功")
        
        # 测试获取token
        print("\n正在获取有效token...")
        token = token_manager.get_valid_token()
        
        if token:
            print(f"✓ 获取token成功: {token[:20]}...")
            
            # 获取token信息
            token_info = token_manager.get_token_info()
            if token_info:
                print(f"  - 用户ID: {token_info.user_id}")
                print(f"  - 邮箱: {token_info.email}")
                print(f"  - 过期时间: {token_info.expires_at}")
                print(f"  - 是否过期: {token_info.is_expired()}")
                print(f"  - 即将过期: {token_info.will_expire_soon()}")
        else:
            print("✗ 获取token失败")
            return False
        
        # 测试强制刷新
        print("\n正在测试强制刷新token...")
        refresh_success = token_manager.force_refresh()
        
        if refresh_success:
            print("✓ Token强制刷新成功")
            new_token = token_manager.get_valid_token()
            print(f"  - 新token: {new_token[:20]}...")
        else:
            print("✗ Token强制刷新失败")
        
        # 停止token管理器
        token_manager.stop()
        print("\n✓ Token管理器已停止")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_message_processor():
    """测试简单消息处理器"""
    print("\n" + "=" * 50)
    print("简单消息处理器测试")
    print("=" * 50)
    
    try:
        from app.services.simple_message_processor import SimpleMessageProcessor
        
        # 创建消息处理器
        processor = SimpleMessageProcessor()
        print("✓ 消息处理器创建成功")
        
        # 测试处理消息
        test_message = "买书，25元"
        test_sender = "张杰"
        
        print(f"\n正在处理测试消息: {test_message}")
        success, result = processor.process_message(test_message, test_sender)
        
        print(f"处理结果: {'成功' if success else '失败'}")
        print(f"结果消息: {result}")
        
        return success
        
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始测试token管理系统...")
    
    # 测试token管理器
    token_test_success = test_token_manager()
    
    # 测试消息处理器
    processor_test_success = test_simple_message_processor()
    
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    print(f"Token管理器测试: {'✓ 通过' if token_test_success else '✗ 失败'}")
    print(f"消息处理器测试: {'✓ 通过' if processor_test_success else '✗ 失败'}")
    
    if token_test_success and processor_test_success:
        print("\n🎉 所有测试通过！Token管理系统工作正常。")
    else:
        print("\n❌ 部分测试失败，请检查配置和网络连接。")
    
    input("\n按回车键退出...")
