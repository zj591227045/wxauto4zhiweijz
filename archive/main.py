#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只为记账-微信助手 主入口
支持多种启动模式
"""

import sys
import os
import argparse

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="只为记账-微信助手")
    parser.add_argument(
        "--service", 
        choices=["simple", "qt", "advanced", "web", "api"], 
        default="simple",
        help="选择启动模式: simple(简约界面), qt/advanced(高级界面), web(Web界面), api(仅API服务)"
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("只为记账-微信助手")
    print("=" * 50)
    
    if args.service == "simple":
        print("启动模式: 简约界面")
        from start_simple_ui import main as start_simple
        return start_simple()
    
    elif args.service in ["qt", "advanced"]:
        print("启动模式: 高级界面")
        from start_qt_ui import main as start_qt
        return start_qt()
    
    elif args.service == "web":
        print("启动模式: Web界面")
        try:
            from app.run import main as start_web
            return start_web()
        except ImportError as e:
            print(f"Web模式启动失败: {e}")
            return 1
    
    elif args.service == "api":
        print("启动模式: 仅API服务")
        try:
            from app.api_service import start_api
            start_api()
            return 0
        except ImportError as e:
            print(f"API服务启动失败: {e}")
            return 1
    
    else:
        print(f"未知的服务类型: {args.service}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 