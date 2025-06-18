#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步消息记录器
将历史消息记录操作移到后台线程执行，避免UI阻塞
"""

import logging
import time
import hashlib
from typing import Set, Optional
from PyQt6.QtCore import QThread, pyqtSignal, QObject

logger = logging.getLogger(__name__)

class AsyncMessageRecorder(QThread):
    """异步消息记录线程"""
    
    # 信号定义
    recording_finished = pyqtSignal(str, bool, str, set)  # (chat_name, success, message, message_ids)
    progress_updated = pyqtSignal(str, str)  # (chat_name, progress_message)
    
    def __init__(self, wx_instance, chat_name: str, max_attempts: int = 3, 
                 interval: int = 2, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.wx_instance = wx_instance
        self.chat_name = chat_name
        self.max_attempts = max_attempts
        self.interval = interval
        self.startup_message_ids = set()
        
    def run(self):
        """执行异步消息记录"""
        try:
            logger.info(f"开始异步记录{self.chat_name}的启动时历史消息...")
            self.progress_updated.emit(self.chat_name, f"开始记录{self.chat_name}的历史消息...")
            
            total_messages = 0
            
            for attempt in range(self.max_attempts):
                self.progress_updated.emit(
                    self.chat_name, 
                    f"第{attempt + 1}/{self.max_attempts}次获取历史消息..."
                )
                logger.info(f"第{attempt + 1}次获取历史消息...")
                
                try:
                    # 获取当前所有消息
                    messages = self.wx_instance.GetListenMessage(self.chat_name)
                    
                    if messages and isinstance(messages, list):
                        batch_count = 0
                        for message in messages:
                            # 为每条消息生成唯一ID
                            message_id = self._generate_message_id(message)
                            if message_id not in self.startup_message_ids:
                                self.startup_message_ids.add(message_id)
                                batch_count += 1
                        
                        total_messages += batch_count
                        logger.info(f"第{attempt + 1}次获取到{len(messages)}条消息，其中{batch_count}条为新消息")
                        
                        # 如果这次没有新消息，说明历史消息已经全部获取完毕
                        if batch_count == 0:
                            logger.info(f"历史消息获取完毕，共记录{total_messages}条历史消息")
                            break
                    else:
                        logger.info(f"第{attempt + 1}次获取到空消息列表")
                    
                    # 如果不是最后一次尝试，等待指定间隔
                    if attempt < self.max_attempts - 1:
                        self.progress_updated.emit(
                            self.chat_name, 
                            f"等待{self.interval}秒后进行下一次获取..."
                        )
                        time.sleep(self.interval)
                        
                except Exception as e:
                    logger.warning(f"第{attempt + 1}次获取历史消息失败: {e}")
                    continue
            
            logger.info(f"历史消息记录完成，总计记录{len(self.startup_message_ids)}条历史消息ID")
            
            # 短暂等待，确保微信内部状态稳定
            self.progress_updated.emit(self.chat_name, "等待微信状态稳定...")
            time.sleep(2)  # 减少等待时间从5秒到2秒
            
            self.progress_updated.emit(self.chat_name, "历史消息记录完成")
            logger.info("历史消息处理完成，开始监控新消息")
            
            self.recording_finished.emit(
                self.chat_name, 
                True, 
                f"成功记录{len(self.startup_message_ids)}条历史消息", 
                self.startup_message_ids
            )
            
        except Exception as e:
            error_msg = f"记录启动时消息ID失败: {e}"
            logger.error(error_msg)
            self.recording_finished.emit(self.chat_name, False, error_msg, set())
    
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
            stable_content = f"{sender}:{content}"
            content_hash = hashlib.md5(stable_content.encode('utf-8')).hexdigest()
            
            return content_hash
        except Exception as e:
            logger.warning(f"生成消息ID失败: {e}")
            return f"error_{hash(str(message))}"

class AsyncMessageRecorderManager(QObject):
    """异步消息记录管理器"""
    
    # 信号定义
    recording_finished = pyqtSignal(str, bool, str, set)  # (chat_name, success, message, message_ids)
    progress_updated = pyqtSignal(str, str)  # (chat_name, progress_message)
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._active_recorders = {}  # 存储活动的记录器线程
        
    def start_recording(self, wx_instance, chat_name: str, max_attempts: int = 3, 
                       interval: int = 2) -> AsyncMessageRecorder:
        """开始异步记录历史消息"""
        # 如果同一个聊天对象的记录正在进行，先停止它
        if chat_name in self._active_recorders:
            old_recorder = self._active_recorders[chat_name]
            if old_recorder.isRunning():
                old_recorder.terminate()
                old_recorder.wait(1000)
        
        # 创建新的记录器
        recorder = AsyncMessageRecorder(wx_instance, chat_name, max_attempts, interval, self)
        
        # 连接信号
        recorder.recording_finished.connect(self._on_recording_finished)
        recorder.recording_finished.connect(self.recording_finished.emit)
        recorder.progress_updated.connect(self.progress_updated.emit)
        
        # 存储并启动
        self._active_recorders[chat_name] = recorder
        recorder.start()
        
        return recorder
    
    def _on_recording_finished(self, chat_name: str, success: bool, message: str, message_ids: set):
        """记录完成回调"""
        # 清理完成的记录器
        if chat_name in self._active_recorders:
            recorder = self._active_recorders[chat_name]
            recorder.deleteLater()
            del self._active_recorders[chat_name]
    
    def cancel_all_recordings(self):
        """取消所有活动的记录"""
        for recorder in list(self._active_recorders.values()):
            if recorder.isRunning():
                recorder.terminate()
                recorder.wait(1000)
        self._active_recorders.clear()
    
    def is_recording(self, chat_name: str) -> bool:
        """检查指定聊天对象是否正在记录"""
        return (chat_name in self._active_recorders and 
                self._active_recorders[chat_name].isRunning())

# 全局异步消息记录管理器实例
async_message_recorder_manager = AsyncMessageRecorderManager()
