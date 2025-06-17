#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成消息服务 - 多平台版本
将消息监控和多平台投递服务集成在一起
职责：
1. 管理消息监控器
2. 管理多平台投递服务
3. 连接监控器和投递服务的信号
4. 支持DIFY、COZE、N8N等多个平台
"""

import logging
from typing import List, Dict
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class IntegratedMessageService(QObject):
    """集成消息服务 - 多平台版本"""

    # 信号定义
    message_received = pyqtSignal(str, str, str)      # chat_name, content, sender_name
    platform_result = pyqtSignal(str, str, bool, str, dict)  # platform_name, chat_name, success, message, data
    wechat_reply_sent = pyqtSignal(str, bool, str)    # chat_name, success, message
    error_occurred = pyqtSignal(str)                  # error_message
    status_changed = pyqtSignal(bool)                 # is_running

    # 兼容性信号（保持向后兼容）
    accounting_completed = pyqtSignal(str, bool, str) # chat_name, success, result_msg

    def __init__(self, parent=None):
        super().__init__(parent)

        # 初始化消息监控器
        from app.services.clean_message_monitor import CleanMessageMonitor
        self.message_monitor = CleanMessageMonitor()

        # 初始化多平台管理器
        from app.services.platform_manager import PlatformManager
        self.platform_manager = PlatformManager()

        # 初始化各平台服务
        self._init_platforms()

        # 连接信号
        self._connect_signals()

        logger.info("多平台集成消息服务初始化完成")
    
    def _init_platforms(self):
        """初始化各平台服务"""
        try:
            # 获取平台配置
            from app.utils.config_manager import ConfigManager
            config_manager = ConfigManager()

            # 初始化记账平台（保持兼容性）
            from app.services.message_delivery_service import MessageDeliveryService
            accounting_service = MessageDeliveryService()

            # 包装记账服务为平台接口
            from app.services.platform_adapters import AccountingPlatformAdapter
            accounting_platform = AccountingPlatformAdapter(accounting_service)
            self.platform_manager.register_platform(accounting_platform)

            # 初始化其他平台（如果配置存在）
            self._init_optional_platforms(config_manager)

            logger.info(f"已初始化 {len(self.platform_manager.platforms)} 个平台")

        except Exception as e:
            logger.error(f"初始化平台失败: {e}")

    def _init_optional_platforms(self, config_manager):
        """初始化可选平台"""
        try:
            # 尝试获取平台配置
            platform_configs = getattr(config_manager, 'get_platform_configs', lambda: {})()

            if not platform_configs:
                logger.info("未找到平台配置，仅使用记账服务")
                return

            # 初始化DIFY平台
            if 'dify' in platform_configs:
                from app.services.platform_manager import DifyPlatform
                dify_platform = DifyPlatform(platform_configs['dify'])
                self.platform_manager.register_platform(dify_platform)

            # 初始化COZE平台
            if 'coze' in platform_configs:
                from app.services.platform_manager import CozePlatform
                coze_platform = CozePlatform(platform_configs['coze'])
                self.platform_manager.register_platform(coze_platform)

            # 初始化N8N平台
            if 'n8n' in platform_configs:
                from app.services.platform_manager import N8nPlatform
                n8n_platform = N8nPlatform(platform_configs['n8n'])
                self.platform_manager.register_platform(n8n_platform)

        except Exception as e:
            logger.warning(f"初始化可选平台失败: {e}")

    def _connect_signals(self):
        """连接各组件的信号"""
        # 监控器信号连接
        self.message_monitor.message_received.connect(self._on_message_received)
        self.message_monitor.error_occurred.connect(self.error_occurred.emit)
        self.message_monitor.status_changed.connect(self.status_changed.emit)

        # 平台管理器信号连接
        self.platform_manager.platform_result.connect(self._on_platform_result)

        logger.debug("信号连接完成")
    
    def _on_message_received(self, chat_name: str, content: str, sender_name: str):
        """
        处理接收到的消息

        Args:
            chat_name: 聊天对象名称
            content: 消息内容
            sender_name: 发送者名称
        """
        try:
            logger.info(f"[{chat_name}] 接收到消息: {sender_name} - {content}")

            # 转发消息接收信号
            self.message_received.emit(chat_name, content, sender_name)

            # 构建消息上下文
            context = {
                'chat_name': chat_name,
                'timestamp': datetime.now().isoformat(),
                'source': 'wechat'
            }

            # 使用多平台管理器处理消息
            results = self.platform_manager.process_message(content, sender_name, context)

            # 处理结果
            self._handle_platform_results(chat_name, results)

        except Exception as e:
            error_msg = f"处理接收消息失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def _on_platform_result(self, platform_name: str, chat_name: str, success: bool, message: str, data: Dict):
        """
        处理平台处理结果

        Args:
            platform_name: 平台名称
            chat_name: 聊天对象名称
            success: 处理是否成功
            message: 结果消息
            data: 结果数据
        """
        try:
            # 转发平台结果信号
            self.platform_result.emit(platform_name, chat_name, success, message, data)

            # 如果是记账平台，发出兼容性信号
            if platform_name == "智能记账服务":
                self.accounting_completed.emit(chat_name, success, message)

            logger.debug(f"[{chat_name}] 平台 {platform_name} 处理结果: {success} - {message}")

        except Exception as e:
            logger.error(f"处理平台结果失败: {e}")

    def _handle_platform_results(self, chat_name: str, results: List[Dict]):
        """
        处理所有平台的结果

        Args:
            chat_name: 聊天对象名称
            results: 平台处理结果列表
        """
        try:
            # 获取需要发送到微信的回复
            replies = self.platform_manager.get_wechat_replies(results)

            # 发送回复到微信
            for reply in replies:
                success = self._send_wechat_reply(chat_name, reply)
                self.wechat_reply_sent.emit(chat_name, success, reply)

            # 如果没有回复，记录日志
            if not replies:
                logger.info(f"[{chat_name}] 所有平台处理完成，无需回复微信")

        except Exception as e:
            error_msg = f"处理平台结果失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def _send_wechat_reply(self, chat_name: str, message: str) -> bool:
        """
        发送回复到微信

        Args:
            chat_name: 聊天对象名称
            message: 回复消息

        Returns:
            True表示发送成功，False表示失败
        """
        try:
            # 使用原有的投递服务发送回复
            from app.services.message_delivery_service import MessageDeliveryService
            temp_delivery = MessageDeliveryService()
            return temp_delivery._send_wechat_reply(chat_name, message)

        except Exception as e:
            logger.error(f"发送微信回复失败: {e}")
            return False
    
    # 监控器管理方法
    def add_chat_target(self, chat_name: str) -> bool:
        """添加监听对象"""
        return self.message_monitor.add_chat_target(chat_name)
    
    def remove_chat_target(self, chat_name: str) -> bool:
        """移除监听对象"""
        return self.message_monitor.remove_chat_target(chat_name)
    
    def start_monitoring(self) -> bool:
        """开始监控"""
        return self.message_monitor.start_monitoring()
    
    def stop_monitoring(self):
        """停止监控"""
        self.message_monitor.stop_monitoring()
    
    def start_chat_monitoring(self, chat_name: str) -> bool:
        """启动指定聊天对象的监控"""
        return self.message_monitor.start_chat_monitoring(chat_name)
    
    def stop_chat_monitoring(self, chat_name: str) -> bool:
        """停止指定聊天对象的监控"""
        return self.message_monitor.stop_chat_monitoring(chat_name)
    
    def check_wechat_status(self) -> bool:
        """检查微信状态"""
        return self.message_monitor.check_wechat_status()
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        return self.message_monitor.get_statistics()
    
    # 属性访问
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.message_monitor.is_running
    
    @property
    def monitored_chats(self) -> List[str]:
        """监控的聊天对象列表"""
        return self.message_monitor.monitored_chats
    
    @property
    def wx_instance(self):
        """微信实例"""
        return self.message_monitor.wx_instance
    
    # 手动投递方法（用于测试或特殊情况）
    def manual_deliver_message(self, chat_name: str, message_content: str, sender_name: str = None):
        """
        手动投递消息（用于测试或特殊情况）
        
        Args:
            chat_name: 聊天对象名称
            message_content: 消息内容
            sender_name: 发送者名称
        """
        try:
            logger.info(f"[{chat_name}] 手动投递消息: {message_content}")
            self.delivery_service.process_and_deliver_message(chat_name, message_content, sender_name)
        except Exception as e:
            error_msg = f"手动投递消息失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
    
    def get_component_status(self) -> dict:
        """
        获取各组件状态

        Returns:
            包含各组件状态的字典
        """
        return {
            'monitor': {
                'is_running': self.message_monitor.is_running,
                'monitored_chats': self.message_monitor.monitored_chats,
                'wx_instance_available': self.message_monitor.wx_instance is not None
            },
            'platforms': self.platform_manager.get_platform_status(),
            'enabled_platforms': len(self.platform_manager.get_enabled_platforms())
        }

    def get_platform_status(self) -> Dict:
        """获取平台状态"""
        return self.platform_manager.get_platform_status()

    def get_enabled_platforms(self) -> List:
        """获取已启用的平台列表"""
        return [
            {
                'type': platform.get_platform_type().value,
                'name': platform.get_platform_name(),
                'enabled': platform.is_enabled()
            }
            for platform in self.platform_manager.get_enabled_platforms()
        ]

    def manual_process_message(self, chat_name: str, message_content: str, sender_name: str = None):
        """
        手动处理消息（用于测试或特殊情况）

        Args:
            chat_name: 聊天对象名称
            message_content: 消息内容
            sender_name: 发送者名称
        """
        try:
            logger.info(f"[{chat_name}] 手动处理消息: {message_content}")

            # 构建消息上下文
            context = {
                'chat_name': chat_name,
                'timestamp': datetime.now().isoformat(),
                'source': 'manual'
            }

            # 使用多平台管理器处理消息
            results = self.platform_manager.process_message(message_content, sender_name or chat_name, context)

            # 处理结果
            self._handle_platform_results(chat_name, results)

            return results

        except Exception as e:
            error_msg = f"手动处理消息失败: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return []
