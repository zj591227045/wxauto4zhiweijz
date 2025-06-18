"""
纯净的消息监听服务
只负责监听微信消息，不处理记账和回复逻辑
职责：
1. 监听微信消息
2. 过滤和去重消息
3. 发出消息接收信号
"""

import threading
import time
import logging
from typing import Dict, List, Set
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

class CleanMessageMonitor(QObject):
    """纯净的消息监听服务"""

    # 信号定义
    message_received = pyqtSignal(str, str, str)  # chat_name, content, sender_name
    error_occurred = pyqtSignal(str)  # error_message
    status_changed = pyqtSignal(bool)  # is_running

    def __init__(self):
        super().__init__()
        self.wx_instance = None
        self.is_running = False
        self.monitored_chats = []
        self.monitor_threads = {}
        self.stop_events = {}
        self.check_interval = 5  # 5秒检查一次

        # 消息去重：记录已处理的消息内容
        self.processed_messages = {}  # chat_name -> Set[message_content]

        # 状态管理器
        self.state_manager = None
        self._init_state_manager()

        # 初始化微信
        self._init_wechat()

    def _init_state_manager(self):
        """初始化状态管理器"""
        try:
            from app.utils.state_manager import state_manager
            self.state_manager = state_manager
            logger.info("状态管理器初始化成功")
        except Exception as e:
            logger.error(f"状态管理器初始化失败: {e}")

    def _init_wechat(self):
        """初始化微信实例"""
        try:
            from app.wechat import wechat_manager
            success = wechat_manager.initialize()
            if success:
                self.wx_instance = wechat_manager.get_instance()
                logger.info("微信实例初始化成功")
            else:
                logger.error("微信实例初始化失败")
                self.error_occurred.emit("微信实例初始化失败")
        except Exception as e:
            logger.error(f"初始化微信失败: {e}")
            self.error_occurred.emit(f"初始化微信失败: {e}")
    
    def add_chat_target(self, chat_name: str) -> bool:
        """添加监听对象"""
        if chat_name not in self.monitored_chats:
            self.monitored_chats.append(chat_name)
            # 初始化消息去重集合
            self.processed_messages[chat_name] = set()
            logger.info(f"添加监听对象: {chat_name}")
            return True
        return False
    
    def remove_chat_target(self, chat_name: str) -> bool:
        """移除监听对象"""
        if chat_name in self.monitored_chats:
            self.monitored_chats.remove(chat_name)
            self.stop_chat_monitoring(chat_name)
            # 清理消息去重集合
            if chat_name in self.processed_messages:
                del self.processed_messages[chat_name]
            logger.info(f"移除监听对象: {chat_name}")
            return True
        return False
    
    def start_monitoring(self) -> bool:
        """开始监控"""
        if self.is_running:
            logger.warning("监控已在运行中")
            return False
        
        if not self.monitored_chats:
            logger.warning("没有配置要监控的聊天")
            return False
        
        if not self.wx_instance:
            logger.error("微信实例未初始化")
            return False
        
        try:
            # 启动所有聊天对象的监控
            success_count = 0
            for chat_name in self.monitored_chats:
                if self.start_chat_monitoring(chat_name):
                    success_count += 1
            
            if success_count > 0:
                self.is_running = True
                self.status_changed.emit(True)

                # 更新监控状态
                if self.state_manager:
                    self.state_manager.update_monitoring_status(
                        is_active=True,
                        monitored_chats=self.monitored_chats,
                        check_interval=self.check_interval
                    )

                logger.info(f"消息监控已启动，成功启动 {success_count}/{len(self.monitored_chats)} 个聊天对象")
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
        """启动指定聊天对象的监控"""
        if not self.wx_instance:
            logger.error("微信实例未初始化")
            return False

        if chat_name in self.monitor_threads and self.monitor_threads[chat_name].is_alive():
            logger.warning(f"聊天对象已在监控中: {chat_name}")
            return True

        try:
            # 添加监听对象到微信
            try:
                # 先移除旧的监听对象
                self.wx_instance.RemoveListenChat(chat_name)
            except:
                pass

            # 添加新的监听对象
            self.wx_instance.AddListenChat(chat_name)
            logger.info(f"已添加监听对象: {chat_name}")

            # 清空历史消息 - 关键步骤！
            try:
                logger.info(f"清空{chat_name}的历史消息...")
                initial_messages = self.wx_instance.GetListenMessage(chat_name)
                if initial_messages:
                    logger.info(f"清空了{len(initial_messages)}条历史消息")
                else:
                    logger.info("没有历史消息需要清空")
            except Exception as e:
                logger.warning(f"清空历史消息失败: {e}")

            # 创建停止事件
            stop_event = threading.Event()
            self.stop_events[chat_name] = stop_event

            # 启动监控线程
            monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(chat_name, stop_event),
                daemon=True,
                name=f"CleanMonitor-{chat_name}"
            )
            monitor_thread.start()
            self.monitor_threads[chat_name] = monitor_thread

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
            for chat_name in list(self.monitored_chats):
                self.stop_chat_monitoring(chat_name)
            
            self.is_running = False
            self.status_changed.emit(False)

            # 更新监控状态
            if self.state_manager:
                self.state_manager.update_monitoring_status(
                    is_active=False,
                    monitored_chats=[],
                    check_interval=self.check_interval
                )

            logger.info("消息监控已停止")
        
        except Exception as e:
            error_msg = f"停止监控失败: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
    
    def stop_chat_monitoring(self, chat_name: str) -> bool:
        """停止指定聊天对象的监控"""
        try:
            # 停止监控线程
            if chat_name in self.stop_events:
                self.stop_events[chat_name].set()
            
            # 等待线程结束
            if chat_name in self.monitor_threads:
                thread = self.monitor_threads[chat_name]
                if thread.is_alive():
                    thread.join(timeout=5)
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
            
            logger.info(f"成功停止聊天监控: {chat_name}")
            return True
        
        except Exception as e:
            error_msg = f"停止聊天监控失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False
    
    def _monitor_loop(self, chat_name: str, stop_event: threading.Event):
        """监控循环 - 完全简化版本"""
        try:
            logger.info(f"开始简化监控循环: {chat_name}")

            loop_count = 0
            last_status_update = time.time()

            while not stop_event.is_set():
                try:
                    loop_count += 1
                    logger.debug(f"[{chat_name}] 第{loop_count}次检查")
                    
                    # 获取监听消息
                    messages = self.wx_instance.GetListenMessage(chat_name)

                    # 添加详细的调试信息
                    logger.debug(f"[{chat_name}] GetListenMessage返回: {type(messages)} - {messages}")

                    if messages and isinstance(messages, list):
                        logger.info(f"[{chat_name}] 获取到{len(messages)}条消息: {messages}")

                        for message in messages:
                            logger.debug(f"[{chat_name}] 处理消息: {type(message)} - {message}")

                            # 根据wxauto文档，只处理friend类型的消息，自动过滤系统消息、时间消息、撤回消息和自己的消息
                            if hasattr(message, 'type') and message.type == 'friend':
                                # 提取消息内容
                                if hasattr(message, 'content'):
                                    content = message.content
                                elif hasattr(message, '__str__'):
                                    content = str(message)
                                else:
                                    content = message

                                # 提取发送者信息 - 优先使用sender_remark（备注名），如果没有则使用sender
                                sender_name = None
                                if hasattr(message, 'sender_remark') and message.sender_remark:
                                    sender_name = message.sender_remark
                                    logger.info(f"[{chat_name}] 使用发送者备注名: {sender_name}")
                                elif hasattr(message, 'sender') and message.sender:
                                    sender_name = message.sender
                                    logger.info(f"[{chat_name}] 使用发送者名称: {sender_name}")
                                else:
                                    sender_name = chat_name  # 兜底使用聊天对象名称
                                    logger.info(f"[{chat_name}] 使用聊天对象名称作为发送者: {sender_name}")

                                logger.info(f"[{chat_name}] 解析朋友消息: 发送者={sender_name}, 内容={content}")

                                # 检查内容是否有效
                                if not content or not isinstance(content, str) or content.strip() == '':
                                    logger.debug(f"[{chat_name}] 跳过空消息")
                                    continue

                                # 过滤系统自己发送的回复消息
                                if self._is_system_reply_message(content):
                                    logger.debug(f"[{chat_name}] 跳过系统回复消息: {content[:50]}...")
                                    continue

                                # 简单去重：检查是否已处理过这条消息
                                message_key = f"{sender_name}:{content}"
                                if message_key not in self.processed_messages[chat_name]:
                                    logger.info(f"[{chat_name}] 处理新朋友消息: {sender_name} - {content}")

                                    # 添加到已处理集合
                                    self.processed_messages[chat_name].add(message_key)

                                    # 发出消息接收信号（包含发送者信息）
                                    self.message_received.emit(chat_name, content, sender_name)
                                    logger.info(f"[{chat_name}] 发出消息接收信号: {sender_name} - {content[:50]}...")
                                else:
                                    logger.debug(f"[{chat_name}] 跳过重复消息: {content}")
                            else:
                                # 不是friend类型的消息，跳过处理
                                message_type = getattr(message, 'type', 'unknown')
                                logger.debug(f"[{chat_name}] 跳过非朋友消息，类型: {message_type}")
                    
                    # 定期更新监控状态和微信状态（每次循环都更新）
                    current_time = time.time()
                    if self.state_manager and (current_time - last_status_update) >= 2:  # 每2秒更新一次状态
                        try:
                            # 检查微信在线状态
                            wechat_online = self.check_wechat_status()

                            # 更新监控状态
                            self.state_manager.update_monitoring_status(
                                is_active=True,
                                monitored_chats=self.monitored_chats,
                                check_interval=self.check_interval
                            )
                            last_status_update = current_time
                            logger.debug(f"[{chat_name}] 更新监控状态，微信在线: {wechat_online}")
                        except Exception as e:
                            logger.warning(f"[{chat_name}] 更新监控状态失败: {e}")

                    # 等待下次检查
                    stop_event.wait(self.check_interval)
                
                except Exception as e:
                    logger.error(f"[{chat_name}] 监控循环异常: {e}")
                    self.error_occurred.emit(f"[{chat_name}] 监控异常: {e}")
                    stop_event.wait(10)  # 异常时等待更长时间
            
            logger.info(f"监控循环结束: {chat_name}")
        
        except Exception as e:
            logger.error(f"[{chat_name}] 监控循环启动失败: {e}")
            self.error_occurred.emit(f"[{chat_name}] 监控启动失败: {e}")
    
    def check_wechat_status(self) -> bool:
        """检查微信状态"""
        try:
            if not self.wx_instance:
                logger.debug("微信实例不存在")
                return False

            # 使用 wx.IsOnline() 检查微信在线状态
            is_online = self.wx_instance.IsOnline()
            logger.debug(f"微信在线状态: {is_online}")

            # 更新微信状态到状态管理器
            if self.state_manager:
                try:
                    status = 'online' if is_online else 'offline'
                    self.state_manager.update_wechat_status(
                        status=status,
                        library_type='wxauto'
                    )
                except Exception as e:
                    logger.warning(f"更新微信状态失败: {e}")

            return is_online
        except Exception as e:
            logger.error(f"检查微信状态失败: {e}")

            # 更新错误状态
            if self.state_manager:
                try:
                    self.state_manager.update_wechat_status(
                        status='error',
                        error_message=str(e),
                        library_type='wxauto'
                    )
                except Exception:
                    pass

            return False

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

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        stats = {}
        for chat_name in self.monitored_chats:
            stats[chat_name] = {
                'processed_messages': len(self.processed_messages.get(chat_name, set())),
                'is_monitoring': chat_name in self.monitor_threads and self.monitor_threads[chat_name].is_alive()
            }
        return stats
