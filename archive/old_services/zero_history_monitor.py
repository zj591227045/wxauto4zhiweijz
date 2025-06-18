#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
零历史消息监听服务
彻底解决历史消息重复处理问题
"""

import threading
import time
import logging
from typing import Dict, Set
from PyQt6.QtCore import QObject, pyqtSignal

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

# 导入异步消息记录器
try:
    from app.utils.async_message_recorder import AsyncMessageRecorderManager
except ImportError:
    logger.warning("无法导入异步消息记录器，将使用同步方式")
    AsyncMessageRecorderManager = None

class ZeroHistoryMonitor(QObject):
    """零历史消息监听服务 - 彻底解决历史消息问题"""
    
    # 信号定义
    message_received = pyqtSignal(str, str)  # 聊天名称, 消息内容
    accounting_result = pyqtSignal(str, bool, str)  # 聊天名称, 成功状态, 结果消息
    error_occurred = pyqtSignal(str)  # 错误消息
    status_changed = pyqtSignal(bool)  # 运行状态
    
    def __init__(self):
        super().__init__()
        self.wx_instance = None
        self.message_processor = None
        self.monitor_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        self.processed_messages: Dict[str, Set[str]] = {}
        self.is_running = False
        self.window_name = None  # 微信窗口名称
        self.monitored_chats = []  # 添加监控聊天列表属性

        # 历史消息过滤器 - 记录启动时的消息ID
        self.startup_message_ids: Dict[str, Set[str]] = {}

        # 初始化异步消息记录器
        if AsyncMessageRecorderManager:
            self.async_recorder_manager = AsyncMessageRecorderManager(self)
            self.async_recorder_manager.recording_finished.connect(self._on_async_recording_finished)
            self.async_recorder_manager.progress_updated.connect(self._on_async_recording_progress)
        else:
            self.async_recorder_manager = None

        self._init_wx_instance()
        self._init_message_processor()
    
    def _init_wx_instance(self):
        """初始化微信实例"""
        try:
            # 尝试多种导入方式
            try:
                from app.utils.wxauto_manager import get_wx_instance
                self.wx_instance = get_wx_instance()
            except ImportError:
                # 直接导入wxauto
                import wxauto
                self.wx_instance = wxauto.WeChat()

            if self.wx_instance:
                # 获取微信窗口名称
                try:
                    # 尝试多种可能的属性名称
                    window_name = None

                    # 检查常见的属性名称
                    for attr_name in ['nickname', 'name', 'window_name', 'title', 'Name']:
                        if hasattr(self.wx_instance, attr_name):
                            attr_value = getattr(self.wx_instance, attr_name)
                            if attr_value and str(attr_value).strip():
                                window_name = str(attr_value).strip()
                                logger.debug(f"从属性 {attr_name} 获取到窗口名称: {window_name}")
                                break

                    # 如果还没有获取到，尝试调用方法
                    if not window_name:
                        for method_name in ['get_name', 'get_window_name', 'get_title']:
                            if hasattr(self.wx_instance, method_name):
                                try:
                                    method_result = getattr(self.wx_instance, method_name)()
                                    if method_result and str(method_result).strip():
                                        window_name = str(method_result).strip()
                                        logger.debug(f"从方法 {method_name} 获取到窗口名称: {window_name}")
                                        break
                                except:
                                    continue

                    # 如果仍然没有获取到，尝试从wxauto的输出中解析
                    if not window_name:
                        # 检查是否有其他可能的属性
                        logger.debug(f"wxauto实例属性: {[attr for attr in dir(self.wx_instance) if not attr.startswith('_')]}")
                        window_name = "助手"  # 根据日志，我们知道窗口名称是"助手"

                    self.window_name = window_name
                    logger.info(f"微信实例初始化成功，窗口名称: {self.window_name}")

                except Exception as e:
                    self.window_name = "助手"  # 使用默认值
                    logger.warning(f"获取窗口名称失败: {e}，使用默认值: {self.window_name}")
            else:
                logger.error("微信实例初始化失败")
        except Exception as e:
            logger.error(f"初始化微信实例失败: {e}")
    
    def _init_message_processor(self):
        """初始化消息处理器"""
        try:
            from app.services.simple_message_processor import SimpleMessageProcessor
            self.message_processor = SimpleMessageProcessor()
            logger.info("消息处理器初始化成功")
        except Exception as e:
            logger.error(f"初始化消息处理器失败: {e}")

    def _on_async_recording_finished(self, chat_name: str, success: bool, message: str, message_ids: set):
        """异步记录完成回调"""
        if success:
            # 更新启动消息ID集合
            self.startup_message_ids[chat_name] = message_ids
            logger.info(f"异步历史消息记录完成: {chat_name} - {message}")

            # 启动监控线程
            self._start_monitoring_thread(chat_name)
        else:
            logger.error(f"异步历史消息记录失败: {chat_name} - {message}")
            self.error_occurred.emit(f"历史消息记录失败: {message}")

    def _on_async_recording_progress(self, chat_name: str, progress_message: str):
        """异步记录进度回调"""
        logger.info(f"异步记录进度 [{chat_name}]: {progress_message}")

    def _start_monitoring_thread(self, chat_name: str):
        """启动监控线程"""
        try:
            # 创建停止事件
            stop_event = threading.Event()
            self.stop_events[chat_name] = stop_event

            # 启动监控线程
            monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(chat_name, stop_event),
                daemon=True,
                name=f"ZeroHistoryMonitor-{chat_name}"
            )
            monitor_thread.start()
            self.monitor_threads[chat_name] = monitor_thread

            logger.info(f"成功启动聊天监控线程: {chat_name}")
        except Exception as e:
            logger.error(f"启动监控线程失败: {e}")
            self.error_occurred.emit(f"启动监控线程失败: {e}")
    
    def check_wechat_status(self) -> bool:
        """检查微信状态"""
        return self.wx_instance is not None

    def get_wechat_info(self) -> dict:
        """获取微信信息"""
        return {
            'is_connected': self.wx_instance is not None,
            'window_name': self.window_name or "未连接",
            'library_type': 'wxauto',
            'status': 'online' if self.wx_instance else 'offline'
        }
    
    def add_chat_target(self, chat_name: str) -> bool:
        """添加监听对象"""
        try:
            if chat_name not in self.processed_messages:
                self.processed_messages[chat_name] = set()
            if chat_name not in self.startup_message_ids:
                self.startup_message_ids[chat_name] = set()
            if chat_name not in self.monitored_chats:
                self.monitored_chats.append(chat_name)
            logger.info(f"添加监听对象: {chat_name}")
            return True
        except Exception as e:
            logger.error(f"添加监听对象失败: {e}")
            return False
    
    def start_monitoring(self) -> bool:
        """启动监控"""
        try:
            if not self.wx_instance:
                logger.error("微信实例未初始化")
                return False
            
            # 启动所有聊天对象的监控
            success_count = 0
            for chat_name in self.processed_messages.keys():
                if self.start_chat_monitoring(chat_name):
                    success_count += 1
            
            if success_count > 0:
                self.is_running = True
                self.status_changed.emit(True)
                logger.info(f"监控启动成功，共启动 {success_count} 个目标")
                return True
            else:
                logger.error("没有成功启动任何监控目标")
                return False
                
        except Exception as e:
            error_msg = f"启动监控失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False
    
    def start_chat_monitoring(self, chat_name: str) -> bool:
        """启动指定聊天对象的监控（异步版本）"""
        if not self.wx_instance:
            logger.error("微信实例未初始化")
            return False

        if chat_name in self.monitor_threads and self.monitor_threads[chat_name].is_alive():
            logger.warning(f"聊天对象已在监控中: {chat_name}")
            return True

        try:
            # 添加监听对象到微信
            try:
                self.wx_instance.RemoveListenChat(chat_name)
            except:
                pass

            self.wx_instance.AddListenChat(chat_name)
            logger.info(f"已添加监听对象: {chat_name}")

            # 使用异步方式记录启动时的所有消息ID
            if self.async_recorder_manager:
                logger.info(f"开始异步记录{chat_name}的历史消息...")
                self.async_recorder_manager.start_recording(
                    self.wx_instance,
                    chat_name,
                    max_attempts=3,  # 减少到3次
                    interval=2       # 每2秒一次
                )
                # 异步记录完成后会通过回调启动监控线程
                return True
            else:
                # 如果异步记录器不可用，使用同步方式（但会阻塞）
                logger.warning("异步记录器不可用，使用同步方式记录历史消息")
                self._record_startup_messages_sync(chat_name)

                # 启动监控线程
                self._start_monitoring_thread(chat_name)
                return True

        except Exception as e:
            error_msg = f"启动聊天监控失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False
    
    def _record_startup_messages_sync(self, chat_name: str):
        """同步记录启动时的所有消息ID，用于过滤历史消息（备用方法）"""
        try:
            logger.info(f"开始同步记录{chat_name}的启动时历史消息...")

            # 减少尝试次数和等待时间
            max_attempts = 3  # 减少到3次
            total_messages = 0

            for attempt in range(max_attempts):
                logger.info(f"第{attempt + 1}次获取历史消息...")

                # 获取当前所有消息
                messages = self.wx_instance.GetListenMessage(chat_name)

                if messages and isinstance(messages, list):
                    batch_count = 0
                    for message in messages:
                        # 为每条消息生成唯一ID
                        message_id = self._generate_message_id(message)
                        if message_id not in self.startup_message_ids[chat_name]:
                            self.startup_message_ids[chat_name].add(message_id)
                            batch_count += 1

                    total_messages += batch_count
                    logger.info(f"第{attempt + 1}次获取到{len(messages)}条消息，其中{batch_count}条为新消息")

                    # 如果这次没有新消息，说明历史消息已经全部获取完毕
                    if batch_count == 0:
                        logger.info(f"历史消息获取完毕，共记录{total_messages}条历史消息")
                        break
                else:
                    logger.info(f"第{attempt + 1}次获取到空消息列表")

                # 等待2秒再次获取，确保所有历史消息都被处理
                if attempt < max_attempts - 1:  # 最后一次不等待
                    time.sleep(2)

            logger.info(f"历史消息记录完成，总计记录{len(self.startup_message_ids[chat_name])}条历史消息ID")

            # 减少等待时间从5秒到2秒
            logger.info("等待2秒，确保微信内部状态稳定...")
            time.sleep(2)
            logger.info("历史消息处理完成，开始监控新消息")

        except Exception as e:
            logger.warning(f"记录启动时消息ID失败: {e}")
    
    def _generate_message_id(self, message) -> str:
        """为消息生成唯一ID（简化稳定版）"""
        try:
            # 提取消息内容
            if hasattr(message, 'content'):
                content = str(message.content).strip()
            else:
                content = str(message).strip()

            # 提取发送者信息
            sender = "unknown"
            if hasattr(message, 'sender_remark') and message.sender_remark:
                sender = str(message.sender_remark).strip()
            elif hasattr(message, 'sender') and message.sender:
                sender = str(message.sender).strip()

            # 使用简单稳定的ID：发送者+内容的哈希
            import hashlib
            stable_content = f"{sender}:{content}"
            content_hash = hashlib.md5(stable_content.encode('utf-8')).hexdigest()

            return content_hash
        except Exception as e:
            logger.warning(f"生成消息ID失败: {e}")
            return f"error_{hash(str(message))}"
    
    def _monitor_loop(self, chat_name: str, stop_event: threading.Event):
        """监控循环"""
        logger.info(f"开始零历史监控循环: {chat_name}")
        
        while not stop_event.is_set():
            try:
                # 获取监听消息
                messages = self.wx_instance.GetListenMessage(chat_name)
                
                if messages and isinstance(messages, list):
                    logger.debug(f"[{chat_name}] 获取到{len(messages)}条消息")
                    
                    for message in messages:
                        # 生成消息ID
                        message_id = self._generate_message_id(message)
                        
                        # 关键过滤：跳过启动时记录的历史消息
                        if message_id in self.startup_message_ids[chat_name]:
                            logger.debug(f"[{chat_name}] 跳过历史消息: {message_id}")
                            continue
                        
                        # 处理新消息
                        self._process_new_message(chat_name, message)
                
                # 短暂休眠
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"[{chat_name}] 监控循环异常: {e}")
                time.sleep(5)
    
    def _process_new_message(self, chat_name: str, message):
        """处理新消息"""
        try:
            # 根据wxauto文档，只处理friend类型的消息，自动过滤系统消息、时间消息、撤回消息和自己的消息
            if hasattr(message, 'type') and message.type == 'friend':
                # 提取消息内容
                if hasattr(message, 'content'):
                    content = message.content
                else:
                    content = str(message)

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

                logger.info(f"[{chat_name}] 处理新朋友消息: {sender_name} - {content}")

                # 检查内容是否有效
                if not content or not isinstance(content, str) or content.strip() == '':
                    logger.debug(f"[{chat_name}] 跳过空消息")
                    return

                # 过滤系统自己发送的回复消息
                if self._is_system_reply_message(content):
                    logger.debug(f"[{chat_name}] 跳过系统回复消息: {content[:50]}...")
                    return

                # 去重检查
                message_key = f"{sender_name}:{content}"
                if message_key not in self.processed_messages[chat_name]:
                    # 添加到已处理集合
                    self.processed_messages[chat_name].add(message_key)

                    # 发出消息接收信号
                    self.message_received.emit(chat_name, content)

                    # 调用记账服务，传递发送者名称
                    try:
                        success, result_msg = self.message_processor.process_message(content, sender_name)
                        self.accounting_result.emit(chat_name, success, result_msg)
                        logger.info(f"[{chat_name}] 记账结果: {'成功' if success else '失败'} - {result_msg}")

                        # 发送回复到微信的逻辑：
                        # 1. 如果是"信息与记账无关"，不发送回复
                        # 2. 如果是记账成功，发送成功信息
                        # 3. 如果是记账失败（token受限、网络错误等），发送错误信息
                        should_send_reply = True

                        # 检查是否与记账无关
                        if "信息与记账无关" in result_msg:
                            should_send_reply = False
                            logger.info(f"[{chat_name}] 消息与记账无关，不发送回复: {result_msg}")

                        # 发送回复到微信
                        if should_send_reply and result_msg:
                            self._send_reply_to_wechat(chat_name, result_msg)

                    except Exception as e:
                        logger.error(f"[{chat_name}] 记账处理失败: {e}")
                        self.accounting_result.emit(chat_name, False, f"记账处理失败: {e}")
                else:
                    logger.debug(f"[{chat_name}] 跳过重复消息: {sender_name} - {content[:30]}...")
            else:
                # 不是friend类型的消息，跳过处理
                message_type = getattr(message, 'type', 'unknown')
                logger.debug(f"[{chat_name}] 跳过非朋友消息，类型: {message_type}")
                
        except Exception as e:
            logger.error(f"[{chat_name}] 处理消息失败: {e}")

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

        # 检查是否包含系统回复的特征
        system_feature_count = 0
        for pattern in system_reply_patterns:
            if pattern in content:
                system_feature_count += 1

        # 如果包含1个或以上系统特征，认为是系统回复
        if system_feature_count >= 1:
            logger.debug(f"检测到系统回复消息，包含{system_feature_count}个特征: {content[:100]}...")
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

            # 检查监听列表
            if not hasattr(self.wx_instance, 'listen') or not self.wx_instance.listen:
                logger.error("监听列表为空")
                return False

            # 检查聊天对象是否在监听列表中
            if chat_name not in self.wx_instance.listen:
                logger.error(f"聊天对象 {chat_name} 不在监听列表中")
                return False

            # 获取聊天窗口对象
            chat = self.wx_instance.listen[chat_name]

            # 使用聊天窗口对象发送消息
            try:
                result = chat.SendMsg(message)
                logger.debug(f"[{chat_name}] SendMsg返回结果: {result} (类型: {type(result)})")

                # wxauto的SendMsg方法可能返回不同类型的值
                # 通常情况下，成功发送不会抛出异常，我们认为发送成功
                logger.info(f"[{chat_name}] 发送回复成功: {message[:50]}...")
                return True

            except Exception as send_error:
                logger.warning(f"[{chat_name}] 发送回复失败: {send_error} - 消息: {message[:50]}...")
                return False

        except Exception as e:
            logger.error(f"发送回复失败: {e}")
            return False

    def stop_monitoring(self):
        """停止监控"""
        try:
            # 停止所有监控线程
            for chat_name, stop_event in self.stop_events.items():
                stop_event.set()

            # 等待线程结束
            for chat_name, thread in self.monitor_threads.items():
                if thread.is_alive():
                    thread.join(timeout=2)

            # 清理资源（但保留startup_message_ids用于下次启动）
            self.monitor_threads.clear()
            self.stop_events.clear()
            # 注意：不清理startup_message_ids，保留用于下次启动时过滤历史消息

            self.is_running = False
            self.status_changed.emit(False)
            logger.info("监控已停止")

        except Exception as e:
            logger.error(f"停止监控失败: {e}")
    
    def get_statistics(self) -> Dict[str, Dict]:
        """获取统计信息"""
        stats = {}
        for chat_name in self.processed_messages.keys():
            stats[chat_name] = {
                'processed_messages': len(self.processed_messages[chat_name]),
                'is_monitoring': chat_name in self.monitor_threads and self.monitor_threads[chat_name].is_alive(),
                'startup_messages_count': len(self.startup_message_ids.get(chat_name, set()))
            }
        return stats
