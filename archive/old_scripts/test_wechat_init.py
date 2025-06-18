#!/usr/bin/env python3
"""
测试微信初始化功能
"""

import sys
import os
import time

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_enhanced_wechat_manager():
    """测试增强版微信管理器"""
    print("🔍 测试增强版微信管理器...")
    print("=" * 50)
    
    try:
        from app.utils.enhanced_async_wechat import async_wechat_manager
        
        # 检查管理器状态
        print(f"管理器状态: {'运行中' if async_wechat_manager.is_running() else '未运行'}")
        print(f"连接状态: {'已连接' if async_wechat_manager.is_connected() else '未连接'}")
        
        # 获取统计信息
        stats = async_wechat_manager.get_stats()
        print(f"统计信息: {stats}")
        
        # 测试微信初始化
        print("\n开始测试微信初始化...")
        
        def on_init_result(success, result, message):
            print(f"初始化结果: {'成功' if success else '失败'}")
            print(f"消息: {message}")
            if result:
                print(f"详细信息: {result}")
        
        # 异步初始化微信
        async_wechat_manager.initialize_wechat(callback=on_init_result)
        
        # 等待初始化完成
        print("等待初始化完成...")
        time.sleep(10)
        
        # 再次检查状态
        print(f"\n初始化后状态:")
        print(f"管理器状态: {'运行中' if async_wechat_manager.is_running() else '未运行'}")
        print(f"连接状态: {'已连接' if async_wechat_manager.is_connected() else '未连接'}")
        
        stats = async_wechat_manager.get_stats()
        print(f"统计信息: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试增强版微信管理器失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_wxauto_direct():
    """直接测试wxauto库"""
    print("\n🔍 直接测试wxauto库...")
    print("=" * 50)
    
    try:
        import wxauto
        print("✅ wxauto库导入成功")
        
        # 尝试创建微信实例
        print("正在创建微信实例...")
        wx = wxauto.WeChat()
        
        if wx:
            print("✅ 微信实例创建成功")
            
            # 尝试获取微信信息
            try:
                # 获取当前聊天
                current_chat = wx.CurrentChat()
                print(f"当前聊天: {current_chat}")
            except Exception as e:
                print(f"获取当前聊天失败: {e}")
            
            try:
                # 获取聊天列表
                chat_list = wx.GetSessionList()
                if chat_list:
                    print(f"聊天列表数量: {len(chat_list)}")
                    print(f"前3个聊天: {chat_list[:3] if len(chat_list) >= 3 else chat_list}")
                else:
                    print("聊天列表为空")
            except Exception as e:
                print(f"获取聊天列表失败: {e}")
            
            return True
        else:
            print("❌ 微信实例创建失败")
            return False
            
    except ImportError as e:
        print(f"❌ wxauto库导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 直接测试wxauto失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_wechat_adapter():
    """测试微信适配器"""
    print("\n🔍 测试微信适配器...")
    print("=" * 50)
    
    try:
        from app.wechat_adapter import WeChatAdapter
        
        # 创建适配器
        adapter = WeChatAdapter('wxauto')
        print("✅ 微信适配器创建成功")
        
        # 初始化适配器
        print("正在初始化适配器...")
        success = adapter.initialize()
        
        if success:
            print("✅ 微信适配器初始化成功")
            
            # 获取实例
            instance = adapter.get_instance()
            if instance:
                print("✅ 获取微信实例成功")
                
                # 测试基本功能
                try:
                    lib_name = adapter.get_lib_name()
                    print(f"使用的库: {lib_name}")
                except Exception as e:
                    print(f"获取库名失败: {e}")
                
                return True
            else:
                print("❌ 获取微信实例失败")
                return False
        else:
            print("❌ 微信适配器初始化失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试微信适配器失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_wechat_manager():
    """测试微信管理器"""
    print("\n🔍 测试微信管理器...")
    print("=" * 50)
    
    try:
        from app.wechat import WeChatManager
        
        # 创建管理器
        manager = WeChatManager()
        print("✅ 微信管理器创建成功")
        
        # 初始化管理器
        print("正在初始化管理器...")
        success = manager.initialize()
        
        if success:
            print("✅ 微信管理器初始化成功")
            
            # 获取实例
            instance = manager.get_instance()
            if instance:
                print("✅ 获取微信实例成功")
                return True
            else:
                print("❌ 获取微信实例失败")
                return False
        else:
            print("❌ 微信管理器初始化失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试微信管理器失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🧪 微信初始化功能测试")
    print("=" * 60)
    print("时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    results = []
    
    # 测试1: 直接测试wxauto库
    results.append(("直接测试wxauto库", test_wxauto_direct()))
    
    # 测试2: 测试微信适配器
    results.append(("测试微信适配器", test_wechat_adapter()))
    
    # 测试3: 测试微信管理器
    results.append(("测试微信管理器", test_wechat_manager()))
    
    # 测试4: 测试增强版微信管理器
    results.append(("测试增强版微信管理器", test_enhanced_wechat_manager()))
    
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
        print("🎉 所有测试通过！微信初始化功能正常")
    elif passed > 0:
        print("⚠️ 部分测试通过，可能存在兼容性问题")
    else:
        print("💥 所有测试失败，微信初始化功能异常")
    
    print("\n💡 建议:")
    if passed == 0:
        print("- 检查微信是否已启动并登录")
        print("- 检查wxauto库是否正确安装")
        print("- 检查Python环境和依赖")
    elif passed < total:
        print("- 部分组件工作正常，检查失败的组件")
        print("- 可能需要重启微信或Python程序")
    else:
        print("- 微信初始化功能正常，可以正常使用")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
