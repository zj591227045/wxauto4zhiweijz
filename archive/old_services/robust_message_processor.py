#!/usr/bin/env python3
"""
健壮的消息处理器
确保消息处理流程的每个环节都有错误处理和重试机制
"""

import time
import logging
import requests
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class ProcessingStatus(Enum):
    """处理状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    IRRELEVANT = "irrelevant"

@dataclass
class ProcessingResult:
    """处理结果"""
    status: ProcessingStatus
    message: str
    should_reply: bool = True
    retry_count: int = 0
    details: Dict[str, Any] = None

class RobustMessageProcessor:
    """健壮的消息处理器"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # 统计信息
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'irrelevant': 0,
            'retries': 0
        }
        
        # 配置管理器
        self._init_config_manager()
    
    def _init_config_manager(self):
        """初始化配置管理器"""
        try:
            from app.utils.config_manager import ConfigManager
            self.config_manager = ConfigManager()
            logger.info("配置管理器初始化成功")
        except Exception as e:
            logger.error(f"初始化配置管理器失败: {e}")
            self.config_manager = None
    
    def process_message(self, message_content: str, sender_name: str = None) -> Tuple[bool, str]:
        """
        处理消息的主入口
        
        Args:
            message_content: 消息内容
            sender_name: 发送者名称
            
        Returns:
            (success, result_message)
        """
        try:
            self.stats['total_processed'] += 1
            
            # 验证输入
            if not self._validate_input(message_content, sender_name):
                result = ProcessingResult(
                    status=ProcessingStatus.FAILED,
                    message="输入验证失败",
                    should_reply=False
                )
                return self._handle_result(result)
            
            # 获取配置
            config = self._get_accounting_config()
            if not config:
                result = ProcessingResult(
                    status=ProcessingStatus.FAILED,
                    message="记账配置不可用",
                    should_reply=True
                )
                return self._handle_result(result)
            
            # 处理消息（带重试）
            result = self._process_with_retry(message_content, sender_name, config)
            
            return self._handle_result(result)
            
        except Exception as e:
            logger.error(f"处理消息异常: {e}")
            self.stats['failed'] += 1
            return False, f"消息处理异常: {str(e)}"
    
    def _validate_input(self, message_content: str, sender_name: str) -> bool:
        """验证输入参数"""
        try:
            # 检查消息内容
            if not message_content or not isinstance(message_content, str):
                logger.warning("消息内容为空或类型错误")
                return False
            
            if len(message_content.strip()) == 0:
                logger.warning("消息内容为空白")
                return False
            
            # 检查发送者名称
            if sender_name is not None and not isinstance(sender_name, str):
                logger.warning("发送者名称类型错误")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"输入验证异常: {e}")
            return False
    
    def _get_accounting_config(self) -> Optional[Dict[str, Any]]:
        """获取记账配置"""
        try:
            if not self.config_manager:
                logger.error("配置管理器不可用")
                return None
            
            # 获取记账配置
            config = self.config_manager.get_accounting_config()
            
            # 验证必要字段
            required_fields = ['server_url', 'token', 'account_book_id']
            for field in required_fields:
                if not config.get(field):
                    logger.error(f"记账配置缺少必要字段: {field}")
                    return None
            
            return config
            
        except Exception as e:
            logger.error(f"获取记账配置失败: {e}")
            return None
    
    def _process_with_retry(self, message_content: str, sender_name: str, config: Dict[str, Any]) -> ProcessingResult:
        """带重试的消息处理"""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # 调用智能记账API
                result = self._call_smart_accounting_api(message_content, sender_name, config)
                
                # 如果成功或不相关，直接返回
                if result.status in [ProcessingStatus.SUCCESS, ProcessingStatus.IRRELEVANT]:
                    return result
                
                # 如果失败但不需要重试，直接返回
                if result.status == ProcessingStatus.FAILED and not self._should_retry(result, attempt):
                    return result
                
                # 记录重试
                if attempt < self.max_retries:
                    self.stats['retries'] += 1
                    logger.warning(f"第 {attempt + 1} 次尝试失败，{self.retry_delay}秒后重试: {result.message}")
                    time.sleep(self.retry_delay)
                    last_error = result.message
                else:
                    # 达到最大重试次数
                    result.message = f"达到最大重试次数 ({self.max_retries})，最后错误: {result.message}"
                    return result
                
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    self.stats['retries'] += 1
                    logger.error(f"第 {attempt + 1} 次尝试异常，{self.retry_delay}秒后重试: {e}")
                    time.sleep(self.retry_delay)
                else:
                    return ProcessingResult(
                        status=ProcessingStatus.FAILED,
                        message=f"处理异常，达到最大重试次数: {last_error}",
                        retry_count=attempt
                    )
        
        # 不应该到达这里
        return ProcessingResult(
            status=ProcessingStatus.FAILED,
            message=f"未知错误，最后错误: {last_error}",
            retry_count=self.max_retries
        )
    
    def _call_smart_accounting_api(self, message_content: str, sender_name: str, config: Dict[str, Any]) -> ProcessingResult:
        """调用智能记账API"""
        try:
            # 构建请求URL
            server_url = config['server_url'].rstrip('/')
            api_url = f"{server_url}/api/ai/smart-accounting/direct"
            
            # 构建请求数据
            request_data = {
                "description": message_content,
                "accountBookId": config['account_book_id']
            }
            
            # 添加用户名信息
            if sender_name:
                request_data["userName"] = sender_name
            
            # 构建请求头
            headers = {
                'Authorization': f'Bearer {config["token"]}',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"调用智能记账API: {message_content[:50]}...")
            
            # 发送请求
            response = requests.post(
                api_url,
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            # 处理响应
            return self._handle_api_response(response, message_content)
            
        except requests.exceptions.Timeout:
            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                message="记账服务请求超时，请稍后重试",
                should_reply=True
            )
        except requests.exceptions.ConnectionError:
            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                message="无法连接到记账服务器，请检查网络连接",
                should_reply=True
            )
        except Exception as e:
            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                message=f"调用记账API异常: {str(e)}",
                should_reply=True
            )
    
    def _handle_api_response(self, response: requests.Response, message_content: str) -> ProcessingResult:
        """处理API响应"""
        try:
            # 检查HTTP状态码
            if response.status_code == 401:
                return ProcessingResult(
                    status=ProcessingStatus.FAILED,
                    message="记账服务认证失败，请检查token配置",
                    should_reply=True
                )
            elif response.status_code == 403:
                return ProcessingResult(
                    status=ProcessingStatus.FAILED,
                    message="记账服务访问被拒绝，请检查权限配置",
                    should_reply=True
                )
            elif response.status_code != 200:
                return ProcessingResult(
                    status=ProcessingStatus.FAILED,
                    message=f"记账服务返回错误: HTTP {response.status_code}",
                    should_reply=True
                )
            
            # 解析JSON响应
            try:
                result_data = response.json()
            except ValueError as e:
                return ProcessingResult(
                    status=ProcessingStatus.FAILED,
                    message="记账服务返回无效的JSON响应",
                    should_reply=True
                )
            
            # 检查业务逻辑结果
            if result_data.get('success'):
                # 记账成功，解析结果
                formatted_result = self._format_success_result(result_data)
                return ProcessingResult(
                    status=ProcessingStatus.SUCCESS,
                    message=formatted_result,
                    should_reply=True,
                    details=result_data
                )
            else:
                # 记账失败，检查是否是不相关信息
                error_message = result_data.get('message', '未知错误')
                
                if self._is_irrelevant_message(error_message):
                    return ProcessingResult(
                        status=ProcessingStatus.IRRELEVANT,
                        message=error_message,
                        should_reply=False
                    )
                else:
                    return ProcessingResult(
                        status=ProcessingStatus.FAILED,
                        message=f"记账失败: {error_message}",
                        should_reply=True
                    )
            
        except Exception as e:
            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                message=f"处理API响应异常: {str(e)}",
                should_reply=True
            )
    
    def _format_success_result(self, result_data: Dict[str, Any]) -> str:
        """格式化成功结果"""
        try:
            # 提取关键信息
            data = result_data.get('data', {})
            
            # 构建格式化消息
            formatted_parts = ["✅ 记账成功！"]
            
            # 添加明细信息
            if 'description' in data:
                formatted_parts.append(f"📝 明细：{data['description']}")
            
            if 'date' in data:
                formatted_parts.append(f"📅 日期：{data['date']}")
            
            if 'direction' in data and 'category' in data:
                formatted_parts.append(f"💸 方向和分类：{data['direction']} - {data['category']}")
            
            if 'amount' in data:
                formatted_parts.append(f"💰 金额：{data['amount']}")
            
            if 'budget' in data:
                formatted_parts.append(f"📊 预算：{data['budget']}")
            
            return "\n".join(formatted_parts)
            
        except Exception as e:
            logger.warning(f"格式化成功结果失败: {e}")
            return "✅ 记账成功！"
    
    def _is_irrelevant_message(self, error_message: str) -> bool:
        """判断是否是不相关信息"""
        irrelevant_keywords = [
            "信息与记账无关",
            "聊天与记账无关",
            "无法识别记账信息",
            "不是记账相关内容"
        ]
        
        return any(keyword in error_message for keyword in irrelevant_keywords)
    
    def _should_retry(self, result: ProcessingResult, attempt: int) -> bool:
        """判断是否应该重试"""
        # 不相关信息不重试
        if result.status == ProcessingStatus.IRRELEVANT:
            return False
        
        # 认证错误不重试
        if "认证失败" in result.message or "访问被拒绝" in result.message:
            return False
        
        # 网络相关错误可以重试
        retry_keywords = [
            "超时",
            "连接",
            "网络",
            "服务器错误",
            "HTTP 5"
        ]
        
        return any(keyword in result.message for keyword in retry_keywords)
    
    def _handle_result(self, result: ProcessingResult) -> Tuple[bool, str]:
        """处理最终结果"""
        try:
            # 更新统计
            if result.status == ProcessingStatus.SUCCESS:
                self.stats['successful'] += 1
            elif result.status == ProcessingStatus.IRRELEVANT:
                self.stats['irrelevant'] += 1
            else:
                self.stats['failed'] += 1
            
            # 记录日志
            if result.status == ProcessingStatus.SUCCESS:
                logger.info(f"消息处理成功: {result.message[:100]}...")
            elif result.status == ProcessingStatus.IRRELEVANT:
                logger.info(f"消息与记账无关: {result.message}")
            else:
                logger.error(f"消息处理失败: {result.message}")
            
            # 返回结果
            success = result.status == ProcessingStatus.SUCCESS
            return success, result.message
            
        except Exception as e:
            logger.error(f"处理最终结果异常: {e}")
            self.stats['failed'] += 1
            return False, f"处理结果异常: {str(e)}"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.stats['total_processed']
        if total > 0:
            success_rate = (self.stats['successful'] / total) * 100
            irrelevant_rate = (self.stats['irrelevant'] / total) * 100
            failure_rate = (self.stats['failed'] / total) * 100
        else:
            success_rate = irrelevant_rate = failure_rate = 0
        
        return {
            **self.stats,
            'success_rate': round(success_rate, 2),
            'irrelevant_rate': round(irrelevant_rate, 2),
            'failure_rate': round(failure_rate, 2)
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'irrelevant': 0,
            'retries': 0
        }
