"""
简化版消息处理器
专门用于处理微信消息并调用记账服务
"""

import logging
import requests
from typing import Dict, Optional, Tuple
from app.utils.config_manager import ConfigManager

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class SimpleMessageProcessor:
    """简化版消息处理器"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        
    def process_message(self, message_content: str, sender_name: str = None) -> Tuple[bool, str]:
        """
        处理消息并调用记账服务

        Args:
            message_content: 消息内容
            sender_name: 发送者名称（优先使用sender_remark，如果没有则使用sender）

        Returns:
            (成功状态, 结果消息)
        """
        try:
            # 获取记账配置 - 从状态管理器读取
            from app.utils.state_manager import state_manager
            accounting_status = state_manager.get_accounting_service_status()

            # 检查配置是否完整
            server_url = accounting_status.get('server_url')
            token = accounting_status.get('token')
            account_book_id = accounting_status.get('selected_account_book')

            logger.info(f"记账配置检查 - server_url: {server_url}, token: {'***' if token else 'None'}, account_book_id: {account_book_id}")

            if not all([server_url, token, account_book_id]):
                missing_configs = []
                if not server_url: missing_configs.append('server_url')
                if not token: missing_configs.append('token')
                if not account_book_id: missing_configs.append('account_book_id')

                error_msg = f"记账配置不完整，缺少: {', '.join(missing_configs)}"
                logger.error(error_msg)
                return False, error_msg

            # 调用智能记账API
            success, result_msg = self._call_smart_accounting_api(
                message_content,
                server_url,
                token,
                account_book_id,
                sender_name
            )
            
            return success, result_msg
            
        except Exception as e:
            error_msg = f"处理消息失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def _call_smart_accounting_api(self, message_content: str, server_url: str,
                                 token: str, account_book_id: str, sender_name: str = None) -> Tuple[bool, str]:
        """
        调用智能记账API

        Args:
            message_content: 消息内容
            server_url: 服务器地址
            token: 认证令牌
            account_book_id: 账本ID
            sender_name: 发送者名称

        Returns:
            (成功状态, 结果消息)
        """
        try:
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
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"智能记账API响应: {result}")
                
                # 检查是否有smartAccountingResult字段（新格式）
                if 'smartAccountingResult' in result:
                    formatted_msg = self._format_accounting_response(result)
                    logger.info(f"记账成功，格式化响应: {formatted_msg}")
                    return True, formatted_msg
                
                # 兼容旧格式
                elif result.get('success', False) or result.get('code') == 0 or response.status_code == 201:
                    success_msg = "✅ 记账成功！"
                    if 'data' in result:
                        data_info = result['data']
                        if isinstance(data_info, dict):
                            amount = data_info.get('amount', '')
                            category = data_info.get('category', '')
                            if amount and category:
                                success_msg = f"✅ 记账成功！\n💰 {category} {amount}元"
                            elif amount:
                                success_msg = f"✅ 记账成功！\n💰 {amount}元"
                    
                    logger.info(success_msg)
                    return True, success_msg
                else:
                    error_msg = result.get('message', '记账失败')
                    logger.error(f"智能记账失败: {error_msg}")
                    return False, f"❌ 记账失败: {error_msg}"
            
            elif response.status_code == 401:
                error_msg = "记账服务认证失败，请检查token是否有效"
                logger.error(error_msg)
                return False, f"🔐 {error_msg}"

            elif response.status_code == 404:
                error_msg = "记账服务API不存在，请检查server_url配置"
                logger.error(error_msg)
                return False, f"🔍 {error_msg}"

            elif response.status_code == 429:
                error_msg = "访问过于频繁，请稍后再试"
                logger.error(error_msg)
                return False, f"⏱️ {error_msg}"

            elif response.status_code == 402:
                error_msg = "token使用达到限制，请检查账户余额"
                logger.error(error_msg)
                return False, f"💳 {error_msg}"

            else:
                error_msg = f"记账服务返回错误: HTTP {response.status_code}"
                logger.error(error_msg)
                try:
                    error_detail = response.json().get('message', '')
                    if error_detail:
                        error_msg += f" - {error_detail}"
                        # 检查错误消息中的特定关键词
                        if 'token' in error_detail.lower() and ('limit' in error_detail.lower() or '限制' in error_detail):
                            return False, f"💳 token使用达到限制: {error_detail}"
                        elif 'rate' in error_detail.lower() or '频繁' in error_detail or 'too many' in error_detail.lower():
                            return False, f"⏱️ 访问过于频繁: {error_detail}"
                except:
                    pass
                return False, f"⚠️ {error_msg}"
                
        except requests.exceptions.Timeout:
            error_msg = "记账服务请求超时"
            logger.error(error_msg)
            return False, f"⏰ {error_msg}"
            
        except requests.exceptions.ConnectionError:
            error_msg = "无法连接到记账服务，请检查server_url配置"
            logger.error(error_msg)
            return False, f"🌐 {error_msg}"
            
        except Exception as e:
            error_msg = f"调用记账API异常: {e}"
            logger.error(error_msg)
            return False, f"💥 {error_msg}"
    
    def _format_accounting_response(self, result: Dict) -> str:
        """
        格式化记账响应

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

            # 检查是否有记账数据（如果有amount字段说明记账成功）
            if smart_result.get('amount') is not None:
                # 提取记账信息
                amount = smart_result.get('amount', '')
                category_name = smart_result.get('categoryName', '')
                original_description = smart_result.get('originalDescription', '')
                account_type = smart_result.get('type', 'EXPENSE')
                budget_name = smart_result.get('budgetName', '')
                budget_owner = smart_result.get('budgetOwnerName', '')
                date_str = smart_result.get('date', '')

                # 格式化日期
                formatted_date = date_str
                if date_str:
                    try:
                        from datetime import datetime
                        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        formatted_date = date_obj.strftime('%Y-%m-%d')
                    except:
                        formatted_date = date_str[:10] if len(date_str) >= 10 else date_str

                # 确定交易类型和图标
                if account_type == 'INCOME':
                    type_info = {'text': '收入', 'icon': '💰'}
                else:
                    type_info = {'text': '支出', 'icon': '💸'}

                # 确定分类图标
                category_icon = '📝'
                if '餐饮' in category_name or '食' in category_name:
                    category_icon = '🍽️'
                elif '交通' in category_name or '出行' in category_name:
                    category_icon = '🚗'
                elif '购物' in category_name or '商品' in category_name:
                    category_icon = '🛒'
                elif '娱乐' in category_name:
                    category_icon = '🎮'
                elif '学习' in category_name or '教育' in category_name:
                    category_icon = '📚'
                elif '医疗' in category_name or '健康' in category_name:
                    category_icon = '🏥'

                # 构建格式化消息
                message_lines = [
                    "✅ 记账成功！",
                    f"📝 明细：{original_description}",
                    f"📅 日期：{formatted_date}",
                    f"{type_info['icon']} 方向：{type_info['text']}；分类：{category_icon}{category_name}",
                    f"💰 金额：{amount}元"
                ]

                # 添加预算信息（如果有）
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

    def get_processing_statistics(self, chat_name: str) -> Dict:
        """
        获取处理统计信息（兼容性方法）

        Args:
            chat_name: 聊天对象名称

        Returns:
            统计信息字典
        """
        # 简化版本返回默认统计信息
        return {
            'total_messages': 0,
            'processed_messages': 0,
            'successful_accounting': 0,
            'failed_accounting': 0,
            'success_rate': 0.0
        }
