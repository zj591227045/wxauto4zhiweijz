"""
只为记账服务模块
负责与只为记账API的交互
"""

import requests
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class AccountingConfig:
    """记账服务配置"""
    server_url: str = ""
    username: str = ""
    password: str = ""
    token: str = ""
    account_book_id: str = ""
    monitored_chats: List[str] = None
    
    def __post_init__(self):
        if self.monitored_chats is None:
            self.monitored_chats = []

@dataclass
class AccountBook:
    """账本信息"""
    id: str
    name: str
    description: str
    type: str
    is_default: bool
    transaction_count: int = 0
    category_count: int = 0
    budget_count: int = 0

@dataclass
class User:
    """用户信息"""
    id: str
    email: str
    name: str

class AccountingService:
    """只为记账服务类"""
    
    def __init__(self, config: AccountingConfig = None):
        self.config = config or AccountingConfig()
        self.session = requests.Session()
        self.session.timeout = 30
        
    def update_config(self, config: AccountingConfig):
        """更新配置"""
        self.config = config
        if self.config.token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.config.token}'
            })
    
    def login(self, server_url: str, username: str, password: str) -> tuple[bool, str, Optional[User]]:
        """
        登录获取token
        返回: (成功状态, 消息, 用户信息)
        """
        try:
            url = f"{server_url.rstrip('/')}/api/auth/login"
            data = {
                "email": username,
                "password": password
            }
            
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            if 'token' in result and 'user' in result:
                self.config.server_url = server_url
                self.config.username = username
                self.config.password = password
                self.config.token = result['token']
                
                # 更新session header
                self.session.headers.update({
                    'Authorization': f'Bearer {self.config.token}'
                })
                
                user = User(
                    id=result['user']['id'],
                    email=result['user']['email'],
                    name=result['user']['name']
                )
                
                logger.info(f"登录成功: {user.name} ({user.email})")
                return True, "登录成功", user
            else:
                return False, "登录响应格式错误", None
                
        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
        except json.JSONDecodeError as e:
            error_msg = f"响应解析失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"登录失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def get_account_books(self) -> tuple[bool, str, List[AccountBook]]:
        """
        获取账本列表
        返回: (成功状态, 消息, 账本列表)
        """
        try:
            if not self.config.token:
                return False, "请先登录", []
            
            url = f"{self.config.server_url.rstrip('/')}/api/account-books"
            response = self.session.get(url)
            response.raise_for_status()
            
            result = response.json()
            
            if 'data' in result:
                account_books = []
                for book_data in result['data']:
                    book = AccountBook(
                        id=book_data['id'],
                        name=book_data['name'],
                        description=book_data.get('description', ''),
                        type=book_data.get('type', ''),
                        is_default=book_data.get('isDefault', False),
                        transaction_count=book_data.get('transactionCount', 0),
                        category_count=book_data.get('categoryCount', 0),
                        budget_count=book_data.get('budgetCount', 0)
                    )
                    account_books.append(book)
                
                logger.info(f"获取到 {len(account_books)} 个账本")
                return True, "获取成功", account_books
            else:
                return False, "响应格式错误", []
                
        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, []
        except json.JSONDecodeError as e:
            error_msg = f"响应解析失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, []
        except Exception as e:
            error_msg = f"获取账本失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, []
    
    def smart_accounting(self, description: str, account_book_id: str = None) -> tuple[bool, str, Optional[Dict]]:
        """
        智能记账
        返回: (成功状态, 消息, 响应数据)
        """
        try:
            if not self.config.token:
                return False, "请先登录", None
            
            # 使用指定的账本ID或配置中的默认账本ID
            book_id = account_book_id or self.config.account_book_id
            if not book_id:
                return False, "请先选择账本", None
            
            url = f"{self.config.server_url.rstrip('/')}/api/ai/smart-accounting/direct"
            data = {
                "description": description,
                "accountBookId": book_id
            }
            
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"智能记账成功: {description}")
            return True, "记账成功", result
            
        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
        except json.JSONDecodeError as e:
            error_msg = f"响应解析失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"智能记账失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def test_connection(self) -> tuple[bool, str]:
        """
        测试连接
        返回: (成功状态, 消息)
        """
        try:
            if not self.config.server_url:
                return False, "请先配置服务器地址"
            
            # 简单的健康检查
            url = f"{self.config.server_url.rstrip('/')}/api/account-books"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 401:
                return False, "认证失败，请重新登录"
            elif response.status_code == 200:
                return True, "连接正常"
            else:
                return False, f"服务器响应异常: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "连接超时"
        except requests.exceptions.ConnectionError:
            return False, "无法连接到服务器"
        except Exception as e:
            return False, f"连接测试失败: {str(e)}"
