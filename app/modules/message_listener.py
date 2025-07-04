"""
消息监听服务模块
专门负责消息监听，只调用wxauto库模块，不直接操作微信
"""

import logging
import threading
import time
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .base_interfaces import (
    BaseService, ServiceStatus, HealthStatus, ServiceInfo, 
    HealthCheckResult, IMessageListener
)

logger = logging.getLogger(__name__)


@dataclass
class MessageRecord:
    """消息记录"""
    message_id: str
    sender: str
    sender_remark: str
    content: str
    message_type: str
    timestamp: str
    chat_name: str


class MessageListener(BaseService, IMessageListener):
    """消息监听服务"""
    
    # 信号定义
    new_message_received = pyqtSignal(str, dict)    # (chat_name, message_data)
    listening_started = pyqtSignal(list)            # (chat_names)
    listening_stopped = pyqtSignal()                # ()
    chat_added = pyqtSignal(str)                    # (chat_name)
    chat_removed = pyqtSignal(str)                  # (chat_name)
    error_occurred = pyqtSignal(str)                # (error_message)
    
    def __init__(self, wxauto_manager=None, parent=None):
        super().__init__("message_listener", parent)
        
        self.wxauto_manager = wxauto_manager
        self._lock = threading.RLock()

        # 连接wxauto管理器的消息信号（用于回调模式）
        if self.wxauto_manager:
            self.wxauto_manager.messages_received.connect(self._on_wxauto_messages_received)
        
        # 监听状态
        self._is_listening = False
        self._monitored_chats: List[str] = []
        
        # 消息处理
        self._processed_messages: Set[str] = set()  # 已处理的消息ID
        self._message_buffer: List[MessageRecord] = []
        self._max_buffer_size = 1000
        
        # 监听线程
        self._listen_thread = None
        self._stop_listening = threading.Event()
        
        # 监听配置
        self._poll_interval = 5.0  # 5秒轮询一次 - 符合用户需求
        self._max_messages_per_poll = 50  # 每次最多处理50条消息
        self._use_callback_mode = True  # 是否使用回调模式（新的监听方法）
        
        # 统计信息
        self._stats = {
            'total_messages': 0,
            'processed_messages': 0,
            'duplicate_messages': 0,
            'error_count': 0,
            'last_poll_time': 0
        }
        
        logger.info("消息监听服务初始化完成")
    
    def start(self) -> bool:
        """启动服务"""
        try:
            self._update_status(ServiceStatus.STARTING)
            
            # 检查wxauto管理器
            if not self.wxauto_manager:
                logger.error("wxauto管理器未设置")
                self._update_status(ServiceStatus.ERROR)
                return False
            
            # 检查wxauto管理器状态
            if not self.wxauto_manager.is_connected():
                logger.error("wxauto管理器未连接")
                self._update_status(ServiceStatus.ERROR)
                return False
            
            self._update_status(ServiceStatus.RUNNING)
            self._update_health(HealthStatus.HEALTHY)
            return True
            
        except Exception as e:
            logger.error(f"启动消息监听服务失败: {e}")
            self._update_status(ServiceStatus.ERROR)
            self._update_health(HealthStatus.UNHEALTHY)
            return False
    
    def stop(self) -> bool:
        """停止服务"""
        try:
            self._update_status(ServiceStatus.STOPPING)
            
            # 停止监听
            if self._is_listening:
                self.stop_listening()
            
            self._update_status(ServiceStatus.STOPPED)
            self._update_health(HealthStatus.UNKNOWN)
            return True
            
        except Exception as e:
            logger.error(f"停止消息监听服务失败: {e}")
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
            'is_listening': self._is_listening,
            'monitored_chats': self._monitored_chats.copy(),
            'monitored_chats_count': len(self._monitored_chats),
            'processed_messages_count': len(self._processed_messages),
            'buffer_size': len(self._message_buffer),
            'poll_interval': self._poll_interval,
            'stats': self._stats.copy()
        }
        
        return ServiceInfo(
            name=self.service_name,
            status=self.status,
            health=self.health,
            message=f"监听{'运行中' if self._is_listening else '已停止'}，{len(self._monitored_chats)}个聊天",
            details=details
        )
    
    def check_health(self) -> HealthCheckResult:
        """检查服务健康状态"""
        start_time = time.time()
        
        try:
            # 检查wxauto管理器
            wxauto_healthy = False
            wxauto_message = "wxauto管理器未设置"
            
            if self.wxauto_manager:
                try:
                    wxauto_healthy = self.wxauto_manager.is_connected()
                    wxauto_message = "微信连接正常" if wxauto_healthy else "微信连接异常"
                except Exception as e:
                    wxauto_message = f"检查微信连接失败: {str(e)}"
            
            # 检查监听状态
            listening_issues = []
            if self._is_listening:
                if not self._monitored_chats:
                    listening_issues.append("监听已启动但无监控目标")
                
                # 检查监听线程
                if not self._listen_thread or not self._listen_thread.is_alive():
                    listening_issues.append("监听线程未运行")
                
                # 检查最近的轮询时间
                current_time = time.time()
                if self._stats['last_poll_time'] > 0:
                    time_since_last_poll = current_time - self._stats['last_poll_time']
                    if time_since_last_poll > self._poll_interval * 3:  # 超过3个轮询周期
                        listening_issues.append(f"轮询延迟: {time_since_last_poll:.1f}秒")
            
            # 检查错误率
            error_rate = 0
            if self._stats['total_messages'] > 0:
                error_rate = (self._stats['error_count'] / self._stats['total_messages']) * 100
            
            if error_rate > 10:  # 错误率超过10%
                listening_issues.append(f"错误率过高: {error_rate:.1f}%")
            
            # 判断健康状态
            if not wxauto_healthy:
                status = HealthStatus.UNHEALTHY
                message = wxauto_message
            elif listening_issues:
                status = HealthStatus.DEGRADED
                message = "; ".join(listening_issues)
            else:
                status = HealthStatus.HEALTHY
                message = "消息监听服务运行正常"
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    'wxauto_healthy': wxauto_healthy,
                    'wxauto_message': wxauto_message,
                    'is_listening': self._is_listening,
                    'listening_issues': listening_issues,
                    'error_rate': error_rate,
                    'monitored_chats_count': len(self._monitored_chats)
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
    
    # IMessageListener接口实现
    
    def start_listening(self, chat_names: List[str]) -> bool:
        """开始监听"""
        try:
            with self._lock:
                if self._is_listening:
                    logger.warning("消息监听已在运行")
                    return True
                
                if not chat_names:
                    logger.error("无监听目标")
                    return False
                
                if not self.wxauto_manager or not self.wxauto_manager.is_connected():
                    logger.error("wxauto管理器未连接")
                    return False
                
                # 设置监听目标
                self._monitored_chats = chat_names.copy()
                
                # 添加监听聊天到wxauto管理器
                for chat_name in self._monitored_chats:
                    if not self.wxauto_manager.add_listen_chat(chat_name):
                        logger.error(f"添加监听聊天失败: {chat_name}")
                        return False
                
                # 启动监听线程
                self._stop_listening.clear()
                self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
                self._listen_thread.start()
                
                self._is_listening = True
                logger.info(f"开始监听 {len(self._monitored_chats)} 个聊天")
                self.listening_started.emit(self._monitored_chats.copy())
                return True
                
        except Exception as e:
            logger.error(f"开始监听失败: {e}")
            self.error_occurred.emit(f"开始监听失败: {str(e)}")
            return False
    
    def stop_listening(self) -> bool:
        """停止监听"""
        try:
            with self._lock:
                if not self._is_listening:
                    logger.warning("消息监听未在运行")
                    return True
                
                # 停止监听线程
                self._stop_listening.set()
                if self._listen_thread and self._listen_thread.is_alive():
                    self._listen_thread.join(timeout=5)
                
                # 从wxauto管理器移除监听聊天
                if self.wxauto_manager:
                    for chat_name in self._monitored_chats:
                        self.wxauto_manager.remove_listen_chat(chat_name)
                
                self._is_listening = False
                self._monitored_chats.clear()
                
                logger.info("停止监听")
                self.listening_stopped.emit()
                return True
                
        except Exception as e:
            logger.error(f"停止监听失败: {e}")
            self.error_occurred.emit(f"停止监听失败: {str(e)}")
            return False
    
    def add_chat(self, chat_name: str) -> bool:
        """添加监听聊天"""
        try:
            with self._lock:
                if chat_name in self._monitored_chats:
                    logger.warning(f"聊天已在监听列表中: {chat_name}")
                    return True
                
                # 添加到监听列表
                self._monitored_chats.append(chat_name)
                
                # 如果正在监听，添加到wxauto管理器
                if self._is_listening and self.wxauto_manager:
                    if not self.wxauto_manager.add_listen_chat(chat_name):
                        # 如果添加失败，从列表中移除
                        self._monitored_chats.remove(chat_name)
                        logger.error(f"添加监听聊天失败: {chat_name}")
                        return False
                
                logger.info(f"添加监听聊天: {chat_name}")
                self.chat_added.emit(chat_name)
                return True
                
        except Exception as e:
            logger.error(f"添加监听聊天失败: {e}")
            self.error_occurred.emit(f"添加监听聊天失败: {str(e)}")
            return False

    def remove_chat(self, chat_name: str) -> bool:
        """移除监听聊天"""
        try:
            with self._lock:
                if chat_name not in self._monitored_chats:
                    logger.warning(f"聊天不在监听列表中: {chat_name}")
                    return True

                # 从监听列表移除
                self._monitored_chats.remove(chat_name)

                # 如果正在监听，从wxauto管理器移除
                if self._is_listening and self.wxauto_manager:
                    self.wxauto_manager.remove_listen_chat(chat_name)

                logger.info(f"移除监听聊天: {chat_name}")
                self.chat_removed.emit(chat_name)
                return True

        except Exception as e:
            logger.error(f"移除监听聊天失败: {e}")
            self.error_occurred.emit(f"移除监听聊天失败: {str(e)}")
            return False

    def get_monitored_chats(self) -> List[str]:
        """获取监听聊天列表"""
        with self._lock:
            return self._monitored_chats.copy()

    def is_listening(self) -> bool:
        """检查是否正在监听"""
        return self._is_listening

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return self._stats.copy()

    def clear_message_buffer(self) -> bool:
        """清空消息缓冲区"""
        try:
            with self._lock:
                self._message_buffer.clear()
                self._processed_messages.clear()
                logger.info("消息缓冲区已清空")
                return True
        except Exception as e:
            logger.error(f"清空消息缓冲区失败: {e}")
            return False

    # 私有方法

    def _listen_loop(self):
        """监听循环"""
        if self._use_callback_mode:
            logger.info("消息监听循环开始（回调模式）")
            # 在回调模式下，消息通过wxauto_manager的回调直接处理
            # 这里只需要保持线程活跃，等待停止信号
            while not self._stop_listening.is_set():
                self._stats['last_poll_time'] = time.time()
                # 在回调模式下，只需要等待停止信号
                self._stop_listening.wait(self._poll_interval)
        else:
            logger.info("消息监听循环开始（轮询模式）")
            consecutive_errors = 0
            max_consecutive_errors = 5

            while not self._stop_listening.is_set():
                try:
                    self._stats['last_poll_time'] = time.time()
                    logger.debug(f"开始轮询消息，监听聊天: {self._monitored_chats}")

                    # 获取新消息
                    new_messages = self._poll_messages()

                    # 处理新消息
                    if new_messages:
                        logger.info(f"获取到 {len(new_messages)} 条新消息，开始处理")
                        self._process_new_messages(new_messages)
                        consecutive_errors = 0  # 重置错误计数
                    else:
                        logger.debug("本次轮询未获取到新消息")

                    # 等待下次轮询
                    self._stop_listening.wait(self._poll_interval)

                except Exception as e:
                    consecutive_errors += 1

                    # 对于常见的wxauto错误，降低日志级别
                    if any(error_text in str(e) for error_text in [
                        "Find Control Timeout",
                        "dictionary changed size during iteration",
                        "控件查找超时"
                    ]):
                        logger.debug(f"监听循环出现预期错误 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                    else:
                        logger.error(f"监听循环异常 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                        self.error_occurred.emit(f"监听循环异常: {str(e)}")

                    self._stats['error_count'] += 1

                    # 如果连续错误过多，增加等待时间
                    if consecutive_errors >= max_consecutive_errors:
                        logger.warning(f"连续错误过多，增加等待时间")
                        self._stop_listening.wait(self._poll_interval * 5)
                        consecutive_errors = 0  # 重置计数
                    else:
                        # 出错时等待更长时间
                        wait_time = self._poll_interval * min(consecutive_errors, 3)
                        self._stop_listening.wait(wait_time)

        logger.info("消息监听循环结束")

    def _on_wxauto_messages_received(self, chat_name: str, messages: List[dict]):
        """处理从wxauto管理器接收到的消息（回调模式）"""
        try:
            if not self._use_callback_mode:
                # 如果不是回调模式，忽略这些消息
                return

            if not self._is_listening:
                # 如果没有在监听，忽略消息
                return

            if chat_name not in self._monitored_chats:
                # 如果不是监听的聊天，忽略消息
                logger.debug(f"收到非监听聊天的消息，忽略: {chat_name}")
                return

            logger.info(f"通过回调接收到 {len(messages)} 条消息: {chat_name}")

            # 处理消息（复用现有的处理逻辑）
            self._process_new_messages(messages)

        except Exception as e:
            logger.error(f"处理wxauto回调消息失败: {e}")
            self.error_occurred.emit(f"处理回调消息失败: {str(e)}")

    def _poll_messages(self) -> List[Dict[str, Any]]:
        """轮询消息"""
        try:
            if not self.wxauto_manager or not self.wxauto_manager.is_connected():
                logger.debug("wxauto管理器未连接，跳过消息轮询")
                return []

            # 获取所有新消息
            all_messages = []
            failed_chats = []

            # 创建监听聊天列表的副本，避免迭代时修改
            monitored_chats_copy = list(self._monitored_chats)

            for chat_name in monitored_chats_copy:
                try:
                    messages = self.wxauto_manager.get_messages(chat_name)
                    # 直接添加消息，chat_name已经在WxautoManager中设置
                    if messages:
                        all_messages.extend(messages)
                        logger.debug(f"从 {chat_name} 获取到 {len(messages)} 条消息")
                except Exception as e:
                    # 对于常见的wxauto错误，降低日志级别
                    if any(error_text in str(e) for error_text in [
                        "Find Control Timeout",
                        "dictionary changed size during iteration",
                        "控件查找超时"
                    ]):
                        logger.debug(f"获取聊天消息时出现预期错误 {chat_name}: {e}")
                    else:
                        logger.warning(f"获取聊天消息失败 {chat_name}: {e}")
                    failed_chats.append(chat_name)
                    continue

            # 更新统计信息
            self._stats['total_messages'] += len(all_messages)

            if failed_chats:
                logger.debug(f"本次轮询中 {len(failed_chats)} 个聊天获取消息失败")

            return all_messages

        except Exception as e:
            # 对于常见错误，降低日志级别
            if any(error_text in str(e) for error_text in [
                "Find Control Timeout",
                "dictionary changed size during iteration"
            ]):
                logger.debug(f"轮询消息时出现预期错误: {e}")
            else:
                logger.error(f"轮询消息失败: {e}")
            self._stats['error_count'] += 1
            return []

    def _process_new_messages(self, messages: List[Dict[str, Any]]):
        """处理新消息"""
        try:
            processed_count = 0

            for msg_data in messages[:self._max_messages_per_poll]:
                try:
                    # 生成消息ID
                    message_id = self._generate_message_id(msg_data)

                    # 检查是否已处理
                    if message_id in self._processed_messages:
                        self._stats['duplicate_messages'] += 1
                        continue

                    # 创建消息记录
                    message_record = MessageRecord(
                        message_id=message_id,
                        sender=msg_data.get('sender', ''),
                        sender_remark=msg_data.get('sender_remark', ''),
                        content=msg_data.get('content', ''),
                        message_type=msg_data.get('type', ''),
                        timestamp=msg_data.get('time', ''),
                        chat_name=msg_data.get('chat_name', '')
                    )

                    # 添加到缓冲区
                    self._add_to_buffer(message_record)

                    # 标记为已处理
                    self._processed_messages.add(message_id)

                    # 发出新消息信号
                    self.new_message_received.emit(message_record.chat_name, {
                        'message_id': message_record.message_id,
                        'sender': message_record.sender,
                        'sender_remark': message_record.sender_remark,
                        'content': message_record.content,
                        'type': message_record.message_type,
                        'time': message_record.timestamp,
                        'chat_name': message_record.chat_name
                    })

                    processed_count += 1

                except Exception as e:
                    logger.error(f"处理单条消息失败: {e}")
                    self._stats['error_count'] += 1
                    continue

            self._stats['processed_messages'] += processed_count

            if processed_count > 0:
                logger.debug(f"处理了 {processed_count} 条新消息")

        except Exception as e:
            logger.error(f"处理新消息失败: {e}")
            self._stats['error_count'] += 1

    def _generate_message_id(self, msg_data: Dict[str, Any]) -> str:
        """生成消息ID"""
        try:
            # 使用发送者、内容、时间和聊天名称生成唯一ID
            sender = msg_data.get('sender', '')
            content = msg_data.get('content', '')
            timestamp = msg_data.get('time', '')
            chat_name = msg_data.get('chat_name', '')

            # 简单的哈希生成
            import hashlib
            raw_id = f"{chat_name}_{sender}_{content}_{timestamp}"
            return hashlib.md5(raw_id.encode('utf-8')).hexdigest()

        except Exception as e:
            logger.warning(f"生成消息ID失败: {e}")
            # 使用时间戳作为备用ID
            return f"msg_{int(time.time() * 1000)}"

    def _add_to_buffer(self, message_record: MessageRecord):
        """添加到消息缓冲区"""
        try:
            with self._lock:
                self._message_buffer.append(message_record)

                # 限制缓冲区大小
                if len(self._message_buffer) > self._max_buffer_size:
                    # 移除最旧的消息
                    removed_count = len(self._message_buffer) - self._max_buffer_size
                    removed_messages = self._message_buffer[:removed_count]
                    self._message_buffer = self._message_buffer[removed_count:]

                    # 同时从已处理集合中移除对应的ID
                    for removed_msg in removed_messages:
                        self._processed_messages.discard(removed_msg.message_id)

                    logger.debug(f"缓冲区已满，移除了 {removed_count} 条旧消息")

        except Exception as e:
            logger.error(f"添加到缓冲区失败: {e}")

    def get_recent_messages(self, chat_name: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近的消息"""
        try:
            with self._lock:
                messages = self._message_buffer.copy()

                # 过滤指定聊天
                if chat_name:
                    messages = [msg for msg in messages if msg.chat_name == chat_name]

                # 按时间排序（最新的在前）
                messages.sort(key=lambda x: x.timestamp, reverse=True)

                # 限制数量
                messages = messages[:limit]

                # 转换为字典格式
                result = []
                for msg in messages:
                    result.append({
                        'message_id': msg.message_id,
                        'sender': msg.sender,
                        'sender_remark': msg.sender_remark,
                        'content': msg.content,
                        'type': msg.message_type,
                        'time': msg.timestamp,
                        'chat_name': msg.chat_name
                    })

                return result

        except Exception as e:
            logger.error(f"获取最近消息失败: {e}")
            return []
