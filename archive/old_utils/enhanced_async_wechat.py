#!/usr/bin/env python3
"""
增强版异步微信管理器
确保所有wxauto操作都在异步线程中执行，避免UI阻塞
"""

import time
import threading
import logging
from typing import Dict, Any, Optional, Callable, List, Tuple
from queue import Queue, Empty
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class WechatOperation:
    """微信操作封装"""
    
    def __init__(self, operation_type: str, args: tuple = (), kwargs: dict = None, 
                 callback: Callable = None, timeout: float = 30.0):
        self.operation_type = operation_type
        self.args = args
        self.kwargs = kwargs or {}
        self.callback = callback
        self.timeout = timeout
        self.created_time = time.time()
        self.result = None
        self.error = None
        self.completed = False

class AsyncWechatWorker(QThread):
    """异步微信工作线程"""
    
    # 信号定义
    operation_completed = pyqtSignal(str, bool, object, str)  # operation_type, success, result, error_msg
    wechat_initialized = pyqtSignal(bool, str, dict)  # success, message, info
    message_sent = pyqtSignal(str, bool, str)  # chat_name, success, message
    messages_received = pyqtSignal(str, list)  # chat_name, messages
    connection_status_changed = pyqtSignal(bool, str)  # is_connected, status_message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 操作队列
        self.operation_queue = Queue()
        self.is_running = False
        self.stop_requested = False
        
        # 微信实例
        self.wx_instance = None
        self.is_connected = False
        self.last_connection_check = 0
        self.connection_check_interval = 30  # 30秒检查一次连接
        
        # 统计信息
        self.stats = {
            'operations_processed': 0,
            'operations_failed': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'connection_failures': 0
        }
        
        # 操作超时管理
        self.pending_operations = {}
        self.operation_id_counter = 0
    
    def run(self):
        """工作线程主循环"""
        logger.info("异步微信工作线程启动")
        self.is_running = True
        
        while not self.stop_requested:
            try:
                # 检查连接状态
                self._check_connection_status()
                
                # 处理操作队列
                self._process_operations()
                
                # 清理超时操作
                self._cleanup_timeout_operations()
                
                # 短暂休眠
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"异步微信工作线程异常: {e}")
                time.sleep(1)
        
        logger.info("异步微信工作线程结束")
        self.is_running = False
    
    def stop_worker(self):
        """停止工作线程"""
        self.stop_requested = True
        
        # 等待线程结束
        if self.isRunning():
            self.wait(5000)  # 等待5秒
    
    def add_operation(self, operation: WechatOperation) -> int:
        """添加操作到队列"""
        try:
            operation_id = self.operation_id_counter
            self.operation_id_counter += 1
            
            self.pending_operations[operation_id] = operation
            self.operation_queue.put((operation_id, operation))
            
            logger.debug(f"添加微信操作到队列: {operation.operation_type}")
            return operation_id
            
        except Exception as e:
            logger.error(f"添加微信操作失败: {e}")
            return -1
    
    def _process_operations(self):
        """处理操作队列"""
        try:
            # 批量处理操作（最多10个）
            processed_count = 0
            while processed_count < 10 and not self.operation_queue.empty():
                try:
                    operation_id, operation = self.operation_queue.get_nowait()
                    self._execute_operation(operation_id, operation)
                    processed_count += 1
                except Empty:
                    break
                except Exception as e:
                    logger.error(f"处理操作异常: {e}")
                    
        except Exception as e:
            logger.error(f"处理操作队列异常: {e}")
    
    def _execute_operation(self, operation_id: int, operation: WechatOperation):
        """执行单个操作"""
        try:
            start_time = time.time()
            
            # 检查操作是否超时
            if start_time - operation.created_time > operation.timeout:
                self._handle_operation_timeout(operation_id, operation)
                return
            
            # 执行操作
            success, result, error_msg = self._dispatch_operation(operation)
            
            # 更新统计
            if success:
                self.stats['operations_processed'] += 1
            else:
                self.stats['operations_failed'] += 1
            
            # 发射完成信号
            self.operation_completed.emit(operation.operation_type, success, result, error_msg)
            
            # 调用回调
            if operation.callback:
                try:
                    operation.callback(success, result, error_msg)
                except Exception as e:
                    logger.error(f"操作回调异常: {e}")
            
            # 清理
            if operation_id in self.pending_operations:
                del self.pending_operations[operation_id]
            
            execution_time = time.time() - start_time
            logger.debug(f"操作执行完成: {operation.operation_type}, 耗时: {execution_time:.2f}s")
            
        except Exception as e:
            logger.error(f"执行操作异常: {e}")
            self.operation_completed.emit(operation.operation_type, False, None, str(e))
    
    def _dispatch_operation(self, operation: WechatOperation) -> Tuple[bool, Any, str]:
        """分发操作到具体的处理方法"""
        try:
            operation_type = operation.operation_type
            
            if operation_type == "initialize":
                return self._initialize_wechat(*operation.args, **operation.kwargs)
            elif operation_type == "send_message":
                return self._send_message(*operation.args, **operation.kwargs)
            elif operation_type == "get_messages":
                return self._get_messages(*operation.args, **operation.kwargs)
            elif operation_type == "add_listener":
                return self._add_listener(*operation.args, **operation.kwargs)
            elif operation_type == "remove_listener":
                return self._remove_listener(*operation.args, **operation.kwargs)
            elif operation_type == "check_status":
                return self._check_wechat_status(*operation.args, **operation.kwargs)
            else:
                return False, None, f"未知操作类型: {operation_type}"
                
        except Exception as e:
            return False, None, f"操作分发异常: {str(e)}"
    
    def _initialize_wechat(self) -> Tuple[bool, Any, str]:
        """初始化微信"""
        try:
            logger.info("开始初始化微信实例...")
            
            # 导入wxauto
            try:
                import wxauto
                self.wx_instance = wxauto.WeChat()
                
                if self.wx_instance:
                    # 获取微信信息
                    window_name = self._get_window_name()
                    
                    self.is_connected = True
                    self.last_connection_check = time.time()
                    
                    info = {
                        'window_name': window_name,
                        'library_type': 'wxauto',
                        'status': 'online'
                    }
                    
                    logger.info(f"微信初始化成功: {window_name}")
                    self.wechat_initialized.emit(True, "初始化成功", info)
                    self.connection_status_changed.emit(True, "连接成功")
                    
                    return True, info, "初始化成功"
                else:
                    error_msg = "微信实例创建失败"
                    logger.error(error_msg)
                    self.wechat_initialized.emit(False, error_msg, {})
                    return False, None, error_msg
                    
            except ImportError as e:
                error_msg = f"导入wxauto失败: {e}"
                logger.error(error_msg)
                return False, None, error_msg
            except Exception as e:
                error_msg = f"创建微信实例失败: {e}"
                logger.error(error_msg)
                return False, None, error_msg
                
        except Exception as e:
            error_msg = f"初始化微信异常: {e}"
            logger.error(error_msg)
            return False, None, error_msg
    
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
            
            return "助手"
            
        except Exception as e:
            logger.warning(f"获取窗口名称失败: {e}")
            return "助手"
    
    def _send_message(self, chat_name: str, message: str) -> Tuple[bool, Any, str]:
        """发送消息"""
        try:
            if not self.wx_instance:
                return False, None, "微信实例不可用"
            
            if not self.is_connected:
                return False, None, "微信未连接"
            
            # 发送消息
            self.wx_instance.SendMsg(message, chat_name)
            
            self.stats['messages_sent'] += 1
            self.message_sent.emit(chat_name, True, "发送成功")
            
            logger.info(f"消息发送成功: {chat_name} - {message[:50]}...")
            return True, None, "发送成功"
            
        except Exception as e:
            error_msg = f"发送消息失败: {e}"
            logger.error(error_msg)
            self.message_sent.emit(chat_name, False, error_msg)
            return False, None, error_msg
    
    def _get_messages(self, chat_name: str = None) -> Tuple[bool, Any, str]:
        """获取消息"""
        try:
            if not self.wx_instance:
                return False, None, "微信实例不可用"
            
            if not self.is_connected:
                return False, None, "微信未连接"
            
            # 获取消息
            if chat_name:
                messages = self.wx_instance.GetListenMessage(chat_name)
            else:
                messages = self.wx_instance.GetListenMessage()
            
            if messages:
                self.stats['messages_received'] += len(messages) if isinstance(messages, list) else 1
                
                if chat_name:
                    self.messages_received.emit(chat_name, messages if isinstance(messages, list) else [messages])
                
                logger.debug(f"获取消息成功: {chat_name or '所有'} - {len(messages) if isinstance(messages, list) else 1} 条")
                return True, messages, "获取成功"
            else:
                return True, [], "无新消息"
                
        except Exception as e:
            error_msg = f"获取消息失败: {e}"
            logger.error(error_msg)
            return False, None, error_msg
    
    def _add_listener(self, chat_name: str) -> Tuple[bool, Any, str]:
        """添加监听对象"""
        try:
            if not self.wx_instance:
                return False, None, "微信实例不可用"
            
            # 先移除可能存在的监听
            try:
                self.wx_instance.RemoveListenChat(chat_name)
            except:
                pass
            
            # 添加监听
            self.wx_instance.AddListenChat(chat_name)
            
            logger.info(f"添加监听对象成功: {chat_name}")
            return True, None, "添加成功"
            
        except Exception as e:
            error_msg = f"添加监听对象失败: {e}"
            logger.error(error_msg)
            return False, None, error_msg
    
    def _remove_listener(self, chat_name: str) -> Tuple[bool, Any, str]:
        """移除监听对象"""
        try:
            if not self.wx_instance:
                return False, None, "微信实例不可用"
            
            self.wx_instance.RemoveListenChat(chat_name)
            
            logger.info(f"移除监听对象成功: {chat_name}")
            return True, None, "移除成功"
            
        except Exception as e:
            error_msg = f"移除监听对象失败: {e}"
            logger.error(error_msg)
            return False, None, error_msg
    
    def _check_wechat_status(self) -> Tuple[bool, Any, str]:
        """检查微信状态"""
        try:
            if not self.wx_instance:
                return False, None, "微信实例不可用"
            
            # 尝试获取会话列表来验证连接
            try:
                sessions = self.wx_instance.GetSessionList()
                if sessions is not None:
                    self.is_connected = True
                    self.last_connection_check = time.time()
                    return True, {'status': 'online', 'sessions_count': len(sessions) if isinstance(sessions, list) else 0}, "连接正常"
                else:
                    self.is_connected = False
                    return False, {'status': 'offline'}, "连接异常"
            except Exception as e:
                self.is_connected = False
                return False, {'status': 'error', 'error': str(e)}, f"状态检查失败: {e}"
                
        except Exception as e:
            error_msg = f"检查微信状态异常: {e}"
            logger.error(error_msg)
            return False, None, error_msg
    
    def _check_connection_status(self):
        """定期检查连接状态"""
        try:
            current_time = time.time()
            
            # 如果距离上次检查超过间隔时间，进行连接检查
            if current_time - self.last_connection_check > self.connection_check_interval:
                if self.wx_instance:
                    success, result, error_msg = self._check_wechat_status()
                    
                    if not success:
                        self.stats['connection_failures'] += 1
                        self.connection_status_changed.emit(False, error_msg)
                        logger.warning(f"连接状态检查失败: {error_msg}")
                    else:
                        self.connection_status_changed.emit(True, "连接正常")
                
                self.last_connection_check = current_time
                
        except Exception as e:
            logger.error(f"连接状态检查异常: {e}")
    
    def _cleanup_timeout_operations(self):
        """清理超时操作"""
        try:
            current_time = time.time()
            timeout_operations = []
            
            for operation_id, operation in self.pending_operations.items():
                if current_time - operation.created_time > operation.timeout:
                    timeout_operations.append(operation_id)
            
            for operation_id in timeout_operations:
                operation = self.pending_operations.pop(operation_id, None)
                if operation:
                    self._handle_operation_timeout(operation_id, operation)
                    
        except Exception as e:
            logger.error(f"清理超时操作异常: {e}")
    
    def _handle_operation_timeout(self, operation_id: int, operation: WechatOperation):
        """处理操作超时"""
        try:
            error_msg = f"操作超时: {operation.operation_type}"
            logger.warning(error_msg)
            
            self.operation_completed.emit(operation.operation_type, False, None, error_msg)
            
            if operation.callback:
                try:
                    operation.callback(False, None, error_msg)
                except Exception as e:
                    logger.error(f"超时回调异常: {e}")
                    
        except Exception as e:
            logger.error(f"处理操作超时异常: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            'is_running': self.is_running,
            'is_connected': self.is_connected,
            'pending_operations': len(self.pending_operations),
            'queue_size': self.operation_queue.qsize()
        }

class EnhancedAsyncWechatManager(QObject):
    """增强版异步微信管理器"""

    # 信号定义
    wechat_initialized = pyqtSignal(bool, str, dict)  # success, message, info
    wechat_ready = pyqtSignal(bool, str, dict)  # success, message, info (兼容性)
    message_sent = pyqtSignal(str, bool, str)  # chat_name, success, message
    messages_received = pyqtSignal(str, list)  # chat_name, messages
    connection_status_changed = pyqtSignal(bool, str)  # is_connected, status_message
    status_changed = pyqtSignal(bool, str)  # is_connected, status_message (兼容性)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 创建工作线程
        self.worker = AsyncWechatWorker()
        
        # 连接信号
        self.worker.wechat_initialized.connect(self.wechat_initialized)
        self.worker.wechat_initialized.connect(self.wechat_ready)  # 兼容性
        self.worker.message_sent.connect(self.message_sent)
        self.worker.messages_received.connect(self.messages_received)
        self.worker.connection_status_changed.connect(self.connection_status_changed)
        self.worker.connection_status_changed.connect(self.status_changed)  # 兼容性
        
        # 启动工作线程
        self.worker.start()
        
        logger.info("增强版异步微信管理器初始化完成")
    
    def initialize_wechat(self, callback: Callable = None):
        """异步初始化微信"""
        operation = WechatOperation("initialize", callback=callback)
        return self.worker.add_operation(operation)
    
    def send_message(self, chat_name: str, message: str, callback: Callable = None):
        """异步发送消息"""
        operation = WechatOperation("send_message", args=(chat_name, message), callback=callback)
        return self.worker.add_operation(operation)
    
    def get_messages(self, chat_name: str = None, callback: Callable = None):
        """异步获取消息"""
        operation = WechatOperation("get_messages", args=(chat_name,), callback=callback)
        return self.worker.add_operation(operation)
    
    def add_listener(self, chat_name: str, callback: Callable = None):
        """异步添加监听对象"""
        operation = WechatOperation("add_listener", args=(chat_name,), callback=callback)
        return self.worker.add_operation(operation)
    
    def remove_listener(self, chat_name: str, callback: Callable = None):
        """异步移除监听对象"""
        operation = WechatOperation("remove_listener", args=(chat_name,), callback=callback)
        return self.worker.add_operation(operation)
    
    def check_status(self, callback: Callable = None):
        """异步检查状态"""
        operation = WechatOperation("check_status", callback=callback)
        return self.worker.add_operation(operation)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.worker.get_stats()

    def is_running(self) -> bool:
        """检查管理器是否运行中"""
        return self.worker.is_alive() if hasattr(self.worker, 'is_alive') else True

    def is_connected(self) -> bool:
        """检查微信是否已连接"""
        return self.worker.is_connected if hasattr(self.worker, 'is_connected') else False

    def cleanup(self):
        """清理资源"""
        try:
            logger.info("开始清理异步微信管理器...")

            # 停止工作线程
            self.worker.stop_worker()

            logger.info("异步微信管理器清理完成")

        except Exception as e:
            logger.error(f"清理异步微信管理器失败: {e}")

# 全局实例
async_wechat_manager = EnhancedAsyncWechatManager()
