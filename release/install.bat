@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   只为记账-微信助手 安装程序
echo ========================================
echo.

:: 检查是否以管理员权限运行
net session >nul 2>&1
if %errorLevel% == 0 (
    echo ✓ 检测到管理员权限
) else (
    echo ⚠️ 建议以管理员权限运行此安装程序
    echo   右键点击此文件，选择"以管理员身份运行"
    echo.
)

:: 创建必要的目录
echo 📁 创建必要的目录...
if not exist "data" mkdir data
if not exist "data\Logs" mkdir data\Logs
if not exist "data\backup" mkdir data\backup
if not exist "data\temp" mkdir data\temp
echo ✓ 目录创建完成

:: 复制配置模板
echo 📄 设置配置文件...
if not exist "data\config.json" (
    if exist "config_template.json" (
        copy "config_template.json" "data\config.json" >nul
        echo ✓ 配置模板已复制到 data\config.json
    ) else (
        echo ⚠️ 未找到配置模板文件
    )
) else (
    echo ✓ 配置文件已存在，跳过复制
)

:: 创建桌面快捷方式（可选）
echo.
set /p create_shortcut="是否创建桌面快捷方式？(Y/N): "
if /i "%create_shortcut%"=="Y" (
    echo 🔗 创建桌面快捷方式...
    
    :: 使用PowerShell创建快捷方式
    powershell -Command "& {$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\只为记账微信助手.lnk'); $Shortcut.TargetPath = '%CD%\只为记账微信助手.exe'; $Shortcut.WorkingDirectory = '%CD%'; $Shortcut.Save()}"
    
    if exist "%USERPROFILE%\Desktop\只为记账微信助手.lnk" (
        echo ✓ 桌面快捷方式创建成功
    ) else (
        echo ❌ 桌面快捷方式创建失败
    )
)

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 📋 使用说明：
echo   1. 双击"只为记账微信助手.exe"启动程序
echo   2. 首次运行需要配置记账服务信息
echo   3. 配置微信监控参数
echo   4. 开始使用自动记账功能
echo.
echo 📁 重要文件位置：
echo   - 程序文件：只为记账微信助手.exe
echo   - 配置文件：data\config.json
echo   - 日志文件：data\Logs\
echo   - 备份文件：data\backup\
echo.
echo 🔒 安全提示：
echo   - 请妥善保管配置文件中的账号密码信息
echo   - 建议定期备份配置文件
echo   - 不要将包含敏感信息的配置文件分享给他人
echo.

pause
