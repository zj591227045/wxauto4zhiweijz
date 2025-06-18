#!/usr/bin/env python3
"""
增强版零历史消息监控器
基于健壮的监控基类，提供稳定的消息监听服务
"""

import time
import logging
from datetime import datetime
from typing import Dict, List, Set, Optional, Any
from PyQt6.QtCore import pyqtSignal

# 导入健壮的监控基类
from app.services.robust_message_monitor import RobustMessageMonitor, MonitorStatus

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class EnhancedZeroHistoryMonitor(RobustMessageMonitor):
    """增强版零历史消息监控器"""
    
    # 额外的信号定义
    accounting_result = pyqtSignal(str, bool, str)  # chat_name, success, result_msg
    
    def __init__(self, check_interval: int = 5, max_retry_attempts: int = 3):
        super().__init__(check_interval, max_retry_attempts)
        
        # 消息处理器
        self.message_processor = None
        
        # 历史消息过滤
        self.startup_message_ids: Dict[str, Set[str]] = {}
        self.processed_messages: Dict[str, Set[str]] = {}
        
        # 微信窗口信息
        self.window_name = None
        
        # 初始化组件
        self._init_message_processor()
        
        # 添加错误和恢复处理器
        self.add_error_handler(self._handle_monitor_error)
        self.add_recovery_handler(self._recover_wechat_connection)
    
    def _init_message_processor(self):
        """初始化消息处理器"""
        try:
            from app.services.simple_message_processor import SimpleMessageProcessor
            self.message_processor = SimpleMessageProcessor()
            logger.info("消息处理器初始化成功")
        except Exception as e:
            logger.error(f"初始化消息处理器失败: {e}")
    
    def _initialize_wechat(self) -> bool:
        """初始化微信连接"""
        try:
            logger.info("开始初始化微信连接...")
            
            # 尝试多种导入方式
            try:
                from app.utils.wxauto_manager import get_wx_instance
                self.wx_instance = get_wx_instance()
                logger.info("使用wxauto_manager获取微信实例")
            except ImportError:
                # 直接导入wxauto
                import wxauto
                self.wx_instance = wxauto.WeChat()
                logger.info("直接使用wxauto创建微信实例")
            
            if not self.wx_instance:
                logger.error("微信实例创建失败")
                return False
            
            # 获取微信窗口名称
            self.window_name = self._get_window_name()
            logger.info(f"微信连接初始化成功，窗口名称: {self.window_name}")
            
            # 验证连接
            if self._check_wechat_connection():
                self.connection_healthy = True
                return True
            else:
                logger.error("微信连接验证失败")
                return False
                
        except Exception as e:
            logger.error(f"初始化微信连接失败: {e}")
            return False
    
    def _get_window_name(self) -> str:
        """获取微信窗口名称"""
        try:
            # 尝试多种可能的属性名称
            for attr_name in ['nickname', 'name', 'window_name', 'title', 'Name']:
                if hasattr(self.wx_instance, attr_name):
                    attr_value = getattr(self.wx_instance, attr_name)
                    if attr_value and str(attr_value).strip():
                        return str(attr_value).strip()
            
            # 尝试调用方法
            for method_name in ['get_name', 'get_window_name', 'get_title']:
                if hasattr(self.wx_instance, method_name):
                    try:
                        method_result = getattr(self.wx_instance, method_name)()
                        if method_result and str(method_result).strip():
                            return str(method_result).strip()
                    except:
                        continue
            
            # 默认值
            return "助手"
            
        except Exception as e:
            logger.warning(f"获取窗口名称失败: {e}")
            return "助手"
    
    def _check_wechat_connection(self) -> bool:
        """检查微信连接状态"""
        try:
            if not self.wx_instance:
                return False
            
            # 尝试获取会话列表来验证连接
            try:
                sessions = self.wx_instance.GetSessionList()
                return sessions is not None
            except Exception as e:
                logger.debug(f"连接检查失败: {e}")
                return False
                
        except Exception as e:
            logger.error(f"检查微信连接状态失败: {e}")
            return False
    
    def _get_messages_for_chat(self, chat_name: str) -> List[Dict[str, Any]]:
        """获取指定聊天的消息"""
        try:
            if not self.wx_instance:
                return []
            
            # 获取监听消息
            messages = self.wx_instance.GetListenMessage(chat_name)
            
            if not messages or not isinstance(messages, list):
                return []
            
            # 过滤和处理消息
            processed_messages = []
            for message in messages:
                # 只处理friend类型的消息
                if hasattr(message, 'type') and message.type == 'friend':
                    # 生成消息ID
                    message_id = self._generate_message_id(message)
                    
                    # 跳过历史消息
                    if message_id in self.startup_message_ids.get(chat_name, set()):
                        continue
                    
                    # 提取消息信息
                    content = getattr(message, 'content', str(message))
                    sender = self._get_sender_name(message, chat_name)
                    
                    # 检查是否是有效消息
                    if self._is_valid_message(content):
                        processed_messages.append({
                            'content': content,
                            'sender': sender,
                            'message_id': message_id,
                            'raw_message': message
                        })
            
            return processed_messages
            
        except Exception as e:
            logger.error(f"获取聊天消息失败 {chat_name}: {e}")
            return []
    
    def _generate_message_id(self, message) -> str:
        """为消息生成唯一ID"""
        try:
            # 提取消息内容
            content = getattr(message, 'content', str(message)).strip()
            
            # 提取发送者信息
            sender = "unknown"
            if hasattr(message, 'sender_remark') and message.sender_remark:
                sender = str(message.sender_remark).strip()
            elif hasattr(message, 'sender') and message.sender:
                sender = str(message.sender).strip()
            
            # 生成稳定的ID
            import hashlib
            stable_content = f"{sender}:{content}"
            return hashlib.md5(stable_content.encode('utf-8')).hexdigest()
            
        except Exception as e:
            logger.warning(f"生成消息ID失败: {e}")
            return f"error_{hash(str(message))}"
    
    def _get_sender_name(self, message, chat_name: str) -> str:
        """获取发送者名称"""
        try:
            # 优先使用sender_remark（备注名）
            if hasattr(message, 'sender_remark') and message.sender_remark:
                return str(message.sender_remark).strip()
            
            # 其次使用sender
            if hasattr(message, 'sender') and message.sender:
                return str(message.sender).strip()
            
            # 兜底使用聊天对象名称
            return chat_name
            
        except Exception as e:
            logger.warning(f"获取发送者名称失败: {e}")
            return chat_name
    
    def _is_valid_message(self, content: str) -> bool:
        """检查是否是有效消息"""
        try:
            # 检查内容是否为空
            if not content or not isinstance(content, str) or content.strip() == '':
                return False
            
            # 过滤系统回复消息
            if self._is_system_reply_message(content):
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"检查消息有效性失败: {e}")
            return False
    
    def _is_system_reply_message(self, content: str) -> bool:
        """判断是否是系统发送的回复消息"""
        system_reply_patterns = [
            "✅ 记账成功！",
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
        
        return any(pattern in content for pattern in system_reply_patterns)
    
    def _process_message(self, chat_name: str, message: Dict[str, Any]):
        """处理消息（重写基类方法）"""
        try:
            content = message['content']
            sender = message['sender']
            message_id = message['message_id']
            
            # 去重检查
            if chat_name not in self.processed_messages:
                self.processed_messages[chat_name] = set()
            
            message_key = f"{sender}:{content}"
            if message_key in self.processed_messages[chat_name]:
                logger.debug(f"跳过重复消息: {chat_name} - {sender}: {content[:30]}...")
                return
            
            # 添加到已处理集合
            self.processed_messages[chat_name].add(message_key)
            
            # 发射消息接收信号
            self.message_received.emit(chat_name, content, sender)
            
            # 处理记账
            if self.message_processor:
                try:
                    success, result_msg = self.message_processor.process_message(content, sender)
                    self.accounting_result.emit(chat_name, success, result_msg)
                    
                    logger.info(f"[{chat_name}] 记账结果: {'成功' if success else '失败'} - {result_msg}")
                    
                    # 发送回复到微信
                    if self._should_send_reply(result_msg):
                        self._send_reply_to_wechat(chat_name, result_msg)
                    
                except Exception as e:
                    logger.error(f"[{chat_name}] 记账处理失败: {e}")
                    self.accounting_result.emit(chat_name, False, f"记账处理失败: {e}")
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
    
    def _should_send_reply(self, result_msg: str) -> bool:
        """判断是否应该发送回复"""
        # 如果是"信息与记账无关"，不发送回复
        return "信息与记账无关" not in result_msg and result_msg.strip()
    
    def _send_reply_to_wechat(self, chat_name: str, message: str) -> bool:
        """发送回复到微信"""
        try:
            if not self.wx_instance:
                logger.error("微信实例不可用，无法发送回复")
                return False
            
            # 发送消息
            self.wx_instance.SendMsg(message, chat_name)
            logger.info(f"[{chat_name}] 回复发送成功: {message[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"[{chat_name}] 发送回复失败: {e}")
            return False
    
    def _handle_monitor_error(self, error_message: str):
        """处理监控错误"""
        logger.warning(f"监控错误处理: {error_message}")
        # 可以在这里添加特定的错误处理逻辑
    
    def _recover_wechat_connection(self) -> bool:
        """恢复微信连接"""
        try:
            logger.info("尝试恢复微信连接...")
            
            # 清理旧连接
            self.wx_instance = None
            self.connection_healthy = False
            
            # 重新初始化
            if self._initialize_wechat():
                logger.info("微信连接恢复成功")
                return True
            else:
                logger.error("微信连接恢复失败")
                return False
                
        except Exception as e:
            logger.error(f"恢复微信连接异常: {e}")
            return False
    
    def add_chat_target(self, chat_name: str) -> bool:
        """添加监听对象"""
        try:
            if not self.wx_instance:
                logger.error("微信实例未初始化")
                return False
            
            # 初始化数据结构
            if chat_name not in self.processed_messages:
                self.processed_messages[chat_name] = set()
            if chat_name not in self.startup_message_ids:
                self.startup_message_ids[chat_name] = set()
            
            # 添加到微信监听
            try:
                self.wx_instance.RemoveListenChat(chat_name)
            except:
                pass
            
            self.wx_instance.AddListenChat(chat_name)
            
            # 记录历史消息ID
            self._record_startup_messages(chat_name)
            
            logger.info(f"添加监听对象成功: {chat_name}")
            return True
            
        except Exception as e:
            logger.error(f"添加监听对象失败 {chat_name}: {e}")
            return False
    
    def _record_startup_messages(self, chat_name: str):
        """记录启动时的历史消息ID"""
        try:
            logger.info(f"开始记录历史消息: {chat_name}")
            
            for attempt in range(3):  # 最多3次尝试
                try:
                    messages = self.wx_instance.GetListenMessage(chat_name)
                    
                    if messages and isinstance(messages, list):
                        for message in messages:
                            message_id = self._generate_message_id(message)
                            self.startup_message_ids[chat_name].add(message_id)
                    
                    time.sleep(1)  # 等待1秒
                    
                except Exception as e:
                    logger.warning(f"记录历史消息失败 (尝试 {attempt + 1}): {e}")
            
            logger.info(f"历史消息记录完成: {chat_name} - {len(self.startup_message_ids[chat_name])} 条")
            
        except Exception as e:
            logger.error(f"记录历史消息异常 {chat_name}: {e}")
    
    def start_chat_monitoring(self, chat_name: str) -> bool:
        """启动指定聊天的监控"""
        try:
            # 添加聊天目标（如果尚未添加）
            if not self.add_chat_target(chat_name):
                logger.error(f"添加聊天目标失败: {chat_name}")
                return False

            # 启动监控（调用基类的监控方法）
            if not self.is_running:
                success = self.start_monitoring([chat_name])
                if success:
                    logger.info(f"启动监控成功: {chat_name}")
                    return True
                else:
                    logger.error(f"启动监控失败: {chat_name}")
                    return False
            else:
                # 如果监控已经在运行，只需要添加到监控列表
                if chat_name not in self.monitored_chats:
                    self.monitored_chats.append(chat_name)
                    # 启动新的监控线程
                    self._start_monitor_threads()
                logger.info(f"监控已运行，添加新目标: {chat_name}")
                return True

        except Exception as e:
            logger.error(f"启动聊天监控失败 {chat_name}: {e}")
            return False

    def stop_monitoring(self):
        """停止所有监控"""
        try:
            logger.info("停止所有聊天监控")

            # 调用基类的停止方法
            super().stop_monitoring()

            # 清理增强版特有的数据
            self.processed_messages.clear()
            self.startup_message_ids.clear()

            logger.info("监控停止完成")
            return True

        except Exception as e:
            logger.error(f"停止监控失败: {e}")
            return False

    def get_wechat_info(self) -> dict:
        """获取微信信息"""
        return {
            'is_connected': self.connection_healthy,
            'window_name': self.window_name or "未连接",
            'library_type': 'wxauto',
            'status': 'online' if self.connection_healthy else 'offline'
        }
