# 模块接口定义文档

## 概述

本文档详细描述了8个核心模块的接口定义、方法签名和调用方式。

## 1. 配置管理模块接口

### ConfigManager

```python
class ConfigManager(ConfigurableService):
    """统一配置管理器"""
    
    # 信号定义
    config_loaded = pyqtSignal(dict)                    # 配置加载完成
    config_saved = pyqtSignal(str)                      # 配置保存完成
    config_changed = pyqtSignal(str, dict)              # 配置变更
    config_reset = pyqtSignal(str)                      # 配置重置
    backup_created = pyqtSignal(str)                    # 备份创建
    config_error = pyqtSignal(str, str)                 # 配置错误
    
    # 核心方法
    def __init__(self, config_file: str = None, parent=None)
    def start(self) -> bool
    def stop(self) -> bool
    def restart(self) -> bool
    def get_info(self) -> ServiceInfo
    def check_health(self) -> HealthCheckResult
    
    # 配置操作
    def load_config(self) -> bool
    def save_config(self) -> bool
    def reload_config(self) -> bool
    def reset_config(self, section: str = None) -> bool
    
    # 配置获取
    def get_config(self) -> AppConfig
    def get_accounting_config(self) -> AccountingConfig
    def get_wechat_monitor_config(self) -> WechatMonitorConfig
    def get_wxauto_config(self) -> WxautoConfig
    def get_log_config(self) -> LogConfig
    def get_service_monitor_config(self) -> ServiceMonitorConfig
    def get_ui_config(self) -> UIConfig
    def get_system_config(self) -> SystemConfig
    
    # 配置更新
    def update_accounting_config(self, **kwargs) -> bool
    def update_wechat_monitor_config(self, **kwargs) -> bool
    def update_wxauto_config(self, **kwargs) -> bool
    def update_log_config(self, **kwargs) -> bool
    def update_service_monitor_config(self, **kwargs) -> bool
    def update_ui_config(self, **kwargs) -> bool
    def update_system_config(self, **kwargs) -> bool
    
    # 监听器管理
    def add_config_listener(self, section: str, callback: callable)
    def remove_config_listener(self, section: str, callback: callable)
    
    # 备份和恢复
    def create_backup(self, backup_name: str = None) -> Optional[str]
    def restore_backup(self, backup_file: str) -> bool
    def list_backups(self) -> List[Dict[str, Any]]
    def cleanup_old_backups(self) -> int
```

### 调用示例

```python
# 初始化配置管理器
config_manager = ConfigManager()
config_manager.start()

# 更新记账配置
config_manager.update_accounting_config(
    server_url="https://api.example.com",
    username="user@example.com",
    password="password123"
)

# 监听配置变更
def on_accounting_config_changed(config_data):
    print(f"记账配置已更新: {config_data}")

config_manager.add_config_listener("accounting", on_accounting_config_changed)

# 创建备份
backup_file = config_manager.create_backup()
print(f"备份已创建: {backup_file}")
```

## 2. wxauto库管理模块接口

### WxautoManager

```python
class WxautoManager(BaseService, IWxautoManager):
    """wxauto库统一管理器"""
    
    # 信号定义
    instance_initialized = pyqtSignal(bool, str, dict)  # 实例初始化结果
    connection_status_changed = pyqtSignal(bool, str)   # 连接状态变化
    message_sent = pyqtSignal(str, bool, str)           # 消息发送结果
    messages_received = pyqtSignal(str, list)           # 收到消息
    
    # 核心方法
    def __init__(self, parent=None)
    def start(self) -> bool
    def stop(self) -> bool
    def restart(self) -> bool
    def get_info(self) -> ServiceInfo
    def check_health(self) -> HealthCheckResult
    
    # 微信实例管理
    def get_instance(self)
    def is_connected(self) -> bool
    
    # 消息操作
    def send_message(self, chat_name: str, message: str) -> bool
    def get_messages(self, chat_name: str) -> List[Dict[str, Any]]
    
    # 监听管理
    def add_listen_chat(self, chat_name: str) -> bool
    def remove_listen_chat(self, chat_name: str) -> bool
```

### 调用示例

```python
# 初始化wxauto管理器
wxauto_manager = WxautoManager()
wxauto_manager.start()

# 检查连接状态
if wxauto_manager.is_connected():
    print("微信已连接")
    
    # 发送消息
    success = wxauto_manager.send_message("张三", "你好！")
    if success:
        print("消息发送成功")
    
    # 添加监听聊天
    wxauto_manager.add_listen_chat("张三")
    
    # 获取消息
    messages = wxauto_manager.get_messages("张三")
    for msg in messages:
        print(f"收到消息: {msg['content']}")
```

## 3. 记账服务管理模块接口

### AccountingManager

```python
class AccountingManager(ConfigurableService, IAccountingManager):
    """只为记账服务管理器"""
    
    # 信号定义
    login_completed = pyqtSignal(bool, str, dict)      # 登录完成
    token_refreshed = pyqtSignal(bool, str)            # Token刷新
    accounting_completed = pyqtSignal(bool, str, dict) # 记账完成
    config_updated = pyqtSignal(dict)                  # 配置更新
    
    # 核心方法
    def __init__(self, state_manager=None, parent=None)
    def start(self) -> bool
    def stop(self) -> bool
    def restart(self) -> bool
    def get_info(self) -> ServiceInfo
    def check_health(self) -> HealthCheckResult
    
    # 认证管理
    def login(self, server_url: str, username: str, password: str) -> Tuple[bool, str]
    def get_token(self) -> Optional[str]
    
    # 记账操作
    def smart_accounting(self, description: str, sender_name: str = None) -> Tuple[bool, str]
    
    # 配置管理
    def update_config(self, config: Dict[str, Any]) -> bool
    def get_config(self) -> Dict[str, Any]
```

### 调用示例

```python
# 初始化记账管理器
accounting_manager = AccountingManager()
accounting_manager.start()

# 登录
success, message = accounting_manager.login(
    "https://api.zhiweijz.com",
    "user@example.com", 
    "password123"
)

if success:
    print("登录成功")
    
    # 智能记账
    success, result = accounting_manager.smart_accounting(
        "午餐 麦当劳 35元",
        "张三"
    )
    
    if success:
        print(f"记账成功: {result}")
```

## 4. 微信监控服务管理模块接口

### WechatServiceManager

```python
class WechatServiceManager(ConfigurableService):
    """微信监控服务管理器"""
    
    # 信号定义
    chat_added = pyqtSignal(str)                    # 聊天添加
    chat_removed = pyqtSignal(str)                  # 聊天移除
    stats_updated = pyqtSignal(str, dict)           # 统计更新
    monitoring_started = pyqtSignal(list)           # 监控开始
    monitoring_stopped = pyqtSignal()               # 监控停止
    config_changed = pyqtSignal(dict)               # 配置变更
    
    # 核心方法
    def __init__(self, state_manager=None, wxauto_manager=None, parent=None)
    def start(self) -> bool
    def stop(self) -> bool
    def restart(self) -> bool
    def get_info(self) -> ServiceInfo
    def check_health(self) -> HealthCheckResult
    
    # 聊天管理
    def add_chat(self, chat_name: str) -> bool
    def remove_chat(self, chat_name: str) -> bool
    def get_monitored_chats(self) -> List[str]
    
    # 监控控制
    def start_monitoring(self) -> bool
    def stop_monitoring(self) -> bool
    def is_monitoring(self) -> bool
    def is_chat_monitored(self, chat_name: str) -> bool
    
    # 统计管理
    def update_chat_stats(self, chat_name: str, processed: bool = False, 
                         accounting_success: bool = False, irrelevant: bool = False) -> bool
    def get_chat_stats(self, chat_name: str) -> Optional[Dict[str, Any]]
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]
    def reset_chat_stats(self, chat_name: str) -> bool
    
    # 配置管理
    def update_config(self, config: Dict[str, Any]) -> bool
    def get_config(self) -> Dict[str, Any]
```

### 调用示例

```python
# 初始化微信服务管理器
wechat_manager = WechatServiceManager(wxauto_manager=wxauto_manager)
wechat_manager.start()

# 添加监控聊天
wechat_manager.add_chat("张三")
wechat_manager.add_chat("李四")

# 开始监控
if wechat_manager.start_monitoring():
    print("监控已开始")

# 更新统计
wechat_manager.update_chat_stats("张三", processed=True, accounting_success=True)

# 获取统计信息
stats = wechat_manager.get_chat_stats("张三")
print(f"张三的统计: {stats}")
```

## 5. 消息监听服务模块接口

### MessageListener

```python
class MessageListener(BaseService, IMessageListener):
    """消息监听服务"""
    
    # 信号定义
    new_message_received = pyqtSignal(str, dict)    # 收到新消息
    listening_started = pyqtSignal(list)            # 监听开始
    listening_stopped = pyqtSignal()                # 监听停止
    chat_added = pyqtSignal(str)                    # 聊天添加
    chat_removed = pyqtSignal(str)                  # 聊天移除
    error_occurred = pyqtSignal(str)                # 错误发生
    
    # 核心方法
    def __init__(self, wxauto_manager=None, parent=None)
    def start(self) -> bool
    def stop(self) -> bool
    def restart(self) -> bool
    def get_info(self) -> ServiceInfo
    def check_health(self) -> HealthCheckResult
    
    # 监听控制
    def start_listening(self, chat_names: List[str]) -> bool
    def stop_listening(self) -> bool
    def is_listening(self) -> bool
    
    # 聊天管理
    def add_chat(self, chat_name: str) -> bool
    def remove_chat(self, chat_name: str) -> bool
    def get_monitored_chats(self) -> List[str]
    
    # 消息管理
    def get_recent_messages(self, chat_name: str = None, limit: int = 50) -> List[Dict[str, Any]]
    def clear_message_buffer(self) -> bool
    def get_stats(self) -> Dict[str, Any]
```

### 调用示例

```python
# 初始化消息监听器
message_listener = MessageListener(wxauto_manager=wxauto_manager)
message_listener.start()

# 连接新消息信号
def on_new_message(chat_name, message_data):
    print(f"收到来自 {chat_name} 的消息: {message_data['content']}")

message_listener.new_message_received.connect(on_new_message)

# 开始监听
chat_names = ["张三", "李四"]
if message_listener.start_listening(chat_names):
    print(f"开始监听 {len(chat_names)} 个聊天")

# 获取最近消息
recent_messages = message_listener.get_recent_messages("张三", limit=10)
for msg in recent_messages:
    print(f"历史消息: {msg['content']}")
```

## 6. 消息投递服务模块接口

### MessageDelivery

```python
class MessageDelivery(BaseService, IMessageDelivery):
    """消息投递服务"""
    
    # 信号定义
    accounting_completed = pyqtSignal(str, bool, str, dict)  # 记账完成
    wechat_reply_sent = pyqtSignal(str, bool, str)           # 微信回复发送
    task_completed = pyqtSignal(str, bool, str, dict)        # 任务完成
    queue_status_changed = pyqtSignal(int, int)              # 队列状态变化
    
    # 核心方法
    def __init__(self, accounting_manager=None, wxauto_manager=None, parent=None)
    def start(self) -> bool
    def stop(self) -> bool
    def restart(self) -> bool
    def get_info(self) -> ServiceInfo
    def check_health(self) -> HealthCheckResult
    
    # 消息处理
    def process_message(self, chat_name: str, message_content: str, sender_name: str) -> Tuple[bool, str]
    def send_reply(self, chat_name: str, reply_message: str) -> bool
    
    # 配置管理
    def set_auto_reply(self, enabled: bool)
    def set_reply_template(self, template: str)
    
    # 状态查询
    def get_queue_status(self) -> Dict[str, int]
    def get_stats(self) -> Dict[str, Any]
```

### 调用示例

```python
# 初始化消息投递服务
message_delivery = MessageDelivery(
    accounting_manager=accounting_manager,
    wxauto_manager=wxauto_manager
)
message_delivery.start()

# 设置自动回复
message_delivery.set_auto_reply(True)
message_delivery.set_reply_template("记账结果: {result}")

# 处理消息
success, task_id = message_delivery.process_message(
    "张三",
    "午餐 麦当劳 35元",
    "张三"
)

if success:
    print(f"消息已加入处理队列: {task_id}")

# 获取队列状态
status = message_delivery.get_queue_status()
print(f"队列状态: 待处理 {status['pending']}, 处理中 {status['processing']}")
```

## 7. 日志管理模块接口

### LogManager

```python
class LogManager(BaseService, ILogManager):
    """日志管理器"""

    # 信号定义
    new_log = pyqtSignal(str, str)              # 新日志
    log_cleared = pyqtSignal()                  # 日志清空
    log_file_rotated = pyqtSignal(str)          # 日志文件轮转
    stats_updated = pyqtSignal(dict)            # 统计更新

    # 核心方法
    def __init__(self, log_dir: str = None, parent=None)
    def start(self) -> bool
    def stop(self) -> bool
    def restart(self) -> bool
    def get_info(self) -> ServiceInfo
    def check_health(self) -> HealthCheckResult

    # 日志查询
    def get_logs(self, level_filter: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]
    def get_error_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]
    def clear_logs(self) -> bool

    # 文件管理
    def create_file_handler(self, name: str, filename: str = None) -> bool
    def remove_file_handler(self, name: str) -> bool
    def rotate_log_file(self, name: str) -> bool

    # 配置管理
    def set_level_filter(self, levels: Optional[List[str]])
    def set_module_filter(self, modules: Optional[List[str]])

    # 导出功能
    def export_logs(self, file_path: str, level_filter: Optional[str] = None,
                   start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> bool

    # 统计信息
    def get_stats(self) -> Dict[str, Any]
```

### 调用示例

```python
# 初始化日志管理器
log_manager = LogManager()
log_manager.start()

# 连接新日志信号
def on_new_log(message, level):
    print(f"[{level}] {message}")

log_manager.new_log.connect(on_new_log)

# 获取最近的错误日志
error_logs = log_manager.get_error_logs(limit=10)
for log in error_logs:
    print(f"错误日志: {log['message']}")

# 设置日志级别过滤
log_manager.set_level_filter(["ERROR", "WARNING"])

# 导出日志
from datetime import datetime, timedelta
start_time = datetime.now() - timedelta(hours=1)
log_manager.export_logs(
    "logs/export.log",
    level_filter="ERROR",
    start_time=start_time
)

# 获取统计信息
stats = log_manager.get_stats()
print(f"日志统计: {stats}")
```

## 8. 服务监控及自动修复模块接口

### ServiceMonitor

```python
class ServiceMonitor(BaseService, IServiceMonitor):
    """服务监控器"""

    # 信号定义
    service_registered = pyqtSignal(str)                    # 服务注册
    service_unregistered = pyqtSignal(str)                  # 服务注销
    service_status_changed = pyqtSignal(str, str, str)      # 服务状态变化
    service_failed = pyqtSignal(str, str)                   # 服务失败
    service_recovered = pyqtSignal(str)                     # 服务恢复
    recovery_attempted = pyqtSignal(str, bool)              # 恢复尝试
    monitoring_started = pyqtSignal(list)                   # 监控开始
    monitoring_stopped = pyqtSignal()                       # 监控停止

    # 核心方法
    def __init__(self, parent=None)
    def start(self) -> bool
    def stop(self) -> bool
    def restart(self) -> bool
    def get_info(self) -> ServiceInfo
    def check_health(self) -> HealthCheckResult

    # 服务注册
    def register_service(self, service_name: str, health_checker: Callable, recovery_handler: Callable = None) -> bool
    def unregister_service(self, service_name: str) -> bool

    # 监控控制
    def start_monitoring(self) -> bool
    def stop_monitoring(self) -> bool

    # 状态查询
    def get_service_status(self, service_name: str) -> Optional[HealthStatus]
    def get_service_record(self, service_name: str) -> Optional[Dict[str, Any]]
    def get_all_service_records(self) -> Dict[str, Dict[str, Any]]

    # 手动操作
    def force_check_service(self, service_name: str) -> Optional[HealthCheckResult]
    def force_recover_service(self, service_name: str) -> bool
    def reset_service_stats(self, service_name: str) -> bool

    # 统计信息
    def get_stats(self) -> Dict[str, Any]
```

### 调用示例

```python
# 初始化服务监控器
service_monitor = ServiceMonitor()
service_monitor.start()

# 连接服务状态变化信号
def on_service_status_changed(service_name, old_status, new_status):
    print(f"服务 {service_name} 状态变化: {old_status} -> {new_status}")

service_monitor.service_status_changed.connect(on_service_status_changed)

# 注册服务
def check_accounting_health():
    return accounting_manager.check_health()

def recover_accounting():
    return accounting_manager.restart()

service_monitor.register_service(
    "accounting_manager",
    check_accounting_health,
    recover_accounting
)

# 开始监控
service_names = ["accounting_manager", "wxauto_manager", "message_listener"]
if service_monitor.start_monitoring():
    print(f"开始监控 {len(service_names)} 个服务")

# 手动检查服务
result = service_monitor.force_check_service("accounting_manager")
if result:
    print(f"健康检查结果: {result.status.value} - {result.message}")

# 获取所有服务记录
records = service_monitor.get_all_service_records()
for service_name, record in records.items():
    print(f"服务 {service_name}: 成功率 {record['success_rate']:.1f}%")
```

## 模块间集成示例

### 完整的消息处理流程

```python
# 1. 初始化所有模块
config_manager = ConfigManager()
log_manager = LogManager()
wxauto_manager = WxautoManager()
accounting_manager = AccountingManager()
wechat_service_manager = WechatServiceManager(wxauto_manager=wxauto_manager)
message_listener = MessageListener(wxauto_manager=wxauto_manager)
message_delivery = MessageDelivery(
    accounting_manager=accounting_manager,
    wxauto_manager=wxauto_manager
)
service_monitor = ServiceMonitor()

# 2. 启动所有模块
modules = [
    config_manager, log_manager, wxauto_manager, accounting_manager,
    wechat_service_manager, message_listener, message_delivery, service_monitor
]

for module in modules:
    module.start()

# 3. 注册服务到监控器
services = [
    ("config_manager", config_manager),
    ("wxauto_manager", wxauto_manager),
    ("accounting_manager", accounting_manager),
    ("message_listener", message_listener),
    ("message_delivery", message_delivery)
]

for service_name, service in services:
    service_monitor.register_service(
        service_name,
        service.check_health,
        service.restart
    )

# 4. 设置信号连接
def on_new_message(chat_name, message_data):
    """处理新消息"""
    message_delivery.process_message(
        chat_name,
        message_data['content'],
        message_data.get('sender_remark', message_data.get('sender', ''))
    )

message_listener.new_message_received.connect(on_new_message)

def on_accounting_completed(chat_name, success, message, data):
    """记账完成后更新统计"""
    wechat_service_manager.update_chat_stats(
        chat_name,
        processed=True,
        accounting_success=success
    )

message_delivery.accounting_completed.connect(on_accounting_completed)

# 5. 配置监控聊天
monitored_chats = ["张三", "李四", "王五"]
for chat in monitored_chats:
    wechat_service_manager.add_chat(chat)

# 6. 开始监控
wechat_service_manager.start_monitoring()
message_listener.start_listening(monitored_chats)
service_monitor.start_monitoring()

print("所有模块已启动，开始监控...")
```

### 配置管理集成示例

```python
# 1. 配置变更监听
def on_accounting_config_changed(config_data):
    """记账配置变更时更新记账管理器"""
    accounting_manager.update_config(config_data)

def on_wechat_config_changed(config_data):
    """微信配置变更时更新相关模块"""
    wechat_service_manager.update_config(config_data)

    # 更新监控聊天列表
    new_chats = config_data.get('monitored_chats', [])
    current_chats = wechat_service_manager.get_monitored_chats()

    # 移除不再监控的聊天
    for chat in current_chats:
        if chat not in new_chats:
            wechat_service_manager.remove_chat(chat)
            message_listener.remove_chat(chat)

    # 添加新的监控聊天
    for chat in new_chats:
        if chat not in current_chats:
            wechat_service_manager.add_chat(chat)
            message_listener.add_chat(chat)

# 2. 注册配置监听器
config_manager.add_config_listener("accounting", on_accounting_config_changed)
config_manager.add_config_listener("wechat_monitor", on_wechat_config_changed)

# 3. 初始化配置
config_manager.load_config()
```

### 错误处理和恢复示例

```python
# 1. 服务故障处理
def on_service_failed(service_name, error_message):
    """服务故障时的处理"""
    print(f"服务故障: {service_name} - {error_message}")

    # 记录错误日志
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"服务 {service_name} 故障: {error_message}")

    # 根据服务类型采取不同的处理策略
    if service_name == "wxauto_manager":
        # 微信服务故障，暂停消息监听
        message_listener.stop_listening()
        wechat_service_manager.stop_monitoring()
    elif service_name == "accounting_manager":
        # 记账服务故障，停止消息投递
        message_delivery.set_auto_reply(False)

def on_service_recovered(service_name):
    """服务恢复时的处理"""
    print(f"服务已恢复: {service_name}")

    # 根据服务类型恢复相关功能
    if service_name == "wxauto_manager":
        # 微信服务恢复，重新开始监听
        monitored_chats = wechat_service_manager.get_monitored_chats()
        if monitored_chats:
            message_listener.start_listening(monitored_chats)
            wechat_service_manager.start_monitoring()
    elif service_name == "accounting_manager":
        # 记账服务恢复，重新启用自动回复
        config = config_manager.get_wechat_monitor_config()
        message_delivery.set_auto_reply(config.auto_reply)

# 2. 连接服务监控信号
service_monitor.service_failed.connect(on_service_failed)
service_monitor.service_recovered.connect(on_service_recovered)
```

## 总结

本文档详细描述了8个核心模块的接口定义和调用方式。通过这些标准化的接口，可以实现：

1. **模块间的松耦合**: 通过信号槽机制进行通信
2. **统一的服务管理**: 所有模块都实现BaseService接口
3. **灵活的配置管理**: 通过ConfigManager统一管理配置
4. **健壮的错误处理**: 通过ServiceMonitor监控和恢复
5. **可扩展的架构**: 新模块可以轻松集成到现有系统

这种模块化设计为项目的长期维护和功能扩展提供了坚实的基础。
```
