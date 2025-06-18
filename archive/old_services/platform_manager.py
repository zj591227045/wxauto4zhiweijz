#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多平台管理器
支持DIFY、COZE、N8N等多个平台的统一消息处理
"""

import logging
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List, Optional
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class PlatformType(Enum):
    """平台类型枚举"""
    ACCOUNTING = "accounting"
    DIFY = "dify"
    COZE = "coze"
    N8N = "n8n"
    CUSTOM = "custom"

class MessagePlatform(ABC):
    """平台投递服务抽象基类"""
    
    @abstractmethod
    def get_platform_type(self) -> PlatformType:
        """获取平台类型"""
        pass
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """获取平台显示名称"""
        pass
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """平台是否启用"""
        pass
    
    @abstractmethod
    def is_message_relevant(self, message: str, sender: str) -> bool:
        """判断消息是否与该平台相关"""
        pass
    
    @abstractmethod
    def process_message(self, message: str, sender: str, context: Dict) -> Tuple[bool, str, Dict]:
        """处理消息并返回结果"""
        pass
    
    @abstractmethod
    def should_reply_to_wechat(self, result: Dict) -> bool:
        """判断是否需要回复到微信"""
        pass
    
    @abstractmethod
    def format_wechat_reply(self, result: Dict) -> str:
        """格式化微信回复消息"""
        pass

class DifyPlatform(MessagePlatform):
    """DIFY平台服务"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.api_key = config.get('api_key', '')
        self.base_url = config.get('base_url', '').rstrip('/')
        self.workflow_id = config.get('workflow_id', '')
        self.enabled = config.get('enabled', False)
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.DIFY
    
    def get_platform_name(self) -> str:
        return "DIFY AI工作流"
    
    def is_enabled(self) -> bool:
        return self.enabled and bool(self.api_key and self.base_url)
    
    def is_message_relevant(self, message: str, sender: str) -> bool:
        # DIFY可以处理所有类型的消息进行AI分析
        # 可以根据配置的关键词或规则来判断
        keywords = self.config.get('keywords', [])
        if keywords:
            return any(keyword in message for keyword in keywords)
        return True  # 默认处理所有消息
    
    def process_message(self, message: str, sender: str, context: Dict) -> Tuple[bool, str, Dict]:
        """调用DIFY工作流API"""
        try:
            if not self.is_enabled():
                return False, "DIFY平台未启用或配置不完整", {}
            
            # 构建DIFY API请求
            payload = {
                "inputs": {
                    "message": message,
                    "sender": sender,
                    "chat_name": context.get('chat_name', ''),
                    "timestamp": context.get('timestamp', '')
                },
                "response_mode": "blocking",
                "user": sender
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"调用DIFY API: {self.base_url}/v1/workflows/run")
            
            response = requests.post(
                f"{self.base_url}/v1/workflows/run",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"DIFY处理成功: {result}")
                return True, "🤖 DIFY AI分析完成", result
            else:
                error_msg = f"DIFY API错误: HTTP {response.status_code}"
                logger.error(error_msg)
                return False, error_msg, {}
                
        except requests.exceptions.Timeout:
            return False, "⏰ DIFY API请求超时", {}
        except requests.exceptions.ConnectionError:
            return False, "🌐 无法连接到DIFY服务", {}
        except Exception as e:
            error_msg = f"DIFY处理失败: {e}"
            logger.error(error_msg)
            return False, error_msg, {}
    
    def should_reply_to_wechat(self, result: Dict) -> bool:
        # 根据DIFY返回结果判断是否需要回复
        if not result:
            return False
        
        data = result.get('data', {})
        outputs = data.get('outputs', {})
        
        # 检查是否有回复内容
        return bool(outputs.get('reply_message') or outputs.get('response'))
    
    def format_wechat_reply(self, result: Dict) -> str:
        # 格式化DIFY的回复消息
        if not result:
            return "🤖 DIFY处理完成"
        
        data = result.get('data', {})
        outputs = data.get('outputs', {})
        
        reply_message = outputs.get('reply_message') or outputs.get('response', '')
        
        if reply_message:
            return f"🤖 DIFY AI分析：\n{reply_message}"
        else:
            return "🤖 DIFY AI分析完成"

class CozePlatform(MessagePlatform):
    """COZE平台服务"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.api_token = config.get('api_token', '')
        self.bot_id = config.get('bot_id', '')
        self.base_url = config.get('base_url', 'https://api.coze.com').rstrip('/')
        self.enabled = config.get('enabled', False)
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.COZE
    
    def get_platform_name(self) -> str:
        return "COZE对话AI"
    
    def is_enabled(self) -> bool:
        return self.enabled and bool(self.api_token and self.bot_id)
    
    def is_message_relevant(self, message: str, sender: str) -> bool:
        # COZE主要处理对话类消息
        question_keywords = ['问', '怎么', '什么', '为什么', '如何', '?', '？', '吗', '呢']
        return any(keyword in message for keyword in question_keywords)
    
    def process_message(self, message: str, sender: str, context: Dict) -> Tuple[bool, str, Dict]:
        """调用COZE对话API"""
        try:
            if not self.is_enabled():
                return False, "COZE平台未启用或配置不完整", {}
            
            payload = {
                "bot_id": self.bot_id,
                "user_id": sender,
                "query": message,
                "stream": False
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"调用COZE API: {self.base_url}/v3/chat")
            
            response = requests.post(
                f"{self.base_url}/v3/chat",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"COZE对话成功: {result}")
                return True, "💬 COZE对话完成", result
            else:
                error_msg = f"COZE API错误: HTTP {response.status_code}"
                logger.error(error_msg)
                return False, error_msg, {}
                
        except requests.exceptions.Timeout:
            return False, "⏰ COZE API请求超时", {}
        except requests.exceptions.ConnectionError:
            return False, "🌐 无法连接到COZE服务", {}
        except Exception as e:
            error_msg = f"COZE处理失败: {e}"
            logger.error(error_msg)
            return False, error_msg, {}
    
    def should_reply_to_wechat(self, result: Dict) -> bool:
        # COZE的对话结果通常都需要回复
        if not result:
            return False
        return result.get('code') == 0 and bool(result.get('data', {}).get('content'))
    
    def format_wechat_reply(self, result: Dict) -> str:
        if not result:
            return "💬 COZE对话完成"
        
        data = result.get('data', {})
        content = data.get('content', '')
        
        if content:
            return f"💬 COZE回复：\n{content}"
        else:
            return "💬 COZE对话完成"

class N8nPlatform(MessagePlatform):
    """N8N自动化平台服务"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.webhook_url = config.get('webhook_url', '')
        self.api_key = config.get('api_key', '')
        self.triggers = config.get('triggers', [])
        self.enabled = config.get('enabled', False)
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.N8N
    
    def get_platform_name(self) -> str:
        return "N8N自动化工作流"
    
    def is_enabled(self) -> bool:
        return self.enabled and bool(self.webhook_url)
    
    def is_message_relevant(self, message: str, sender: str) -> bool:
        # 根据配置的触发词判断
        if not self.triggers:
            return False
        return any(trigger in message for trigger in self.triggers)
    
    def process_message(self, message: str, sender: str, context: Dict) -> Tuple[bool, str, Dict]:
        """触发N8N工作流"""
        try:
            if not self.is_enabled():
                return False, "N8N平台未启用或配置不完整", {}
            
            payload = {
                "message": message,
                "sender": sender,
                "chat_name": context.get('chat_name', ''),
                "timestamp": context.get('timestamp', ''),
                "trigger_source": "wechat_monitor"
            }
            
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            logger.info(f"触发N8N工作流: {self.webhook_url}")
            
            response = requests.post(
                self.webhook_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json() if response.content else {"status": "triggered"}
                logger.info(f"N8N工作流触发成功: {result}")
                return True, "⚙️ N8N工作流已触发", result
            else:
                error_msg = f"N8N Webhook错误: HTTP {response.status_code}"
                logger.error(error_msg)
                return False, error_msg, {}
                
        except requests.exceptions.Timeout:
            return False, "⏰ N8N Webhook请求超时", {}
        except requests.exceptions.ConnectionError:
            return False, "🌐 无法连接到N8N服务", {}
        except Exception as e:
            error_msg = f"N8N处理失败: {e}"
            logger.error(error_msg)
            return False, error_msg, {}
    
    def should_reply_to_wechat(self, result: Dict) -> bool:
        # 根据N8N工作流返回结果判断
        return result.get('reply_to_wechat', False)
    
    def format_wechat_reply(self, result: Dict) -> str:
        reply_message = result.get('reply_message', '')
        if reply_message:
            return f"⚙️ N8N自动化：\n{reply_message}"
        else:
            return "⚙️ N8N工作流已触发"

class PlatformManager(QObject):
    """多平台管理器"""
    
    # 信号定义
    platform_result = pyqtSignal(str, str, bool, str, dict)  # platform_name, chat_name, success, message, data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.platforms: Dict[PlatformType, MessagePlatform] = {}
        
        # 平台处理优先级（记账优先，其他平台并行）
        self.processing_order = [
            PlatformType.ACCOUNTING,  # 优先处理记账
            PlatformType.DIFY,        # AI工作流
            PlatformType.COZE,        # 对话AI
            PlatformType.N8N,         # 自动化
        ]
    
    def register_platform(self, platform: MessagePlatform):
        """注册平台服务"""
        platform_type = platform.get_platform_type()
        self.platforms[platform_type] = platform
        logger.info(f"注册平台: {platform.get_platform_name()}")
    
    def get_enabled_platforms(self) -> List[MessagePlatform]:
        """获取已启用的平台列表"""
        return [platform for platform in self.platforms.values() if platform.is_enabled()]
    
    def process_message(self, message: str, sender: str, context: Dict) -> List[Dict]:
        """处理消息，返回所有相关平台的处理结果"""
        results = []
        
        for platform_type in self.processing_order:
            if platform_type not in self.platforms:
                continue
                
            platform = self.platforms[platform_type]
            
            # 检查平台是否启用
            if not platform.is_enabled():
                logger.debug(f"平台 {platform.get_platform_name()} 未启用，跳过")
                continue
            
            # 检查消息是否相关
            if not platform.is_message_relevant(message, sender):
                logger.debug(f"消息与平台 {platform.get_platform_name()} 不相关，跳过")
                continue
            
            # 处理消息
            try:
                logger.info(f"使用平台 {platform.get_platform_name()} 处理消息")
                success, msg, data = platform.process_message(message, sender, context)
                
                result = {
                    'platform_type': platform_type.value,
                    'platform_name': platform.get_platform_name(),
                    'success': success,
                    'message': msg,
                    'data': data,
                    'should_reply': platform.should_reply_to_wechat(data) if success else False,
                    'reply_content': platform.format_wechat_reply(data) if success else msg
                }
                
                results.append(result)
                
                # 发出平台处理结果信号
                self.platform_result.emit(
                    platform.get_platform_name(),
                    context.get('chat_name', ''),
                    success,
                    msg,
                    data
                )
                
            except Exception as e:
                error_msg = f"平台 {platform.get_platform_name()} 处理异常: {e}"
                logger.error(error_msg)
                
                error_result = {
                    'platform_type': platform_type.value,
                    'platform_name': platform.get_platform_name(),
                    'success': False,
                    'message': error_msg,
                    'data': {},
                    'should_reply': False,
                    'reply_content': f"❌ {platform.get_platform_name()}处理失败"
                }
                
                results.append(error_result)
                
                # 发出错误信号
                self.platform_result.emit(
                    platform.get_platform_name(),
                    context.get('chat_name', ''),
                    False,
                    error_msg,
                    {}
                )
        
        return results
    
    def get_wechat_replies(self, results: List[Dict]) -> List[str]:
        """获取需要发送到微信的回复"""
        replies = []
        for result in results:
            if result['should_reply'] and result['reply_content']:
                replies.append(result['reply_content'])
        return replies
    
    def get_platform_status(self) -> Dict[str, Dict]:
        """获取所有平台的状态"""
        status = {}
        for platform_type, platform in self.platforms.items():
            status[platform_type.value] = {
                'name': platform.get_platform_name(),
                'enabled': platform.is_enabled(),
                'type': platform_type.value
            }
        return status
