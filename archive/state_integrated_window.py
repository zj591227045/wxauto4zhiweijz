#!/usr/bin/env python3
"""
集成状态管理器的基础窗口类
"""

from PyQt6.QtCore import QObject, pyqtSignal
from app.utils.state_manager import state_manager

class StateIntegratedMixin:
    """状态集成混入类"""
    
    def setup_state_integration(self):
        """设置状态集成"""
        # 连接状态管理器的回调
        state_manager.connect_signal('accounting_service', self.on_accounting_service_changed)
        state_manager.connect_signal('wechat_status', self.on_wechat_status_changed)
        state_manager.connect_signal('api_status', self.on_api_status_changed)
        state_manager.connect_signal('stats', self.on_stats_changed)
        state_manager.connect_signal('monitoring', self.on_monitoring_status_changed)
        
        # 加载初始状态
        self.load_initial_state()
    
    def load_initial_state(self):
        """加载初始状态"""
        # 加载各种状态
        self.on_accounting_service_changed(state_manager.get_accounting_service_status())
        self.on_wechat_status_changed(state_manager.get_wechat_status())
        self.on_api_status_changed(state_manager.get_api_status())
        self.on_stats_changed(state_manager.get_stats())
        self.on_monitoring_status_changed(state_manager.is_monitoring_active())
    
    def on_accounting_service_changed(self, config: dict):
        """只为记账服务状态变化 - 子类应重写此方法"""
        pass
    
    def on_wechat_status_changed(self, status: dict):
        """微信状态变化 - 子类应重写此方法"""
        pass
    
    def on_api_status_changed(self, status: dict):
        """API状态变化 - 子类应重写此方法"""
        pass
    
    def on_stats_changed(self, stats: dict):
        """统计数据变化 - 子类应重写此方法"""
        pass
    
    def on_monitoring_status_changed(self, is_active: bool):
        """监控状态变化 - 子类应重写此方法"""
        pass
    
    def update_accounting_service_from_ui(self):
        """从UI更新只为记账服务状态"""
        # 子类应实现此方法来从UI控件读取数据并更新状态
        pass
    
    def update_monitoring_from_ui(self):
        """从UI更新监控状态"""
        # 子类应实现此方法来从UI控件读取数据并更新状态
        pass 