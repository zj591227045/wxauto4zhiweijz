#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
平台适配器
将现有服务适配为统一的平台接口
"""

import logging
from typing import Dict, Tuple
from app.services.platform_manager import MessagePlatform, PlatformType

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class AccountingPlatformAdapter(MessagePlatform):
    """记账服务平台适配器"""
    
    def __init__(self, delivery_service):
        self.delivery_service = delivery_service
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.ACCOUNTING
    
    def get_platform_name(self) -> str:
        return "智能记账服务"
    
    def is_enabled(self) -> bool:
        # 记账服务默认启用
        return True
    
    def is_message_relevant(self, message: str, sender: str) -> bool:
        # 记账服务处理所有消息
        return True
    
    def process_message(self, message: str, sender: str, context: Dict) -> Tuple[bool, str, Dict]:
        """处理消息并调用记账服务"""
        try:
            # 调用原有的记账服务
            success, result_msg = self.delivery_service._send_to_accounting_api(message, sender)
            
            # 包装结果
            result_data = {
                'success': success,
                'message': result_msg,
                'platform': 'accounting'
            }
            
            return success, result_msg, result_data
            
        except Exception as e:
            error_msg = f"记账服务处理失败: {e}"
            logger.error(error_msg)
            return False, error_msg, {}
    
    def should_reply_to_wechat(self, result: Dict) -> bool:
        """判断是否需要回复到微信"""
        if not result:
            return False
        
        # 使用原有的判断逻辑
        result_msg = result.get('message', '')
        return self.delivery_service._should_send_wechat_reply(result_msg)
    
    def format_wechat_reply(self, result: Dict) -> str:
        """格式化微信回复消息"""
        return result.get('message', '记账处理完成')
