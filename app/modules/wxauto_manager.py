"""
wxauto库管理模块
统一所有wxauto库的调用，避免重复定义，提供统一接口
"""

import logging
import threading
import time
from typing import Optional, List, Dict, Any, Tuple, Callable
from PyQt6.QtCore import QObject, pyqtSignal

from .base_interfaces import (
    BaseService, ServiceStatus, HealthStatus, ServiceInfo, 
    HealthCheckResult, IWxautoManager
)

logger = logging.getLogger(__name__)


class WxautoManager(BaseService, IWxautoManager):
    """wxauto库统一管理器"""
    
    # 信号定义
    instance_initialized = pyqtSignal(bool, str, dict)  # (success, message, info)
    connection_status_changed = pyqtSignal(bool, str)   # (connected, message)
    message_sent = pyqtSignal(str, bool, str)           # (chat_name, success, message)
    messages_received = pyqtSignal(str, list)           # (chat_name, messages)
    
    def __init__(self, parent=None):
        super().__init__("wxauto_manager", parent)
        
        # 微信实例
        self._wx_instance = None
        self._lock = threading.RLock()
        
        # 连接状态
        self._is_connected = False
        self._last_check_time = 0
        self._check_interval = 30  # 30秒检查一次
        
        # 窗口信息
        self._window_name = ""
        self._library_type = "wxauto"
        
        # 初始化状态
        self._initialized = False

        # 监听聊天的Chat对象引用
        self._listen_chats = {}  # {chat_name: Chat对象}

        logger.info("wxauto管理器初始化完成")
    
    def start(self) -> bool:
        """启动服务"""
        try:
            self._update_status(ServiceStatus.STARTING)
            
            if self._initialize_wxauto():
                self._update_status(ServiceStatus.RUNNING)
                self._update_health(HealthStatus.HEALTHY)
                return True
            else:
                self._update_status(ServiceStatus.ERROR)
                self._update_health(HealthStatus.UNHEALTHY)
                return False
                
        except Exception as e:
            logger.error(f"启动wxauto管理器失败: {e}")
            self._update_status(ServiceStatus.ERROR)
            self._update_health(HealthStatus.UNHEALTHY)
            return False
    
    def stop(self) -> bool:
        """停止服务"""
        try:
            self._update_status(ServiceStatus.STOPPING)
            
            with self._lock:
                self._wx_instance = None
                self._is_connected = False
                self._initialized = False
                
            self._update_status(ServiceStatus.STOPPED)
            self._update_health(HealthStatus.UNKNOWN)
            return True
            
        except Exception as e:
            logger.error(f"停止wxauto管理器失败: {e}")
            return False
    
    def restart(self) -> bool:
        """重启服务"""
        if self.stop():
            time.sleep(1)  # 等待1秒
            return self.start()
        return False
    
    def get_info(self) -> ServiceInfo:
        """获取服务信息"""
        details = {
            'initialized': self._initialized,
            'connected': self._is_connected,
            'window_name': self._window_name,
            'library_type': self._library_type,
            'last_check_time': self._last_check_time
        }
        
        return ServiceInfo(
            name=self.service_name,
            status=self.status,
            health=self.health,
            message=f"微信实例{'已连接' if self._is_connected else '未连接'}",
            details=details
        )
    
    def check_health(self) -> HealthCheckResult:
        """检查服务健康状态"""
        start_time = time.time()
        
        try:
            with self._lock:
                if not self._wx_instance:
                    return HealthCheckResult(
                        status=HealthStatus.UNHEALTHY,
                        message="微信实例未初始化",
                        details={'instance_exists': False}
                    )
                
                # 检查连接状态
                try:
                    # 尝试调用微信实例的方法来验证连接
                    if hasattr(self._wx_instance, 'GetSessionList'):
                        sessions = self._wx_instance.GetSessionList()
                        connected = sessions is not None
                    else:
                        # 如果没有GetSessionList方法，尝试其他方法
                        connected = True  # 假设连接正常
                    
                    self._is_connected = connected
                    self._last_check_time = time.time()
                    
                    if connected:
                        status = HealthStatus.HEALTHY
                        message = "微信连接正常"
                    else:
                        status = HealthStatus.DEGRADED
                        message = "微信连接异常"
                        
                except Exception as e:
                    logger.warning(f"检查微信连接失败: {e}")
                    status = HealthStatus.DEGRADED
                    message = f"连接检查失败: {str(e)}"
                    connected = False
                
                response_time = time.time() - start_time
                
                return HealthCheckResult(
                    status=status,
                    message=message,
                    details={
                        'connected': connected,
                        'window_name': self._window_name,
                        'library_type': self._library_type
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
    
    def _initialize_wxauto(self) -> bool:
        """初始化wxauto库"""
        try:
            logger.info("开始初始化wxauto库...")
            
            with self._lock:
                # 导入wxauto库
                try:
                    import wxauto
                    logger.info("wxauto库导入成功")
                except ImportError as e:
                    logger.error(f"wxauto库导入失败: {e}")
                    return False
                
                # 创建微信实例
                try:
                    self._wx_instance = wxauto.WeChat()
                    if not self._wx_instance:
                        logger.error("微信实例创建失败")
                        return False
                    
                    logger.info("微信实例创建成功")
                    
                except Exception as e:
                    logger.error(f"创建微信实例失败: {e}")
                    return False
                
                # 获取窗口信息
                self._window_name = self._get_window_name()
                self._library_type = "wxauto"
                
                # 验证连接
                if self._verify_connection():
                    self._is_connected = True
                    self._initialized = True
                    self._last_check_time = time.time()
                    
                    info = {
                        'window_name': self._window_name,
                        'library_type': self._library_type,
                        'status': 'connected'
                    }
                    
                    logger.info(f"wxauto初始化成功: {self._window_name}")
                    self.instance_initialized.emit(True, "初始化成功", info)
                    self.connection_status_changed.emit(True, "连接成功")
                    
                    return True
                else:
                    logger.error("微信连接验证失败")
                    return False
                    
        except Exception as e:
            logger.error(f"初始化wxauto失败: {e}")
            self.instance_initialized.emit(False, f"初始化失败: {str(e)}", {})
            return False
    
    def _get_window_name(self) -> str:
        """获取微信窗口名称"""
        try:
            if not self._wx_instance:
                return "未知"
            
            # 尝试多种方式获取窗口名称
            for attr_name in ['nickname', 'name', 'window_name', 'title', 'Name']:
                if hasattr(self._wx_instance, attr_name):
                    attr_value = getattr(self._wx_instance, attr_name)
                    if attr_value and str(attr_value).strip():
                        return str(attr_value).strip()
            
            return "微信"
            
        except Exception as e:
            logger.warning(f"获取窗口名称失败: {e}")
            return "微信"
    
    def _verify_connection(self) -> bool:
        """验证微信连接"""
        try:
            if not self._wx_instance:
                return False
            
            # 尝试获取会话列表来验证连接
            if hasattr(self._wx_instance, 'GetSessionList'):
                sessions = self._wx_instance.GetSessionList()
                return sessions is not None
            
            # 如果没有GetSessionList方法，假设连接正常
            return True
            
        except Exception as e:
            logger.warning(f"验证微信连接失败: {e}")
            return False
    
    # IWxautoManager接口实现
    
    def get_instance(self):
        """获取微信实例"""
        with self._lock:
            if not self._initialized or not self._wx_instance:
                logger.warning("微信实例未初始化")
                return None
            return self._wx_instance
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        current_time = time.time()
        
        # 如果距离上次检查超过检查间隔，重新检查
        if current_time - self._last_check_time > self._check_interval:
            self._verify_connection()
            self._last_check_time = current_time
        
        return self._is_connected
    
    def send_message(self, chat_name: str, message: str) -> bool:
        """发送消息"""
        try:
            wx_instance = self.get_instance()
            if not wx_instance:
                self.message_sent.emit(chat_name, False, "微信实例未初始化")
                return False

            # 发送消息并检查返回值
            logger.info(f"准备发送消息到: '{chat_name}' - 内容: {message[:50]}...")

            # 优先使用已监听的Chat对象发送消息，避免重新搜索和打开窗口
            if chat_name in self._listen_chats:
                try:
                    chat_obj = self._listen_chats[chat_name]
                    logger.info(f"使用已监听的Chat对象发送消息: '{chat_name}'")
                    result = chat_obj.SendMsg(message)
                    logger.info(f"Chat对象SendMsg调用完成: 目标='{chat_name}', 返回结果={result} (类型: {type(result)})")
                except Exception as e:
                    logger.warning(f"使用Chat对象发送失败: {e}, 回退到ChatWith方式")
                    # 如果Chat对象发送失败，回退到原来的方式
                    chat_obj = None
                else:
                    # Chat对象发送成功，跳过ChatWith方式
                    chat_obj = "success"
            else:
                chat_obj = None

            # 如果没有监听的Chat对象或Chat对象发送失败，使用ChatWith方式
            if not chat_obj:
                try:
                    # 使用 ChatWith 方法切换到目标聊天
                    switch_result = wx_instance.ChatWith(chat_name)
                    logger.info(f"切换到聊天窗口: '{chat_name}', 结果: {switch_result}")

                    # 短暂等待确保切换完成
                    time.sleep(0.5)

                except Exception as e:
                    logger.warning(f"切换聊天窗口失败: {e}, 尝试直接发送")

                # 发送消息
                result = wx_instance.SendMsg(message, chat_name)
                logger.info(f"SendMsg调用完成: 目标='{chat_name}', 返回结果={result} (类型: {type(result)})")

            # 检查发送结果
            if result is None:
                # 如果返回None，可能是旧版本的wxauto，尝试不检查返回值
                logger.warning("SendMsg返回None，可能是旧版本wxauto，假设发送成功")
                self.message_sent.emit(chat_name, True, "发送成功（未验证）")
                return True
            elif hasattr(result, 'is_success') and result.is_success:
                logger.info(f"消息发送成功: {chat_name} - {message[:50]}...")
                self.message_sent.emit(chat_name, True, "发送成功")
                return True
            elif hasattr(result, 'is_success') and not result.is_success:
                error_msg = f"消息发送失败: {result.get('message', '未知错误')}"
                logger.error(error_msg)
                self.message_sent.emit(chat_name, False, error_msg)
                return False
            else:
                # 如果result不是WxResponse对象，尝试其他方式判断
                if result:
                    logger.info(f"消息发送成功（非标准返回值）: {chat_name} - {message[:50]}...")
                    self.message_sent.emit(chat_name, True, "发送成功")
                    return True
                else:
                    error_msg = f"消息发送失败: 返回值为假值 {result}"
                    logger.error(error_msg)
                    self.message_sent.emit(chat_name, False, error_msg)
                    return False

        except Exception as e:
            error_msg = f"发送消息异常: {str(e)}"
            logger.error(error_msg)
            self.message_sent.emit(chat_name, False, error_msg)
            return False
    
    def get_messages(self, chat_name: str) -> List[Dict[str, Any]]:
        """获取消息 - 按照旧版实现方式"""
        try:
            wx_instance = self.get_instance()
            if not wx_instance:
                return []

            # 直接调用GetListenMessage(chat_name)，这是正确的方式
            logger.debug(f"正在调用GetListenMessage('{chat_name}')...")

            try:
                messages = wx_instance.GetListenMessage(chat_name)
                logger.debug(f"GetListenMessage调用完成，结果类型: {type(messages)}, 内容: {messages}")
            except Exception as e:
                # 对于常见的wxauto错误，降低日志级别
                if any(error_text in str(e) for error_text in [
                    "Find Control Timeout",
                    "dictionary changed size during iteration",
                    "控件查找超时"
                ]):
                    logger.debug(f"获取消息时出现预期错误: {e}")
                else:
                    logger.warning(f"获取消息失败: {e}")
                return []

            if not messages:
                logger.debug(f"从 {chat_name} 未获取到消息")
                return []

            # 确保messages是列表
            if not isinstance(messages, list):
                logger.debug(f"消息不是列表格式，转换为列表: {type(messages)}")
                messages = [messages] if messages else []

            # 处理消息
            filtered_messages = []
            for msg in messages:
                try:
                    # 检查消息类型，只处理friend类型的消息（避免系统消息和自己发送的消息）
                    msg_type = getattr(msg, 'type', '')
                    if msg_type == 'friend':
                        message_data = {
                            'sender': getattr(msg, 'sender', ''),
                            'sender_remark': getattr(msg, 'sender_remark', ''),
                            'content': getattr(msg, 'content', ''),
                            'type': msg_type,
                            'time': getattr(msg, 'time', ''),
                            'chat_name': chat_name
                        }
                        filtered_messages.append(message_data)
                        logger.info(f"收到新消息: {message_data['sender']} - {message_data['content'][:50]}...")
                except Exception as e:
                    logger.debug(f"处理单条消息失败，跳过: {e}")
                    continue

            if filtered_messages:
                self.messages_received.emit(chat_name, filtered_messages)
                logger.info(f"从 {chat_name} 获取到 {len(filtered_messages)} 条新消息")

            return filtered_messages

        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            return []

    def _message_callback(self, message, chat) -> None:
        """消息回调函数，处理从AddListenChat接收到的消息

        Args:
            message: Message对象，包含消息内容和属性
            chat: Chat对象或聊天名称字符串
        """
        try:
            # 获取聊天名称
            if hasattr(chat, 'nickname'):
                chat_name = chat.nickname
            elif hasattr(chat, 'name'):
                chat_name = chat.name
            elif isinstance(chat, str):
                chat_name = chat
            else:
                # 尝试从字符串表示中提取聊天名称
                chat_str = str(chat)
                if '"' in chat_str:
                    # 从 '<wxauto - Chat object("张杰")>' 中提取 "张杰"
                    import re
                    match = re.search(r'"([^"]+)"', chat_str)
                    if match:
                        chat_name = match.group(1)
                    else:
                        chat_name = chat_str
                else:
                    chat_name = chat_str

            # 将Message对象转换为字典格式，与现有系统兼容
            message_data = {
                'content': getattr(message, 'content', ''),
                'type': getattr(message, 'type', 'unknown'),
                'attr': getattr(message, 'attr', 'unknown'),
                'sender': getattr(message, 'sender', ''),
                'sender_remark': getattr(message, 'sender_remark', ''),
                'id': getattr(message, 'id', ''),
                'message_type_name': getattr(message, 'message_type_name', ''),
                'timestamp': time.time()  # 添加时间戳
            }

            logger.info(f"收到新消息回调: {chat_name} - {message_data['content'][:50]}...")

            # 发出消息接收信号，与现有系统集成
            self.messages_received.emit(chat_name, [message_data])

        except Exception as e:
            logger.error(f"处理消息回调失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def add_listen_chat(self, chat_name: str) -> bool:
        """添加监听聊天"""
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                wx_instance = self.get_instance()
                if not wx_instance:
                    logger.warning(f"微信实例未初始化，无法添加监听聊天: {chat_name}")
                    return False

                with self._lock:
                    # 移除旧的监听（如果存在）
                    try:
                        wx_instance.RemoveListenChat(chat_name)
                        time.sleep(0.5)  # 短暂等待确保移除完成
                    except Exception as e:
                        logger.debug(f"移除旧监听时出现错误（可忽略）: {e}")

                    # 添加新的监听，传入回调函数
                    try:
                        result = wx_instance.AddListenChat(chat_name, self._message_callback)
                        time.sleep(0.5)  # 短暂等待确保添加完成

                        # 保存Chat对象引用，用于后续直接发送消息
                        if hasattr(result, 'SendMsg'):  # 确认返回的是Chat对象
                            self._listen_chats[chat_name] = result
                            logger.info(f"保存Chat对象引用: {chat_name}")

                        # 启动监听功能
                        wx_instance.StartListening()
                        logger.info(f"添加监听聊天成功并启动监听: {chat_name}, 结果: {result}")
                        return True
                    except Exception as e:
                        if "Find Control Timeout" in str(e):
                            logger.warning(f"添加监听聊天超时 (尝试 {attempt + 1}/{max_retries}): {chat_name}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay * (attempt + 1))
                                continue
                        else:
                            raise e

            except Exception as e:
                error_msg = f"添加监听聊天失败 (尝试 {attempt + 1}/{max_retries}): {chat_name} - {e}"
                if attempt == max_retries - 1:
                    logger.error(error_msg)
                else:
                    logger.warning(error_msg)
                    time.sleep(retry_delay * (attempt + 1))

        return False
    
    def remove_listen_chat(self, chat_name: str) -> bool:
        """移除监听聊天"""
        max_retries = 2
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                wx_instance = self.get_instance()
                if not wx_instance:
                    logger.warning(f"微信实例未初始化，无法移除监听聊天: {chat_name}")
                    return False

                with self._lock:
                    wx_instance.RemoveListenChat(chat_name)
                    time.sleep(0.3)  # 短暂等待确保移除完成

                    # 清理保存的Chat对象引用
                    if chat_name in self._listen_chats:
                        del self._listen_chats[chat_name]
                        logger.info(f"清理Chat对象引用: {chat_name}")

                    logger.info(f"移除监听聊天成功: {chat_name}")
                    return True

            except Exception as e:
                error_msg = f"移除监听聊天失败 (尝试 {attempt + 1}/{max_retries}): {chat_name} - {e}"
                if attempt == max_retries - 1:
                    logger.error(error_msg)
                else:
                    logger.warning(error_msg)
                    time.sleep(retry_delay)

        return False
