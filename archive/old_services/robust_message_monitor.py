#!/usr/bin/env python3
"""
健壮的消息监听器基类
提供稳定的消息监听服务，包括连接检测、异常恢复、状态验证等功能
"""

import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from abc import ABCMeta, abstractmethod
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

# 解决元类冲突的问题
class QObjectMeta(type(QObject), ABCMeta):
    pass

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class MonitorStatus:
    """监控状态常量"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    RECOVERING = "recovering"

class RobustMessageMonitor(QObject, metaclass=QObjectMeta):
    """健壮的消息监听器基类"""
    
    # 信号定义
    message_received = pyqtSignal(str, str, str)  # chat_name, content, sender_name
    status_changed = pyqtSignal(str)  # status
    error_occurred = pyqtSignal(str)  # error_message
    connection_lost = pyqtSignal(str)  # reason
    connection_restored = pyqtSignal()
    
    def __init__(self, check_interval: int = 5, max_retry_attempts: int = 3):
        super().__init__()
        
        # 基本配置
        self.check_interval = check_interval
        self.max_retry_attempts = max_retry_attempts
        
        # 状态管理
        self.status = MonitorStatus.STOPPED
        self.monitored_chats: List[str] = []
        self.is_running = False
        
        # 连接状态
        self.wx_instance = None
        self.connection_healthy = False
        self.last_successful_check = datetime.now()
        self.consecutive_failures = 0
        
        # 线程管理
        self.monitor_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        self.thread_lock = threading.RLock()
        
        # 健康检查
        self.health_check_timer = QTimer()
        self.health_check_timer.timeout.connect(self._perform_health_check)
        self.health_check_interval = 30  # 30秒进行一次健康检查
        
        # 统计信息
        self.stats = {
            'total_messages': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'recovery_attempts': 0,
            'last_message_time': None,
            'uptime_start': None
        }
        
        # 错误处理
        self.error_handlers: List[Callable] = []
        self.recovery_handlers: List[Callable] = []
        
    def add_error_handler(self, handler: Callable[[str], None]):
        """添加错误处理器"""
        self.error_handlers.append(handler)
    
    def add_recovery_handler(self, handler: Callable[[], bool]):
        """添加恢复处理器"""
        self.recovery_handlers.append(handler)
    
    def start_monitoring(self, chat_targets: List[str]) -> bool:
        """开始监控"""
        try:
            if self.is_running:
                logger.warning("监控器已在运行")
                return True
            
            logger.info(f"开始启动监控器，目标聊天: {chat_targets}")
            self._update_status(MonitorStatus.STARTING)
            
            # 初始化微信连接
            if not self._initialize_wechat():
                self._update_status(MonitorStatus.ERROR)
                return False
            
            # 设置监控目标
            self.monitored_chats = chat_targets.copy()
            
            # 启动监控线程
            success = self._start_monitor_threads()
            
            if success:
                self.is_running = True
                self.stats['uptime_start'] = datetime.now()
                self._update_status(MonitorStatus.RUNNING)
                
                # 启动健康检查
                self.health_check_timer.start(self.health_check_interval * 1000)
                
                logger.info("监控器启动成功")
                return True
            else:
                self._update_status(MonitorStatus.ERROR)
                return False
                
        except Exception as e:
            logger.error(f"启动监控器失败: {e}")
            self._update_status(MonitorStatus.ERROR)
            return False
    
    def stop_monitoring(self) -> bool:
        """停止监控"""
        try:
            if not self.is_running:
                return True
            
            logger.info("开始停止监控器")
            self.is_running = False
            
            # 停止健康检查
            self.health_check_timer.stop()
            
            # 停止所有监控线程
            self._stop_monitor_threads()
            
            # 清理资源
            self._cleanup_resources()
            
            self._update_status(MonitorStatus.STOPPED)
            logger.info("监控器已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止监控器失败: {e}")
            return False
    
    def pause_monitoring(self) -> bool:
        """暂停监控"""
        try:
            if self.status != MonitorStatus.RUNNING:
                return False
            
            self._update_status(MonitorStatus.PAUSED)
            logger.info("监控器已暂停")
            return True
            
        except Exception as e:
            logger.error(f"暂停监控器失败: {e}")
            return False
    
    def resume_monitoring(self) -> bool:
        """恢复监控"""
        try:
            if self.status != MonitorStatus.PAUSED:
                return False
            
            self._update_status(MonitorStatus.RUNNING)
            logger.info("监控器已恢复")
            return True
            
        except Exception as e:
            logger.error(f"恢复监控器失败: {e}")
            return False
    
    @abstractmethod
    def _initialize_wechat(self) -> bool:
        """初始化微信连接（子类实现）"""
        pass
    
    @abstractmethod
    def _check_wechat_connection(self) -> bool:
        """检查微信连接状态（子类实现）"""
        pass
    
    @abstractmethod
    def _get_messages_for_chat(self, chat_name: str) -> List[Dict[str, Any]]:
        """获取指定聊天的消息（子类实现）"""
        pass
    
    def _start_monitor_threads(self) -> bool:
        """启动监控线程"""
        try:
            with self.thread_lock:
                for chat_name in self.monitored_chats:
                    if chat_name not in self.monitor_threads:
                        stop_event = threading.Event()
                        self.stop_events[chat_name] = stop_event
                        
                        thread = threading.Thread(
                            target=self._monitor_chat_loop,
                            args=(chat_name, stop_event),
                            name=f"Monitor-{chat_name}",
                            daemon=True
                        )
                        
                        self.monitor_threads[chat_name] = thread
                        thread.start()
                        
                        logger.info(f"启动监控线程: {chat_name}")
                
                return True
                
        except Exception as e:
            logger.error(f"启动监控线程失败: {e}")
            return False
    
    def _stop_monitor_threads(self):
        """停止监控线程"""
        try:
            with self.thread_lock:
                # 设置停止事件
                for stop_event in self.stop_events.values():
                    stop_event.set()
                
                # 等待线程结束
                for chat_name, thread in self.monitor_threads.items():
                    if thread.is_alive():
                        thread.join(timeout=5)
                        if thread.is_alive():
                            logger.warning(f"监控线程 {chat_name} 未能正常结束")
                
                # 清理
                self.monitor_threads.clear()
                self.stop_events.clear()
                
        except Exception as e:
            logger.error(f"停止监控线程失败: {e}")
    
    def _monitor_chat_loop(self, chat_name: str, stop_event: threading.Event):
        """监控聊天循环"""
        logger.info(f"开始监控聊天: {chat_name}")
        retry_count = 0
        
        while not stop_event.is_set() and self.is_running:
            try:
                # 检查状态
                if self.status == MonitorStatus.PAUSED:
                    stop_event.wait(1)
                    continue
                
                # 检查连接
                if not self._check_wechat_connection():
                    logger.warning(f"微信连接异常，尝试恢复...")
                    if not self._attempt_recovery():
                        stop_event.wait(self.check_interval)
                        continue
                
                # 获取消息
                messages = self._get_messages_for_chat(chat_name)
                
                if messages:
                    for message in messages:
                        if stop_event.is_set():
                            break
                        
                        self._process_message(chat_name, message)
                
                # 更新统计
                self.stats['successful_checks'] += 1
                self.consecutive_failures = 0
                retry_count = 0
                
                # 等待下次检查
                stop_event.wait(self.check_interval)
                
            except Exception as e:
                retry_count += 1
                self.consecutive_failures += 1
                self.stats['failed_checks'] += 1
                
                logger.error(f"监控聊天 {chat_name} 异常 (重试 {retry_count}/{self.max_retry_attempts}): {e}")
                
                # 触发错误处理
                self._handle_error(f"监控聊天 {chat_name} 异常: {e}")
                
                if retry_count >= self.max_retry_attempts:
                    logger.error(f"监控聊天 {chat_name} 达到最大重试次数，停止监控")
                    break
                
                # 等待后重试
                stop_event.wait(min(self.check_interval * retry_count, 30))
        
        logger.info(f"监控聊天循环结束: {chat_name}")
    
    def _process_message(self, chat_name: str, message: Dict[str, Any]):
        """处理消息"""
        try:
            # 提取消息信息
            content = message.get('content', '')
            sender = message.get('sender', '')
            
            if content and sender:
                self.stats['total_messages'] += 1
                self.stats['last_message_time'] = datetime.now()
                
                # 发射消息信号
                self.message_received.emit(chat_name, content, sender)
                
                logger.debug(f"处理消息: {chat_name} - {sender}: {content[:50]}...")
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
    
    def _perform_health_check(self):
        """执行健康检查"""
        try:
            if not self.is_running:
                return
            
            # 检查连接状态
            connection_ok = self._check_wechat_connection()
            
            if connection_ok:
                if not self.connection_healthy:
                    self.connection_healthy = True
                    self.connection_restored.emit()
                    logger.info("微信连接已恢复")
                
                self.last_successful_check = datetime.now()
            else:
                if self.connection_healthy:
                    self.connection_healthy = False
                    self.connection_lost.emit("健康检查失败")
                    logger.warning("微信连接丢失")
                
                # 尝试恢复
                self._attempt_recovery()
            
            # 检查线程状态
            self._check_thread_health()
            
        except Exception as e:
            logger.error(f"健康检查异常: {e}")
    
    def _check_thread_health(self):
        """检查线程健康状态"""
        try:
            with self.thread_lock:
                for chat_name, thread in list(self.monitor_threads.items()):
                    if not thread.is_alive():
                        logger.warning(f"监控线程 {chat_name} 已停止，尝试重启")
                        
                        # 清理旧线程
                        if chat_name in self.stop_events:
                            del self.stop_events[chat_name]
                        del self.monitor_threads[chat_name]
                        
                        # 重启线程
                        if chat_name in self.monitored_chats:
                            stop_event = threading.Event()
                            self.stop_events[chat_name] = stop_event
                            
                            new_thread = threading.Thread(
                                target=self._monitor_chat_loop,
                                args=(chat_name, stop_event),
                                name=f"Monitor-{chat_name}",
                                daemon=True
                            )
                            
                            self.monitor_threads[chat_name] = new_thread
                            new_thread.start()
                            
                            logger.info(f"重启监控线程: {chat_name}")
            
        except Exception as e:
            logger.error(f"检查线程健康状态失败: {e}")
    
    def _attempt_recovery(self) -> bool:
        """尝试恢复"""
        try:
            if self.status == MonitorStatus.RECOVERING:
                return False
            
            self._update_status(MonitorStatus.RECOVERING)
            self.stats['recovery_attempts'] += 1
            
            logger.info("开始尝试恢复监控器")
            
            # 执行恢复处理器
            for handler in self.recovery_handlers:
                try:
                    if handler():
                        logger.info("恢复处理器执行成功")
                        self._update_status(MonitorStatus.RUNNING)
                        return True
                except Exception as e:
                    logger.error(f"恢复处理器执行失败: {e}")
            
            # 尝试重新初始化微信
            if self._initialize_wechat():
                logger.info("微信重新初始化成功")
                self._update_status(MonitorStatus.RUNNING)
                return True
            
            logger.error("恢复尝试失败")
            self._update_status(MonitorStatus.ERROR)
            return False
            
        except Exception as e:
            logger.error(f"恢复尝试异常: {e}")
            self._update_status(MonitorStatus.ERROR)
            return False
    
    def _handle_error(self, error_message: str):
        """处理错误"""
        try:
            # 发射错误信号
            self.error_occurred.emit(error_message)
            
            # 执行错误处理器
            for handler in self.error_handlers:
                try:
                    handler(error_message)
                except Exception as e:
                    logger.error(f"错误处理器执行失败: {e}")
            
        except Exception as e:
            logger.error(f"处理错误失败: {e}")
    
    def _update_status(self, new_status: str):
        """更新状态"""
        if self.status != new_status:
            old_status = self.status
            self.status = new_status
            self.status_changed.emit(new_status)
            logger.info(f"监控器状态变更: {old_status} -> {new_status}")
    
    def _cleanup_resources(self):
        """清理资源"""
        try:
            # 清理微信实例
            self.wx_instance = None
            self.connection_healthy = False
            
            # 重置统计
            if self.stats['uptime_start']:
                uptime = datetime.now() - self.stats['uptime_start']
                logger.info(f"监控器运行时间: {uptime}")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
    
    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            'status': self.status,
            'is_running': self.is_running,
            'connection_healthy': self.connection_healthy,
            'monitored_chats': self.monitored_chats.copy(),
            'consecutive_failures': self.consecutive_failures,
            'last_successful_check': self.last_successful_check.isoformat(),
            'stats': self.stats.copy(),
            'active_threads': len(self.monitor_threads)
        }
