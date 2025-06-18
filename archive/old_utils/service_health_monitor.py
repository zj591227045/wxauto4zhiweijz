#!/usr/bin/env python3
"""
服务健康监控器
提供统一的服务健康检查、故障检测和自动恢复机制
"""

import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass, field
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    """服务状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    RECOVERING = "recovering"

@dataclass
class HealthCheckResult:
    """健康检查结果"""
    status: ServiceStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    response_time: float = 0.0

@dataclass
class ServiceConfig:
    """服务配置"""
    name: str
    check_interval: int = 30  # 检查间隔（秒）
    timeout: int = 10  # 超时时间（秒）
    max_failures: int = 3  # 最大失败次数
    recovery_delay: int = 5  # 恢复延迟（秒）
    auto_recovery: bool = True  # 是否自动恢复
    critical: bool = True  # 是否为关键服务

class ServiceHealthMonitor(QObject):
    """服务健康监控器"""
    
    # 信号定义
    service_status_changed = pyqtSignal(str, str, str)  # service_name, old_status, new_status
    service_recovered = pyqtSignal(str, str)  # service_name, message
    service_failed = pyqtSignal(str, str)  # service_name, error_message
    health_report_updated = pyqtSignal(dict)  # health_report
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 服务注册表
        self._services: Dict[str, ServiceConfig] = {}
        
        # 健康检查函数
        self._health_checkers: Dict[str, Callable] = {}
        
        # 恢复函数
        self._recovery_handlers: Dict[str, Callable] = {}
        
        # 服务状态
        self._service_status: Dict[str, ServiceStatus] = {}
        
        # 失败计数
        self._failure_counts: Dict[str, int] = {}
        
        # 最后检查时间
        self._last_check_times: Dict[str, datetime] = {}
        
        # 最后检查结果
        self._last_results: Dict[str, HealthCheckResult] = {}
        
        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        
        # 线程锁
        self._lock = threading.RLock()
        
        # 定时器（用于UI更新）
        self._ui_timer = QTimer()
        self._ui_timer.timeout.connect(self._emit_health_report)
        self._ui_timer.start(5000)  # 每5秒更新一次UI
        
    def register_service(self, 
                        service_name: str,
                        health_checker: Callable,
                        recovery_handler: Optional[Callable] = None,
                        config: Optional[ServiceConfig] = None) -> bool:
        """
        注册服务
        
        Args:
            service_name: 服务名称
            health_checker: 健康检查函数，返回HealthCheckResult
            recovery_handler: 恢复处理函数，可选
            config: 服务配置，可选
            
        Returns:
            注册是否成功
        """
        try:
            with self._lock:
                if config is None:
                    config = ServiceConfig(name=service_name)
                
                self._services[service_name] = config
                self._health_checkers[service_name] = health_checker
                
                if recovery_handler:
                    self._recovery_handlers[service_name] = recovery_handler
                
                # 初始化状态
                self._service_status[service_name] = ServiceStatus.UNKNOWN
                self._failure_counts[service_name] = 0
                self._last_check_times[service_name] = datetime.now()
                
                logger.info(f"服务已注册: {service_name}")
                return True
                
        except Exception as e:
            logger.error(f"注册服务失败 {service_name}: {e}")
            return False
    
    def unregister_service(self, service_name: str) -> bool:
        """注销服务"""
        try:
            with self._lock:
                if service_name in self._services:
                    del self._services[service_name]
                    del self._health_checkers[service_name]
                    
                    if service_name in self._recovery_handlers:
                        del self._recovery_handlers[service_name]
                    
                    if service_name in self._service_status:
                        del self._service_status[service_name]
                    
                    if service_name in self._failure_counts:
                        del self._failure_counts[service_name]
                    
                    if service_name in self._last_check_times:
                        del self._last_check_times[service_name]
                    
                    if service_name in self._last_results:
                        del self._last_results[service_name]
                    
                    logger.info(f"服务已注销: {service_name}")
                    return True
                    
        except Exception as e:
            logger.error(f"注销服务失败 {service_name}: {e}")
            return False
    
    def start_monitoring(self) -> bool:
        """开始监控"""
        try:
            if self._running:
                logger.warning("健康监控器已在运行")
                return True
            
            self._stop_event.clear()
            self._running = True
            
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="ServiceHealthMonitor",
                daemon=True
            )
            self._monitor_thread.start()
            
            logger.info("服务健康监控器已启动")
            return True
            
        except Exception as e:
            logger.error(f"启动健康监控器失败: {e}")
            self._running = False
            return False
    
    def stop_monitoring(self) -> bool:
        """停止监控"""
        try:
            if not self._running:
                return True
            
            self._running = False
            self._stop_event.set()
            
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)
            
            logger.info("服务健康监控器已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止健康监控器失败: {e}")
            return False
    
    def _monitor_loop(self):
        """监控循环"""
        logger.info("健康监控循环开始")
        
        while not self._stop_event.is_set():
            try:
                current_time = datetime.now()
                
                with self._lock:
                    services_to_check = list(self._services.items())
                
                for service_name, config in services_to_check:
                    if self._stop_event.is_set():
                        break
                    
                    try:
                        # 检查是否需要进行健康检查
                        last_check = self._last_check_times.get(service_name, datetime.min)
                        if (current_time - last_check).total_seconds() >= config.check_interval:
                            self._check_service_health(service_name)
                    
                    except Exception as e:
                        logger.error(f"检查服务健康状态失败 {service_name}: {e}")
                
                # 等待一段时间再进行下一轮检查
                self._stop_event.wait(min(5, min(config.check_interval for config in self._services.values()) if self._services else 5))
                
            except Exception as e:
                logger.error(f"健康监控循环异常: {e}")
                self._stop_event.wait(5)
        
        logger.info("健康监控循环结束")
    
    def _check_service_health(self, service_name: str):
        """检查单个服务的健康状态"""
        try:
            config = self._services.get(service_name)
            health_checker = self._health_checkers.get(service_name)
            
            if not config or not health_checker:
                return
            
            # 记录检查时间
            check_start = time.time()
            self._last_check_times[service_name] = datetime.now()
            
            # 执行健康检查
            try:
                result = health_checker()
                if not isinstance(result, HealthCheckResult):
                    result = HealthCheckResult(
                        status=ServiceStatus.UNKNOWN,
                        message="健康检查返回无效结果"
                    )
                
                result.response_time = time.time() - check_start
                
            except Exception as e:
                result = HealthCheckResult(
                    status=ServiceStatus.UNHEALTHY,
                    message=f"健康检查异常: {str(e)}",
                    response_time=time.time() - check_start
                )
            
            # 保存结果
            self._last_results[service_name] = result
            
            # 更新服务状态
            self._update_service_status(service_name, result)
            
        except Exception as e:
            logger.error(f"检查服务健康状态异常 {service_name}: {e}")
    
    def _update_service_status(self, service_name: str, result: HealthCheckResult):
        """更新服务状态"""
        try:
            config = self._services.get(service_name)
            if not config:
                return
            
            old_status = self._service_status.get(service_name, ServiceStatus.UNKNOWN)
            new_status = result.status
            
            # 处理状态变化
            if new_status == ServiceStatus.HEALTHY:
                # 服务健康，重置失败计数
                self._failure_counts[service_name] = 0
                
                if old_status != ServiceStatus.HEALTHY:
                    logger.info(f"服务恢复健康: {service_name} - {result.message}")
                    self.service_recovered.emit(service_name, result.message)
            
            elif new_status in [ServiceStatus.UNHEALTHY, ServiceStatus.DEGRADED]:
                # 服务不健康，增加失败计数
                self._failure_counts[service_name] += 1
                failure_count = self._failure_counts[service_name]
                
                logger.warning(f"服务健康检查失败 {service_name} ({failure_count}/{config.max_failures}): {result.message}")
                
                # 检查是否需要触发恢复
                if failure_count >= config.max_failures and config.auto_recovery:
                    self._trigger_recovery(service_name)
            
            # 更新状态
            if old_status != new_status:
                self._service_status[service_name] = new_status
                self.service_status_changed.emit(service_name, old_status.value, new_status.value)
                
                if new_status == ServiceStatus.UNHEALTHY:
                    self.service_failed.emit(service_name, result.message)
            
        except Exception as e:
            logger.error(f"更新服务状态失败 {service_name}: {e}")
    
    def _trigger_recovery(self, service_name: str):
        """触发服务恢复"""
        try:
            config = self._services.get(service_name)
            recovery_handler = self._recovery_handlers.get(service_name)
            
            if not config or not recovery_handler:
                logger.warning(f"无法恢复服务 {service_name}: 缺少配置或恢复处理器")
                return
            
            logger.info(f"开始恢复服务: {service_name}")
            self._service_status[service_name] = ServiceStatus.RECOVERING
            
            # 在单独的线程中执行恢复
            recovery_thread = threading.Thread(
                target=self._execute_recovery,
                args=(service_name, recovery_handler, config),
                name=f"Recovery-{service_name}",
                daemon=True
            )
            recovery_thread.start()
            
        except Exception as e:
            logger.error(f"触发服务恢复失败 {service_name}: {e}")
    
    def _execute_recovery(self, service_name: str, recovery_handler: Callable, config: ServiceConfig):
        """执行服务恢复"""
        try:
            # 等待恢复延迟
            if config.recovery_delay > 0:
                time.sleep(config.recovery_delay)
            
            # 执行恢复操作
            success = recovery_handler()
            
            if success:
                logger.info(f"服务恢复成功: {service_name}")
                # 重置失败计数
                self._failure_counts[service_name] = 0
                # 立即进行一次健康检查
                self._check_service_health(service_name)
            else:
                logger.error(f"服务恢复失败: {service_name}")
                self._service_status[service_name] = ServiceStatus.UNHEALTHY
            
        except Exception as e:
            logger.error(f"执行服务恢复异常 {service_name}: {e}")
            self._service_status[service_name] = ServiceStatus.UNHEALTHY
    
    def get_service_status(self, service_name: str) -> Optional[ServiceStatus]:
        """获取服务状态"""
        return self._service_status.get(service_name)
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        try:
            with self._lock:
                report = {
                    'timestamp': datetime.now().isoformat(),
                    'services': {},
                    'summary': {
                        'total': len(self._services),
                        'healthy': 0,
                        'unhealthy': 0,
                        'degraded': 0,
                        'unknown': 0,
                        'recovering': 0
                    }
                }
                
                for service_name in self._services:
                    status = self._service_status.get(service_name, ServiceStatus.UNKNOWN)
                    last_result = self._last_results.get(service_name)
                    
                    service_info = {
                        'status': status.value,
                        'failure_count': self._failure_counts.get(service_name, 0),
                        'last_check': self._last_check_times.get(service_name, datetime.min).isoformat(),
                        'config': {
                            'check_interval': self._services[service_name].check_interval,
                            'max_failures': self._services[service_name].max_failures,
                            'auto_recovery': self._services[service_name].auto_recovery,
                            'critical': self._services[service_name].critical
                        }
                    }
                    
                    if last_result:
                        service_info['last_result'] = {
                            'message': last_result.message,
                            'response_time': last_result.response_time,
                            'details': last_result.details
                        }
                    
                    report['services'][service_name] = service_info
                    
                    # 更新摘要
                    if status == ServiceStatus.HEALTHY:
                        report['summary']['healthy'] += 1
                    elif status == ServiceStatus.UNHEALTHY:
                        report['summary']['unhealthy'] += 1
                    elif status == ServiceStatus.DEGRADED:
                        report['summary']['degraded'] += 1
                    elif status == ServiceStatus.RECOVERING:
                        report['summary']['recovering'] += 1
                    else:
                        report['summary']['unknown'] += 1
                
                return report
                
        except Exception as e:
            logger.error(f"获取健康报告失败: {e}")
            return {}
    
    def _emit_health_report(self):
        """发射健康报告信号"""
        try:
            report = self.get_health_report()
            if report:
                self.health_report_updated.emit(report)
        except Exception as e:
            logger.error(f"发射健康报告信号失败: {e}")
    
    def force_check(self, service_name: str = None) -> bool:
        """强制检查服务健康状态"""
        try:
            if service_name:
                if service_name in self._services:
                    self._check_service_health(service_name)
                    return True
                else:
                    logger.warning(f"服务不存在: {service_name}")
                    return False
            else:
                # 检查所有服务
                for name in self._services:
                    self._check_service_health(name)
                return True
                
        except Exception as e:
            logger.error(f"强制检查失败: {e}")
            return False
    
    def is_running(self) -> bool:
        """检查监控器是否在运行"""
        return self._running

# 全局健康监控器实例
health_monitor = ServiceHealthMonitor()
