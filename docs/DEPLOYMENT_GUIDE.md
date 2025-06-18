# 部署和使用指南

## 概述

本指南详细说明如何部署和使用模块化版本的只为记账-微信助手。

## 系统要求

### 硬件要求
- **内存**: 最少 4GB RAM，推荐 8GB 或更多
- **存储**: 最少 500MB 可用空间
- **处理器**: Intel i3 或同等性能的 AMD 处理器

### 软件要求
- **操作系统**: Windows 10/11 (64位)
- **Python**: 3.8 或更高版本
- **微信**: 已安装并登录的微信客户端
- **网络**: 稳定的互联网连接

### Python依赖包
```
PyQt6>=6.4.0
requests>=2.28.0
wxauto>=3.0.0
```

## 安装步骤

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/your-repo/wxauto_for_zhiweijz.git
cd wxauto_for_zhiweijz

# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

### 2. 目录结构检查

确保以下目录存在：
```
wxauto_for_zhiweijz/
├── app/
│   ├── modules/          # 核心模块
│   ├── qt_ui/           # 用户界面
│   ├── services/        # 服务层
│   └── utils/           # 工具类
├── data/                # 数据目录
│   ├── Logs/           # 日志文件
│   ├── backup/         # 配置备份
│   └── temp/           # 临时文件
├── config/             # 配置文件
├── docs/               # 文档
└── icons/              # 图标资源
```

### 3. 配置文件初始化

首次运行时，程序会自动创建默认配置文件 `data/config.json`：

```json
{
  "version": "1.0.0",
  "accounting": {
    "server_url": "",
    "username": "",
    "password": "",
    "account_book_id": "",
    "auto_login": true,
    "token_refresh_interval": 300,
    "request_timeout": 30,
    "max_retries": 3
  },
  "wechat_monitor": {
    "enabled": true,
    "monitored_chats": [],
    "auto_reply": true,
    "reply_template": "",
    "max_retry_count": 3,
    "connection_timeout": 30
  },
  "wxauto": {
    "library_type": "wxauto",
    "auto_init": true,
    "connection_timeout": 30,
    "max_retry_count": 3
  },
  "log": {
    "level": "INFO",
    "console_output": true,
    "file_output": true,
    "max_file_size": 10485760,
    "max_files": 10,
    "auto_rotate": true
  },
  "service_monitor": {
    "enabled": true,
    "global_check_interval": 30,
    "max_concurrent_recoveries": 2,
    "auto_recovery": true,
    "recovery_cooldown": 300
  },
  "ui": {
    "theme": "default",
    "window_width": 800,
    "window_height": 600,
    "auto_scroll_logs": true,
    "log_display_limit": 1000,
    "minimize_to_tray": true
  },
  "system": {
    "data_dir": "data",
    "temp_dir": "data/temp",
    "backup_dir": "data/backup",
    "auto_backup": true,
    "backup_interval": 3600,
    "max_backups": 10
  }
}
```

## 启动应用

### 方式一：直接启动（推荐）

```bash
python start_modular_ui.py
```

### 方式二：开发模式启动

```bash
# 设置环境变量启用调试模式
set MCP_DEBUG=true
python start_modular_ui.py
```

## 首次配置

### 1. 记账服务配置

1. 点击界面右侧的"记账服务"状态指示器
2. 在弹出的配置对话框中填写：
   - **服务器地址**: 只为记账API服务器地址
   - **用户名**: 您的只为记账账号
   - **密码**: 您的只为记账密码
3. 点击"测试连接"验证配置
4. 点击"保存"保存配置

### 2. 微信服务配置

1. 确保微信客户端已启动并登录
2. 点击界面右侧的"微信服务"状态指示器
3. 在配置对话框中设置：
   - **启用微信监控**: 勾选启用
   - **监控聊天列表**: 每行输入一个要监控的聊天名称
   - **启用自动回复**: 勾选启用自动回复功能
   - **回复模板**: 设置回复消息模板（可选）
4. 点击"保存"保存配置

### 3. 验证配置

配置完成后，检查状态指示器：
- **记账服务**: 应显示"已连接"
- **微信服务**: 应显示微信昵称或"已连接"
- **监控服务**: 应显示"已停止"

## 使用说明

### 开始监控

1. 确保记账服务和微信服务都已连接
2. 点击中央的"开始监听"按钮
3. 按钮变为"停止监听"，状态文本显示"监控运行中..."
4. 监控服务状态指示器显示"监控X个聊天"

### 查看统计信息

界面下方的统计卡片实时显示：
- **总处理**: 处理的消息总数
- **成功**: 成功记账的消息数
- **失败**: 记账失败的消息数
- **无关**: 无关消息数

### 查看日志

1. 点击"查看日志"按钮
2. 在日志窗口中可以：
   - 查看实时日志
   - 按级别过滤日志
   - 导出日志文件
   - 清空日志缓冲区

### 服务监控

1. 点击"服务监控"按钮（开发中）
2. 可以查看各个服务的健康状态
3. 手动触发服务恢复

## 高级配置

### 配置文件详细说明

#### 记账服务配置 (accounting)

```json
{
  "server_url": "https://api.zhiweijz.com",  // API服务器地址
  "username": "user@example.com",            // 登录用户名
  "password": "password123",                 // 登录密码
  "account_book_id": "book_id",             // 账本ID
  "auto_login": true,                       // 自动登录
  "token_refresh_interval": 300,            // Token刷新间隔（秒）
  "request_timeout": 30,                    // 请求超时时间（秒）
  "max_retries": 3                          // 最大重试次数
}
```

#### 微信监控配置 (wechat_monitor)

```json
{
  "enabled": true,                          // 启用监控
  "monitored_chats": ["张三", "李四"],       // 监控的聊天列表
  "auto_reply": true,                       // 自动回复
  "reply_template": "记账结果: {result}",    // 回复模板
  "max_retry_count": 3,                     // 最大重试次数
  "connection_timeout": 30,                 // 连接超时时间
  "message_filter_enabled": false,          // 消息过滤
  "message_filter_keywords": []             // 过滤关键词
}
```

#### wxauto库配置 (wxauto)

```json
{
  "library_type": "wxauto",                 // 库类型: wxauto 或 wxautox
  "auto_init": true,                        // 自动初始化
  "connection_timeout": 30,                 // 连接超时时间
  "max_retry_count": 3,                     // 最大重试次数
  "save_path": "",                          // 保存路径
  "enable_logging": true                    // 启用日志
}
```

#### 日志配置 (log)

```json
{
  "level": "INFO",                          // 日志级别
  "console_output": true,                   // 控制台输出
  "file_output": true,                      // 文件输出
  "max_file_size": 10485760,               // 最大文件大小（字节）
  "max_files": 10,                         // 最大文件数量
  "auto_rotate": true,                     // 自动轮转
  "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
}
```

#### 服务监控配置 (service_monitor)

```json
{
  "enabled": true,                          // 启用监控
  "global_check_interval": 30,              // 全局检查间隔（秒）
  "max_concurrent_recoveries": 2,           // 最大并发恢复数
  "auto_recovery": true,                    // 自动恢复
  "recovery_cooldown": 300,                 // 恢复冷却时间（秒）
  "alert_enabled": true,                    // 启用告警
  "alert_threshold": 3                      // 告警阈值
}
```

### 环境变量

可以通过环境变量覆盖部分配置：

```bash
# 启用调试模式
set MCP_DEBUG=true

# 设置配置文件路径
set CONFIG_FILE=custom_config.json

# 设置数据目录
set DATA_DIR=custom_data

# 设置日志级别
set LOG_LEVEL=DEBUG
```

## 故障排除

### 常见问题

#### 1. 微信连接失败

**症状**: 微信服务状态显示"未连接"或"初始化失败"

**解决方案**:
1. 确保微信客户端已启动并登录
2. 检查微信版本是否兼容
3. 重启微信客户端
4. 重启应用程序

#### 2. 记账服务连接失败

**症状**: 记账服务状态显示"未连接"或"登录失败"

**解决方案**:
1. 检查网络连接
2. 验证服务器地址是否正确
3. 确认用户名和密码正确
4. 检查只为记账服务是否正常

#### 3. 消息监听不工作

**症状**: 发送消息后没有自动记账

**解决方案**:
1. 确保监控聊天列表配置正确
2. 检查聊天名称是否与微信中的完全一致
3. 验证消息格式是否符合记账要求
4. 查看日志了解详细错误信息

#### 4. 自动回复不工作

**症状**: 记账成功但没有收到回复消息

**解决方案**:
1. 确认自动回复功能已启用
2. 检查回复模板配置
3. 验证微信发送权限
4. 查看消息投递服务状态

### 日志分析

#### 日志级别说明

- **DEBUG**: 详细的调试信息
- **INFO**: 一般信息
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

#### 关键日志模式

```
# 微信连接成功
INFO - wxauto_manager - 微信实例创建成功
INFO - wxauto_manager - wxauto初始化成功: 用户昵称

# 记账成功
INFO - accounting_manager - 智能记账成功
INFO - message_delivery - 记账完成: 成功

# 服务故障
ERROR - service_monitor - 服务故障: wxauto_manager - 连接断开
INFO - service_monitor - 开始尝试恢复服务: wxauto_manager

# 配置更新
INFO - config_manager - 配置保存成功: data/config.json
INFO - config_manager - 配置变更: accounting
```

### 性能优化

#### 内存使用优化

1. 定期清理日志缓冲区
2. 限制消息缓冲区大小
3. 启用自动垃圾回收

#### 网络优化

1. 调整请求超时时间
2. 配置合适的重试次数
3. 使用连接池

#### 存储优化

1. 启用日志自动轮转
2. 定期清理旧备份文件
3. 压缩历史日志文件

## 备份和恢复

### 自动备份

系统会自动备份配置文件：
- 备份间隔: 1小时（可配置）
- 备份位置: `data/backup/`
- 保留数量: 10个（可配置）

### 手动备份

```python
# 通过配置管理器创建备份
config_manager.create_backup("manual_backup_20250618")
```

### 恢复配置

```python
# 恢复指定备份
config_manager.restore_backup("data/backup/config_backup_20250618_143506.json")
```

## 更新和维护

### 版本更新

1. 备份当前配置
2. 下载新版本
3. 替换程序文件
4. 启动程序验证

### 定期维护

1. **每周**: 检查日志文件大小，清理过大的日志
2. **每月**: 备份重要配置，清理临时文件
3. **每季度**: 更新依赖包，检查安全更新

### 监控指标

关注以下关键指标：
- 消息处理成功率
- 服务可用性
- 响应时间
- 内存使用量
- 磁盘空间使用

## 技术支持

### 获取帮助

1. 查看日志文件了解详细错误信息
2. 检查配置文件是否正确
3. 参考本文档的故障排除部分
4. 联系技术支持

### 反馈问题

提交问题时请包含：
1. 问题描述和重现步骤
2. 错误日志
3. 配置文件（隐藏敏感信息）
4. 系统环境信息

---

通过遵循本指南，您应该能够成功部署和使用模块化版本的只为记账-微信助手。如有任何问题，请参考故障排除部分或联系技术支持。
