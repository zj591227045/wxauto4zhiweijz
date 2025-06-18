#!/usr/bin/env python3
"""
健壮的消息投递服务
确保微信回复的可靠性，包括重试机制和错误处理
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from queue import Queue, Empty
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class DeliveryStatus(Enum):
    """投递状态枚举"""
    PENDING = "pending"
    SENDING = "sending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"

@dataclass
class DeliveryTask:
    """投递任务"""
    chat_name: str
    message: str
    max_retries: int = 3
    retry_count: int = 0
    status: DeliveryStatus = DeliveryStatus.PENDING
    created_time: float = None
    last_attempt_time: float = None
    error_message: str = ""
    
    def __post_init__(self):
        if self.created_time is None:
            self.created_time = time.time()

class RobustMessageDelivery(QObject):
    """健壮的消息投递服务"""
    
    # 信号定义
    message_sent = pyqtSignal(str, bool, str)  # chat_name, success, message
    delivery_failed = pyqtSignal(str, str, str)  # chat_name, message, error
    queue_status_changed = pyqtSignal(int)  # queue_size
    
    def __init__(self, max_workers: int = 2, retry_delay: float = 2.0):
        super().__init__()
        
        self.max_workers = max_workers
        self.retry_delay = retry_delay
        
        # 任务队列
        self.task_queue = Queue()
        self.failed_tasks = []
        
        # 工作线程
        self.workers = []
        self.is_running = False
        self.stop_event = threading.Event()
        
        # 微信实例
        self.wx_instance = None
        
        # 统计信息
        self.stats = {
            'total_tasks': 0,
            'successful_deliveries': 0,
            'failed_deliveries': 0,
            'retries': 0,
            'queue_size': 0
        }
        
        # 状态监控定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_queue_status)
        self.status_timer.start(1000)  # 每秒更新一次状态
    
    def set_wechat_instance(self, wx_instance):
        """设置微信实例"""
        self.wx_instance = wx_instance
        logger.info("微信实例已设置")
    
    def start_delivery_service(self) -> bool:
        """启动投递服务"""
        try:
            if self.is_running:
                logger.warning("投递服务已在运行")
                return True
            
            self.is_running = True
            self.stop_event.clear()
            
            # 启动工作线程
            for i in range(self.max_workers):
                worker = threading.Thread(
                    target=self._delivery_worker,
                    name=f"DeliveryWorker-{i}",
                    daemon=True
                )
                worker.start()
                self.workers.append(worker)
            
            logger.info(f"投递服务已启动，工作线程数: {self.max_workers}")
            return True
            
        except Exception as e:
            logger.error(f"启动投递服务失败: {e}")
            self.is_running = False
            return False
    
    def stop_delivery_service(self) -> bool:
        """停止投递服务"""
        try:
            if not self.is_running:
                return True
            
            logger.info("正在停止投递服务...")
            self.is_running = False
            self.stop_event.set()
            
            # 等待工作线程结束
            for worker in self.workers:
                if worker.is_alive():
                    worker.join(timeout=5)
            
            self.workers.clear()
            logger.info("投递服务已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止投递服务失败: {e}")
            return False
    
    def send_message(self, chat_name: str, message: str, max_retries: int = 3) -> bool:
        """发送消息（异步）"""
        try:
            if not self.is_running:
                logger.error("投递服务未启动")
                return False
            
            # 创建投递任务
            task = DeliveryTask(
                chat_name=chat_name,
                message=message,
                max_retries=max_retries
            )
            
            # 添加到队列
            self.task_queue.put(task)
            self.stats['total_tasks'] += 1
            
            logger.info(f"消息已加入投递队列: {chat_name} - {message[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"添加投递任务失败: {e}")
            return False
    
    def send_message_sync(self, chat_name: str, message: str, max_retries: int = 3) -> Tuple[bool, str]:
        """发送消息（同步）"""
        try:
            if not self.wx_instance:
                return False, "微信实例不可用"
            
            # 直接发送，带重试
            for attempt in range(max_retries + 1):
                try:
                    success, error_msg = self._send_to_wechat(chat_name, message)
                    
                    if success:
                        self.stats['successful_deliveries'] += 1
                        logger.info(f"同步发送成功: {chat_name} - {message[:50]}...")
                        return True, "发送成功"
                    else:
                        if attempt < max_retries:
                            self.stats['retries'] += 1
                            logger.warning(f"同步发送失败 (尝试 {attempt + 1}/{max_retries + 1}): {error_msg}")
                            time.sleep(self.retry_delay)
                        else:
                            self.stats['failed_deliveries'] += 1
                            logger.error(f"同步发送最终失败: {error_msg}")
                            return False, error_msg
                
                except Exception as e:
                    error_msg = str(e)
                    if attempt < max_retries:
                        self.stats['retries'] += 1
                        logger.warning(f"同步发送异常 (尝试 {attempt + 1}/{max_retries + 1}): {error_msg}")
                        time.sleep(self.retry_delay)
                    else:
                        self.stats['failed_deliveries'] += 1
                        logger.error(f"同步发送最终异常: {error_msg}")
                        return False, error_msg
            
            return False, "达到最大重试次数"
            
        except Exception as e:
            self.stats['failed_deliveries'] += 1
            logger.error(f"同步发送消息异常: {e}")
            return False, str(e)
    
    def _delivery_worker(self):
        """投递工作线程"""
        logger.info(f"投递工作线程启动: {threading.current_thread().name}")
        
        while not self.stop_event.is_set():
            try:
                # 获取任务
                try:
                    task = self.task_queue.get(timeout=1)
                except Empty:
                    continue
                
                # 处理任务
                self._process_delivery_task(task)
                
                # 标记任务完成
                self.task_queue.task_done()
                
            except Exception as e:
                logger.error(f"投递工作线程异常: {e}")
                time.sleep(1)
        
        logger.info(f"投递工作线程结束: {threading.current_thread().name}")
    
    def _process_delivery_task(self, task: DeliveryTask):
        """处理投递任务"""
        try:
            task.status = DeliveryStatus.SENDING
            task.last_attempt_time = time.time()
            
            logger.info(f"开始处理投递任务: {task.chat_name} - {task.message[:50]}...")
            
            # 检查微信实例
            if not self.wx_instance:
                task.status = DeliveryStatus.FAILED
                task.error_message = "微信实例不可用"
                self._handle_failed_task(task)
                return
            
            # 尝试发送
            success, error_msg = self._send_to_wechat(task.chat_name, task.message)
            
            if success:
                # 发送成功
                task.status = DeliveryStatus.SUCCESS
                self.stats['successful_deliveries'] += 1
                self.message_sent.emit(task.chat_name, True, task.message)
                logger.info(f"投递成功: {task.chat_name} - {task.message[:50]}...")
            else:
                # 发送失败，检查是否需要重试
                task.error_message = error_msg
                
                if task.retry_count < task.max_retries and self._should_retry(error_msg):
                    # 重试
                    task.retry_count += 1
                    task.status = DeliveryStatus.RETRY
                    self.stats['retries'] += 1
                    
                    logger.warning(f"投递失败，将重试 ({task.retry_count}/{task.max_retries}): {error_msg}")
                    
                    # 延迟后重新加入队列
                    time.sleep(self.retry_delay)
                    self.task_queue.put(task)
                else:
                    # 不再重试
                    task.status = DeliveryStatus.FAILED
                    self._handle_failed_task(task)
            
        except Exception as e:
            task.status = DeliveryStatus.FAILED
            task.error_message = str(e)
            logger.error(f"处理投递任务异常: {e}")
            self._handle_failed_task(task)
    
    def _send_to_wechat(self, chat_name: str, message: str) -> Tuple[bool, str]:
        """发送消息到微信"""
        try:
            # 验证参数
            if not chat_name or not message:
                return False, "聊天名称或消息内容为空"
            
            # 检查微信实例
            if not self.wx_instance:
                return False, "微信实例不可用"
            
            # 发送消息
            self.wx_instance.SendMsg(message, chat_name)
            
            # 验证发送（可选）
            # 这里可以添加发送验证逻辑
            
            return True, "发送成功"
            
        except AttributeError as e:
            return False, f"微信实例方法不可用: {str(e)}"
        except Exception as e:
            return False, f"发送消息异常: {str(e)}"
    
    def _should_retry(self, error_msg: str) -> bool:
        """判断是否应该重试"""
        # 网络相关错误可以重试
        retry_keywords = [
            "连接",
            "网络",
            "超时",
            "临时",
            "繁忙"
        ]
        
        # 不应该重试的错误
        no_retry_keywords = [
            "不可用",
            "权限",
            "禁止",
            "无效"
        ]
        
        # 检查不应该重试的错误
        for keyword in no_retry_keywords:
            if keyword in error_msg:
                return False
        
        # 检查可以重试的错误
        for keyword in retry_keywords:
            if keyword in error_msg:
                return True
        
        # 默认重试
        return True
    
    def _handle_failed_task(self, task: DeliveryTask):
        """处理失败的任务"""
        try:
            self.stats['failed_deliveries'] += 1
            self.failed_tasks.append(task)
            
            # 发射失败信号
            self.delivery_failed.emit(task.chat_name, task.message, task.error_message)
            self.message_sent.emit(task.chat_name, False, task.error_message)
            
            logger.error(f"投递最终失败: {task.chat_name} - {task.error_message}")
            
            # 限制失败任务列表大小
            if len(self.failed_tasks) > 100:
                self.failed_tasks = self.failed_tasks[-50:]
            
        except Exception as e:
            logger.error(f"处理失败任务异常: {e}")
    
    def _update_queue_status(self):
        """更新队列状态"""
        try:
            queue_size = self.task_queue.qsize()
            if queue_size != self.stats['queue_size']:
                self.stats['queue_size'] = queue_size
                self.queue_status_changed.emit(queue_size)
        except Exception as e:
            logger.error(f"更新队列状态失败: {e}")
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        try:
            return self.task_queue.qsize()
        except Exception:
            return 0
    
    def get_failed_tasks(self) -> List[DeliveryTask]:
        """获取失败的任务"""
        return self.failed_tasks.copy()
    
    def retry_failed_tasks(self) -> int:
        """重试失败的任务"""
        try:
            if not self.is_running:
                logger.error("投递服务未启动")
                return 0
            
            retry_count = 0
            failed_tasks_copy = self.failed_tasks.copy()
            self.failed_tasks.clear()
            
            for task in failed_tasks_copy:
                # 重置任务状态
                task.status = DeliveryStatus.PENDING
                task.retry_count = 0
                task.error_message = ""
                
                # 重新加入队列
                self.task_queue.put(task)
                retry_count += 1
            
            logger.info(f"重试失败任务: {retry_count} 个")
            return retry_count
            
        except Exception as e:
            logger.error(f"重试失败任务异常: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        stats['failed_tasks_count'] = len(self.failed_tasks)
        stats['is_running'] = self.is_running
        stats['worker_count'] = len(self.workers)
        
        # 计算成功率
        total_completed = stats['successful_deliveries'] + stats['failed_deliveries']
        if total_completed > 0:
            stats['success_rate'] = round((stats['successful_deliveries'] / total_completed) * 100, 2)
        else:
            stats['success_rate'] = 0
        
        return stats
    
    def clear_failed_tasks(self):
        """清空失败任务"""
        self.failed_tasks.clear()
        logger.info("已清空失败任务列表")
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_tasks': 0,
            'successful_deliveries': 0,
            'failed_deliveries': 0,
            'retries': 0,
            'queue_size': 0
        }
        logger.info("统计信息已重置")
