#!/usr/bin/env python3
"""
只为记账-微信助手 打包脚本
使用PyInstaller将应用打包为Windows可执行文件
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def check_dependencies():
    """检查打包依赖"""
    try:
        import PyInstaller
        print(f"✓ PyInstaller 已安装: {PyInstaller.__version__}")
    except ImportError:
        print("❌ PyInstaller 未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✓ PyInstaller 安装完成")

def clean_build():
    """清理构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✓ 清理目录: {dir_name}")

def create_spec_file():
    """创建PyInstaller spec文件"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['start_ui.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 注意：排除data目录以防止敏感配置信息被打包
        # data目录包含用户名、密码、token等敏感信息，不应包含在分发包中
        # 用户需要在首次运行时自行配置这些信息
        ('app', 'app'),
        ('icons', 'icons'),
        ('README.md', '.'),
        ('requirements.txt', '.'),
        ('config_template.json', '.'),
    ],
    hiddenimports=[
        # PyQt6 核心模块
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        # 第三方库
        'requests',
        'flask',
        'cryptography',
        'psutil',
        'pyperclip',
        'tenacity',
        'comtypes',
        'win32gui',
        'win32con',
        'win32api',
        'win32process',
        'wxauto',
        'wxautox',
        # 新模块化架构 - 核心模块
        'app.modules.config_manager',
        'app.modules.accounting_manager',
        'app.modules.wechat_service_manager',
        'app.modules.wxauto_manager',
        'app.modules.message_listener',
        'app.modules.message_delivery',
        'app.modules.log_manager',
        'app.modules.service_monitor',
        # UI模块
        'app.qt_ui.legacy_ui_with_modules',
        'app.qt_ui.enhanced_log_window',
        'app.qt_ui.enhanced_ui_components',
        'app.qt_ui.log_window',
        'app.qt_ui.ui_components',
        'app.qt_ui.simple_main_window',
        'app.qt_ui.modular_main_window',
        # 服务模块（仅包含存在的模块）
        'app.services.accounting_service',
        # 工具模块（仅包含存在的模块）
        'app.utils.state_manager',
        # 标准库模块
        'threading',
        'queue',
        'json',
        'datetime',
        'time',
        'os',
        'sys',
        'logging',
        'traceback',
        'enum',
        'abc',
        'typing',
        'pathlib',
        'urllib.parse',
        'urllib.request',
        'http.client',
        'socket',
        'ssl',
        'subprocess',
        'dataclasses',
        # 第三方库
        'typing_extensions',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='只为记账微信助手',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/app_icon.ico' if os.path.exists('icons/app_icon.ico') else None,
)
'''
    
    with open('app.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print("✓ 创建 app.spec 文件")

def build_executable():
    """构建可执行文件"""
    print("开始构建可执行文件...")
    
    # 使用spec文件构建
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        'app.spec'
    ]
    
    try:
        subprocess.check_call(cmd)
        print("✓ 构建完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        return False

def copy_additional_files():
    """复制额外的文件到dist目录"""
    dist_dir = Path('dist')
    if not dist_dir.exists():
        print("❌ dist目录不存在")
        return

    print(f"✓ 找到dist目录: {dist_dir}")

    # 复制配置文件到dist目录
    files_to_copy = [
        'README.md',
        'requirements.txt',
    ]

    for file_name in files_to_copy:
        if os.path.exists(file_name):
            shutil.copy2(file_name, dist_dir)
            print(f"✓ 复制文件: {file_name}")

def create_installer_script():
    """创建安装脚本"""
    installer_content = '''@echo off
echo 只为记账-微信助手 安装程序
echo ================================

echo 正在检查系统环境...

REM 检查是否为Windows系统
if not "%OS%"=="Windows_NT" (
    echo 错误：此程序仅支持Windows系统
    pause
    exit /b 1
)

echo [OK] Windows系统检查通过

echo.
echo 安装完成！
echo.
echo 使用说明：
echo 1. 双击"只为记账微信助手.exe"启动程序
echo 2. 首次使用需要配置记账服务信息
echo    - 参考config_template.json文件进行配置
echo    - 程序会自动创建data目录和配置文件
echo 3. 添加要监控的微信聊天对象
echo 4. 点击"开始监听"即可自动记账
echo.
echo 注意事项：
echo - 请确保微信已登录并保持运行状态
echo - 程序需要管理员权限才能正常工作
echo - 建议将程序添加到防火墙白名单
echo.
pause
'''

    try:
        with open('dist/install.bat', 'w', encoding='utf-8') as f:
            f.write(installer_content)
        print("✓ 创建安装脚本")
    except Exception as e:
        print(f"⚠️ 创建安装脚本失败: {e}")

def main():
    """主函数"""
    print("只为记账-微信助手 打包程序")
    print("=" * 50)
    
    # 检查依赖
    check_dependencies()
    
    # 清理构建目录
    clean_build()
    
    # 创建spec文件
    create_spec_file()
    
    # 构建可执行文件
    if build_executable():
        # 复制额外文件
        copy_additional_files()
        
        # 创建安装脚本
        create_installer_script()
        
        print("\n" + "=" * 50)
        print("✓ 打包完成！")
        print(f"✓ 可执行文件位置: {os.path.abspath('dist')}")
        print("✓ 可以将dist目录下的所有文件分发给用户")
        print("\n🔒 安全提示：")
        print("- data目录已被排除在打包文件之外，防止敏感配置信息泄露")
        print("- 用户需要在首次运行时自行配置记账服务信息")
        print("- 请确保不要将包含敏感信息的配置文件分发给其他用户")
        print("\n使用方法：")
        print("1. 将dist目录复制到目标计算机")
        print("2. 运行install.bat进行安装")
        print("3. 双击'只为记账微信助手.exe'启动程序")
    else:
        print("\n❌ 打包失败，请检查错误信息")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
