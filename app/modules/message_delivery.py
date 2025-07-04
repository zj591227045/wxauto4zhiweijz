"""
消息投递服务模块
负责消息投递到智能记账API和微信回复发送
"""

import logging
import threading
import time
import queue
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal

from .base_interfaces import (
    BaseService, ServiceStatus, HealthStatus, ServiceInfo, 
    HealthCheckResult, IMessageDelivery
)

logger = logging.getLogger(__name__)


class DeliveryTaskType(Enum):
    """投递任务类型"""
    ACCOUNTING = "accounting"
    WECHAT_REPLY = "wechat_reply"


@dataclass
class DeliveryTask:
    """投递任务"""
    task_id: str
    task_type: DeliveryTaskType
    chat_name: str
    message_content: str
    sender_name: str = ""
    reply_message: str = ""
    max_retries: int = 3
    retry_count: int = 0
    created_time: float = 0.0
    
    def __post_init__(self):
        if self.created_time == 0.0:
            self.created_time = time.time()


@dataclass
class DeliveryResult:
    """投递结果"""
    task_id: str
    success: bool
    message: str
    data: Dict[str, Any] = None
    processing_time: float = 0.0
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}


class MessageDelivery(BaseService, IMessageDelivery):
    """消息投递服务"""
    
    # 信号定义
    accounting_completed = pyqtSignal(str, bool, str, dict)  # (chat_name, success, message, data)
    wechat_reply_sent = pyqtSignal(str, bool, str)           # (chat_name, success, message)
    task_completed = pyqtSignal(str, bool, str, dict)        # (task_id, success, message, data)
    queue_status_changed = pyqtSignal(int, int)              # (pending_tasks, processing_tasks)
    
    def __init__(self, accounting_manager=None, wxauto_manager=None, parent=None):
        super().__init__("message_delivery", parent)
        
        self.accounting_manager = accounting_manager
        self.wxauto_manager = wxauto_manager
        self._lock = threading.RLock()
        
        # 任务队列
        self._task_queue = queue.Queue()
        self._processing_tasks: Dict[str, DeliveryTask] = {}
        
        # 工作线程
        self._worker_threads: List[threading.Thread] = []
        self._stop_workers = threading.Event()
        self._max_workers = 3  # 最多3个工作线程
        
        # 配置
        self._auto_reply_enabled = True
        self._reply_template = ""
        self._max_queue_size = 1000
        self._task_timeout = 60  # 任务超时时间（秒）
        
        # 统计信息
        self._stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'accounting_success': 0,
            'accounting_failed': 0,
            'reply_success': 0,
            'reply_failed': 0,
            'queue_overflow': 0
        }
        
        logger.info("消息投递服务初始化完成")
    
    def start(self) -> bool:
        """启动服务"""
        try:
            self._update_status(ServiceStatus.STARTING)
            
            # 检查依赖服务
            if not self.accounting_manager:
                logger.error("记账管理器未设置")
                self._update_status(ServiceStatus.ERROR)
                return False
            
            if not self.wxauto_manager:
                logger.error("wxauto管理器未设置")
                self._update_status(ServiceStatus.ERROR)
                return False
            
            # 启动工作线程
            self._start_worker_threads()
            
            self._update_status(ServiceStatus.RUNNING)
            self._update_health(HealthStatus.HEALTHY)
            return True
            
        except Exception as e:
            logger.error(f"启动消息投递服务失败: {e}")
            self._update_status(ServiceStatus.ERROR)
            self._update_health(HealthStatus.UNHEALTHY)
            return False
    
    def stop(self) -> bool:
        """停止服务"""
        try:
            self._update_status(ServiceStatus.STOPPING)
            
            # 停止工作线程
            self._stop_worker_threads()
            
            # 清空队列
            while not self._task_queue.empty():
                try:
                    self._task_queue.get_nowait()
                except queue.Empty:
                    break
            
            self._update_status(ServiceStatus.STOPPED)
            self._update_health(HealthStatus.UNKNOWN)
            return True
            
        except Exception as e:
            logger.error(f"停止消息投递服务失败: {e}")
            return False
    
    def restart(self) -> bool:
        """重启服务"""
        if self.stop():
            time.sleep(1)
            return self.start()
        return False
    
    def get_info(self) -> ServiceInfo:
        """获取服务信息"""
        queue_size = self._task_queue.qsize()
        processing_count = len(self._processing_tasks)
        
        details = {
            'auto_reply_enabled': self._auto_reply_enabled,
            'queue_size': queue_size,
            'processing_tasks': processing_count,
            'worker_threads': len(self._worker_threads),
            'max_workers': self._max_workers,
            'stats': self._stats.copy()
        }
        
        return ServiceInfo(
            name=self.service_name,
            status=self.status,
            health=self.health,
            message=f"队列: {queue_size}, 处理中: {processing_count}",
            details=details
        )
    
    def check_health(self) -> HealthCheckResult:
        """检查服务健康状态"""
        start_time = time.time()
        
        try:
            # 检查依赖服务
            accounting_healthy = False
            wxauto_healthy = False
            
            if self.accounting_manager:
                try:
                    accounting_result = self.accounting_manager.check_health()
                    accounting_healthy = accounting_result.status == HealthStatus.HEALTHY
                except:
                    accounting_healthy = False
            
            if self.wxauto_manager:
                try:
                    wxauto_result = self.wxauto_manager.check_health()
                    wxauto_healthy = wxauto_result.status == HealthStatus.HEALTHY
                except:
                    wxauto_healthy = False
            
            # 检查工作线程
            active_workers = sum(1 for t in self._worker_threads if t.is_alive())
            
            # 检查队列状态
            queue_size = self._task_queue.qsize()
            processing_count = len(self._processing_tasks)
            
            # 检查任务超时
            current_time = time.time()
            timeout_tasks = []
            for task_id, task in self._processing_tasks.items():
                if current_time - task.created_time > self._task_timeout:
                    timeout_tasks.append(task_id)
            
            # 判断健康状态
            issues = []
            
            if not accounting_healthy:
                issues.append("记账服务不健康")
            
            if not wxauto_healthy:
                issues.append("微信服务不健康")
            
            if active_workers == 0:
                issues.append("无活跃工作线程")
            elif active_workers < self._max_workers // 2:
                issues.append(f"工作线程不足: {active_workers}/{self._max_workers}")
            
            if queue_size > self._max_queue_size * 0.8:
                issues.append(f"队列接近满载: {queue_size}/{self._max_queue_size}")
            
            if timeout_tasks:
                issues.append(f"{len(timeout_tasks)}个任务超时")
            
            # 计算错误率
            total_tasks = self._stats['completed_tasks'] + self._stats['failed_tasks']
            error_rate = 0
            if total_tasks > 0:
                error_rate = (self._stats['failed_tasks'] / total_tasks) * 100
            
            if error_rate > 20:  # 错误率超过20%
                issues.append(f"错误率过高: {error_rate:.1f}%")
            
            # 确定健康状态
            if not accounting_healthy or not wxauto_healthy or active_workers == 0:
                status = HealthStatus.UNHEALTHY
                message = "; ".join(issues) if issues else "服务不可用"
            elif issues:
                status = HealthStatus.DEGRADED
                message = "; ".join(issues)
            else:
                status = HealthStatus.HEALTHY
                message = "消息投递服务运行正常"
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    'accounting_healthy': accounting_healthy,
                    'wxauto_healthy': wxauto_healthy,
                    'active_workers': active_workers,
                    'queue_size': queue_size,
                    'processing_count': processing_count,
                    'timeout_tasks': len(timeout_tasks),
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
    
    # IMessageDelivery接口实现
    
    def process_message(self, chat_name: str, message_content: str, sender_name: str) -> Tuple[bool, str]:
        """处理消息"""
        try:
            # 创建记账任务
            task_id = self._generate_task_id()
            task = DeliveryTask(
                task_id=task_id,
                task_type=DeliveryTaskType.ACCOUNTING,
                chat_name=chat_name,
                message_content=message_content,
                sender_name=sender_name
            )
            
            # 添加到队列
            if self._add_task_to_queue(task):
                logger.info(f"消息已加入处理队列: {chat_name} - {message_content[:50]}...")
                return True, f"任务已创建: {task_id}"
            else:
                return False, "队列已满，无法处理消息"
                
        except Exception as e:
            error_msg = f"处理消息失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def send_reply(self, chat_name: str, reply_message: str) -> bool:
        """发送回复"""
        try:
            # 创建回复任务
            task_id = self._generate_task_id()
            task = DeliveryTask(
                task_id=task_id,
                task_type=DeliveryTaskType.WECHAT_REPLY,
                chat_name=chat_name,
                message_content="",
                reply_message=reply_message
            )
            
            # 添加到队列
            if self._add_task_to_queue(task):
                logger.info(f"回复已加入发送队列: {chat_name} - {reply_message[:50]}...")
                return True
            else:
                logger.error("队列已满，无法发送回复")
                return False
                
        except Exception as e:
            logger.error(f"发送回复失败: {e}")
            return False

    # 配置方法

    def set_auto_reply(self, enabled: bool):
        """设置自动回复"""
        self._auto_reply_enabled = enabled
        logger.info(f"自动回复已{'启用' if enabled else '禁用'}")

    def set_reply_template(self, template: str):
        """设置回复模板"""
        self._reply_template = template
        logger.info("回复模板已更新")

    def get_queue_status(self) -> Dict[str, int]:
        """获取队列状态"""
        return {
            'pending': self._task_queue.qsize(),
            'processing': len(self._processing_tasks),
            'total_processed': self._stats['completed_tasks'] + self._stats['failed_tasks']
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()

    # 私有方法

    def _generate_task_id(self) -> str:
        """生成任务ID"""
        import uuid
        return str(uuid.uuid4())[:8]

    def _add_task_to_queue(self, task: DeliveryTask) -> bool:
        """添加任务到队列"""
        try:
            if self._task_queue.qsize() >= self._max_queue_size:
                self._stats['queue_overflow'] += 1
                logger.warning("任务队列已满")
                return False

            self._task_queue.put(task)
            self._stats['total_tasks'] += 1

            # 发出队列状态变化信号
            self.queue_status_changed.emit(
                self._task_queue.qsize(),
                len(self._processing_tasks)
            )

            return True

        except Exception as e:
            logger.error(f"添加任务到队列失败: {e}")
            return False

    def _start_worker_threads(self):
        """启动工作线程"""
        self._stop_workers.clear()

        for i in range(self._max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"DeliveryWorker-{i+1}",
                daemon=True
            )
            worker.start()
            self._worker_threads.append(worker)

        logger.info(f"启动了 {len(self._worker_threads)} 个工作线程")

    def _stop_worker_threads(self):
        """停止工作线程"""
        self._stop_workers.set()

        # 等待所有线程结束
        for worker in self._worker_threads:
            if worker.is_alive():
                worker.join(timeout=5)

        self._worker_threads.clear()
        logger.info("所有工作线程已停止")

    def _worker_loop(self):
        """工作线程循环"""
        thread_name = threading.current_thread().name
        logger.info(f"工作线程 {thread_name} 开始")

        while not self._stop_workers.is_set():
            try:
                # 获取任务（带超时）
                try:
                    task = self._task_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # 处理任务
                self._process_task(task)

                # 标记任务完成
                self._task_queue.task_done()

            except Exception as e:
                logger.error(f"工作线程 {thread_name} 异常: {e}")
                time.sleep(1)

        logger.info(f"工作线程 {thread_name} 结束")

    def _process_task(self, task: DeliveryTask):
        """处理任务"""
        start_time = time.time()

        try:
            # 添加到处理中任务
            with self._lock:
                self._processing_tasks[task.task_id] = task

            # 根据任务类型处理
            if task.task_type == DeliveryTaskType.ACCOUNTING:
                result = self._process_accounting_task(task)
            elif task.task_type == DeliveryTaskType.WECHAT_REPLY:
                result = self._process_reply_task(task)
            else:
                result = DeliveryResult(
                    task_id=task.task_id,
                    success=False,
                    message=f"未知任务类型: {task.task_type}"
                )

            # 计算处理时间
            result.processing_time = time.time() - start_time

            # 更新统计
            if result.success:
                self._stats['completed_tasks'] += 1
            else:
                self._stats['failed_tasks'] += 1
                # 移除重试机制：记账失败直接返回失败，不再重试

            # 发出任务完成信号
            self.task_completed.emit(
                task.task_id,
                result.success,
                result.message,
                result.data
            )

        except Exception as e:
            logger.error(f"处理任务异常 {task.task_id}: {e}")
            self._stats['failed_tasks'] += 1

            # 发出任务失败信号
            self.task_completed.emit(
                task.task_id,
                False,
                f"处理异常: {str(e)}",
                {}
            )

        finally:
            # 从处理中任务移除
            with self._lock:
                self._processing_tasks.pop(task.task_id, None)

            # 发出队列状态变化信号
            self.queue_status_changed.emit(
                self._task_queue.qsize(),
                len(self._processing_tasks)
            )

    def _process_accounting_task(self, task: DeliveryTask) -> DeliveryResult:
        """处理记账任务"""
        try:
            # 调用记账服务
            success, message = self.accounting_manager.smart_accounting(
                task.message_content,
                task.sender_name
            )

            if success:
                self._stats['accounting_success'] += 1

                # 发出记账完成信号
                self.accounting_completed.emit(
                    task.chat_name,
                    True,
                    message,
                    {'task_id': task.task_id}
                )

                # 如果启用自动回复，创建回复任务
                if self._auto_reply_enabled and self._should_send_reply(message):
                    reply_message = self._format_reply_message(message)
                    self.send_reply(task.chat_name, reply_message)

                return DeliveryResult(
                    task_id=task.task_id,
                    success=True,
                    message=message,
                    data={'accounting_result': message}
                )
            else:
                self._stats['accounting_failed'] += 1

                # 发出记账失败信号
                self.accounting_completed.emit(
                    task.chat_name,
                    False,
                    message,
                    {'task_id': task.task_id}
                )

                return DeliveryResult(
                    task_id=task.task_id,
                    success=False,
                    message=message
                )

        except Exception as e:
            self._stats['accounting_failed'] += 1
            error_msg = f"记账任务处理异常: {str(e)}"

            # 发出记账失败信号
            self.accounting_completed.emit(
                task.chat_name,
                False,
                error_msg,
                {'task_id': task.task_id}
            )

            return DeliveryResult(
                task_id=task.task_id,
                success=False,
                message=error_msg
            )

    def _process_reply_task(self, task: DeliveryTask) -> DeliveryResult:
        """处理回复任务"""
        try:
            # 发送微信回复
            success = self.wxauto_manager.send_message(
                task.chat_name,
                task.reply_message
            )

            if success:
                self._stats['reply_success'] += 1
                message = "回复发送成功"
            else:
                self._stats['reply_failed'] += 1
                message = "回复发送失败"

            # 发出回复发送信号
            self.wechat_reply_sent.emit(
                task.chat_name,
                success,
                message
            )

            return DeliveryResult(
                task_id=task.task_id,
                success=success,
                message=message,
                data={'reply_message': task.reply_message}
            )

        except Exception as e:
            self._stats['reply_failed'] += 1
            error_msg = f"回复任务处理异常: {str(e)}"

            # 发出回复失败信号
            self.wechat_reply_sent.emit(
                task.chat_name,
                False,
                error_msg
            )

            return DeliveryResult(
                task_id=task.task_id,
                success=False,
                message=error_msg
            )

    def _should_send_reply(self, accounting_result: str) -> bool:
        """
        判断是否应该发送回复（参考旧版代码逻辑）

        Args:
            accounting_result: 记账结果消息

        Returns:
            True表示应该发送回复，False表示不应该发送
        """
        # 如果是"信息与记账无关"，不发送回复
        if "信息与记账无关" in accounting_result:
            return False

        # 其他情况（记账成功、失败、错误等）都发送回复
        return True

    def _format_reply_message(self, accounting_result: str) -> str:
        """
        格式化回复消息（参考旧版代码逻辑）

        Args:
            accounting_result: 记账结果消息

        Returns:
            格式化后的回复消息
        """
        if self._reply_template:
            # 使用自定义模板
            return self._reply_template.format(result=accounting_result)
        else:
            # 直接返回记账结果，因为accounting_manager已经格式化过了
            return accounting_result

    def _get_category_icon(self, category: str) -> str:
        """
        获取分类图标

        Args:
            category: 分类名称

        Returns:
            对应的图标
        """
        category_icons = {
            '餐饮': '🍽️',
            '交通': '🚗',
            '购物': '🛒',
            '娱乐': '🎮',
            '医疗': '🏥',
            '教育': '📚',
            '住房': '🏠',
            '通讯': '📱',
            '服装': '👕',
            '美容': '💄',
            '运动': '⚽',
            '旅游': '✈️',
            '投资': '💰',
            '保险': '🛡️',
            '转账': '💸',
            '红包': '🧧',
            '工资': '💼',
            '奖金': '🎁',
            '兼职': '👨‍💻',
            '理财': '📈',
            '其他': '📦'
        }
        return category_icons.get(category, '📂')

    def _get_direction_info(self, direction: str) -> Dict[str, str]:
        """
        获取方向信息

        Args:
            direction: 方向（支出/收入等）

        Returns:
            包含图标和文本的字典
        """
        direction_map = {
            '支出': {'icon': '💸', 'text': '支出'},
            '收入': {'icon': '💰', 'text': '收入'},
            'expense': {'icon': '💸', 'text': '支出'},
            'income': {'icon': '💰', 'text': '收入'},
            'transfer': {'icon': '🔄', 'text': '转账'}
        }

        # 默认值
        default_info = {'icon': '💸', 'text': direction or '支出'}

        return direction_map.get(direction.lower() if direction else '', default_info)
