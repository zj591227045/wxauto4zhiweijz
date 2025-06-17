"""
消息监控服务 - 简化版本
直接使用wxautox库进行微信消息监听，移除Flask API依赖
"""

import threading
import logging
from typing import Dict, List
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

@dataclass
class MonitorConfig:
    """监控配置"""
    check_interval: int = 5  # 检查间隔（秒）
    enabled: bool = False
    monitored_chats: List[str] = None
    wechat_lib: str = "wxautox"  # 使用的微信库

    def __post_init__(self):
        if self.monitored_chats is None:
            self.monitored_chats = []

class MessageMonitor(QObject):
    """消息监控器 - 简化版本，直接使用wxautox"""

    # 信号定义
    message_received = pyqtSignal(str, str)  # 聊天名称, 消息内容
    accounting_result = pyqtSignal(str, bool, str)  # 聊天名称, 成功状态, 结果消息
    status_changed = pyqtSignal(bool)  # 监控状态变化
    error_occurred = pyqtSignal(str)  # 错误信息
    chat_status_changed = pyqtSignal(str, bool)  # 聊天对象状态变化
    statistics_updated = pyqtSignal(str, dict)  # 统计信息更新

    def __init__(self, accounting_service=None):
        super().__init__()
        self.accounting_service = accounting_service
        self.config = MonitorConfig()
        self.is_running = False

        # 微信实例
        self.wx_instance = None

        # 监控线程管理
        self.monitor_threads = {}  # chat_name -> thread
        self.stop_events = {}      # chat_name -> stop_event

        # 统计信息
        self.statistics = {}       # chat_name -> stats

        # 简化版消息处理器
        from app.services.simple_message_processor import SimpleMessageProcessor
        self.message_processor = SimpleMessageProcessor()

        # 从状态管理器获取微信库配置
        self._load_wechat_config()

        # 初始化微信
        self._init_wechat()

    def _load_wechat_config(self):
        """从配置文件加载微信配置"""
        try:
            from app.utils.config_manager import ConfigManager
            config_manager = ConfigManager()
            config = config_manager.load_config()

            # 获取库类型，默认使用wxauto（无需授权）
            library_type = config.app.wechat_lib
            self.config.wechat_lib = library_type

            # 同时加载其他监控配置
            self.config.monitored_chats = config.wechat_monitor.monitored_chats
            self.config.check_interval = config.wechat_monitor.check_interval

            logger.info(f"从配置文件加载微信库类型: {library_type}")
            logger.info(f"监控聊天对象: {self.config.monitored_chats}")

        except Exception as e:
            logger.warning(f"加载微信配置失败，使用默认配置: {e}")
            self.config.wechat_lib = "wxauto"  # 默认使用wxauto

    def _init_wechat(self):
        """初始化微信实例"""
        try:
            # 首先尝试使用全局的微信管理器实例
            try:
                from app.wechat import wechat_manager
                self.wx_instance = wechat_manager.get_instance()

                if self.wx_instance and hasattr(self.wx_instance, '_instance') and self.wx_instance._instance:
                    logger.info(f"{self.config.wechat_lib}微信实例初始化成功（使用wechat_manager）")
                    return
                else:
                    logger.warning("wechat_manager中没有可用的微信实例，尝试直接创建")
            except Exception as e:
                logger.warning(f"无法使用wechat_manager: {e}，尝试直接创建微信实例")

            # 如果无法使用wechat_manager，则直接创建微信实例
            if self.config.wechat_lib == "wxautox":
                from wxautox import WeChat
                logger.info("正在创建wxautox微信实例...")
                self.wx_instance = WeChat()
                logger.info("wxautox微信实例创建完成")

                # 验证微信实例是否正确初始化
                try:
                    # 尝试获取会话列表来验证连接
                    sessions = self.wx_instance.GetSessionList()
                    if sessions:
                        logger.info(f"wxautox微信实例初始化成功，找到 {len(sessions)} 个会话")
                    else:
                        logger.warning("wxautox微信实例创建成功，但未找到会话列表")
                except Exception as e:
                    logger.error(f"wxautox微信实例验证失败: {e}")
                    raise
            else:
                from wxauto import WeChat
                logger.info("正在创建wxauto微信实例...")
                self.wx_instance = WeChat()
                logger.info("wxauto微信实例创建完成")

                # 验证微信实例是否正确初始化
                try:
                    # 尝试获取会话列表来验证连接
                    sessions = self.wx_instance.GetSessionList()
                    if sessions:
                        logger.info(f"wxauto微信实例初始化成功，找到 {len(sessions)} 个会话")
                    else:
                        logger.warning("wxauto微信实例创建成功，但未找到会话列表")
                except Exception as e:
                    logger.error(f"wxauto微信实例验证失败: {e}")
                    raise

        except ImportError as e:
            error_msg = f"导入微信库失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
        except Exception as e:
            error_msg = f"微信初始化失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def check_wechat_status(self) -> bool:
        """检查微信连接状态"""
        if not self.wx_instance:
            logger.error("微信实例为空")
            return False

        logger.info("开始检查微信连接状态...")

        try:
            # 首先尝试使用微信管理器的连接检查方法
            try:
                from app.wechat import wechat_manager
                if hasattr(self.wx_instance, '_instance') and self.wx_instance._instance:
                    # 如果使用的是wechat_manager的实例
                    logger.info("使用wechat_manager检查连接状态")
                    result = wechat_manager.check_connection()
                    logger.info(f"wechat_manager连接检查结果: {result}")
                    if result:
                        return True
            except Exception as e:
                logger.debug(f"无法使用wechat_manager检查连接: {e}")

            # 如果是直接创建的微信实例，使用多种方法检查连接
            logger.info("使用直接方法检查微信连接状态")

            # 方法1：尝试GetSessionList
            try:
                logger.info("尝试GetSessionList方法...")
                sessions = self.wx_instance.GetSessionList()
                if sessions:
                    logger.info(f"GetSessionList成功，找到 {len(sessions)} 个会话")
                    return True
                else:
                    logger.warning("GetSessionList返回空列表，但微信可能仍然可用")
            except Exception as e:
                logger.warning(f"GetSessionList检查失败: {e}")

            # 方法2：尝试获取当前聊天信息
            try:
                logger.info("尝试CurrentChat方法...")
                current_chat = self.wx_instance.CurrentChat()
                if current_chat:
                    logger.info(f"CurrentChat成功，当前聊天: {current_chat}")
                    return True
                else:
                    logger.warning("CurrentChat返回空值，但微信可能仍然可用")
            except Exception as e:
                logger.warning(f"CurrentChat检查失败: {e}")

            # 如果所有检查都失败，但微信实例存在，我们假设它是可用的
            # 这是因为有时候微信API在初始化后需要一些时间才能正常工作
            logger.warning("所有连接检查方法都失败，但微信实例存在，假设可用")
            logger.info("将尝试启动监控，如果微信真的不可用，监控循环会报错")
            return True

        except Exception as e:
            logger.error(f"检查微信状态时发生异常: {e}")
            return False

    def update_config(self, config: MonitorConfig):
        """更新监控配置"""
        old_lib = self.config.wechat_lib
        self.config = config

        # 如果库类型发生变化，重新初始化微信实例
        if old_lib != self.config.wechat_lib:
            logger.info(f"微信库类型变化: {old_lib} -> {self.config.wechat_lib}")
            self._init_wechat()

    def add_chat_target(self, chat_name: str) -> bool:
        """
        添加聊天监控目标

        Args:
            chat_name: 聊天对象名称

        Returns:
            True表示添加成功，False表示失败
        """
        if chat_name not in self.config.monitored_chats:
            self.config.monitored_chats.append(chat_name)
            logger.info(f"添加聊天监控目标: {chat_name}")
            return True
        else:
            logger.warning(f"聊天监控目标已存在: {chat_name}")
            return False

    def remove_chat_target(self, chat_name: str) -> bool:
        """
        移除聊天监控目标

        Args:
            chat_name: 聊天对象名称

        Returns:
            True表示移除成功，False表示失败
        """
        if chat_name in self.config.monitored_chats:
            self.config.monitored_chats.remove(chat_name)

            # 如果正在监控，先停止监控
            self.stop_chat_monitoring(chat_name)

            logger.info(f"移除聊天监控目标: {chat_name}")
            return True
        else:
            logger.warning(f"聊天监控目标不存在: {chat_name}")
            return False

    def get_chat_targets(self) -> List[str]:
        """获取所有聊天监控目标"""
        return self.config.monitored_chats.copy()

    def is_chat_monitoring(self, chat_name: str) -> bool:
        """检查指定聊天对象是否正在监控"""
        return chat_name in self.monitor_threads and self.monitor_threads[chat_name].is_alive()

    def get_chat_statistics(self, chat_name: str) -> Dict:
        """获取指定聊天对象的统计信息"""
        return self.statistics.get(chat_name, {
            'total_messages': 0,
            'processed_messages': 0,
            'successful_accounting': 0,
            'failed_accounting': 0,
            'success_rate': 0.0
        })

    def get_all_chat_targets(self) -> List[str]:
        """获取所有聊天监控目标"""
        return self.config.monitored_chats.copy()

    def start_monitoring(self) -> bool:
        """开始监控"""
        if self.is_running:
            logger.warning("监控已在运行中")
            return False

        if not self.config.monitored_chats:
            logger.warning("没有配置要监控的聊天")
            return False

        if not self.wx_instance:
            logger.error("微信实例未初始化")
            return False

        try:
            # 启动所有聊天对象的监控
            success_count = 0
            for chat_name in self.config.monitored_chats:
                if self.start_chat_monitoring(chat_name):
                    success_count += 1
                else:
                    logger.warning(f"启动监控失败: {chat_name}")

            if success_count > 0:
                self.is_running = True
                self.status_changed.emit(True)
                logger.info(f"消息监控已启动，成功启动 {success_count}/{len(self.config.monitored_chats)} 个聊天对象")
                return True
            else:
                self.error_occurred.emit("所有聊天对象监控启动失败")
                return False

        except Exception as e:
            error_msg = f"启动监控失败: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def start_chat_monitoring(self, chat_name: str) -> bool:
        """
        启动指定聊天对象的监控

        Args:
            chat_name: 聊天对象名称

        Returns:
            True表示启动成功，False表示失败
        """
        if not self.wx_instance:
            logger.error("微信实例未初始化")
            return False

        if chat_name in self.monitor_threads and self.monitor_threads[chat_name].is_alive():
            logger.warning(f"聊天对象已在监控中: {chat_name}")
            return True

        try:
            # 确保聊天对象在列表中
            if chat_name not in self.config.monitored_chats:
                self.add_chat_target(chat_name)

            # 先尝试移除监听对象（如果存在）
            try:
                self.wx_instance.RemoveListenChat(chat_name)
                logger.info(f"已移除旧的监听对象: {chat_name}")
            except Exception as e:
                logger.debug(f"移除监听对象时出错（可能不存在）: {e}")

            # 添加监听对象到微信
            try:
                self.wx_instance.AddListenChat(chat_name)
                logger.info(f"已添加监听对象: {chat_name}")
            except Exception as e:
                # 如果添加监听对象失败，可能是聊天对象不存在或微信窗口问题
                error_msg = f"添加监听对象失败: {e}"
                logger.error(error_msg)

                # 尝试检查微信窗口状态
                try:
                    current_chat = self.wx_instance.CurrentChat()
                    if current_chat:
                        logger.info(f"当前微信聊天窗口: {current_chat}")
                    else:
                        logger.warning("微信当前没有打开聊天窗口")
                except Exception as check_e:
                    logger.warning(f"检查微信窗口状态失败: {check_e}")

                # 抛出异常，让上层处理
                raise Exception(f"无法添加监听对象 '{chat_name}': {e}")

            # 初始化统计信息
            self.statistics[chat_name] = {
                'total_messages': 0,
                'processed_messages': 0,
                'successful_accounting': 0,
                'failed_accounting': 0,
                'success_rate': 0.0
            }

            # 创建停止事件
            stop_event = threading.Event()
            self.stop_events[chat_name] = stop_event

            # 启动监控线程
            logger.info(f"正在创建监控线程: {chat_name}")
            monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(chat_name, stop_event),
                daemon=True,
                name=f"Monitor-{chat_name}"
            )

            logger.info(f"正在启动监控线程: {chat_name}")
            monitor_thread.start()
            self.monitor_threads[chat_name] = monitor_thread

            # 等待一小段时间，确保线程启动
            import time
            time.sleep(0.1)

            # 检查线程是否正常启动
            if monitor_thread.is_alive():
                logger.info(f"监控线程启动成功: {chat_name}, 线程ID: {monitor_thread.ident}")
            else:
                logger.error(f"监控线程启动失败: {chat_name}")
                return False

            # 发出状态变化信号
            self.chat_status_changed.emit(chat_name, True)

            logger.info(f"成功启动聊天监控: {chat_name}")
            return True

        except Exception as e:
            error_msg = f"启动聊天监控失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def stop_monitoring(self):
        """停止监控"""
        if not self.is_running:
            return

        try:
            # 停止所有聊天对象的监控
            for chat_name in list(self.config.monitored_chats):
                self.stop_chat_monitoring(chat_name)

            self.is_running = False
            self.status_changed.emit(False)
            logger.info("消息监控已停止")

        except Exception as e:
            error_msg = f"停止监控失败: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def stop_chat_monitoring(self, chat_name: str) -> bool:
        """
        停止指定聊天对象的监控

        Args:
            chat_name: 聊天对象名称

        Returns:
            True表示停止成功，False表示失败
        """
        try:
            # 停止监控线程
            if chat_name in self.stop_events:
                self.stop_events[chat_name].set()

            # 等待线程结束
            if chat_name in self.monitor_threads:
                thread = self.monitor_threads[chat_name]
                if thread.is_alive():
                    thread.join(timeout=5)  # 最多等待5秒
                del self.monitor_threads[chat_name]

            # 清理停止事件
            if chat_name in self.stop_events:
                del self.stop_events[chat_name]

            # 从微信移除监听对象
            if self.wx_instance:
                try:
                    self.wx_instance.RemoveListenChat(chat_name)
                    logger.info(f"已移除监听对象: {chat_name}")
                except Exception as e:
                    logger.warning(f"移除监听对象失败: {e}")

            # 发出状态变化信号
            self.chat_status_changed.emit(chat_name, False)

            logger.info(f"成功停止聊天监控: {chat_name}")

            # 检查是否还有其他聊天对象在监控中
            has_active_monitoring = any(
                self.is_chat_monitoring(chat)
                for chat in self.config.monitored_chats
            )

            if not has_active_monitoring and self.is_running:
                self.is_running = False
                self.status_changed.emit(False)

            return True

        except Exception as e:
            error_msg = f"停止聊天监控失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def _monitor_loop(self, chat_name: str, stop_event: threading.Event):
        """
        监控循环 - 简化版本

        Args:
            chat_name: 聊天对象名称
            stop_event: 停止事件
        """
        try:
            logger.info(f"开始监控循环: {chat_name}")
            logger.info(f"线程ID: {threading.current_thread().ident}, 线程名: {threading.current_thread().name}")

            # 检查必要的组件
            if not self.wx_instance:
                logger.error(f"[{chat_name}] 微信实例为空，监控循环无法启动")
                return

            if not hasattr(self, 'config') or not self.config:
                logger.error(f"[{chat_name}] 配置对象为空，监控循环无法启动")
                return

            logger.info(f"[{chat_name}] 检查间隔: {self.config.check_interval}秒")

            # 统计信息更新计数器（60秒更新一次）
            stats_update_counter = 0
            stats_update_interval = max(1, 60 // self.config.check_interval)  # 确保至少为1
            logger.info(f"[{chat_name}] 统计更新间隔: 每{stats_update_interval}次循环更新一次")

            loop_count = 0
            while not stop_event.is_set():
                try:
                    loop_count += 1
                    logger.info(f"[{chat_name}] 开始第{loop_count}次检查")

                    # 获取监听消息 - 添加详细调试
                    logger.info(f"[{chat_name}] 正在调用GetListenMessage('{chat_name}')...")

                    try:
                        messages = self.wx_instance.GetListenMessage(chat_name)
                        logger.info(f"[{chat_name}] GetListenMessage调用完成，结果: {messages}")
                    except Exception as e:
                        logger.error(f"[{chat_name}] GetListenMessage调用异常: {e}")
                        import traceback
                        logger.error(f"[{chat_name}] GetListenMessage异常详情: {traceback.format_exc()}")
                        continue

                    if messages:
                        logger.info(f"[{chat_name}] 获取到新消息，类型: {type(messages)}, 内容: {messages}")
                        # 处理新消息 - 根据实际返回格式进行处理
                        if isinstance(messages, list):
                            logger.info(f"[{chat_name}] 处理消息列表，共{len(messages)}条消息")
                            for message in messages:
                                # 检查消息格式
                                if isinstance(message, list) and len(message) >= 2:
                                    # 格式: ['张杰', '买饮料，4块钱']
                                    sender = message[0]
                                    content = message[1]
                                    logger.info(f"[{chat_name}] 解析消息: 发送者={sender}, 内容={content}")

                                    # 创建一个简单的消息对象来兼容现有处理逻辑
                                    class SimpleMessage:
                                        def __init__(self, sender, content):
                                            self.sender = sender
                                            self.content = content
                                            self.type = 'friend'  # 假设是朋友消息

                                    simple_msg = SimpleMessage(sender, content)
                                    self._process_single_message(chat_name, simple_msg)
                                elif hasattr(message, 'content'):
                                    # 如果是Message对象格式
                                    logger.info(f"[{chat_name}] 处理Message对象: {message}")
                                    self._process_single_message(chat_name, message)
                                else:
                                    logger.warning(f"[{chat_name}] 未知的消息格式: {type(message)} - {message}")
                        elif isinstance(messages, dict):
                            # 如果返回字典（未指定chat_name或多个聊天对象）
                            logger.info(f"[{chat_name}] 处理消息字典，共{len(messages)}个聊天窗口")
                            for chat_wnd, msg_list in messages.items():
                                if isinstance(msg_list, list):
                                    for message in msg_list:
                                        self._process_single_message(chat_name, message)
                        else:
                            logger.warning(f"[{chat_name}] 收到未知类型的消息数据: {type(messages)} - {messages}")

                    # 每60秒更新一次统计信息
                    stats_update_counter += 1
                    if stats_update_counter >= stats_update_interval:
                        self._update_statistics(chat_name)
                        stats_update_counter = 0

                    # 等待下次检查
                    logger.info(f"[{chat_name}] 等待{self.config.check_interval}秒后进行下次检查")
                    stop_event.wait(self.config.check_interval)
                    logger.info(f"[{chat_name}] 等待结束，准备下次检查")

                except Exception as e:
                    error_msg = f"监控循环异常: {str(e)}"
                    logger.error(f"[{chat_name}] {error_msg}")
                    import traceback
                    logger.error(f"[{chat_name}] 异常详情: {traceback.format_exc()}")
                    self.error_occurred.emit(f"[{chat_name}] {error_msg}")
                    # 发生异常时等待更长时间再重试
                    stop_event.wait(10)

            logger.info(f"监控循环结束: {chat_name}")

        except Exception as e:
            logger.error(f"[{chat_name}] 监控循环启动失败: {e}")
            import traceback
            logger.error(f"[{chat_name}] 启动失败详情: {traceback.format_exc()}")
            self.error_occurred.emit(f"[{chat_name}] 监控循环启动失败: {e}")

    def _process_single_message(self, chat_name: str, message):
        """
        处理单条消息

        Args:
            chat_name: 聊天对象名称
            message: 消息对象或消息数据
        """
        try:
            logger.info(f"[{chat_name}] 开始处理消息，消息类型: {type(message)}")

            # 检查消息格式并提取内容
            content = None
            sender = None

            if isinstance(message, list) and len(message) >= 2:
                # 格式: ['张杰', '买饮料，4块钱']
                sender_name = message[0]  # 这里通常已经是备注名或真实姓名
                content = message[1]
                logger.info(f"[{chat_name}] 从列表格式提取消息: 发送者={sender_name}, 内容={content}")
            elif hasattr(message, 'content'):
                # Message对象格式
                content = getattr(message, 'content', None)

                # 提取发送者信息 - 优先使用sender_remark（备注名），如果没有则使用sender
                sender_name = None
                if hasattr(message, 'sender_remark') and getattr(message, 'sender_remark', None):
                    sender_name = message.sender_remark
                    logger.info(f"[{chat_name}] 使用发送者备注名: {sender_name}")
                elif hasattr(message, 'sender') and getattr(message, 'sender', None):
                    sender_name = message.sender
                    logger.info(f"[{chat_name}] 使用发送者名称: {sender_name}")
                else:
                    sender_name = '未知发送者'
                    logger.info(f"[{chat_name}] 使用默认发送者名称: {sender_name}")

                msg_type = getattr(message, 'type', None)
                logger.info(f"[{chat_name}] 从Message对象提取消息: type={msg_type}, 发送者={sender_name}, 内容={content}")

                # 根据wxauto文档，只处理friend类型的消息，自动过滤系统消息、时间消息、撤回消息和自己的消息
                if msg_type != 'friend':
                    logger.debug(f"[{chat_name}] 跳过非朋友消息，类型: {msg_type}")
                    return

                # 检查消息对象的属性（用于调试）
                if hasattr(message, '__dict__'):
                    logger.debug(f"[{chat_name}] 消息属性: {message.__dict__}")
            else:
                logger.warning(f"[{chat_name}] 无法识别的消息格式: {type(message)} - {message}")
                return

            # 检查内容是否有效
            if not content or not isinstance(content, str) or not content.strip():
                logger.warning(f"[{chat_name}] 消息内容为空或无效，跳过处理")
                return

            # 过滤系统自己发送的回复消息
            if self._is_system_reply_message(content):
                logger.debug(f"[{chat_name}] 跳过系统回复消息: {content[:50]}...")
                return

            logger.info(f"[{chat_name}] 收到有效消息: {sender_name} - {content}")

            # 发出消息接收信号
            self.message_received.emit(chat_name, content)

            # 更新统计
            stats = self.statistics.get(chat_name, {})
            stats['total_messages'] = stats.get('total_messages', 0) + 1
            stats['processed_messages'] = stats.get('processed_messages', 0) + 1

            # 调用记账服务，传递发送者名称
            success, result_msg = self.message_processor.process_message(content, sender_name)

            # 更新统计
            if success:
                stats['successful_accounting'] = stats.get('successful_accounting', 0) + 1
            else:
                stats['failed_accounting'] = stats.get('failed_accounting', 0) + 1

            # 计算成功率
            total_accounting = stats.get('successful_accounting', 0) + stats.get('failed_accounting', 0)
            if total_accounting > 0:
                stats['success_rate'] = stats.get('successful_accounting', 0) / total_accounting

            # 发出记账结果信号
            self.accounting_result.emit(chat_name, success, result_msg)

            # 发送回复到微信（如果记账成功且有回复内容）
            if success and result_msg and not result_msg.startswith("信息与记账无关"):
                self._send_reply_to_wechat(chat_name, result_msg)

            self.statistics[chat_name] = stats

            logger.info(f"[{chat_name}] 消息处理完成")

        except Exception as e:
            logger.error(f"[{chat_name}] 处理消息失败: {e}")
            import traceback
            logger.error(f"[{chat_name}] 处理消息异常详情: {traceback.format_exc()}")
            self.error_occurred.emit(f"[{chat_name}] 处理消息失败: {e}")



    def _is_system_reply_message(self, content: str) -> bool:
        """
        判断是否是系统发送的回复消息

        Args:
            content: 消息内容

        Returns:
            True表示是系统回复消息，False表示不是
        """
        # 系统回复消息的特征（更精确的匹配）
        system_reply_patterns = [
            "✅ 记账成功！",  # 完整匹配记账成功消息
            "📝 明细：",
            "📅 日期：",
            "💸 方向：",
            "💰 金额：",
            "📊 预算：",
            "⚠️ 记账服务返回错误",
            "❌ 记账失败",
            "聊天与记账无关",
            "信息与记账无关"
        ]

        # 额外检查：如果消息包含多个系统特征，更可能是系统回复
        system_feature_count = 0
        for pattern in system_reply_patterns:
            if pattern in content:
                system_feature_count += 1

        # 如果包含2个或以上系统特征，认为是系统回复
        if system_feature_count >= 2:
            return True

        # 检查是否包含系统回复的特征
        for pattern in system_reply_patterns:
            if pattern in content:
                return True

        return False

    def _send_reply_to_wechat(self, chat_name: str, message: str) -> bool:
        """
        发送回复到微信

        Args:
            chat_name: 聊天对象名称
            message: 回复消息

        Returns:
            True表示发送成功，False表示失败
        """
        try:
            if not self.wx_instance:
                logger.error("微信实例未初始化")
                return False

            # 发送消息
            success = self.wx_instance.SendMsg(message, who=chat_name)
            if success:
                logger.info(f"[{chat_name}] 发送回复成功: {message[:50]}...")
            else:
                logger.warning(f"[{chat_name}] 发送回复失败: {message[:50]}...")

            return success

        except Exception as e:
            logger.error(f"发送回复失败: {e}")
            return False

    def _update_statistics(self, chat_name: str):
        """
        更新统计信息

        Args:
            chat_name: 聊天对象名称
        """
        if chat_name in self.statistics:
            stats = self.statistics[chat_name]
            self.statistics_updated.emit(chat_name, stats)

    # 兼容性方法
    def _add_listen_target(self, chat_name: str) -> bool:
        """添加监听目标（兼容性方法）"""
        return self.add_chat_target(chat_name)

    def _send_wechat_message(self, chat_name: str, message: str) -> bool:
        """发送微信消息（兼容性方法）"""
        return self._send_reply_to_wechat(chat_name, message)
