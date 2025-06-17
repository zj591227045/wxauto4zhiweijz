#!/usr/bin/env python3
"""
测试API修复 - 验证不再使用GetAllMessage方法
"""

import sys
import os
import re

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def search_get_all_message_usage():
    """搜索代码中GetAllMessage的使用情况"""
    print("搜索代码中GetAllMessage的使用情况...")
    
    # 需要检查的文件列表
    files_to_check = [
        'app/api/routes_minimal.py',
        'app/api/routes.py',
        'app/utils/message_processor.py',
        'app/services/clean_message_monitor.py',
        'app/services/message_monitor.py',
        'app/services/zero_history_monitor.py',
        'app/services/simple_message_processor.py'
    ]
    
    get_all_message_found = []
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 搜索GetAllMessage的使用
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'GetAllMessage' in line and not line.strip().startswith('#'):
                        # 排除注释行
                        if not line.strip().startswith('"""') and not line.strip().startswith("'''"):
                            get_all_message_found.append({
                                'file': file_path,
                                'line': i,
                                'content': line.strip()
                            })
                            
            except Exception as e:
                print(f"❌ 检查文件 {file_path} 时出错: {e}")
        else:
            print(f"⚠️  文件不存在: {file_path}")
    
    return get_all_message_found

def check_api_endpoints():
    """检查API端点是否正确使用GetListenMessage"""
    print("\n检查API端点...")
    
    routes_file = 'app/api/routes_minimal.py'
    if not os.path.exists(routes_file):
        print(f"❌ 文件不存在: {routes_file}")
        return False
    
    try:
        with open(routes_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否包含GetListenMessage
        if 'GetListenMessage' in content:
            print("✅ routes_minimal.py 已使用GetListenMessage")
            
            # 统计GetListenMessage的使用次数
            listen_count = content.count('GetListenMessage')
            print(f"   GetListenMessage使用次数: {listen_count}")
            
            return True
        else:
            print("❌ routes_minimal.py 未使用GetListenMessage")
            return False
            
    except Exception as e:
        print(f"❌ 检查routes_minimal.py时出错: {e}")
        return False

def check_message_processor():
    """检查消息处理器是否正确调用API"""
    print("\n检查消息处理器...")
    
    processor_file = 'app/utils/message_processor.py'
    if not os.path.exists(processor_file):
        print(f"❌ 文件不存在: {processor_file}")
        return False
    
    try:
        with open(processor_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查API端点调用
        if '/api/chat-window/get-all-messages' in content:
            print("✅ message_processor.py 调用正确的API端点")
            return True
        else:
            print("❌ message_processor.py 未调用正确的API端点")
            return False
            
    except Exception as e:
        print(f"❌ 检查message_processor.py时出错: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("测试API修复 - 验证不再使用GetAllMessage方法")
    print("=" * 60)
    
    # 搜索GetAllMessage的使用情况
    get_all_message_usage = search_get_all_message_usage()
    
    print(f"\n发现GetAllMessage使用情况: {len(get_all_message_usage)}处")
    
    if get_all_message_usage:
        print("\n⚠️  仍然存在GetAllMessage的使用:")
        for usage in get_all_message_usage:
            print(f"   📁 {usage['file']}:{usage['line']}")
            print(f"      {usage['content']}")
        
        # 检查是否是适配器中的合理使用
        adapter_usage = [u for u in get_all_message_usage if 'wechat_adapter.py' in u['file']]
        api_usage = [u for u in get_all_message_usage if 'wechat_adapter.py' not in u['file']]
        
        if api_usage:
            print(f"\n❌ 发现{len(api_usage)}处不合理的GetAllMessage使用（需要修复）")
            for usage in api_usage:
                print(f"   📁 {usage['file']}:{usage['line']}")
        else:
            print(f"\n✅ 所有GetAllMessage使用都在适配器中（合理）")
    else:
        print("\n✅ 未发现GetAllMessage的使用")
    
    # 检查API端点
    api_ok = check_api_endpoints()
    
    # 检查消息处理器
    processor_ok = check_message_processor()
    
    print("\n" + "=" * 60)
    print("测试结果总结:")
    print("=" * 60)
    
    if len([u for u in get_all_message_usage if 'wechat_adapter.py' not in u['file']]) == 0:
        print("✅ GetAllMessage使用检查: 通过")
    else:
        print("❌ GetAllMessage使用检查: 失败")
    
    if api_ok:
        print("✅ API端点检查: 通过")
    else:
        print("❌ API端点检查: 失败")
    
    if processor_ok:
        print("✅ 消息处理器检查: 通过")
    else:
        print("❌ 消息处理器检查: 失败")
    
    all_passed = (len([u for u in get_all_message_usage if 'wechat_adapter.py' not in u['file']]) == 0 
                  and api_ok and processor_ok)
    
    if all_passed:
        print("\n🎉 所有检查都通过！API修复成功！")
    else:
        print("\n⚠️  部分检查未通过，需要进一步修复")

if __name__ == "__main__":
    main()
