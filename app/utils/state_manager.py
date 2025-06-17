#!/usr/bin/env python3
"""
全局状态管理器
用于在简约模式和高级模式之间共享状态
"""

import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
import sys

class StateManager:
    """全局状态管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # 状态变化回调
        self._callbacks = {
            'accounting_service': [],
            'wechat_status': [],
            'api_status': [],
            'stats': [],
            'monitoring': []
        }
        
        # 回调执行状态（防止递归调用）
        self._callback_executing = {
            'accounting_service': False,
            'wechat_status': False,
            'api_status': False,
            'stats': False,
            'monitoring': False
        }
        
        # 状态数据
        self._state = {
            # 只为记账服务状态
            'accounting_service': {
                'server_url': 'https://api.zhiweijz.com',
                'username': '',
                'password': '',
                'token': '',
                'account_books': [],
                'selected_account_book': '',
                'selected_account_book_name': '',
                'is_logged_in': False,
                'last_login_time': None,
                'status': 'disconnected'  # disconnected, connecting, connected, error
            },
            
            # 微信状态
            'wechat_status': {
                'status': 'offline',  # offline, online, error
                'window_name': '',
                'last_check_time': None,
                'error_message': '',
                'library_type': 'wxauto',  # wxauto, wxautox
                'auto_initialize': True
            },
            
            # API服务状态
            'api_status': {
                'status': 'stopped',  # stopped, starting, running, error
                'port': 5000,
                'api_key': 'test-key-2',
                'last_check_time': None,
                'error_message': '',
                'auto_start': True
            },
            
            # 监控状态
            'monitoring': {
                'is_active': False,
                'monitored_chats': [],
                'check_interval': 5,
                'last_check_time': None,
                'auto_start_monitoring': False
            },
            
            # 统计数据
            'stats': {
                'processed_messages': 0,
                'successful_records': 0,
                'failed_records': 0,
                'session_start_time': None,
                'last_message_time': None
            },
            
            # 应用设置
            'app_settings': {
                'auto_startup_enabled': False,
                'startup_countdown': 10,
                'default_mode': 'simple',  # simple, advanced
                'theme': 'dark'
            }
        }
        
        # 状态文件路径
        if getattr(sys, 'frozen', False):
            # 打包环境 - 使用exe文件所在目录
            app_dir = os.path.dirname(sys.executable)
            self._state_file = os.path.join(app_dir, 'data', 'app_state.json')
        else:
            # 开发环境 - 使用项目根目录
            self._state_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data', 'app_state.json'
            )
        
        # 确保数据目录存在
        os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
        
        # 加载保存的状态
        self._load_state()
        
        # 自动保存定时器
        self._auto_save_timer = None
        self._start_auto_save()
    
    def connect_signal(self, signal_name: str, callback: Callable):
        """连接信号回调"""
        if signal_name in self._callbacks:
            if callback not in self._callbacks[signal_name]:
                self._callbacks[signal_name].append(callback)
    
    def disconnect_signal(self, signal_name: str, callback: Callable):
        """断开信号回调"""
        if signal_name in self._callbacks:
            if callback in self._callbacks[signal_name]:
                self._callbacks[signal_name].remove(callback)
    
    def _emit_signal(self, signal_name: str, data: Any):
        """发射信号"""
        # 防止递归调用
        if self._callback_executing.get(signal_name, False):
            print(f"跳过递归回调: {signal_name}")
            return
        
        if signal_name in self._callbacks:
            self._callback_executing[signal_name] = True
            try:
                for callback in self._callbacks[signal_name]:
                    try:
                        callback(data)
                    except Exception as e:
                        print(f"回调执行失败 ({signal_name}): {e}")
                        import traceback
                        traceback.print_exc()
            finally:
                self._callback_executing[signal_name] = False
    
    def _load_state(self):
        """加载保存的状态"""
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, 'r', encoding='utf-8') as f:
                    saved_state = json.load(f)
                    # 合并保存的状态，保留默认值
                    self._merge_state(saved_state)
        except Exception as e:
            print(f"加载状态失败: {e}")
    
    def _merge_state(self, saved_state: dict):
        """合并保存的状态"""
        for key, value in saved_state.items():
            if key in self._state:
                if isinstance(value, dict) and isinstance(self._state[key], dict):
                    self._state[key].update(value)
                else:
                    self._state[key] = value
    
    def _save_state(self):
        """保存状态到文件"""
        try:
            # 创建一个副本
            state_to_save = json.loads(json.dumps(self._state))

            # 为了简约UI的正常工作，我们需要保存密码和token
            # 在生产环境中，应该考虑加密存储这些敏感信息
            # 这里暂时保存明文，以确保功能正常

            with open(self._state_file, 'w', encoding='utf-8') as f:
                json.dump(state_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存状态失败: {e}")
    
    def _start_auto_save(self):
        """启动自动保存"""
        def auto_save():
            while True:
                time.sleep(30)  # 每30秒自动保存一次
                self._save_state()
        
        auto_save_thread = threading.Thread(target=auto_save, daemon=True)
        auto_save_thread.start()
    
    def get_state(self, category: str = None) -> Dict[str, Any]:
        """获取状态"""
        if category:
            return self._state.get(category, {}).copy()
        return self._state.copy()
    
    def set_state(self, category: str, data: Dict[str, Any], emit_signal: bool = True):
        """设置状态"""
        if category not in self._state:
            self._state[category] = {}
        
        old_state = self._state[category].copy()
        self._state[category].update(data)
        
        # 发射对应的信号
        if emit_signal:
            if category == 'accounting_service':
                self._emit_signal('accounting_service', self._state[category].copy())
            elif category == 'wechat_status':
                self._emit_signal('wechat_status', self._state[category].copy())
            elif category == 'api_status':
                self._emit_signal('api_status', self._state[category].copy())
            elif category == 'stats':
                self._emit_signal('stats', self._state[category].copy())
            elif category == 'monitoring':
                self._emit_signal('monitoring', self._state[category]['is_active'])
    
    def update_accounting_service(self, **kwargs):
        """更新只为记账服务状态"""
        self.set_state('accounting_service', kwargs)
    
    def update_wechat_status(self, **kwargs):
        """更新微信状态"""
        kwargs['last_check_time'] = datetime.now().isoformat()
        self.set_state('wechat_status', kwargs)
    
    def update_api_status(self, **kwargs):
        """更新API状态"""
        kwargs['last_check_time'] = datetime.now().isoformat()
        self.set_state('api_status', kwargs)
    
    def update_monitoring_status(self, is_active: bool, **kwargs):
        """更新监控状态"""
        data = {'is_active': is_active, **kwargs}
        if is_active:
            data['last_check_time'] = datetime.now().isoformat()
        self.set_state('monitoring', data)
    
    def update_stats(self, **kwargs):
        """更新统计数据"""
        current_stats = self._state['stats']
        
        # 处理增量更新
        if 'processed_messages_delta' in kwargs:
            current_stats['processed_messages'] += kwargs.pop('processed_messages_delta')
        if 'successful_records_delta' in kwargs:
            current_stats['successful_records'] += kwargs.pop('successful_records_delta')
        if 'failed_records_delta' in kwargs:
            current_stats['failed_records'] += kwargs.pop('failed_records_delta')
        
        # 更新最后消息时间
        if any(key in kwargs for key in ['processed_messages_delta', 'successful_records_delta', 'failed_records_delta']):
            kwargs['last_message_time'] = datetime.now().isoformat()
        
        self.set_state('stats', kwargs)
    
    def reset_stats(self):
        """重置统计数据"""
        self.set_state('stats', {
            'processed_messages': 0,
            'successful_records': 0,
            'failed_records': 0,
            'session_start_time': datetime.now().isoformat(),
            'last_message_time': None
        })
    
    def start_session(self):
        """开始新的会话"""
        self.update_stats(session_start_time=datetime.now().isoformat())
    
    def get_accounting_service_status(self) -> dict:
        """获取只为记账服务状态"""
        return self.get_state('accounting_service')
    
    def get_wechat_status(self) -> dict:
        """获取微信状态"""
        return self.get_state('wechat_status')
    
    def get_api_status(self) -> dict:
        """获取API状态"""
        return self.get_state('api_status')
    
    def get_monitoring_status(self) -> dict:
        """获取监控状态"""
        return self.get_state('monitoring')
    
    def get_stats(self) -> dict:
        """获取统计数据"""
        return self.get_state('stats')
    
    def is_monitoring_active(self) -> bool:
        """检查监控是否活跃"""
        return self._state['monitoring']['is_active']
    
    def save_now(self):
        """立即保存状态"""
        self._save_state()

# 全局状态管理器实例
state_manager = StateManager() 