"""
微信监控服务管理模块
整合微信服务的配置、状态管理和监控功能
"""

import logging
import threading
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal

from .base_interfaces import (
    ConfigurableService, ServiceStatus, HealthStatus, ServiceInfo, 
    HealthCheckResult
)

logger = logging.getLogger(__name__)


@dataclass
class WechatConfig:
    """微信配置"""
    enabled: bool = True
    auto_reply: bool = True
    monitored_chats: List[str] = None
    reply_template: str = ""
    max_retry_count: int = 3
    connection_timeout: int = 30
    
    def __post_init__(self):
        if self.monitored_chats is None:
            self.monitored_chats = []


@dataclass
class ChatStats:
    """聊天统计信息"""
    chat_name: str
    total_processed: int = 0
    successful_accounting: int = 0
    failed_accounting: int = 0
    irrelevant_messages: int = 0
    last_message_time: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_processed == 0:
            return 0.0
        return (self.successful_accounting / self.total_processed) * 100


class WechatServiceManager(ConfigurableService):
    """微信监控服务管理器"""
    
    # 信号定义
    chat_added = pyqtSignal(str)                    # (chat_name)
    chat_removed = pyqtSignal(str)                  # (chat_name)
    stats_updated = pyqtSignal(str, dict)           # (chat_name, stats)
    monitoring_started = pyqtSignal(list)           # (chat_names)
    monitoring_stopped = pyqtSignal()               # ()
    config_changed = pyqtSignal(dict)               # (new_config)
    
    def __init__(self, state_manager=None, wxauto_manager=None, parent=None):
        super().__init__("wechat_service_manager", parent)
        
        self.state_manager = state_manager
        self.wxauto_manager = wxauto_manager
        self._config = WechatConfig()
        self._lock = threading.RLock()
        
        # 聊天统计
        self._chat_stats: Dict[str, ChatStats] = {}
        
        # 监控状态
        self._is_monitoring = False
        self._monitored_chats: List[str] = []
        
        # 连接状态
        self._connection_healthy = False
        self._last_health_check = 0
        self._health_check_interval = 30  # 30秒检查一次
        
        logger.info("微信服务管理器初始化完成")
    
    def start(self) -> bool:
        """启动服务"""
        try:
            self._update_status(ServiceStatus.STARTING)
            
            # 加载配置
            if not self._load_config():
                logger.warning("加载微信配置失败，使用默认配置")
            
            # 加载统计数据
            self._load_stats()
            
            # 检查wxauto管理器
            if not self.wxauto_manager:
                logger.error("wxauto管理器未设置")
                self._update_status(ServiceStatus.ERROR)
                return False
            
            self._update_status(ServiceStatus.RUNNING)
            self._update_health(HealthStatus.HEALTHY)
            return True
            
        except Exception as e:
            logger.error(f"启动微信服务管理器失败: {e}")
            self._update_status(ServiceStatus.ERROR)
            self._update_health(HealthStatus.UNHEALTHY)
            return False
    
    def stop(self) -> bool:
        """停止服务"""
        try:
            self._update_status(ServiceStatus.STOPPING)
            
            # 停止监控
            if self._is_monitoring:
                self.stop_monitoring()
            
            # 保存统计数据
            self._save_stats()
            
            self._update_status(ServiceStatus.STOPPED)
            self._update_health(HealthStatus.UNKNOWN)
            return True
            
        except Exception as e:
            logger.error(f"停止微信服务管理器失败: {e}")
            return False
    
    def restart(self) -> bool:
        """重启服务"""
        if self.stop():
            time.sleep(1)
            return self.start()
        return False
    
    def get_info(self) -> ServiceInfo:
        """获取服务信息"""
        details = {
            'enabled': self._config.enabled,
            'auto_reply': self._config.auto_reply,
            'monitored_chats': self._monitored_chats.copy(),
            'is_monitoring': self._is_monitoring,
            'connection_healthy': self._connection_healthy,
            'total_chats': len(self._chat_stats),
            'chat_stats': {name: {
                'total_processed': stats.total_processed,
                'success_rate': stats.success_rate
            } for name, stats in self._chat_stats.items()}
        }
        
        return ServiceInfo(
            name=self.service_name,
            status=self.status,
            health=self.health,
            message=f"监控{'运行中' if self._is_monitoring else '已停止'}，{len(self._monitored_chats)}个聊天",
            details=details
        )
    
    def check_health(self) -> HealthCheckResult:
        """检查服务健康状态"""
        start_time = time.time()
        
        try:
            # 检查wxauto管理器状态
            wxauto_healthy = False
            wxauto_message = "wxauto管理器未设置"
            
            if self.wxauto_manager:
                try:
                    wxauto_healthy = self.wxauto_manager.is_connected()
                    wxauto_message = "微信连接正常" if wxauto_healthy else "微信连接异常"
                except Exception as e:
                    wxauto_message = f"检查微信连接失败: {str(e)}"
            
            self._connection_healthy = wxauto_healthy
            self._last_health_check = time.time()
            
            # 检查监控状态
            monitoring_issues = []
            if self._is_monitoring and not self._monitored_chats:
                monitoring_issues.append("监控已启动但无监控目标")
            
            # 判断健康状态
            if not wxauto_healthy:
                status = HealthStatus.UNHEALTHY
                message = wxauto_message
            elif monitoring_issues:
                status = HealthStatus.DEGRADED
                message = "; ".join(monitoring_issues)
            else:
                status = HealthStatus.HEALTHY
                message = "微信服务运行正常"
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    'wxauto_healthy': wxauto_healthy,
                    'wxauto_message': wxauto_message,
                    'is_monitoring': self._is_monitoring,
                    'monitored_chats_count': len(self._monitored_chats),
                    'monitoring_issues': monitoring_issues
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
    
    def update_config(self, config: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            with self._lock:
                # 更新配置
                if 'enabled' in config:
                    self._config.enabled = config['enabled']
                if 'auto_reply' in config:
                    self._config.auto_reply = config['auto_reply']
                if 'monitored_chats' in config:
                    self._config.monitored_chats = config['monitored_chats']
                if 'reply_template' in config:
                    self._config.reply_template = config['reply_template']
                if 'max_retry_count' in config:
                    self._config.max_retry_count = config['max_retry_count']
                if 'connection_timeout' in config:
                    self._config.connection_timeout = config['connection_timeout']
                
                # 保存配置
                self._save_config()
                
                # 发出配置更新信号
                self.config_changed.emit(self.get_config())
                
                logger.info("微信服务配置更新成功")
                return True
                
        except Exception as e:
            logger.error(f"更新微信服务配置失败: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'enabled': self._config.enabled,
            'auto_reply': self._config.auto_reply,
            'monitored_chats': self._config.monitored_chats.copy(),
            'reply_template': self._config.reply_template,
            'max_retry_count': self._config.max_retry_count,
            'connection_timeout': self._config.connection_timeout
        }
    
    # 聊天管理方法
    
    def add_chat(self, chat_name: str) -> bool:
        """添加监控聊天"""
        try:
            with self._lock:
                if chat_name not in self._monitored_chats:
                    self._monitored_chats.append(chat_name)
                    
                    # 创建统计信息
                    if chat_name not in self._chat_stats:
                        self._chat_stats[chat_name] = ChatStats(chat_name=chat_name)
                    
                    # 更新配置
                    self._config.monitored_chats = self._monitored_chats.copy()
                    self._save_config()
                    
                    # 如果正在监控，添加到wxauto管理器
                    if self._is_monitoring and self.wxauto_manager:
                        self.wxauto_manager.add_listen_chat(chat_name)
                    
                    logger.info(f"添加监控聊天: {chat_name}")
                    self.chat_added.emit(chat_name)
                    return True
                else:
                    logger.warning(f"聊天已在监控列表中: {chat_name}")
                    return True
                    
        except Exception as e:
            logger.error(f"添加监控聊天失败: {e}")
            return False
    
    def remove_chat(self, chat_name: str) -> bool:
        """移除监控聊天"""
        try:
            with self._lock:
                if chat_name in self._monitored_chats:
                    self._monitored_chats.remove(chat_name)
                    
                    # 更新配置
                    self._config.monitored_chats = self._monitored_chats.copy()
                    self._save_config()
                    
                    # 如果正在监控，从wxauto管理器移除
                    if self._is_monitoring and self.wxauto_manager:
                        self.wxauto_manager.remove_listen_chat(chat_name)
                    
                    logger.info(f"移除监控聊天: {chat_name}")
                    self.chat_removed.emit(chat_name)
                    return True
                else:
                    logger.warning(f"聊天不在监控列表中: {chat_name}")
                    return True
                    
        except Exception as e:
            logger.error(f"移除监控聊天失败: {e}")
            return False
    
    def get_monitored_chats(self) -> List[str]:
        """获取监控聊天列表"""
        with self._lock:
            return self._monitored_chats.copy()
    
    def start_monitoring(self) -> bool:
        """开始监控"""
        try:
            with self._lock:
                if self._is_monitoring:
                    logger.warning("监控已在运行")
                    return True
                
                if not self._config.enabled:
                    logger.warning("微信服务未启用")
                    return False
                
                if not self.wxauto_manager:
                    logger.error("wxauto管理器未设置")
                    return False
                
                if not self._monitored_chats:
                    logger.warning("无监控目标")
                    return False
                
                # 添加监听聊天到wxauto管理器
                for chat_name in self._monitored_chats:
                    if not self.wxauto_manager.add_listen_chat(chat_name):
                        logger.error(f"添加监听聊天失败: {chat_name}")
                        return False
                
                self._is_monitoring = True
                logger.info(f"开始监控 {len(self._monitored_chats)} 个聊天")
                self.monitoring_started.emit(self._monitored_chats.copy())
                return True
                
        except Exception as e:
            logger.error(f"开始监控失败: {e}")
            return False
    
    def stop_monitoring(self) -> bool:
        """停止监控"""
        try:
            with self._lock:
                if not self._is_monitoring:
                    logger.warning("监控未在运行")
                    return True
                
                # 从wxauto管理器移除监听聊天
                if self.wxauto_manager:
                    for chat_name in self._monitored_chats:
                        self.wxauto_manager.remove_listen_chat(chat_name)
                
                self._is_monitoring = False
                logger.info("停止监控")
                self.monitoring_stopped.emit()
                return True
                
        except Exception as e:
            logger.error(f"停止监控失败: {e}")
            return False

    # 统计管理方法

    def update_chat_stats(self, chat_name: str, processed: bool = False,
                         accounting_success: bool = False, irrelevant: bool = False) -> bool:
        """更新聊天统计"""
        try:
            with self._lock:
                if chat_name not in self._chat_stats:
                    self._chat_stats[chat_name] = ChatStats(chat_name=chat_name)

                stats = self._chat_stats[chat_name]

                if processed:
                    stats.total_processed += 1
                    stats.last_message_time = time.strftime('%Y-%m-%d %H:%M:%S')

                if accounting_success:
                    stats.successful_accounting += 1
                elif processed and not irrelevant:
                    stats.failed_accounting += 1

                if irrelevant:
                    stats.irrelevant_messages += 1

                # 发出统计更新信号
                stats_dict = {
                    'total_processed': stats.total_processed,
                    'successful_accounting': stats.successful_accounting,
                    'failed_accounting': stats.failed_accounting,
                    'irrelevant_messages': stats.irrelevant_messages,
                    'success_rate': stats.success_rate,
                    'last_message_time': stats.last_message_time
                }

                self.stats_updated.emit(chat_name, stats_dict)

                # 定期保存统计数据
                if stats.total_processed % 10 == 0:  # 每10条消息保存一次
                    self._save_stats()

                return True

        except Exception as e:
            logger.error(f"更新聊天统计失败: {e}")
            return False

    def get_chat_stats(self, chat_name: str) -> Optional[Dict[str, Any]]:
        """获取聊天统计"""
        with self._lock:
            if chat_name in self._chat_stats:
                stats = self._chat_stats[chat_name]
                return {
                    'chat_name': stats.chat_name,
                    'total_processed': stats.total_processed,
                    'successful_accounting': stats.successful_accounting,
                    'failed_accounting': stats.failed_accounting,
                    'irrelevant_messages': stats.irrelevant_messages,
                    'success_rate': stats.success_rate,
                    'last_message_time': stats.last_message_time
                }
            return None

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有聊天统计"""
        with self._lock:
            result = {}
            for chat_name, stats in self._chat_stats.items():
                result[chat_name] = {
                    'total_processed': stats.total_processed,
                    'successful_accounting': stats.successful_accounting,
                    'failed_accounting': stats.failed_accounting,
                    'irrelevant_messages': stats.irrelevant_messages,
                    'success_rate': stats.success_rate,
                    'last_message_time': stats.last_message_time
                }
            return result

    def reset_chat_stats(self, chat_name: str) -> bool:
        """重置聊天统计"""
        try:
            with self._lock:
                if chat_name in self._chat_stats:
                    self._chat_stats[chat_name] = ChatStats(chat_name=chat_name)
                    self._save_stats()
                    logger.info(f"重置聊天统计: {chat_name}")
                    return True
                return False
        except Exception as e:
            logger.error(f"重置聊天统计失败: {e}")
            return False

    def is_monitoring(self) -> bool:
        """检查是否正在监控"""
        return self._is_monitoring

    def is_chat_monitored(self, chat_name: str) -> bool:
        """检查聊天是否被监控"""
        with self._lock:
            return chat_name in self._monitored_chats

    # 私有方法

    def _load_config(self) -> bool:
        """加载配置"""
        try:
            if self.state_manager:
                wechat_status = self.state_manager.get_wechat_service_status()
                self._config.enabled = wechat_status.get('enabled', True)
                self._config.auto_reply = wechat_status.get('auto_reply', True)
                self._config.monitored_chats = wechat_status.get('monitored_chats', [])
                self._config.reply_template = wechat_status.get('reply_template', '')

                # 同步监控聊天列表
                self._monitored_chats = self._config.monitored_chats.copy()

                return True
            return False
        except Exception as e:
            logger.error(f"加载微信配置失败: {e}")
            return False

    def _save_config(self) -> bool:
        """保存配置"""
        try:
            if self.state_manager:
                self.state_manager.update_wechat_service(
                    enabled=self._config.enabled,
                    auto_reply=self._config.auto_reply,
                    monitored_chats=self._config.monitored_chats,
                    reply_template=self._config.reply_template
                )
                return True
            return False
        except Exception as e:
            logger.error(f"保存微信配置失败: {e}")
            return False

    def _load_stats(self) -> bool:
        """加载统计数据"""
        try:
            if self.state_manager:
                stats_data = self.state_manager.get_stats()

                # 为每个监控聊天创建统计对象
                for chat_name in self._monitored_chats:
                    if chat_name not in self._chat_stats:
                        self._chat_stats[chat_name] = ChatStats(chat_name=chat_name)

                # 加载已有的统计数据
                chat_stats = stats_data.get('chat_stats', {})
                for chat_name, stats in chat_stats.items():
                    if chat_name not in self._chat_stats:
                        self._chat_stats[chat_name] = ChatStats(chat_name=chat_name)

                    chat_stat = self._chat_stats[chat_name]
                    chat_stat.total_processed = stats.get('total_processed', 0)
                    chat_stat.successful_accounting = stats.get('successful_accounting', 0)
                    chat_stat.failed_accounting = stats.get('failed_accounting', 0)
                    chat_stat.irrelevant_messages = stats.get('irrelevant_messages', 0)
                    chat_stat.last_message_time = stats.get('last_message_time')

                return True
            return False
        except Exception as e:
            logger.error(f"加载统计数据失败: {e}")
            return False

    def _save_stats(self) -> bool:
        """保存统计数据"""
        try:
            if self.state_manager:
                # 构建统计数据
                chat_stats = {}
                for chat_name, stats in self._chat_stats.items():
                    chat_stats[chat_name] = {
                        'total_processed': stats.total_processed,
                        'successful_accounting': stats.successful_accounting,
                        'failed_accounting': stats.failed_accounting,
                        'irrelevant_messages': stats.irrelevant_messages,
                        'last_message_time': stats.last_message_time
                    }

                # 更新状态管理器
                self.state_manager.update_stats(chat_stats=chat_stats)
                return True
            return False
        except Exception as e:
            logger.error(f"保存统计数据失败: {e}")
            return False
