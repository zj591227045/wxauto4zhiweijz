"""
基础接口定义
定义所有模块的基础接口和抽象类
"""

from abc import ABC, abstractmethod, ABCMeta
from typing import Dict, Any, Optional, List, Tuple, Callable
from enum import Enum
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtCore import QMetaObject


class QABCMeta(type(QObject), ABCMeta):
    """兼容QObject和ABC的元类"""
    pass


class ServiceStatus(Enum):
    """服务状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    RECOVERING = "recovering"


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceInfo:
    """服务信息"""
    name: str
    status: ServiceStatus
    health: HealthStatus
    message: str = ""
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    status: HealthStatus
    message: str
    details: Dict[str, Any] = None
    response_time: float = 0.0
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class BaseService(QObject, ABC, metaclass=QABCMeta):
    """基础服务抽象类"""
    
    # 通用信号
    status_changed = pyqtSignal(str, str)  # (service_name, new_status)
    health_changed = pyqtSignal(str, str)  # (service_name, new_health)
    error_occurred = pyqtSignal(str, str)  # (service_name, error_message)
    
    def __init__(self, service_name: str, parent=None):
        super().__init__(parent)
        self.service_name = service_name
        self._status = ServiceStatus.STOPPED
        self._health = HealthStatus.UNKNOWN
        
    @property
    def status(self) -> ServiceStatus:
        return self._status
        
    @property
    def health(self) -> HealthStatus:
        return self._health
        
    def _update_status(self, new_status: ServiceStatus, message: str = ""):
        """更新服务状态"""
        if self._status != new_status:
            old_status = self._status
            self._status = new_status
            self.status_changed.emit(self.service_name, new_status.value)
            
    def _update_health(self, new_health: HealthStatus, message: str = ""):
        """更新健康状态"""
        if self._health != new_health:
            old_health = self._health
            self._health = new_health
            self.health_changed.emit(self.service_name, new_health.value)
    
    @abstractmethod
    def start(self) -> bool:
        """启动服务"""
        pass
        
    @abstractmethod
    def stop(self) -> bool:
        """停止服务"""
        pass
        
    @abstractmethod
    def restart(self) -> bool:
        """重启服务"""
        pass
        
    @abstractmethod
    def get_info(self) -> ServiceInfo:
        """获取服务信息"""
        pass
        
    @abstractmethod
    def check_health(self) -> HealthCheckResult:
        """检查服务健康状态"""
        pass


class ConfigurableService(BaseService):
    """可配置服务抽象类"""
    
    @abstractmethod
    def update_config(self, config: Dict[str, Any]) -> bool:
        """更新配置"""
        pass
        
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        pass


class RecoverableService(BaseService):
    """可恢复服务抽象类"""
    
    @abstractmethod
    def recover(self) -> bool:
        """尝试恢复服务"""
        pass
        
    @abstractmethod
    def is_recoverable(self) -> bool:
        """检查是否可以恢复"""
        pass


# 接口定义

class IAccountingManager(ABC):
    """记账管理器接口"""
    
    @abstractmethod
    def login(self, server_url: str, username: str, password: str) -> Tuple[bool, str]:
        """登录"""
        pass
        
    @abstractmethod
    def smart_accounting(self, description: str, sender_name: str = None) -> Tuple[bool, str]:
        """智能记账"""
        pass
        
    @abstractmethod
    def get_token(self) -> Optional[str]:
        """获取有效token"""
        pass


class IWxautoManager(ABC):
    """wxauto管理器接口"""
    
    @abstractmethod
    def get_instance(self):
        """获取微信实例"""
        pass
        
    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass
        
    @abstractmethod
    def send_message(self, chat_name: str, message: str) -> bool:
        """发送消息"""
        pass
        
    @abstractmethod
    def get_messages(self, chat_name: str) -> List[Dict[str, Any]]:
        """获取消息"""
        pass


class IMessageListener(ABC):
    """消息监听器接口"""
    
    @abstractmethod
    def start_listening(self, chat_names: List[str]) -> bool:
        """开始监听"""
        pass
        
    @abstractmethod
    def stop_listening(self) -> bool:
        """停止监听"""
        pass
        
    @abstractmethod
    def add_chat(self, chat_name: str) -> bool:
        """添加监听聊天"""
        pass


class IMessageDelivery(ABC):
    """消息投递接口"""
    
    @abstractmethod
    def process_message(self, chat_name: str, message_content: str, sender_name: str) -> Tuple[bool, str]:
        """处理消息"""
        pass
        
    @abstractmethod
    def send_reply(self, chat_name: str, reply_message: str) -> bool:
        """发送回复"""
        pass


class ILogManager(ABC):
    """日志管理器接口"""
    
    @abstractmethod
    def get_logs(self, level_filter: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取日志"""
        pass
        
    @abstractmethod
    def clear_logs(self) -> bool:
        """清空日志"""
        pass


class IServiceMonitor(ABC):
    """服务监控器接口"""
    
    @abstractmethod
    def register_service(self, service_name: str, health_checker: Callable, recovery_handler: Callable = None) -> bool:
        """注册服务"""
        pass
        
    @abstractmethod
    def start_monitoring(self) -> bool:
        """开始监控"""
        pass
        
    @abstractmethod
    def stop_monitoring(self) -> bool:
        """停止监控"""
        pass
