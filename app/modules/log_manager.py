"""
日志管理模块
统一日志处理、存储和信号发射功能
"""

import logging
import threading
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import deque
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from .base_interfaces import (
    BaseService, ServiceStatus, HealthStatus, ServiceInfo, 
    HealthCheckResult, ILogManager
)

logger = logging.getLogger(__name__)


class LogLevel:
    """日志级别常量"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EnhancedMemoryLogHandler(logging.Handler):
    """增强的内存日志处理器"""
    
    def __init__(self, capacity: int = 1000, log_manager=None):
        super().__init__()
        self.capacity = capacity
        self.log_manager = log_manager
        self.buffer = deque(maxlen=capacity)
        self.error_logs = deque(maxlen=100)  # 单独存储错误日志
        self.lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'total_logs': 0,
            'debug_logs': 0,
            'info_logs': 0,
            'warning_logs': 0,
            'error_logs': 0,
            'critical_logs': 0
        }
    
    def emit(self, record):
        try:
            with self.lock:
                # 格式化日志消息
                msg = self.format(record)
                timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                
                # 创建结构化日志条目
                log_entry = {
                    'timestamp': timestamp,
                    'level': record.levelname,
                    'message': msg,
                    'module': record.module,
                    'funcName': record.funcName,
                    'lineno': record.lineno,
                    'thread': record.thread,
                    'raw_record': record
                }
                
                # 添加到缓冲区
                self.buffer.append(log_entry)
                
                # 更新统计信息
                self.stats['total_logs'] += 1
                level_key = f"{record.levelname.lower()}_logs"
                if level_key in self.stats:
                    self.stats[level_key] += 1
                
                # 如果是错误日志，单独保存
                if record.levelno >= logging.ERROR:
                    self.error_logs.append(log_entry)
                
                # 通知日志管理器
                if self.log_manager:
                    self.log_manager._on_new_log(log_entry)
                    
        except Exception as e:
            self.handleError(record)
    
    def get_logs(self, level_filter=None, limit=None):
        """获取日志，支持级别过滤和数量限制"""
        with self.lock:
            logs = list(self.buffer)
            
            if level_filter:
                if isinstance(level_filter, str):
                    level_filter = [level_filter]
                logs = [log for log in logs if log['level'] in level_filter]
            
            if limit:
                logs = logs[-limit:]
            
            return logs
    
    def get_stats(self):
        """获取统计信息"""
        with self.lock:
            return self.stats.copy()
    
    def clear(self):
        """清空日志缓冲区"""
        with self.lock:
            self.buffer.clear()
            self.error_logs.clear()
            # 重置统计信息
            for key in self.stats:
                self.stats[key] = 0


class LogManager(BaseService, ILogManager):
    """日志管理器"""
    
    # 信号定义
    new_log = pyqtSignal(str, str)              # (message, level)
    log_cleared = pyqtSignal()                  # ()
    log_file_rotated = pyqtSignal(str)          # (new_file_path)
    stats_updated = pyqtSignal(dict)            # (stats)
    
    def __init__(self, log_dir: str = None, parent=None):
        super().__init__("log_manager", parent)
        
        # 日志目录
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            # 默认使用项目根目录下的data/Logs
            project_root = Path(__file__).parent.parent.parent
            self.log_dir = project_root / "data" / "Logs"
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存日志处理器
        self.memory_handler = EnhancedMemoryLogHandler(capacity=1000, log_manager=self)
        
        # 文件日志处理器
        self.file_handlers: Dict[str, logging.FileHandler] = {}
        
        # 配置
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.max_files = 10
        self.auto_rotate = True
        self.file_encoding = 'utf-8'
        
        # 过滤配置
        self.level_filter = None
        self.module_filter = None
        
        # 统计信息
        self._stats = {
            'total_logs': 0,
            'files_created': 0,
            'files_rotated': 0,
            'last_log_time': None
        }
        
        self._lock = threading.RLock()
        
        logger.info("日志管理器初始化完成")
    
    def start(self) -> bool:
        """启动服务"""
        try:
            self._update_status(ServiceStatus.STARTING)
            
            # 设置日志格式
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            self.memory_handler.setFormatter(formatter)
            
            # 添加到根日志记录器
            root_logger = logging.getLogger()
            if self.memory_handler not in root_logger.handlers:
                root_logger.addHandler(self.memory_handler)
            
            # 创建默认文件处理器
            self._create_file_handler('main')
            
            self._update_status(ServiceStatus.RUNNING)
            self._update_health(HealthStatus.HEALTHY)
            return True
            
        except Exception as e:
            logger.error(f"启动日志管理器失败: {e}")
            self._update_status(ServiceStatus.ERROR)
            self._update_health(HealthStatus.UNHEALTHY)
            return False
    
    def stop(self) -> bool:
        """停止服务"""
        try:
            self._update_status(ServiceStatus.STOPPING)
            
            # 从根日志记录器移除处理器
            root_logger = logging.getLogger()
            if self.memory_handler in root_logger.handlers:
                root_logger.removeHandler(self.memory_handler)
            
            # 关闭所有文件处理器
            for handler in self.file_handlers.values():
                handler.close()
            self.file_handlers.clear()
            
            self._update_status(ServiceStatus.STOPPED)
            self._update_health(HealthStatus.UNKNOWN)
            return True
            
        except Exception as e:
            logger.error(f"停止日志管理器失败: {e}")
            return False
    
    def restart(self) -> bool:
        """重启服务"""
        if self.stop():
            time.sleep(1)
            return self.start()
        return False
    
    def get_info(self) -> ServiceInfo:
        """获取服务信息"""
        memory_stats = self.memory_handler.get_stats()
        
        details = {
            'log_dir': str(self.log_dir),
            'memory_logs': len(self.memory_handler.buffer),
            'memory_capacity': self.memory_handler.capacity,
            'file_handlers': len(self.file_handlers),
            'auto_rotate': self.auto_rotate,
            'memory_stats': memory_stats,
            'manager_stats': self._stats.copy()
        }
        
        return ServiceInfo(
            name=self.service_name,
            status=self.status,
            health=self.health,
            message=f"内存日志: {len(self.memory_handler.buffer)}, 文件处理器: {len(self.file_handlers)}",
            details=details
        )
    
    def check_health(self) -> HealthCheckResult:
        """检查服务健康状态"""
        start_time = time.time()
        
        try:
            issues = []
            
            # 检查日志目录
            if not self.log_dir.exists():
                issues.append("日志目录不存在")
            elif not os.access(self.log_dir, os.W_OK):
                issues.append("日志目录不可写")
            
            # 检查内存处理器
            if not self.memory_handler:
                issues.append("内存日志处理器不可用")
            
            # 检查文件处理器
            active_file_handlers = 0
            for name, handler in self.file_handlers.items():
                try:
                    # 尝试写入测试日志
                    test_record = logging.LogRecord(
                        name="test", level=logging.INFO, pathname="", lineno=0,
                        msg="health check", args=(), exc_info=None
                    )
                    handler.handle(test_record)
                    active_file_handlers += 1
                except Exception as e:
                    issues.append(f"文件处理器 {name} 异常: {str(e)}")
            
            # 检查日志文件大小
            large_files = []
            for log_file in self.log_dir.glob("*.log"):
                if log_file.stat().st_size > self.max_file_size:
                    large_files.append(log_file.name)
            
            if large_files and self.auto_rotate:
                issues.append(f"{len(large_files)}个日志文件需要轮转")
            
            # 检查错误率
            memory_stats = self.memory_handler.get_stats()
            total_logs = memory_stats.get('total_logs', 0)
            error_logs = memory_stats.get('error_logs', 0)
            
            error_rate = 0
            if total_logs > 0:
                error_rate = (error_logs / total_logs) * 100
            
            if error_rate > 20:  # 错误率超过20%
                issues.append(f"错误日志比例过高: {error_rate:.1f}%")
            
            # 判断健康状态
            if not self.log_dir.exists() or not self.memory_handler:
                status = HealthStatus.UNHEALTHY
                message = "日志系统不可用"
            elif issues:
                status = HealthStatus.DEGRADED
                message = "; ".join(issues)
            else:
                status = HealthStatus.HEALTHY
                message = "日志系统运行正常"
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    'log_dir_exists': self.log_dir.exists(),
                    'log_dir_writable': os.access(self.log_dir, os.W_OK) if self.log_dir.exists() else False,
                    'memory_handler_active': bool(self.memory_handler),
                    'active_file_handlers': active_file_handlers,
                    'large_files': large_files,
                    'error_rate': error_rate,
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
    
    # ILogManager接口实现
    
    def get_logs(self, level_filter: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取日志"""
        try:
            return self.memory_handler.get_logs(level_filter, limit)
        except Exception as e:
            logger.error(f"获取日志失败: {e}")
            return []
    
    def clear_logs(self) -> bool:
        """清空日志"""
        try:
            self.memory_handler.clear()
            self.log_cleared.emit()
            logger.info("日志已清空")
            return True
        except Exception as e:
            logger.error(f"清空日志失败: {e}")
            return False

    # 扩展方法

    def get_error_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取错误日志"""
        try:
            with self.memory_handler.lock:
                error_logs = list(self.memory_handler.error_logs)
                if limit:
                    error_logs = error_logs[-limit:]
                return error_logs
        except Exception as e:
            logger.error(f"获取错误日志失败: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        memory_stats = self.memory_handler.get_stats()
        return {
            'memory_stats': memory_stats,
            'manager_stats': self._stats.copy(),
            'file_handlers': len(self.file_handlers),
            'log_dir': str(self.log_dir)
        }

    def set_level_filter(self, levels: Optional[List[str]]):
        """设置日志级别过滤"""
        self.level_filter = levels
        logger.info(f"日志级别过滤已设置: {levels}")

    def set_module_filter(self, modules: Optional[List[str]]):
        """设置模块过滤"""
        self.module_filter = modules
        logger.info(f"模块过滤已设置: {modules}")

    def create_file_handler(self, name: str, filename: str = None) -> bool:
        """创建文件处理器"""
        try:
            return self._create_file_handler(name, filename)
        except Exception as e:
            logger.error(f"创建文件处理器失败: {e}")
            return False

    def remove_file_handler(self, name: str) -> bool:
        """移除文件处理器"""
        try:
            if name in self.file_handlers:
                handler = self.file_handlers[name]
                handler.close()

                # 从根日志记录器移除
                root_logger = logging.getLogger()
                if handler in root_logger.handlers:
                    root_logger.removeHandler(handler)

                del self.file_handlers[name]
                logger.info(f"文件处理器已移除: {name}")
                return True
            else:
                logger.warning(f"文件处理器不存在: {name}")
                return False
        except Exception as e:
            logger.error(f"移除文件处理器失败: {e}")
            return False

    def rotate_log_file(self, name: str) -> bool:
        """轮转日志文件"""
        try:
            if name not in self.file_handlers:
                logger.warning(f"文件处理器不存在: {name}")
                return False

            handler = self.file_handlers[name]
            old_file = handler.baseFilename

            # 关闭当前处理器
            handler.close()

            # 重命名文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"{old_file}.{timestamp}"
            os.rename(old_file, backup_file)

            # 创建新的处理器
            new_handler = logging.FileHandler(old_file, encoding=self.file_encoding)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            new_handler.setFormatter(formatter)

            # 替换处理器
            root_logger = logging.getLogger()
            root_logger.removeHandler(handler)
            root_logger.addHandler(new_handler)

            self.file_handlers[name] = new_handler
            self._stats['files_rotated'] += 1

            logger.info(f"日志文件已轮转: {old_file} -> {backup_file}")
            self.log_file_rotated.emit(old_file)

            # 清理旧文件
            self._cleanup_old_files(name)

            return True

        except Exception as e:
            logger.error(f"轮转日志文件失败: {e}")
            return False

    def export_logs(self, file_path: str, level_filter: Optional[str] = None,
                   start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> bool:
        """导出日志到文件"""
        try:
            logs = self.get_logs(level_filter)

            # 时间过滤
            if start_time or end_time:
                filtered_logs = []
                for log in logs:
                    log_time = datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S.%f')
                    if start_time and log_time < start_time:
                        continue
                    if end_time and log_time > end_time:
                        continue
                    filtered_logs.append(log)
                logs = filtered_logs

            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                for log in logs:
                    f.write(f"[{log['timestamp']}] {log['level']} - {log['message']}\n")

            logger.info(f"日志已导出到: {file_path}, 共 {len(logs)} 条")
            return True

        except Exception as e:
            logger.error(f"导出日志失败: {e}")
            return False

    # 私有方法

    def _on_new_log(self, log_entry: Dict[str, Any]):
        """处理新日志"""
        try:
            # 更新统计
            self._stats['total_logs'] += 1
            self._stats['last_log_time'] = log_entry['timestamp']

            # 发出新日志信号
            self.new_log.emit(log_entry['message'], log_entry['level'])

            # 定期发出统计更新信号
            if self._stats['total_logs'] % 100 == 0:
                self.stats_updated.emit(self.get_stats())

            # 检查是否需要轮转文件
            if self.auto_rotate:
                self._check_file_rotation()

        except Exception as e:
            logger.error(f"处理新日志失败: {e}")

    def _create_file_handler(self, name: str, filename: str = None) -> bool:
        """创建文件处理器"""
        try:
            if not filename:
                filename = f"{name}_{datetime.now().strftime('%Y%m%d')}.log"

            file_path = self.log_dir / filename

            # 创建文件处理器
            handler = logging.FileHandler(str(file_path), encoding=self.file_encoding)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)

            # 添加到根日志记录器
            root_logger = logging.getLogger()
            root_logger.addHandler(handler)

            # 保存处理器
            self.file_handlers[name] = handler
            self._stats['files_created'] += 1

            logger.info(f"文件处理器已创建: {name} -> {file_path}")
            return True

        except Exception as e:
            logger.error(f"创建文件处理器失败: {e}")
            return False

    def _check_file_rotation(self):
        """检查文件轮转"""
        try:
            for name, handler in self.file_handlers.items():
                file_path = Path(handler.baseFilename)
                if file_path.exists() and file_path.stat().st_size > self.max_file_size:
                    logger.info(f"文件大小超限，开始轮转: {file_path}")
                    self.rotate_log_file(name)
        except Exception as e:
            logger.error(f"检查文件轮转失败: {e}")

    def _cleanup_old_files(self, name: str):
        """清理旧文件"""
        try:
            if name not in self.file_handlers:
                return

            handler = self.file_handlers[name]
            base_file = Path(handler.baseFilename)

            # 查找相关的备份文件
            pattern = f"{base_file.name}.*"
            backup_files = list(self.log_dir.glob(pattern))

            # 按修改时间排序
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # 删除超出数量限制的文件
            if len(backup_files) > self.max_files:
                for old_file in backup_files[self.max_files:]:
                    try:
                        old_file.unlink()
                        logger.debug(f"删除旧日志文件: {old_file}")
                    except Exception as e:
                        logger.warning(f"删除旧日志文件失败 {old_file}: {e}")

        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")
