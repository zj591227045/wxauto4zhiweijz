#!/usr/bin/env python3
"""
测试打包后的exe文件
"""

import subprocess
import sys
import time
import os
from pathlib import Path

def test_exe():
    """测试exe文件启动"""
    exe_path = Path("dist") / "只为记账微信助手.exe"
    
    if not exe_path.exists():
        print(f"❌ exe文件不存在: {exe_path}")
        return False
    
    print(f"✓ 找到exe文件: {exe_path}")
    print(f"✓ 文件大小: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
    
    # 启动exe文件（非阻塞）
    print("🚀 启动exe文件...")
    try:
        # 使用subprocess.Popen启动，不等待完成
        process = subprocess.Popen(
            [str(exe_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=exe_path.parent
        )
        
        print(f"✓ 进程已启动，PID: {process.pid}")
        
        # 等待几秒钟检查进程状态
        time.sleep(3)
        
        # 检查进程是否还在运行
        poll_result = process.poll()
        if poll_result is None:
            print("✓ 进程正在运行中")
            
            # 尝试终止进程
            print("🛑 终止测试进程...")
            process.terminate()
            
            # 等待进程结束
            try:
                process.wait(timeout=5)
                print("✓ 进程已正常终止")
            except subprocess.TimeoutExpired:
                print("⚠️ 进程未能在5秒内终止，强制结束")
                process.kill()
                process.wait()
            
            return True
        else:
            print(f"❌ 进程已退出，返回码: {poll_result}")
            
            # 获取错误输出
            stdout, stderr = process.communicate()
            if stdout:
                print(f"标准输出:\n{stdout}")
            if stderr:
                print(f"错误输出:\n{stderr}")
            
            return False
            
    except Exception as e:
        print(f"❌ 启动exe文件失败: {e}")
        return False

def main():
    """主函数"""
    print("只为记账-微信助手 exe文件测试")
    print("=" * 50)
    
    if test_exe():
        print("\n✅ exe文件测试通过！")
        print("🎉 打包成功，exe文件可以正常启动")
    else:
        print("\n❌ exe文件测试失败！")
        print("💡 请检查错误信息并修复问题")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
