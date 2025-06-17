#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步微信API调用器
专门处理微信相关的API调用，避免UI阻塞
"""

import logging
from typing import Dict, Any, Optional, Callable, List
from PyQt6.QtCore import QObject, pyqtSignal
from .async_http import AsyncHttpManager

logger = logging.getLogger(__name__)

class AsyncWechatAPI(QObject):
    """异步微信API调用器"""
    
    # 信号定义
    wechat_initialized = pyqtSignal(bool, str, dict)  # (success, message, data)
    wechat_status_checked = pyqtSignal(bool, str, dict)  # (success, message, data)
    listener_added = pyqtSignal(bool, str, str)  # (success, message, who)
    messages_received = pyqtSignal(bool, str, dict)  # (success, message, messages)
    
    def __init__(self, base_url: str = "http://localhost:5000", 
                 api_key: str = "test-key-2", parent: Optional[QObject] = None):
        super().__init__(parent)
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.http_manager = AsyncHttpManager(self)
        
    def _get_headers(self) -> Dict[str, str]:
        """获取API请求头"""
        return {"X-API-Key": self.api_key}
    
    def initialize_wechat(self, timeout: int = 30):
        """异步初始化微信"""
        logger.info("开始异步初始化微信...")
        
        url = f"{self.base_url}/api/wechat/initialize"
        headers = self._get_headers()
        
        def on_success(data):
            if data.get('code') == 0:
                window_name = data.get('data', {}).get('window_name', '微信')
                logger.info(f"微信初始化成功: {window_name}")
                self.wechat_initialized.emit(True, "初始化成功", data)
            else:
                error_msg = data.get('message', '未知错误')
                logger.error(f"微信初始化失败: {error_msg}")
                self.wechat_initialized.emit(False, error_msg, data)
        
        def on_error(error_msg):
            logger.error(f"微信初始化请求失败: {error_msg}")
            self.wechat_initialized.emit(False, error_msg, {})
        
        self.http_manager.post(url, headers=headers, timeout=timeout,
                              success_callback=on_success, error_callback=on_error)
    
    def check_wechat_status(self, timeout: int = 10):
        """异步检查微信状态"""
        logger.debug("开始异步检查微信状态...")
        
        url = f"{self.base_url}/api/wechat/status"
        headers = self._get_headers()
        
        def on_success(data):
            if data.get('code') == 0:
                status = data.get('data', {}).get('status', 'unknown')
                logger.debug(f"微信状态检查成功: {status}")
                self.wechat_status_checked.emit(True, "状态检查成功", data)
            else:
                error_msg = data.get('message', '未知错误')
                logger.warning(f"微信状态检查失败: {error_msg}")
                self.wechat_status_checked.emit(False, error_msg, data)
        
        def on_error(error_msg):
            logger.warning(f"微信状态检查请求失败: {error_msg}")
            self.wechat_status_checked.emit(False, error_msg, {})
        
        self.http_manager.get(url, headers=headers, timeout=timeout,
                             success_callback=on_success, error_callback=on_error)
    
    def add_listen_chat(self, who: str, savepic: bool = False, savefile: bool = False,
                       savevoice: bool = False, timeout: int = 10):
        """异步添加监听对象"""
        logger.info(f"开始异步添加监听对象: {who}")
        
        url = f"{self.base_url}/api/message/listen/add"
        headers = self._get_headers()
        data = {
            "who": who,
            "savepic": savepic,
            "savefile": savefile,
            "savevoice": savevoice
        }
        
        def on_success(response_data):
            if response_data.get('code') == 0:
                logger.info(f"添加监听对象成功: {who}")
                self.listener_added.emit(True, "添加成功", who)
            else:
                error_msg = response_data.get('message', '未知错误')
                logger.error(f"添加监听对象失败: {error_msg}")
                self.listener_added.emit(False, error_msg, who)
        
        def on_error(error_msg):
            logger.error(f"添加监听对象请求失败: {error_msg}")
            self.listener_added.emit(False, error_msg, who)
        
        self.http_manager.post(url, headers=headers, json_data=data, timeout=timeout,
                              success_callback=on_success, error_callback=on_error)
    
    def get_listen_messages(self, who: Optional[str] = None, timeout: int = 10):
        """异步获取监听消息"""
        logger.debug(f"开始异步获取监听消息: {who or '所有'}")
        
        url = f"{self.base_url}/api/message/listen/get"
        if who:
            url += f"?who={who}"
        headers = self._get_headers()
        
        def on_success(data):
            if data.get('code') == 0:
                messages = data.get('data', {}).get('messages', {})
                logger.debug(f"获取监听消息成功: {len(messages) if isinstance(messages, dict) else 0} 个对象")
                self.messages_received.emit(True, "获取成功", messages)
            else:
                error_msg = data.get('message', '未知错误')
                logger.warning(f"获取监听消息失败: {error_msg}")
                self.messages_received.emit(False, error_msg, {})
        
        def on_error(error_msg):
            logger.warning(f"获取监听消息请求失败: {error_msg}")
            self.messages_received.emit(False, error_msg, {})
        
        self.http_manager.get(url, headers=headers, timeout=timeout,
                             success_callback=on_success, error_callback=on_error)
    
    def batch_add_listeners(self, chat_list: List[str], timeout: int = 30):
        """批量异步添加监听对象"""
        logger.info(f"开始批量添加监听对象: {chat_list}")
        
        # 为每个聊天对象添加监听
        for chat_name in chat_list:
            self.add_listen_chat(chat_name, timeout=timeout)
    
    def cleanup(self):
        """清理资源"""
        if hasattr(self, 'http_manager'):
            self.http_manager.cancel_all_requests()
