#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息投递服务
专门负责：
1. 发送消息到智能记账API
2. 回复消息到微信
3. 处理各种响应状态
"""

import logging
import requests
from typing import Dict, Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSignal
from app.utils.config_manager import ConfigManager

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class MessageDeliveryService(QObject):
    """消息投递服务"""
    
    # 信号定义
    accounting_completed = pyqtSignal(str, bool, str)  # chat_name, success, result_msg
    wechat_reply_sent = pyqtSignal(str, bool, str)     # chat_name, success, message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        
    def process_and_deliver_message(self, chat_name: str, message_content: str, sender_name: str = None) -> Tuple[bool, str]:
        """
        处理消息：发送到记账API并根据结果决定是否回复微信
        
        Args:
            chat_name: 聊天对象名称
            message_content: 消息内容
            sender_name: 发送者名称
            
        Returns:
            (处理成功状态, 结果消息)
        """
        try:
            # 1. 发送到智能记账API
            accounting_success, accounting_result = self._send_to_accounting_api(message_content, sender_name)
            
            # 发出记账完成信号
            self.accounting_completed.emit(chat_name, accounting_success, accounting_result)
            
            # 2. 根据记账结果决定是否回复微信
            should_reply = self._should_send_wechat_reply(accounting_result)
            
            if should_reply:
                # 3. 发送回复到微信
                reply_success = self._send_wechat_reply(chat_name, accounting_result)
                self.wechat_reply_sent.emit(chat_name, reply_success, accounting_result)
                
                if not reply_success:
                    logger.warning(f"[{chat_name}] 记账成功但微信回复失败")
            else:
                logger.info(f"[{chat_name}] 消息与记账无关，不发送回复")
                self.wechat_reply_sent.emit(chat_name, True, "消息与记账无关，已忽略")
            
            return accounting_success, accounting_result
            
        except Exception as e:
            error_msg = f"消息投递处理失败: {e}"
            logger.error(error_msg)
            self.accounting_completed.emit(chat_name, False, error_msg)
            return False, error_msg
    
    def _send_to_accounting_api(self, message_content: str, sender_name: str = None) -> Tuple[bool, str]:
        """
        发送消息到智能记账API
        
        Args:
            message_content: 消息内容
            sender_name: 发送者名称
            
        Returns:
            (成功状态, 结果消息)
        """
        try:
            # 获取配置
            config = self.config_manager.get_accounting_config()
            server_url = config.get('server_url', '').strip()
            token = config.get('token', '').strip()
            account_book_id = config.get('account_book_id', '').strip()

            if not all([server_url, token, account_book_id]):
                missing_configs = []
                if not server_url: missing_configs.append('server_url')
                if not token: missing_configs.append('token')
                if not account_book_id: missing_configs.append('account_book_id')

                error_msg = f"🔧 记账配置不完整，缺少: {', '.join(missing_configs)}"
                logger.error(error_msg)
                return False, error_msg

            # 构建API请求
            api_url = f"{server_url.rstrip('/')}/api/ai/smart-accounting/direct"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            data = {
                'description': message_content,
                'accountBookId': account_book_id
            }

            # 如果有发送者名称，添加到请求数据中
            if sender_name:
                data['userName'] = sender_name
            
            logger.info(f"调用智能记账API: {api_url}")
            logger.debug(f"请求数据: {data}")
            
            # 发送API请求
            response = requests.post(api_url, headers=headers, json=data, timeout=30)
            
            # 处理HTTP错误
            if response.status_code == 401:
                return False, "🔐 记账服务认证失败，请检查token是否有效"
            elif response.status_code == 402:
                return False, "💳 token使用达到限制，请检查账户余额"
            elif response.status_code == 404:
                return False, "🔍 记账服务API不存在，请检查server_url配置"
            elif response.status_code == 429:
                return False, "⏱️ 访问过于频繁，请稍后再试"
            elif response.status_code != 200:
                return False, f"⚠️ 记账服务返回错误: HTTP {response.status_code}"
            
            # 解析响应
            try:
                result = response.json()
                logger.debug(f"API响应: {result}")
                
                # 格式化响应消息
                formatted_msg = self._format_accounting_response(result)
                return True, formatted_msg
                
            except ValueError as e:
                logger.error(f"解析API响应失败: {e}")
                return False, f"📄 记账服务响应格式错误: {e}"
            
        except requests.exceptions.Timeout:
            return False, "⏰ 记账服务请求超时，请稍后再试"
        except requests.exceptions.ConnectionError:
            return False, "🌐 无法连接到记账服务，请检查网络和server_url配置"
        except Exception as e:
            logger.error(f"调用智能记账API失败: {e}")
            return False, f"❌ 记账服务调用失败: {e}"
    
    def _format_accounting_response(self, result: Dict) -> str:
        """
        格式化记账API响应
        
        Args:
            result: API响应结果
            
        Returns:
            格式化的消息
        """
        try:
            smart_result = result.get('smartAccountingResult', {})

            # 检查是否与记账无关
            if smart_result.get('isRelevant') is False:
                return "信息与记账无关"

            # 检查是否有错误信息
            if 'error' in smart_result:
                error_msg = smart_result.get('error', '记账失败')
                if 'token' in error_msg.lower() and ('limit' in error_msg.lower() or '限制' in error_msg):
                    return f"💳 token使用达到限制: {error_msg}"
                elif 'rate' in error_msg.lower() or '频繁' in error_msg or 'too many' in error_msg.lower():
                    return f"⏱️ 访问过于频繁: {error_msg}"
                else:
                    return f"❌ 记账失败: {error_msg}"

            # 检查是否有记账成功的信息
            if 'amount' in smart_result:
                # 记账成功，格式化详细信息
                message_lines = ["✅ 记账成功！"]

                # 基本信息
                description = smart_result.get('originalDescription', smart_result.get('description', ''))
                if description:
                    message_lines.append(f"📝 明细：{description}")

                # 日期信息
                date = smart_result.get('date', '')
                if date:
                    # 简化日期格式
                    try:
                        if 'T' in date:
                            date = date.split('T')[0]
                        message_lines.append(f"📅 日期：{date}")
                    except:
                        message_lines.append(f"📅 日期：{date}")

                # 分类和方向信息
                category_name = smart_result.get('categoryName', smart_result.get('category', ''))
                account_type = smart_result.get('type', 'EXPENSE')
                
                direction = "收入" if account_type == 'INCOME' else "支出"
                category_emoji = "💰" if account_type == 'INCOME' else "🍽️" if "餐" in category_name else "🛒"
                
                if category_name:
                    message_lines.append(f"💸 方向：{direction}；分类：{category_emoji}{category_name}")
                else:
                    message_lines.append(f"💸 方向：{direction}")

                # 金额信息
                amount = smart_result.get('amount', 0)
                message_lines.append(f"💰 金额：{amount}元")

                # 预算信息（如果有）
                budget_name = smart_result.get('budgetName', smart_result.get('budget', ''))
                budget_owner = smart_result.get('budgetOwnerName', smart_result.get('budgetOwner', ''))
                
                if budget_name and budget_owner:
                    message_lines.append(f"📊 预算：{budget_name}（{budget_owner}）")
                elif budget_name:
                    message_lines.append(f"📊 预算：{budget_name}")

                return "\n".join(message_lines)
            else:
                # 没有amount字段，可能是失败或其他情况
                error_msg = smart_result.get('message', '记账失败')
                return f"❌ 记账失败: {error_msg}"

        except Exception as e:
            logger.error(f"格式化响应失败: {e}")
            # 如果格式化失败，尝试提取基本信息
            try:
                smart_result = result.get('smartAccountingResult', {})
                amount = smart_result.get('amount', '')
                description = smart_result.get('originalDescription', '')
                if amount and description:
                    return f"✅ 记账成功！\n💰 {description} {amount}元"
                else:
                    return "✅ 记账完成"
            except:
                return "✅ 记账完成"
    
    def _should_send_wechat_reply(self, result_msg: str) -> bool:
        """
        判断是否应该发送回复到微信
        
        Args:
            result_msg: 记账结果消息
            
        Returns:
            True表示应该发送回复，False表示不应该发送
        """
        # 如果是"信息与记账无关"，不发送回复
        if "信息与记账无关" in result_msg:
            return False
        
        # 其他情况（记账成功、失败、错误等）都发送回复
        return True
    
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
            # 获取微信API配置
            api_config = self.config_manager.get_api_config()
            api_base_url = api_config.get('base_url', 'http://localhost:8000').rstrip('/')
            api_key = api_config.get('api_key', '')
            
            if not api_key:
                logger.error("API密钥未配置")
                return False
            
            # 构建发送消息的API请求
            send_url = f"{api_base_url}/api/chat-window/message/send"
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': api_key
            }
            data = {
                "who": chat_name,
                "message": message
            }
            
            logger.debug(f"发送微信回复: {send_url}")
            logger.debug(f"请求数据: {data}")
            
            response = requests.post(send_url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') == 0:
                logger.info(f"[{chat_name}] 微信回复发送成功: {message[:50]}...")
                return True
            else:
                logger.error(f"[{chat_name}] 微信回复发送失败: {result.get('message', '未知错误')}")
                return False
                
        except Exception as e:
            logger.error(f"[{chat_name}] 发送微信回复异常: {e}")
            return False
