"""
统一配置管理模块
管理所有服务的配置信息，包括记账服务、微信监控、wxauto库、日志规则等配置
"""

import logging
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict, field
from PyQt6.QtCore import QObject, pyqtSignal

from .base_interfaces import (
    ConfigurableService, ServiceStatus, HealthStatus, ServiceInfo, 
    HealthCheckResult
)

logger = logging.getLogger(__name__)


@dataclass
class AccountingConfig:
    """记账服务配置"""
    server_url: str = ""
    username: str = ""
    password: str = ""
    account_book_id: str = ""
    account_book_name: str = ""
    auto_login: bool = True
    token_refresh_interval: int = 300  # 5分钟
    request_timeout: int = 30
    max_retries: int = 3


@dataclass
class WechatMonitorConfig:
    """微信监控配置"""
    enabled: bool = True
    monitored_chats: List[str] = field(default_factory=list)
    auto_reply: bool = True
    reply_template: str = ""
    max_retry_count: int = 3
    connection_timeout: int = 30
    message_filter_enabled: bool = False
    message_filter_keywords: List[str] = field(default_factory=list)


@dataclass
class WxautoConfig:
    """wxauto库配置"""
    library_type: str = "wxauto"  # wxauto 或 wxautox
    auto_init: bool = True
    connection_timeout: int = 30
    max_retry_count: int = 3
    save_path: str = ""
    enable_logging: bool = True
    # wxautox特有配置
    wxautox_port: int = 39999
    wxautox_host: str = "127.0.0.1"
    wxautox_timeout: int = 30


@dataclass
class LogConfig:
    """日志配置"""
    level: str = "INFO"
    console_output: bool = True
    file_output: bool = True
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    max_files: int = 10
    auto_rotate: bool = True
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # 过滤器配置
    level_filter: Optional[List[str]] = None
    module_filter: Optional[List[str]] = None
    # 特殊日志配置
    error_log_separate: bool = True
    performance_log_enabled: bool = False


@dataclass
class ServiceMonitorConfig:
    """服务监控配置"""
    enabled: bool = True
    global_check_interval: int = 30
    max_concurrent_recoveries: int = 2
    auto_recovery: bool = True
    recovery_cooldown: int = 300  # 5分钟
    alert_enabled: bool = True
    alert_threshold: int = 3  # 连续失败次数
    # 各服务特定配置
    accounting_check_interval: int = 60
    wechat_check_interval: int = 30
    message_check_interval: int = 10


@dataclass
class UIConfig:
    """UI配置"""
    theme: str = "default"
    window_width: int = 800
    window_height: int = 600
    window_x: int = -1
    window_y: int = -1
    auto_scroll_logs: bool = True
    log_display_limit: int = 1000
    show_debug_info: bool = False
    minimize_to_tray: bool = True
    start_minimized: bool = False


@dataclass
class SystemConfig:
    """系统配置"""
    data_dir: str = "data"
    temp_dir: str = "data/temp"
    backup_dir: str = "data/backup"
    config_file: str = "data/config.json"
    state_file: str = "data/app_state.json"
    auto_backup: bool = True
    backup_interval: int = 3600  # 1小时
    max_backups: int = 10
    # 性能配置
    max_memory_usage: int = 512 * 1024 * 1024  # 512MB
    gc_interval: int = 300  # 5分钟


@dataclass
class AppConfig:
    """应用总配置"""
    version: str = "1.0.0"
    accounting: AccountingConfig = field(default_factory=AccountingConfig)
    wechat_monitor: WechatMonitorConfig = field(default_factory=WechatMonitorConfig)
    wxauto: WxautoConfig = field(default_factory=WxautoConfig)
    log: LogConfig = field(default_factory=LogConfig)
    service_monitor: ServiceMonitorConfig = field(default_factory=ServiceMonitorConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    system: SystemConfig = field(default_factory=SystemConfig)
    
    # 元数据
    created_time: str = ""
    last_modified: str = ""
    last_backup: str = ""


class ConfigManager(ConfigurableService):
    """统一配置管理器"""
    
    # 信号定义
    config_loaded = pyqtSignal(dict)                    # (config_data)
    config_saved = pyqtSignal(str)                      # (config_file)
    config_changed = pyqtSignal(str, dict)              # (section, new_config)
    config_reset = pyqtSignal(str)                      # (section)
    backup_created = pyqtSignal(str)                    # (backup_file)
    config_error = pyqtSignal(str, str)                 # (operation, error_message)
    
    def __init__(self, config_file: str = None, parent=None):
        super().__init__("config_manager", parent)

        # 配置文件路径
        if config_file:
            self.config_file = Path(config_file)
        else:
            # 检测是否为打包后的exe文件
            if getattr(sys, 'frozen', False):
                # 打包后的exe文件 - 使用exe文件所在目录
                project_root = Path(sys.executable).parent
            else:
                # 开发环境 - 使用项目根目录
                project_root = Path(__file__).parent.parent.parent

            self.config_file = project_root / "data" / "config.json"

        # 确保配置目录存在
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 应用配置
        self._config = AppConfig()
        self._lock = threading.RLock()
        
        # 配置变更监听器
        self._change_listeners: Dict[str, List[callable]] = {}
        
        # 备份配置
        self._auto_backup_enabled = True
        self._backup_thread = None
        self._stop_backup = threading.Event()
        
        logger.info("配置管理器初始化完成")
    
    def start(self) -> bool:
        """启动服务"""
        try:
            self._update_status(ServiceStatus.STARTING)
            
            # 加载配置
            if not self.load_config():
                logger.warning("加载配置失败，使用默认配置")
                self._config = AppConfig()
                self.save_config()  # 保存默认配置
            
            # 启动自动备份
            if self._config.system.auto_backup:
                self._start_auto_backup()
            
            self._update_status(ServiceStatus.RUNNING)
            self._update_health(HealthStatus.HEALTHY)
            return True
            
        except Exception as e:
            logger.error(f"启动配置管理器失败: {e}")
            self._update_status(ServiceStatus.ERROR)
            self._update_health(HealthStatus.UNHEALTHY)
            return False
    
    def stop(self) -> bool:
        """停止服务"""
        try:
            self._update_status(ServiceStatus.STOPPING)
            
            # 保存当前配置
            self.save_config()
            
            # 停止自动备份
            self._stop_auto_backup()
            
            self._update_status(ServiceStatus.STOPPED)
            self._update_health(HealthStatus.UNKNOWN)
            return True
            
        except Exception as e:
            logger.error(f"停止配置管理器失败: {e}")
            return False
    
    def restart(self) -> bool:
        """重启服务"""
        if self.stop():
            return self.start()
        return False
    
    def get_info(self) -> ServiceInfo:
        """获取服务信息"""
        details = {
            'config_file': str(self.config_file),
            'config_exists': self.config_file.exists(),
            'config_size': self.config_file.stat().st_size if self.config_file.exists() else 0,
            'auto_backup_enabled': self._auto_backup_enabled,
            'change_listeners': {section: len(listeners) for section, listeners in self._change_listeners.items()},
            'version': self._config.version,
            'last_modified': self._config.last_modified
        }
        
        return ServiceInfo(
            name=self.service_name,
            status=self.status,
            health=self.health,
            message=f"配置文件: {self.config_file.name}",
            details=details
        )
    
    def check_health(self) -> HealthCheckResult:
        """检查服务健康状态"""
        start_time = time.time()
        
        try:
            issues = []
            
            # 检查配置文件
            if not self.config_file.exists():
                issues.append("配置文件不存在")
            elif not os.access(self.config_file, os.R_OK):
                issues.append("配置文件不可读")
            elif not os.access(self.config_file, os.W_OK):
                issues.append("配置文件不可写")
            
            # 检查配置目录
            config_dir = self.config_file.parent
            if not config_dir.exists():
                issues.append("配置目录不存在")
            elif not os.access(config_dir, os.W_OK):
                issues.append("配置目录不可写")
            
            # 检查配置完整性
            try:
                self._validate_config()
            except Exception as e:
                issues.append(f"配置验证失败: {str(e)}")
            
            # 检查备份状态
            if self._config.system.auto_backup:
                backup_dir = Path(self._config.system.backup_dir)
                if not backup_dir.exists():
                    issues.append("备份目录不存在")
                elif not os.access(backup_dir, os.W_OK):
                    issues.append("备份目录不可写")
            
            # 判断健康状态
            if not self.config_file.exists() or not config_dir.exists():
                status = HealthStatus.UNHEALTHY
                message = "配置系统不可用"
            elif issues:
                status = HealthStatus.DEGRADED
                message = "; ".join(issues)
            else:
                status = HealthStatus.HEALTHY
                message = "配置管理器运行正常"
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    'config_file_exists': self.config_file.exists(),
                    'config_file_readable': os.access(self.config_file, os.R_OK) if self.config_file.exists() else False,
                    'config_file_writable': os.access(self.config_file, os.W_OK) if self.config_file.exists() else False,
                    'config_dir_writable': os.access(config_dir, os.W_OK) if config_dir.exists() else False,
                    'auto_backup_enabled': self._auto_backup_enabled,
                    'issues': issues
                },
                response_time=response_time
            )
            
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"健康检查异常: {str(e)}",
                details={'exception': str(e)},
                response_time=time.time() - start_time
            )

    # 配置加载和保存

    def load_config(self) -> bool:
        """加载配置"""
        try:
            with self._lock:
                if not self.config_file.exists():
                    logger.info("配置文件不存在，使用默认配置")
                    return False

                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                # 转换为配置对象
                self._config = self._dict_to_config(config_data)

                logger.info(f"配置加载成功: {self.config_file}")
                self.config_loaded.emit(config_data)
                return True

        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.config_error.emit("load", str(e))
            return False

    def save_config(self) -> bool:
        """保存配置"""
        try:
            with self._lock:
                # 更新元数据
                from datetime import datetime
                self._config.last_modified = datetime.now().isoformat()

                # 转换为字典
                config_data = self._config_to_dict(self._config)

                # 创建备份
                if self.config_file.exists():
                    backup_file = f"{self.config_file}.backup"
                    import shutil
                    shutil.copy2(self.config_file, backup_file)

                # 保存配置
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)

                # 设置文件权限
                os.chmod(self.config_file, 0o600)

                logger.info(f"配置保存成功: {self.config_file}")
                self.config_saved.emit(str(self.config_file))
                return True

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            self.config_error.emit("save", str(e))
            return False

    def reload_config(self) -> bool:
        """重新加载配置"""
        logger.info("重新加载配置")
        return self.load_config()

    def reset_config(self, section: str = None) -> bool:
        """重置配置"""
        try:
            with self._lock:
                if section:
                    # 重置指定部分
                    if section == "accounting":
                        self._config.accounting = AccountingConfig()
                    elif section == "wechat_monitor":
                        self._config.wechat_monitor = WechatMonitorConfig()
                    elif section == "wxauto":
                        self._config.wxauto = WxautoConfig()
                    elif section == "log":
                        self._config.log = LogConfig()
                    elif section == "service_monitor":
                        self._config.service_monitor = ServiceMonitorConfig()
                    elif section == "ui":
                        self._config.ui = UIConfig()
                    elif section == "system":
                        self._config.system = SystemConfig()
                    else:
                        logger.warning(f"未知配置部分: {section}")
                        return False

                    logger.info(f"配置部分已重置: {section}")
                    self.config_reset.emit(section)
                else:
                    # 重置全部配置
                    self._config = AppConfig()
                    logger.info("全部配置已重置")
                    self.config_reset.emit("all")

                # 保存重置后的配置
                return self.save_config()

        except Exception as e:
            logger.error(f"重置配置失败: {e}")
            self.config_error.emit("reset", str(e))
            return False

    # 配置获取方法

    def get_config(self) -> AppConfig:
        """获取完整配置"""
        with self._lock:
            return self._config

    def get_accounting_config(self) -> AccountingConfig:
        """获取记账配置"""
        with self._lock:
            return self._config.accounting

    def get_wechat_monitor_config(self) -> WechatMonitorConfig:
        """获取微信监控配置"""
        with self._lock:
            return self._config.wechat_monitor

    def get_wxauto_config(self) -> WxautoConfig:
        """获取wxauto配置"""
        with self._lock:
            return self._config.wxauto

    def get_log_config(self) -> LogConfig:
        """获取日志配置"""
        with self._lock:
            return self._config.log

    def get_service_monitor_config(self) -> ServiceMonitorConfig:
        """获取服务监控配置"""
        with self._lock:
            return self._config.service_monitor

    def get_ui_config(self) -> UIConfig:
        """获取UI配置"""
        with self._lock:
            return self._config.ui

    def get_system_config(self) -> SystemConfig:
        """获取系统配置"""
        with self._lock:
            return self._config.system

    # 配置更新方法

    def update_accounting_config(self, **kwargs) -> bool:
        """更新记账配置"""
        try:
            with self._lock:
                for key, value in kwargs.items():
                    if hasattr(self._config.accounting, key):
                        setattr(self._config.accounting, key, value)
                    else:
                        logger.warning(f"未知的记账配置项: {key}")

                self._notify_config_change("accounting", asdict(self._config.accounting))
                return self.save_config()

        except Exception as e:
            logger.error(f"更新记账配置失败: {e}")
            return False

    def update_wechat_monitor_config(self, **kwargs) -> bool:
        """更新微信监控配置"""
        try:
            with self._lock:
                for key, value in kwargs.items():
                    if hasattr(self._config.wechat_monitor, key):
                        setattr(self._config.wechat_monitor, key, value)
                    else:
                        logger.warning(f"未知的微信监控配置项: {key}")

                self._notify_config_change("wechat_monitor", asdict(self._config.wechat_monitor))
                return self.save_config()

        except Exception as e:
            logger.error(f"更新微信监控配置失败: {e}")
            return False

    def update_wxauto_config(self, **kwargs) -> bool:
        """更新wxauto配置"""
        try:
            with self._lock:
                for key, value in kwargs.items():
                    if hasattr(self._config.wxauto, key):
                        setattr(self._config.wxauto, key, value)
                    else:
                        logger.warning(f"未知的wxauto配置项: {key}")

                self._notify_config_change("wxauto", asdict(self._config.wxauto))
                return self.save_config()

        except Exception as e:
            logger.error(f"更新wxauto配置失败: {e}")
            return False

    def update_log_config(self, **kwargs) -> bool:
        """更新日志配置"""
        try:
            with self._lock:
                for key, value in kwargs.items():
                    if hasattr(self._config.log, key):
                        setattr(self._config.log, key, value)
                    else:
                        logger.warning(f"未知的日志配置项: {key}")

                self._notify_config_change("log", asdict(self._config.log))
                return self.save_config()

        except Exception as e:
            logger.error(f"更新日志配置失败: {e}")
            return False

    def update_service_monitor_config(self, **kwargs) -> bool:
        """更新服务监控配置"""
        try:
            with self._lock:
                for key, value in kwargs.items():
                    if hasattr(self._config.service_monitor, key):
                        setattr(self._config.service_monitor, key, value)
                    else:
                        logger.warning(f"未知的服务监控配置项: {key}")

                self._notify_config_change("service_monitor", asdict(self._config.service_monitor))
                return self.save_config()

        except Exception as e:
            logger.error(f"更新服务监控配置失败: {e}")
            return False

    def update_ui_config(self, **kwargs) -> bool:
        """更新UI配置"""
        try:
            with self._lock:
                for key, value in kwargs.items():
                    if hasattr(self._config.ui, key):
                        setattr(self._config.ui, key, value)
                    else:
                        logger.warning(f"未知的UI配置项: {key}")

                self._notify_config_change("ui", asdict(self._config.ui))
                return self.save_config()

        except Exception as e:
            logger.error(f"更新UI配置失败: {e}")
            return False

    def update_system_config(self, **kwargs) -> bool:
        """更新系统配置"""
        try:
            with self._lock:
                for key, value in kwargs.items():
                    if hasattr(self._config.system, key):
                        setattr(self._config.system, key, value)
                    else:
                        logger.warning(f"未知的系统配置项: {key}")

                self._notify_config_change("system", asdict(self._config.system))
                return self.save_config()

        except Exception as e:
            logger.error(f"更新系统配置失败: {e}")
            return False

    # 配置监听器

    def add_config_listener(self, section: str, callback: callable):
        """添加配置变更监听器"""
        if section not in self._change_listeners:
            self._change_listeners[section] = []
        self._change_listeners[section].append(callback)
        logger.debug(f"添加配置监听器: {section}")

    def remove_config_listener(self, section: str, callback: callable):
        """移除配置变更监听器"""
        if section in self._change_listeners:
            try:
                self._change_listeners[section].remove(callback)
                logger.debug(f"移除配置监听器: {section}")
            except ValueError:
                logger.warning(f"监听器不存在: {section}")

    def _notify_config_change(self, section: str, config_data: Dict[str, Any]):
        """通知配置变更"""
        # 发出信号
        self.config_changed.emit(section, config_data)

        # 调用监听器
        if section in self._change_listeners:
            for callback in self._change_listeners[section]:
                try:
                    callback(config_data)
                except Exception as e:
                    logger.error(f"配置监听器回调失败: {e}")

    # 备份和恢复

    def create_backup(self, backup_name: str = None) -> Optional[str]:
        """创建配置备份"""
        try:
            if not backup_name:
                from datetime import datetime
                backup_name = f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            backup_dir = Path(self._config.system.backup_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_file = backup_dir / backup_name

            # 复制配置文件
            import shutil
            shutil.copy2(self.config_file, backup_file)

            # 更新备份时间
            self._config.last_backup = datetime.now().isoformat()

            logger.info(f"配置备份已创建: {backup_file}")
            self.backup_created.emit(str(backup_file))
            return str(backup_file)

        except Exception as e:
            logger.error(f"创建配置备份失败: {e}")
            self.config_error.emit("backup", str(e))
            return None

    def restore_backup(self, backup_file: str) -> bool:
        """恢复配置备份"""
        try:
            backup_path = Path(backup_file)
            if not backup_path.exists():
                logger.error(f"备份文件不存在: {backup_file}")
                return False

            # 创建当前配置的备份
            current_backup = self.create_backup("before_restore")

            # 恢复备份
            import shutil
            shutil.copy2(backup_path, self.config_file)

            # 重新加载配置
            if self.load_config():
                logger.info(f"配置已从备份恢复: {backup_file}")
                return True
            else:
                # 恢复失败，回滚
                if current_backup:
                    shutil.copy2(current_backup, self.config_file)
                    self.load_config()
                logger.error("配置恢复失败，已回滚")
                return False

        except Exception as e:
            logger.error(f"恢复配置备份失败: {e}")
            self.config_error.emit("restore", str(e))
            return False

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份"""
        try:
            backup_dir = Path(self._config.system.backup_dir)
            if not backup_dir.exists():
                return []

            backups = []
            for backup_file in backup_dir.glob("*.json"):
                stat = backup_file.stat()
                backups.append({
                    'name': backup_file.name,
                    'path': str(backup_file),
                    'size': stat.st_size,
                    'created_time': stat.st_ctime,
                    'modified_time': stat.st_mtime
                })

            # 按修改时间排序
            backups.sort(key=lambda x: x['modified_time'], reverse=True)
            return backups

        except Exception as e:
            logger.error(f"列出备份失败: {e}")
            return []

    def cleanup_old_backups(self) -> int:
        """清理旧备份"""
        try:
            backups = self.list_backups()
            max_backups = self._config.system.max_backups

            if len(backups) <= max_backups:
                return 0

            # 删除超出数量的旧备份
            old_backups = backups[max_backups:]
            deleted_count = 0

            for backup in old_backups:
                try:
                    Path(backup['path']).unlink()
                    deleted_count += 1
                    logger.debug(f"删除旧备份: {backup['name']}")
                except Exception as e:
                    logger.warning(f"删除备份失败 {backup['name']}: {e}")

            logger.info(f"清理了 {deleted_count} 个旧备份")
            return deleted_count

        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")
            return 0

    # 配置验证

    def _validate_config(self):
        """验证配置完整性"""
        # 验证记账配置
        if self._config.accounting.server_url and not self._config.accounting.server_url.startswith(('http://', 'https://')):
            raise ValueError("记账服务器地址格式错误")

        # 验证wxauto配置
        if self._config.wxauto.library_type not in ['wxauto', 'wxautox']:
            raise ValueError("wxauto库类型无效")

        # 验证日志配置
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self._config.log.level not in valid_log_levels:
            raise ValueError("日志级别无效")

        # 验证UI配置
        if self._config.ui.window_width < 400 or self._config.ui.window_height < 300:
            raise ValueError("窗口尺寸过小")

        # 验证系统配置
        if self._config.system.max_memory_usage < 64 * 1024 * 1024:  # 64MB
            raise ValueError("最大内存使用量过小")

    # 私有方法

    def _config_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        """配置对象转字典"""
        return asdict(config)

    def _dict_to_config(self, data: Dict[str, Any]) -> AppConfig:
        """字典转配置对象"""
        # 创建默认配置
        config = AppConfig()

        # 更新各部分配置
        if 'accounting' in data:
            config.accounting = AccountingConfig(**data['accounting'])
        if 'wechat_monitor' in data:
            config.wechat_monitor = WechatMonitorConfig(**data['wechat_monitor'])
        if 'wxauto' in data:
            config.wxauto = WxautoConfig(**data['wxauto'])
        if 'log' in data:
            config.log = LogConfig(**data['log'])
        if 'service_monitor' in data:
            config.service_monitor = ServiceMonitorConfig(**data['service_monitor'])
        if 'ui' in data:
            config.ui = UIConfig(**data['ui'])
        if 'system' in data:
            config.system = SystemConfig(**data['system'])

        # 更新元数据
        config.version = data.get('version', config.version)
        config.created_time = data.get('created_time', config.created_time)
        config.last_modified = data.get('last_modified', config.last_modified)
        config.last_backup = data.get('last_backup', config.last_backup)

        return config

    def _start_auto_backup(self):
        """启动自动备份"""
        if self._backup_thread and self._backup_thread.is_alive():
            return

        self._stop_backup.clear()
        self._backup_thread = threading.Thread(target=self._auto_backup_loop, daemon=True)
        self._backup_thread.start()
        logger.info("自动备份已启动")

    def _stop_auto_backup(self):
        """停止自动备份"""
        self._stop_backup.set()
        if self._backup_thread and self._backup_thread.is_alive():
            self._backup_thread.join(timeout=5)
        logger.info("自动备份已停止")

    def _auto_backup_loop(self):
        """自动备份循环"""
        while not self._stop_backup.is_set():
            try:
                # 等待备份间隔
                self._stop_backup.wait(self._config.system.backup_interval)

                if not self._stop_backup.is_set():
                    # 创建自动备份
                    self.create_backup()

                    # 清理旧备份
                    self.cleanup_old_backups()

            except Exception as e:
                logger.error(f"自动备份循环异常: {e}")
                self._stop_backup.wait(60)  # 出错时等待1分钟

    # ConfigurableService接口实现

    def update_config(self, config: Dict[str, Any]) -> bool:
        """更新配置（通用接口）"""
        try:
            success = True

            for section, section_config in config.items():
                if section == "accounting":
                    success &= self.update_accounting_config(**section_config)
                elif section == "wechat_monitor":
                    success &= self.update_wechat_monitor_config(**section_config)
                elif section == "wxauto":
                    success &= self.update_wxauto_config(**section_config)
                elif section == "log":
                    success &= self.update_log_config(**section_config)
                elif section == "service_monitor":
                    success &= self.update_service_monitor_config(**section_config)
                elif section == "ui":
                    success &= self.update_ui_config(**section_config)
                elif section == "system":
                    success &= self.update_system_config(**section_config)
                else:
                    logger.warning(f"未知配置部分: {section}")
                    success = False

            return success

        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False

    def get_config_dict(self) -> Dict[str, Any]:
        """获取配置字典（通用接口）"""
        with self._lock:
            return self._config_to_dict(self._config)
