"""
服务监控及自动修复模块
整合健康检查、服务监控和自动恢复功能
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal

from .base_interfaces import (
    BaseService, ServiceStatus, HealthStatus, ServiceInfo, 
    HealthCheckResult, IServiceMonitor
)

logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    """服务配置"""
    name: str
    health_checker: Callable[[], HealthCheckResult]
    recovery_handler: Optional[Callable[[], bool]] = None
    check_interval: int = 30  # 检查间隔（秒）
    max_failures: int = 3     # 最大失败次数
    auto_recovery: bool = True
    recovery_cooldown: int = 300  # 恢复冷却时间（秒）


@dataclass
class ServiceRecord:
    """服务记录"""
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    failure_count: int = 0
    recovery_count: int = 0
    last_recovery_time: Optional[datetime] = None
    total_checks: int = 0
    total_failures: int = 0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_checks == 0:
            return 0.0
        return ((self.total_checks - self.total_failures) / self.total_checks) * 100
    
    def is_in_recovery_cooldown(self, cooldown_seconds: int = 300) -> bool:
        """是否在恢复冷却期"""
        if not self.last_recovery_time:
            return False
        return datetime.now() - self.last_recovery_time < timedelta(seconds=cooldown_seconds)


class ServiceMonitor(BaseService, IServiceMonitor):
    """服务监控器"""
    
    # 信号定义
    service_registered = pyqtSignal(str)                    # (service_name)
    service_unregistered = pyqtSignal(str)                  # (service_name)
    service_status_changed = pyqtSignal(str, str, str)      # (service_name, old_status, new_status)
    service_failed = pyqtSignal(str, str)                   # (service_name, error_message)
    service_recovered = pyqtSignal(str)                     # (service_name)
    recovery_attempted = pyqtSignal(str, bool)              # (service_name, success)
    monitoring_started = pyqtSignal(list)                   # (service_names)
    monitoring_stopped = pyqtSignal()                       # ()
    
    def __init__(self, parent=None):
        super().__init__("service_monitor", parent)
        
        self._lock = threading.RLock()
        
        # 服务配置和记录
        self._services: Dict[str, ServiceConfig] = {}
        self._service_records: Dict[str, ServiceRecord] = {}
        
        # 监控线程
        self._monitor_thread = None
        self._stop_monitoring = threading.Event()
        self._is_monitoring = False
        
        # 全局配置
        self._global_check_interval = 30  # 全局检查间隔
        self._max_concurrent_recoveries = 2  # 最大并发恢复数
        self._current_recoveries = 0
        
        # 统计信息
        self._stats = {
            'total_checks': 0,
            'total_failures': 0,
            'total_recoveries': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'monitoring_uptime': 0,
            'start_time': None
        }
        
        logger.info("服务监控器初始化完成")
    
    def start(self) -> bool:
        """启动服务"""
        try:
            self._update_status(ServiceStatus.STARTING)
            
            # 初始化所有服务记录
            for service_name in self._services:
                if service_name not in self._service_records:
                    self._service_records[service_name] = ServiceRecord(name=service_name)
            
            self._update_status(ServiceStatus.RUNNING)
            self._update_health(HealthStatus.HEALTHY)
            return True
            
        except Exception as e:
            logger.error(f"启动服务监控器失败: {e}")
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
            
            self._update_status(ServiceStatus.STOPPED)
            self._update_health(HealthStatus.UNKNOWN)
            return True
            
        except Exception as e:
            logger.error(f"停止服务监控器失败: {e}")
            return False
    
    def restart(self) -> bool:
        """重启服务"""
        if self.stop():
            time.sleep(1)
            return self.start()
        return False
    
    def get_info(self) -> ServiceInfo:
        """获取服务信息"""
        uptime = 0
        if self._stats['start_time']:
            uptime = (datetime.now() - self._stats['start_time']).total_seconds()
        
        details = {
            'registered_services': len(self._services),
            'is_monitoring': self._is_monitoring,
            'current_recoveries': self._current_recoveries,
            'max_concurrent_recoveries': self._max_concurrent_recoveries,
            'monitoring_uptime': uptime,
            'stats': self._stats.copy(),
            'service_status': {
                name: record.status.value 
                for name, record in self._service_records.items()
            }
        }
        
        return ServiceInfo(
            name=self.service_name,
            status=self.status,
            health=self.health,
            message=f"监控{'运行中' if self._is_monitoring else '已停止'}，{len(self._services)}个服务",
            details=details
        )
    
    def check_health(self) -> HealthCheckResult:
        """检查服务健康状态"""
        start_time = time.time()
        
        try:
            issues = []
            
            # 检查监控状态
            if self._is_monitoring:
                if not self._monitor_thread or not self._monitor_thread.is_alive():
                    issues.append("监控线程未运行")
            
            # 检查服务状态
            unhealthy_services = []
            degraded_services = []
            
            for name, record in self._service_records.items():
                if record.status == HealthStatus.UNHEALTHY:
                    unhealthy_services.append(name)
                elif record.status == HealthStatus.DEGRADED:
                    degraded_services.append(name)
            
            if unhealthy_services:
                issues.append(f"{len(unhealthy_services)}个服务不健康: {', '.join(unhealthy_services)}")
            
            if degraded_services:
                issues.append(f"{len(degraded_services)}个服务降级: {', '.join(degraded_services)}")
            
            # 检查恢复状态
            if self._current_recoveries >= self._max_concurrent_recoveries:
                issues.append("恢复操作已达上限")
            
            # 检查成功率
            total_checks = self._stats['total_checks']
            total_failures = self._stats['total_failures']
            
            if total_checks > 0:
                failure_rate = (total_failures / total_checks) * 100
                if failure_rate > 30:  # 失败率超过30%
                    issues.append(f"整体失败率过高: {failure_rate:.1f}%")
            
            # 判断健康状态
            if unhealthy_services:
                status = HealthStatus.UNHEALTHY
                message = f"{len(unhealthy_services)}个服务不健康"
            elif issues:
                status = HealthStatus.DEGRADED
                message = "; ".join(issues)
            else:
                status = HealthStatus.HEALTHY
                message = "服务监控运行正常"
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    'is_monitoring': self._is_monitoring,
                    'unhealthy_services': unhealthy_services,
                    'degraded_services': degraded_services,
                    'current_recoveries': self._current_recoveries,
                    'failure_rate': (total_failures / total_checks * 100) if total_checks > 0 else 0,
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
    
    # IServiceMonitor接口实现
    
    def register_service(self, service_name: str, health_checker: Callable, recovery_handler: Callable = None) -> bool:
        """注册服务"""
        try:
            with self._lock:
                config = ServiceConfig(
                    name=service_name,
                    health_checker=health_checker,
                    recovery_handler=recovery_handler
                )
                
                self._services[service_name] = config
                
                # 创建服务记录
                if service_name not in self._service_records:
                    self._service_records[service_name] = ServiceRecord(name=service_name)
                
                logger.info(f"服务已注册: {service_name}")
                self.service_registered.emit(service_name)
                return True
                
        except Exception as e:
            logger.error(f"注册服务失败: {e}")
            return False
    
    def start_monitoring(self) -> bool:
        """开始监控"""
        try:
            with self._lock:
                if self._is_monitoring:
                    logger.warning("监控已在运行")
                    return True
                
                if not self._services:
                    logger.warning("无注册服务")
                    return False
                
                # 启动监控线程
                self._stop_monitoring.clear()
                self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
                self._monitor_thread.start()
                
                self._is_monitoring = True
                self._stats['start_time'] = datetime.now()
                
                service_names = list(self._services.keys())
                logger.info(f"开始监控 {len(service_names)} 个服务")
                self.monitoring_started.emit(service_names)
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
                
                # 停止监控线程
                self._stop_monitoring.set()
                if self._monitor_thread and self._monitor_thread.is_alive():
                    self._monitor_thread.join(timeout=5)
                
                self._is_monitoring = False
                
                # 更新运行时间
                if self._stats['start_time']:
                    uptime = (datetime.now() - self._stats['start_time']).total_seconds()
                    self._stats['monitoring_uptime'] += uptime
                    self._stats['start_time'] = None
                
                logger.info("停止监控")
                self.monitoring_stopped.emit()
                return True
                
        except Exception as e:
            logger.error(f"停止监控失败: {e}")
            return False

    # 扩展方法

    def unregister_service(self, service_name: str) -> bool:
        """注销服务"""
        try:
            with self._lock:
                if service_name in self._services:
                    del self._services[service_name]
                    logger.info(f"服务已注销: {service_name}")
                    self.service_unregistered.emit(service_name)
                    return True
                else:
                    logger.warning(f"服务未注册: {service_name}")
                    return False
        except Exception as e:
            logger.error(f"注销服务失败: {e}")
            return False

    def get_service_status(self, service_name: str) -> Optional[HealthStatus]:
        """获取服务状态"""
        with self._lock:
            if service_name in self._service_records:
                return self._service_records[service_name].status
            return None

    def get_service_record(self, service_name: str) -> Optional[Dict[str, Any]]:
        """获取服务记录"""
        with self._lock:
            if service_name in self._service_records:
                record = self._service_records[service_name]
                return {
                    'name': record.name,
                    'status': record.status.value,
                    'last_check_time': record.last_check_time.isoformat() if record.last_check_time else None,
                    'last_success_time': record.last_success_time.isoformat() if record.last_success_time else None,
                    'failure_count': record.failure_count,
                    'recovery_count': record.recovery_count,
                    'last_recovery_time': record.last_recovery_time.isoformat() if record.last_recovery_time else None,
                    'total_checks': record.total_checks,
                    'total_failures': record.total_failures,
                    'success_rate': record.success_rate,
                    'is_in_recovery_cooldown': record.is_in_recovery_cooldown()
                }
            return None

    def get_all_service_records(self) -> Dict[str, Dict[str, Any]]:
        """获取所有服务记录"""
        with self._lock:
            result = {}
            for service_name in self._service_records:
                result[service_name] = self.get_service_record(service_name)
            return result

    def force_check_service(self, service_name: str) -> Optional[HealthCheckResult]:
        """强制检查服务"""
        try:
            if service_name not in self._services:
                logger.warning(f"服务未注册: {service_name}")
                return None

            config = self._services[service_name]
            result = self._check_service_health(service_name, config)

            logger.info(f"强制检查服务 {service_name}: {result.status.value}")
            return result

        except Exception as e:
            logger.error(f"强制检查服务失败: {e}")
            return None

    def force_recover_service(self, service_name: str) -> bool:
        """强制恢复服务"""
        try:
            if service_name not in self._services:
                logger.warning(f"服务未注册: {service_name}")
                return False

            config = self._services[service_name]
            if not config.recovery_handler:
                logger.warning(f"服务无恢复处理器: {service_name}")
                return False

            success = self._attempt_recovery(service_name, config)
            logger.info(f"强制恢复服务 {service_name}: {'成功' if success else '失败'}")
            return success

        except Exception as e:
            logger.error(f"强制恢复服务失败: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            stats = self._stats.copy()

            # 计算当前运行时间
            if self._stats['start_time']:
                current_uptime = (datetime.now() - self._stats['start_time']).total_seconds()
                stats['current_uptime'] = current_uptime
                stats['total_uptime'] = self._stats['monitoring_uptime'] + current_uptime
            else:
                stats['current_uptime'] = 0
                stats['total_uptime'] = self._stats['monitoring_uptime']

            return stats

    def reset_service_stats(self, service_name: str) -> bool:
        """重置服务统计"""
        try:
            with self._lock:
                if service_name in self._service_records:
                    record = self._service_records[service_name]
                    record.failure_count = 0
                    record.recovery_count = 0
                    record.total_checks = 0
                    record.total_failures = 0
                    record.last_recovery_time = None

                    logger.info(f"服务统计已重置: {service_name}")
                    return True
                else:
                    logger.warning(f"服务记录不存在: {service_name}")
                    return False
        except Exception as e:
            logger.error(f"重置服务统计失败: {e}")
            return False

    # 私有方法

    def _monitor_loop(self):
        """监控循环"""
        logger.info("服务监控循环开始")

        while not self._stop_monitoring.is_set():
            try:
                current_time = datetime.now()

                # 检查所有服务
                with self._lock:
                    services_to_check = list(self._services.items())

                for service_name, config in services_to_check:
                    if self._stop_monitoring.is_set():
                        break

                    try:
                        # 检查是否需要进行健康检查
                        record = self._service_records.get(service_name)
                        if record and record.last_check_time:
                            time_since_last_check = (current_time - record.last_check_time).total_seconds()
                            if time_since_last_check < config.check_interval:
                                continue

                        # 执行健康检查
                        self._check_service_health(service_name, config)

                    except Exception as e:
                        logger.error(f"检查服务健康状态失败 {service_name}: {e}")

                # 等待下次检查
                self._stop_monitoring.wait(min(self._global_check_interval,
                                             min(config.check_interval for config in self._services.values())
                                             if self._services else self._global_check_interval))

            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                self._stop_monitoring.wait(5)

        logger.info("服务监控循环结束")

    def _check_service_health(self, service_name: str, config: ServiceConfig) -> HealthCheckResult:
        """检查服务健康状态"""
        try:
            # 执行健康检查
            result = config.health_checker()

            # 更新统计
            self._stats['total_checks'] += 1

            # 获取服务记录
            record = self._service_records.get(service_name)
            if not record:
                record = ServiceRecord(name=service_name)
                self._service_records[service_name] = record

            # 更新记录
            old_status = record.status
            record.last_check_time = datetime.now()
            record.total_checks += 1

            if result.status == HealthStatus.HEALTHY:
                # 服务健康
                record.status = HealthStatus.HEALTHY
                record.last_success_time = datetime.now()
                record.failure_count = 0  # 重置失败计数

            elif result.status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]:
                # 服务不健康
                record.status = result.status
                record.total_failures += 1
                self._stats['total_failures'] += 1

                # 控制失败计数器上限，避免无限增长
                if record.failure_count < config.max_failures + 2:  # 允许超出2次用于观察
                    record.failure_count += 1

                # 根据失败类型和次数调整日志级别，减少噪音
                if "任务超时" in result.message and record.failure_count <= 2:
                    # 前两次任务超时使用INFO级别，减少日志噪音
                    logger.info(f"服务健康检查失败 {service_name} ({record.failure_count}/{config.max_failures}): {result.message}")
                elif record.failure_count > config.max_failures:
                    # 超过最大失败次数后，降低日志频率
                    if record.failure_count % 5 == 0:  # 每5次记录一次
                        logger.error(f"服务持续不健康 {service_name} (已失败{record.failure_count}次): {result.message}")
                elif record.failure_count >= config.max_failures - 1:
                    # 接近最大失败次数时使用ERROR级别
                    logger.error(f"服务健康检查失败 {service_name} ({record.failure_count}/{config.max_failures}): {result.message}")
                else:
                    # 其他情况使用WARNING级别
                    logger.warning(f"服务健康检查失败 {service_name} ({record.failure_count}/{config.max_failures}): {result.message}")

                # 检查是否需要触发恢复
                if (record.failure_count == config.max_failures and  # 只在达到最大失败次数时触发一次
                    config.auto_recovery and
                    config.recovery_handler and
                    not record.is_in_recovery_cooldown(config.recovery_cooldown) and
                    self._current_recoveries < self._max_concurrent_recoveries):

                    logger.info(f"触发服务恢复: {service_name} (失败次数达到{config.max_failures})")
                    # 异步执行恢复
                    recovery_thread = threading.Thread(
                        target=self._attempt_recovery,
                        args=(service_name, config),
                        daemon=True
                    )
                    recovery_thread.start()
                elif record.failure_count == config.max_failures and not config.recovery_handler:
                    logger.warning(f"服务 {service_name} 达到最大失败次数但无恢复处理器")
                elif record.failure_count == config.max_failures and record.is_in_recovery_cooldown(config.recovery_cooldown):
                    logger.info(f"服务 {service_name} 在恢复冷却期，跳过恢复")

            # 发出状态变化信号
            if old_status != record.status:
                self.service_status_changed.emit(service_name, old_status.value, record.status.value)

                if record.status == HealthStatus.UNHEALTHY:
                    self.service_failed.emit(service_name, result.message)

            return result

        except Exception as e:
            logger.error(f"检查服务健康状态异常 {service_name}: {e}")

            # 创建错误结果
            error_result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"健康检查异常: {str(e)}",
                details={'exception': str(e)}
            )

            return error_result

    def _attempt_recovery(self, service_name: str, config: ServiceConfig) -> bool:
        """尝试恢复服务"""
        try:
            with self._lock:
                self._current_recoveries += 1

            logger.info(f"开始尝试恢复服务: {service_name}")
            self._stats['total_recoveries'] += 1

            # 获取服务记录
            record = self._service_records.get(service_name)
            if record:
                record.recovery_count += 1
                record.last_recovery_time = datetime.now()

            # 执行恢复处理器
            success = config.recovery_handler()

            if success:
                self._stats['successful_recoveries'] += 1
                logger.info(f"服务恢复成功: {service_name}")
                self.service_recovered.emit(service_name)

                # 重置失败计数
                if record:
                    record.failure_count = 0

            else:
                self._stats['failed_recoveries'] += 1
                logger.error(f"服务恢复失败: {service_name}")

            self.recovery_attempted.emit(service_name, success)
            return success

        except Exception as e:
            self._stats['failed_recoveries'] += 1
            logger.error(f"服务恢复异常 {service_name}: {e}")
            self.recovery_attempted.emit(service_name, False)
            return False

        finally:
            with self._lock:
                self._current_recoveries = max(0, self._current_recoveries - 1)
