#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步HTTP请求处理器
用于避免同步HTTP请求导致的UI线程阻塞
"""

import requests
import logging
from typing import Dict, Any, Optional, Callable
from PyQt6.QtCore import QThread, pyqtSignal, QObject
import json

logger = logging.getLogger(__name__)

class AsyncHttpRequest(QThread):
    """异步HTTP请求线程"""
    
    # 信号定义
    request_finished = pyqtSignal(bool, dict)  # (success, response_data)
    request_failed = pyqtSignal(str)  # error_message
    
    def __init__(self, method: str, url: str, headers: Optional[Dict] = None, 
                 data: Optional[Dict] = None, json_data: Optional[Dict] = None,
                 timeout: int = 30, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.method = method.upper()
        self.url = url
        self.headers = headers or {}
        self.data = data
        self.json_data = json_data
        self.timeout = timeout
        
    def run(self):
        """执行HTTP请求"""
        try:
            logger.debug(f"开始异步HTTP请求: {self.method} {self.url}")
            
            # 准备请求参数
            kwargs = {
                'timeout': self.timeout,
                'headers': self.headers
            }
            
            if self.json_data:
                kwargs['json'] = self.json_data
            elif self.data:
                kwargs['data'] = self.data
                
            # 执行请求
            if self.method == 'GET':
                response = requests.get(self.url, **kwargs)
            elif self.method == 'POST':
                response = requests.post(self.url, **kwargs)
            elif self.method == 'PUT':
                response = requests.put(self.url, **kwargs)
            elif self.method == 'DELETE':
                response = requests.delete(self.url, **kwargs)
            else:
                raise ValueError(f"不支持的HTTP方法: {self.method}")
            
            # 处理响应
            response.raise_for_status()
            
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {'text': response.text, 'status_code': response.status_code}
            
            logger.debug(f"异步HTTP请求成功: {self.method} {self.url}")
            self.request_finished.emit(True, response_data)
            
        except requests.exceptions.Timeout:
            error_msg = f"请求超时: {self.url}"
            logger.error(error_msg)
            self.request_failed.emit(error_msg)
        except requests.exceptions.ConnectionError:
            error_msg = f"连接失败: {self.url}"
            logger.error(error_msg)
            self.request_failed.emit(error_msg)
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code} - {self.url}"
            logger.error(error_msg)
            self.request_failed.emit(error_msg)
        except Exception as e:
            error_msg = f"请求异常: {str(e)} - {self.url}"
            logger.error(error_msg)
            self.request_failed.emit(error_msg)

class AsyncHttpManager(QObject):
    """异步HTTP请求管理器"""
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._active_requests = {}  # 存储活动的请求线程
        
    def get(self, url: str, headers: Optional[Dict] = None, timeout: int = 30,
            success_callback: Optional[Callable] = None, 
            error_callback: Optional[Callable] = None) -> AsyncHttpRequest:
        """发起GET请求"""
        return self._make_request('GET', url, headers=headers, timeout=timeout,
                                success_callback=success_callback, 
                                error_callback=error_callback)
    
    def post(self, url: str, headers: Optional[Dict] = None, data: Optional[Dict] = None,
             json_data: Optional[Dict] = None, timeout: int = 30,
             success_callback: Optional[Callable] = None,
             error_callback: Optional[Callable] = None) -> AsyncHttpRequest:
        """发起POST请求"""
        return self._make_request('POST', url, headers=headers, data=data, 
                                json_data=json_data, timeout=timeout,
                                success_callback=success_callback,
                                error_callback=error_callback)
    
    def _make_request(self, method: str, url: str, headers: Optional[Dict] = None,
                     data: Optional[Dict] = None, json_data: Optional[Dict] = None,
                     timeout: int = 30, success_callback: Optional[Callable] = None,
                     error_callback: Optional[Callable] = None) -> AsyncHttpRequest:
        """创建并启动异步请求"""
        request = AsyncHttpRequest(method, url, headers, data, json_data, timeout, self)
        
        # 连接回调函数
        if success_callback:
            request.request_finished.connect(
                lambda success, data: success_callback(data) if success else None
            )
        if error_callback:
            request.request_failed.connect(error_callback)
            
        # 连接清理函数
        request.finished.connect(lambda: self._cleanup_request(request))
        
        # 存储并启动请求
        request_id = id(request)
        self._active_requests[request_id] = request
        request.start()
        
        return request
    
    def _cleanup_request(self, request: AsyncHttpRequest):
        """清理完成的请求"""
        request_id = id(request)
        if request_id in self._active_requests:
            del self._active_requests[request_id]
        request.deleteLater()
    
    def cancel_all_requests(self):
        """取消所有活动的请求"""
        for request in list(self._active_requests.values()):
            if request.isRunning():
                request.terminate()
                request.wait(1000)  # 等待最多1秒
        self._active_requests.clear()

# 全局异步HTTP管理器实例
async_http_manager = AsyncHttpManager()
