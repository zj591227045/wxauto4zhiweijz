#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步微信操作工作器
将耗时的微信操作移到后台线程执行，避免UI阻塞
"""

import logging
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import QThread, pyqtSignal, QObject
import time

logger = logging.getLogger(__name__)

class AsyncWechatWorker(QThread):
    """异步微信操作工作线程"""
    
    # 信号定义
    operation_finished = pyqtSignal(str, bool, str, dict)  # (operation, success, message, data)
    progress_updated = pyqtSignal(str, str)  # (operation, progress_message)
    
    def __init__(self, operation: str, **kwargs):
        super().__init__()
        self.operation = operation
        self.kwargs = kwargs
        self.result_data = {}
        
    def run(self):
        """执行异步操作"""
        try:
            logger.debug(f"开始异步微信操作: {self.operation}")
            
            if self.operation == "init_message_processor":
                self._init_message_processor()
            elif self.operation == "start_chat_monitoring":
                self._start_chat_monitoring()
            elif self.operation == "add_chat_target":
                self._add_chat_target()
            elif self.operation == "stop_monitoring":
                self._stop_monitoring()
            else:
                raise ValueError(f"不支持的操作: {self.operation}")
                
        except Exception as e:
            logger.error(f"异步微信操作失败 {self.operation}: {e}")
            self.operation_finished.emit(self.operation, False, str(e), {})
    
    def _init_message_processor(self):
        """异步初始化消息处理器"""
        try:
            self.progress_updated.emit(self.operation, "正在初始化记账服务...")
            
            # 延迟导入，避免Flask依赖
            from app.services.accounting_service import AccountingService
            # 优先使用ZeroHistoryMonitor，如果不可用则使用MessageMonitor
            try:
                from app.services.zero_history_monitor import ZeroHistoryMonitor
                monitor_class = ZeroHistoryMonitor
                monitor_name = "ZeroHistoryMonitor"
            except ImportError:
                from app.services.message_monitor import MessageMonitor
                monitor_class = MessageMonitor
                monitor_name = "MessageMonitor"
            
            # 初始化记账服务
            accounting_service = AccountingService()
            self.result_data['accounting_service'] = accounting_service
            
            self.progress_updated.emit(self.operation, "记账服务初始化成功")
            time.sleep(0.1)  # 短暂延迟，让UI有时间更新
            
            self.progress_updated.emit(self.operation, f"正在初始化微信监控器({monitor_name})...")

            # 初始化消息监控器
            if monitor_class == ZeroHistoryMonitor:
                message_monitor = ZeroHistoryMonitor()
            else:
                message_monitor = monitor_class(accounting_service)
            self.result_data['message_monitor'] = message_monitor
            
            self.progress_updated.emit(self.operation, "微信监控器初始化成功")
            
            logger.info("异步消息处理器初始化成功")
            self.operation_finished.emit(self.operation, True, "初始化成功", self.result_data)
            
        except Exception as e:
            logger.error(f"异步初始化消息处理器失败: {e}")
            self.operation_finished.emit(self.operation, False, str(e), {})
    
    def _start_chat_monitoring(self):
        """异步启动聊天监控"""
        try:
            message_monitor = self.kwargs.get('message_monitor')
            chat_targets = self.kwargs.get('chat_targets', [])
            
            if not message_monitor:
                raise ValueError("消息监控器未提供")
            
            if not chat_targets:
                raise ValueError("监控目标列表为空")
            
            success_count = 0
            total_count = len(chat_targets)
            
            for i, chat_name in enumerate(chat_targets):
                self.progress_updated.emit(
                    self.operation, 
                    f"正在启动监控 ({i+1}/{total_count}): {chat_name}"
                )
                
                try:
                    # 这里仍然会调用同步的微信操作，但在后台线程中
                    result = message_monitor.start_chat_monitoring(chat_name)
                    if result:
                        success_count += 1
                        logger.info(f"成功启动监控: {chat_name}")
                    else:
                        # 检查是否实际上已经在监控中
                        if message_monitor.is_chat_monitoring(chat_name):
                            success_count += 1
                            logger.info(f"监控已存在: {chat_name}")
                        else:
                            logger.warning(f"启动监控失败: {chat_name}")
                            
                except Exception as e:
                    logger.error(f"启动监控异常 {chat_name}: {e}")
                    # 即使出现异常，也检查是否实际上已经在监控中
                    try:
                        if message_monitor.is_chat_monitoring(chat_name):
                            success_count += 1
                            logger.info(f"监控实际已启动（异常后检查）: {chat_name}")
                    except:
                        pass
                
                # 短暂延迟，避免操作过快
                time.sleep(0.2)
            
            self.result_data = {
                'success_count': success_count,
                'total_count': total_count,
                'chat_targets': chat_targets
            }
            
            if success_count > 0:
                message = f"成功启动 {success_count}/{total_count} 个监控目标"
                logger.info(message)
                self.operation_finished.emit(self.operation, True, message, self.result_data)
            else:
                message = "没有成功启动任何监控目标"
                logger.warning(message)
                self.operation_finished.emit(self.operation, False, message, self.result_data)
                
        except Exception as e:
            logger.error(f"异步启动聊天监控失败: {e}")
            self.operation_finished.emit(self.operation, False, str(e), {})
    
    def _add_chat_target(self):
        """异步添加聊天目标"""
        try:
            message_monitor = self.kwargs.get('message_monitor')
            chat_targets = self.kwargs.get('chat_targets', [])
            
            if not message_monitor:
                raise ValueError("消息监控器未提供")
            
            if not chat_targets:
                raise ValueError("聊天目标列表为空")
            
            success_count = 0
            total_count = len(chat_targets)
            
            for i, chat_name in enumerate(chat_targets):
                self.progress_updated.emit(
                    self.operation, 
                    f"正在添加监控目标 ({i+1}/{total_count}): {chat_name}"
                )
                
                try:
                    # 这里仍然会调用同步的微信操作，但在后台线程中
                    if message_monitor.add_chat_target(chat_name):
                        success_count += 1
                        logger.info(f"成功添加监控目标: {chat_name}")
                    else:
                        logger.info(f"监控目标已存在: {chat_name}")
                        success_count += 1  # 已存在也算成功
                        
                except Exception as e:
                    logger.error(f"添加监控目标失败 {chat_name}: {e}")
                
                # 短暂延迟，避免操作过快
                time.sleep(0.1)
            
            self.result_data = {
                'success_count': success_count,
                'total_count': total_count,
                'chat_targets': chat_targets
            }
            
            message = f"成功添加 {success_count}/{total_count} 个监控目标"
            logger.info(message)
            self.operation_finished.emit(self.operation, True, message, self.result_data)
                
        except Exception as e:
            logger.error(f"异步添加聊天目标失败: {e}")
            self.operation_finished.emit(self.operation, False, str(e), {})
    
    def _stop_monitoring(self):
        """异步停止监控"""
        try:
            message_monitor = self.kwargs.get('message_monitor')
            
            if not message_monitor:
                raise ValueError("消息监控器未提供")
            
            self.progress_updated.emit(self.operation, "正在停止监控...")
            
            # 这里仍然会调用同步的微信操作，但在后台线程中
            message_monitor.stop_monitoring()
            
            logger.info("异步停止监控成功")
            self.operation_finished.emit(self.operation, True, "停止监控成功", {})
                
        except Exception as e:
            logger.error(f"异步停止监控失败: {e}")
            self.operation_finished.emit(self.operation, False, str(e), {})

class AsyncWechatManager(QObject):
    """异步微信操作管理器"""
    
    # 信号定义
    operation_finished = pyqtSignal(str, bool, str, dict)  # (operation, success, message, data)
    progress_updated = pyqtSignal(str, str)  # (operation, progress_message)
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._active_workers = {}  # 存储活动的工作线程
        
    def init_message_processor(self):
        """异步初始化消息处理器"""
        return self._start_operation("init_message_processor")
    
    def start_chat_monitoring(self, message_monitor, chat_targets: List[str]):
        """异步启动聊天监控"""
        return self._start_operation(
            "start_chat_monitoring",
            message_monitor=message_monitor,
            chat_targets=chat_targets
        )
    
    def add_chat_targets(self, message_monitor, chat_targets: List[str]):
        """异步添加聊天目标"""
        return self._start_operation(
            "add_chat_target",
            message_monitor=message_monitor,
            chat_targets=chat_targets
        )
    
    def stop_monitoring(self, message_monitor):
        """异步停止监控"""
        return self._start_operation(
            "stop_monitoring",
            message_monitor=message_monitor
        )
    
    def _start_operation(self, operation: str, **kwargs) -> AsyncWechatWorker:
        """启动异步操作"""
        # 如果同类型操作正在进行，先停止它
        if operation in self._active_workers:
            old_worker = self._active_workers[operation]
            if old_worker.isRunning():
                old_worker.terminate()
                old_worker.wait(1000)
        
        # 创建新的工作线程
        worker = AsyncWechatWorker(operation, **kwargs)
        
        # 连接信号
        worker.operation_finished.connect(self._on_operation_finished)
        worker.operation_finished.connect(self.operation_finished.emit)
        worker.progress_updated.connect(self.progress_updated.emit)
        
        # 存储并启动
        self._active_workers[operation] = worker
        worker.start()
        
        return worker
    
    def _on_operation_finished(self, operation: str, success: bool, message: str, data: dict):
        """操作完成回调"""
        # 清理完成的工作线程
        if operation in self._active_workers:
            worker = self._active_workers[operation]
            worker.deleteLater()
            del self._active_workers[operation]
    
    def cancel_all_operations(self):
        """取消所有活动的操作"""
        for worker in list(self._active_workers.values()):
            if worker.isRunning():
                worker.terminate()
                worker.wait(1000)
        self._active_workers.clear()

# 全局异步微信管理器实例
async_wechat_manager = AsyncWechatManager()
