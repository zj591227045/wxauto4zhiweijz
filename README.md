# 只为记账-微信助手

一个基于wxauto的微信消息监控和自动记账工具，支持现代化的PyQt6图形界面。

## ✨ 特性

- 🎯 **智能消息监控** - 自动监控指定微信群/好友的消息
- 📊 **自动记账** - 解析消息中的记账信息并自动提交到只为记账服务
- 🖥️ **现代化界面** - 基于PyQt6的美观图形界面，支持简约模式和高级模式
- 🔧 **灵活配置** - 支持多种启动方式和配置选项
- 📝 **实时日志** - 彩色日志显示，便于调试和监控
- 🔐 **安全配置** - 密码加密存储，配置文件自动保存
- 🚀 **自动启动** - 支持启动时自动登录、启动API服务、初始化微信
- ⚡ **简约模式** - 极简科技感界面，一键启动，专注核心功能

## 🚀 快速开始

### 环境要求

- Python 3.8+
- PyQt6
- wxauto库
- 微信PC版

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动方式

#### 方法1: 简约模式界面（推荐）

```bash
# 默认启动简约模式
python main.py

# 或者明确指定简约模式
python main.py --service simple

# 或者使用专用启动脚本
python start_simple_ui.py

# Windows用户可以双击
start_simple_ui.bat
```

#### 方法2: 高级模式界面

```bash
# 启动高级模式
python main.py --service advanced

# 或者使用原有启动脚本
python start_qt_ui.py

# Windows用户可以双击
start_qt_ui.bat
```

#### 方法3: 其他启动方式

```bash
# Web界面
python main.py --service web

# 仅API服务
python main.py --service api

# 传统方式
python app_no_limiter.py
```

## 🎨 界面模式

### 简约模式 (推荐)
- **极简设计**: 现代化深色主题，科技感十足
- **圆形主控**: 120px圆形开始/停止按钮，支持渐变动画
- **智能指示**: 实时状态闪烁指示灯，支持多种状态显示
- **自动启动**: 程序启动时自动启动API服务、初始化微信、开始监控
- **完整配置**: 支持wxauto库选择、监控会话配置、自动化选项
- **快速配置**: 点击状态卡片即可打开详细配置对话框
- **实时统计**: 处理消息数、成功记账数、失败记账数
- **状态同步**: 与高级模式完全共享状态和配置
- **一键切换**: 可随时切换到高级模式

### 高级模式
- **完整功能**: 所有配置选项和高级功能
- **实时日志**: 详细的日志显示和管理
- **调试工具**: 适合开发和调试使用
- **返回简约**: 可随时返回简约模式

## 📁 项目结构

```
wxauto_for_zhiweijz/
├── main.py                # 主入口（支持多种模式）
├── start_simple_ui.py     # 简约模式启动器
├── start_simple_ui.bat    # Windows简约模式启动
├── start_qt_ui.py         # 高级模式启动器
├── start_qt_ui.bat        # Windows高级模式启动
├── test_simple_ui.py      # 简约模式测试
├── app_no_limiter.py      # 无限流器API服务
├── requirements.txt       # 项目依赖
├── README.md             # 项目说明
├── app/                  # 核心应用代码
│   ├── qt_ui/           # PyQt6界面
│   │   ├── simple_main_window.py    # 简约模式界面
│   │   ├── main_window_with_startup.py  # 高级模式界面
│   │   └── main_window_fixed.py    # 基础界面组件
│   ├── api/             # API服务
│   ├── services/        # 业务服务
│   ├── wxauto_wrapper/  # wxauto库包装器
│   └── utils/           # 工具模块
├── docs/                # 项目文档
│   ├── README_SIMPLE.md # 简约模式说明
│   └── README_QT.md     # 高级模式说明
├── tests/               # 测试文件
├── archive/             # 归档文件
├── data/                # 数据文件
├── logs/                # 日志文件
└── wxauto/             # wxauto库源码
```

## 🎯 使用说明

### 简约模式使用流程

1. **启动应用**
   ```bash
   python main.py  # 默认启动简约模式
   ```

2. **配置服务**
   - 点击"只为记账服务"状态卡片，配置服务器地址、用户名、密码
   - 点击"微信监控服务"状态卡片，设置监控间隔和会话

3. **开始监控**
   - 确保微信PC版已登录
   - 点击中央圆形"开始监听"按钮
   - 观察状态指示灯变为绿色并闪烁

4. **查看统计**
   - 底部实时显示处理消息数、成功记账数、失败记账数

5. **切换模式**
   - 点击右下角"高级模式"按钮可切换到完整界面

### 高级模式使用流程

1. **启动应用**
   ```bash
   python main.py --service advanced
   ```

2. **配置记账服务**
   - 服务器地址：`https://api.zhiweijz.com`
   - 输入用户名和密码
   - 选择要使用的账本

3. **配置微信监控**
   - 添加要监控的微信群名或好友名
   - 设置检查间隔（建议5秒）
   - 点击"开始监控"

4. **启动API服务**
   - 在界面中点击"启动API服务"

5. **初始化微信连接**
   - 点击"初始化微信"按钮，确保微信PC版已登录

6. **返回简约模式**
   - 点击状态栏右侧"返回简约模式"按钮

## 🔧 配置说明

### API端点

- `GET /health` - 健康检查
- `GET /api/info` - API信息
- `GET /api/wechat/status` - 微信状态
- `POST /api/wechat/initialize` - 微信初始化

### 环境变量

- `WECHAT_LIB` - 微信库选择（wxauto/wxautox）
- `PORT` - API服务端口（默认5000）
- `WXAUTO_NO_MUTEX_CHECK` - 禁用互斥锁检查

## 📚 文档

详细文档请查看 `docs/` 目录：

- [简约模式说明](docs/README_SIMPLE.md) - 简约模式详细使用指南
- [高级模式说明](docs/README_QT.md) - 高级模式详细使用指南
- [配置管理使用指南](docs/CONFIG_USAGE_GUIDE.md)
- [界面布局优化总结](docs/LAYOUT_OPTIMIZATION_SUMMARY.md)
- [最终使用指南](docs/FINAL_USAGE_GUIDE.md)
- [Flask-Limiter修复总结](docs/FLASK_LIMITER_FIX_SUMMARY.md)
- [API服务修复总结](docs/API_SERVICE_FIX_SUMMARY.md)
- [实现总结](docs/IMPLEMENTATION_SUMMARY.md)

## 🐛 故障排除

### 常见问题

1. **PyQt6导入失败**
   ```bash
   pip install PyQt6
   ```

2. **简约模式界面无法启动**
   - 运行测试脚本：`python test_simple_ui.py`
   - 检查PyQt6是否正确安装

3. **Flask-Limiter错误**
   - 使用 `app_no_limiter.py` 而不是旧的启动方式

4. **wxauto库导入失败**
   - 确保wxauto库已正确安装
   - 检查Python路径配置

5. **微信连接失败**
   - 确保微信PC版已登录
   - 尝试重新初始化微信连接

6. **端口占用**
   - 检查端口5000是否被占用
   - 使用不同端口或终止占用进程

### 日志查看

- 简约模式：`logs/simple_ui.log`
- 高级模式：界面内实时日志显示 + `logs/qt_ui.log`
- API服务：控制台输出

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目采用MIT许可证。

## 🙏 致谢

- [wxauto](https://github.com/cluic/wxauto) - 微信自动化库
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - 图形界面框架
- [Flask](https://flask.palletsprojects.com/) - Web框架
