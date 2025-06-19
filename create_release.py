#!/usr/bin/env python3
"""
创建发布包脚本
将dist目录打包为可分发的压缩包
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

def create_release_package():
    """创建发布包"""
    print("只为记账-微信助手 发布包创建工具")
    print("=" * 50)
    
    # 检查dist目录
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("❌ dist目录不存在，请先运行构建脚本")
        return False
    
    exe_file = dist_dir / "只为记账微信助手.exe"
    if not exe_file.exists():
        print("❌ 可执行文件不存在，请先运行构建脚本")
        return False
    
    print(f"✓ 找到可执行文件: {exe_file}")
    print(f"✓ 文件大小: {exe_file.stat().st_size / 1024 / 1024:.1f} MB")
    
    # 创建发布目录
    release_dir = Path("release")
    if release_dir.exists():
        print("🗑️ 清理旧的发布目录...")
        shutil.rmtree(release_dir)
    
    release_dir.mkdir()
    print(f"✓ 创建发布目录: {release_dir}")
    
    # 复制文件到发布目录
    print("📁 复制文件到发布目录...")
    
    # 复制主要文件
    files_to_copy = [
        "只为记账微信助手.exe",
        "README.md", 
        "config_template.json",
        "install.bat"
    ]
    
    for file_name in files_to_copy:
        src_file = dist_dir / file_name
        if src_file.exists():
            shutil.copy2(src_file, release_dir)
            print(f"  ✓ {file_name}")
        else:
            print(f"  ⚠️ 未找到文件: {file_name}")
    
    # 创建空的data目录结构（不包含敏感配置）
    data_dir = release_dir / "data"
    data_dir.mkdir()
    (data_dir / "Logs").mkdir()
    (data_dir / "backup").mkdir() 
    (data_dir / "temp").mkdir()
    print("  ✓ data目录结构")
    
    # 创建版本信息文件
    version_info = {
        "version": "1.0.0",
        "build_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": "Windows",
        "description": "只为记账-微信助手"
    }
    
    version_file = release_dir / "version.txt"
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write("只为记账-微信助手 版本信息\n")
        f.write("=" * 30 + "\n")
        for key, value in version_info.items():
            f.write(f"{key}: {value}\n")
    print("  ✓ version.txt")
    
    # 创建压缩包
    print("📦 创建压缩包...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"只为记账微信助手_v1.0.0_{timestamp}.zip"
    zip_path = Path(zip_name)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(release_dir):
            for file in files:
                file_path = Path(root) / file
                arc_name = file_path.relative_to(release_dir)
                zipf.write(file_path, arc_name)
                print(f"  ✓ 添加: {arc_name}")
    
    print(f"✓ 压缩包创建完成: {zip_path}")
    print(f"✓ 压缩包大小: {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
    
    # 显示发布信息
    print("\n" + "=" * 50)
    print("🎉 发布包创建完成！")
    print("=" * 50)
    print(f"📦 压缩包文件: {zip_path}")
    print(f"📁 发布目录: {release_dir}")
    print(f"📊 包含文件数量: {len(list(release_dir.rglob('*')))}")
    
    print("\n📋 分发说明：")
    print("1. 将压缩包发送给用户")
    print("2. 用户解压到任意目录")
    print("3. 运行install.bat进行安装")
    print("4. 双击exe文件启动程序")
    
    print("\n🔒 安全提示：")
    print("- 压缩包不包含敏感配置信息")
    print("- 用户需要自行配置记账服务信息")
    print("- 建议用户定期备份配置文件")
    
    return True

def main():
    """主函数"""
    try:
        if create_release_package():
            print("\n✅ 发布包创建成功！")
            return 0
        else:
            print("\n❌ 发布包创建失败！")
            return 1
    except Exception as e:
        print(f"\n❌ 创建发布包时出错: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
