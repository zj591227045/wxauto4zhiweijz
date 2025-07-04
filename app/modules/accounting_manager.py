"""
只为记账服务管理模块
整合所有记账相关功能，包括API调用、token管理、认证等
"""

import logging
import requests
import json
import base64
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal

from .base_interfaces import (
    ConfigurableService, ServiceStatus, HealthStatus, ServiceInfo, 
    HealthCheckResult, IAccountingManager
)

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Token信息"""
    token: str
    expires_at: Optional[datetime] = None
    user_id: str = ""
    email: str = ""
    
    def is_expired(self) -> bool:
        """检查token是否过期"""
        if not self.expires_at:
            return False
        return datetime.now() >= self.expires_at - timedelta(minutes=5)  # 提前5分钟过期


@dataclass
class AccountingConfig:
    """记账配置"""
    server_url: str = ""
    username: str = ""
    password: str = ""
    account_book_id: str = ""
    auto_refresh_token: bool = True
    token_refresh_interval: int = 300  # 5分钟检查一次


class AccountingManager(ConfigurableService, IAccountingManager):
    """只为记账服务管理器"""
    
    # 信号定义
    login_completed = pyqtSignal(bool, str, dict)      # (success, message, user_info)
    token_refreshed = pyqtSignal(bool, str)            # (success, message)
    accounting_completed = pyqtSignal(bool, str, dict) # (success, message, result)
    config_updated = pyqtSignal(dict)                  # (new_config)
    
    def __init__(self, config_manager=None, parent=None):
        super().__init__("accounting_manager", parent)

        self.config_manager = config_manager
        self._config = AccountingConfig()
        self._token_info: Optional[TokenInfo] = None
        self._lock = threading.RLock()

        # HTTP会话
        self._session = requests.Session()
        self._session.timeout = 30

        # Token刷新线程
        self._refresh_thread = None
        self._stop_refresh = threading.Event()

        # 统计信息
        self._stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'token_refreshes': 0
        }

        logger.info("记账管理器初始化完成")
    
    def start(self) -> bool:
        """启动服务"""
        try:
            self._update_status(ServiceStatus.STARTING)

            # 加载配置
            if not self._load_config():
                logger.warning("加载配置失败，使用默认配置")
                self._update_status(ServiceStatus.ERROR)
                self._update_health(HealthStatus.UNHEALTHY)
                return False

            # 尝试自动登录获取token
            if self._config.auto_login and all([self._config.server_url, self._config.username, self._config.password]):
                logger.info("开始自动登录获取token...")
                success, message = self._auto_login()
                if success:
                    logger.info("自动登录成功")
                else:
                    logger.warning(f"自动登录失败: {message}")

            # 启动token刷新线程
            self._start_token_refresh_thread()

            self._update_status(ServiceStatus.RUNNING)
            self._update_health(HealthStatus.HEALTHY)
            return True

        except Exception as e:
            logger.error(f"启动记账管理器失败: {e}")
            self._update_status(ServiceStatus.ERROR)
            self._update_health(HealthStatus.UNHEALTHY)
            return False
    
    def stop(self) -> bool:
        """停止服务"""
        try:
            self._update_status(ServiceStatus.STOPPING)
            
            # 停止token刷新线程
            self._stop_refresh.set()
            if self._refresh_thread and self._refresh_thread.is_alive():
                self._refresh_thread.join(timeout=5)
            
            # 关闭HTTP会话
            self._session.close()
            
            self._update_status(ServiceStatus.STOPPED)
            self._update_health(HealthStatus.UNKNOWN)
            return True
            
        except Exception as e:
            logger.error(f"停止记账管理器失败: {e}")
            return False
    
    def restart(self) -> bool:
        """重启服务"""
        if self.stop():
            time.sleep(1)
            return self.start()
        return False
    
    def get_info(self) -> ServiceInfo:
        """获取服务信息"""
        details = {
            'server_url': self._config.server_url,
            'username': self._config.username,
            'account_book_id': self._config.account_book_id,
            'has_token': bool(self._token_info and self._token_info.token),
            'token_expired': self._token_info.is_expired() if self._token_info else True,
            'stats': self._stats.copy()
        }
        
        return ServiceInfo(
            name=self.service_name,
            status=self.status,
            health=self.health,
            message=f"记账服务{'已登录' if self._token_info else '未登录'}",
            details=details
        )
    
    def check_health(self) -> HealthCheckResult:
        """检查服务健康状态"""
        start_time = time.time()
        
        try:
            # 检查配置
            if not self._config.server_url:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="服务器地址未配置",
                    details={'config_complete': False}
                )
            
            # 检查token状态
            token_status = "无token"
            if self._token_info:
                if self._token_info.is_expired():
                    token_status = "token已过期"
                else:
                    token_status = "token有效"
            
            # 尝试简单的API调用来验证连接
            try:
                response = self._session.get(
                    f"{self._config.server_url.rstrip('/')}/api/health",
                    timeout=10
                )
                api_accessible = response.status_code == 200
            except:
                api_accessible = False
            
            # 判断健康状态
            if not api_accessible:
                status = HealthStatus.UNHEALTHY
                message = "无法连接到记账服务器"
            elif not self._token_info or self._token_info.is_expired():
                status = HealthStatus.DEGRADED
                message = f"记账服务可访问，但{token_status}"
            else:
                status = HealthStatus.HEALTHY
                message = "记账服务运行正常"
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    'api_accessible': api_accessible,
                    'token_status': token_status,
                    'server_url': self._config.server_url
                },
                response_time=response_time
            )
            
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"健康检查异常: {str(e)}",
                details={'exception': str(e)},
                response_time=time.time() - start_time
            )
    
    def update_config(self, config: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            with self._lock:
                # 更新配置
                if 'server_url' in config:
                    self._config.server_url = config['server_url']
                if 'username' in config:
                    self._config.username = config['username']
                if 'password' in config:
                    self._config.password = config['password']
                if 'account_book_id' in config:
                    self._config.account_book_id = config['account_book_id']
                if 'auto_refresh_token' in config:
                    self._config.auto_refresh_token = config['auto_refresh_token']
                
                # 保存配置
                self._save_config()
                
                # 发出配置更新信号
                self.config_updated.emit(self.get_config())
                
                logger.info("记账配置更新成功")
                return True
                
        except Exception as e:
            logger.error(f"更新记账配置失败: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'server_url': self._config.server_url,
            'username': self._config.username,
            'account_book_id': self._config.account_book_id,
            'auto_refresh_token': self._config.auto_refresh_token,
            'token_refresh_interval': self._config.token_refresh_interval
        }
    
    # IAccountingManager接口实现
    
    def login(self, server_url: str, username: str, password: str) -> Tuple[bool, str]:
        """登录"""
        try:
            with self._lock:
                self._stats['total_requests'] += 1
                
                # 构建登录请求
                url = f"{server_url.rstrip('/')}/api/auth/login"
                data = {
                    "email": username,
                    "password": password
                }
                
                logger.info(f"开始登录: {username}")
                
                response = self._session.post(url, json=data, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                
                if 'token' in result and 'user' in result:
                    token = result['token']
                    user = result['user']
                    
                    # 解析token信息
                    token_info = self._parse_token(token)
                    if token_info:
                        token_info.user_id = user.get('id', '')
                        token_info.email = user.get('email', '')
                        
                        self._token_info = token_info
                        
                        # 更新HTTP会话头
                        self._session.headers.update({
                            'Authorization': f'Bearer {token}'
                        })
                        
                        # 更新配置
                        self._config.server_url = server_url
                        self._config.username = username
                        self._config.password = password
                        
                        # 保存状态
                        self._save_token_to_state()
                        self._save_config()
                        
                        self._stats['successful_requests'] += 1
                        
                        logger.info("登录成功")
                        self.login_completed.emit(True, "登录成功", user)
                        return True, "登录成功"
                    else:
                        self._stats['failed_requests'] += 1
                        error_msg = "Token解析失败"
                        logger.error(error_msg)
                        self.login_completed.emit(False, error_msg, {})
                        return False, error_msg
                else:
                    self._stats['failed_requests'] += 1
                    error_msg = "登录响应格式错误"
                    logger.error(error_msg)
                    self.login_completed.emit(False, error_msg, {})
                    return False, error_msg
                    
        except requests.exceptions.RequestException as e:
            self._stats['failed_requests'] += 1
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(error_msg)
            self.login_completed.emit(False, error_msg, {})
            return False, error_msg
        except Exception as e:
            self._stats['failed_requests'] += 1
            error_msg = f"登录失败: {str(e)}"
            logger.error(error_msg)
            self.login_completed.emit(False, error_msg, {})
            return False, error_msg
    
    def smart_accounting(self, description: str, sender_name: str = None) -> Tuple[bool, str]:
        """智能记账"""
        try:
            with self._lock:
                self._stats['total_requests'] += 1
                
                # 检查token
                if not self._token_info or not self._token_info.token:
                    # 尝试自动登录
                    if not self._auto_login():
                        self._stats['failed_requests'] += 1
                        error_msg = "未登录且自动登录失败"
                        self.accounting_completed.emit(False, error_msg, {})
                        return False, error_msg
                
                # 检查token是否过期
                if self._token_info.is_expired():
                    if not self._refresh_token():
                        self._stats['failed_requests'] += 1
                        error_msg = "Token已过期且刷新失败"
                        self.accounting_completed.emit(False, error_msg, {})
                        return False, error_msg
                
                # 构建记账请求
                url = f"{self._config.server_url.rstrip('/')}/api/ai/smart-accounting/direct"
                data = {
                    "description": description,
                    "accountBookId": self._config.account_book_id
                }
                
                # 添加发送者信息
                if sender_name:
                    data["userName"] = sender_name
                
                headers = {
                    'Authorization': f'Bearer {self._token_info.token}',
                    'Content-Type': 'application/json'
                }
                
                logger.info(f"调用智能记账API: {description[:50]}...")
                logger.debug(f"请求URL: {url}")
                logger.debug(f"请求头: {headers}")
                logger.debug(f"请求数据: {data}")

                response = self._session.post(url, json=data, headers=headers, timeout=30)

                logger.debug(f"响应状态码: {response.status_code}")
                logger.debug(f"响应头: {dict(response.headers)}")
                if response.status_code != 200:
                    logger.debug(f"响应内容: {response.text}")

                
                if response.status_code == 401:
                    # 认证失败，尝试刷新token
                    if self._refresh_token():
                        # 使用新token重试
                        headers['Authorization'] = f'Bearer {self._token_info.token}'
                        response = self._session.post(url, json=data, headers=headers, timeout=30)
                    else:
                        self._stats['failed_requests'] += 1
                        error_msg = "认证失败且token刷新失败"
                        self.accounting_completed.emit(False, error_msg, {})
                        return False, error_msg
                
                # 处理响应
                if response.status_code == 200 or response.status_code == 201:
                    # 成功响应
                    result = response.json()
                    success_msg = self._parse_accounting_response(result)

                    self._stats['successful_requests'] += 1
                    logger.info("智能记账成功")
                    self.accounting_completed.emit(True, success_msg, result)
                    return True, success_msg

                elif response.status_code == 400:
                    # 400错误可能是业务逻辑错误，需要特殊处理
                    try:
                        error_result = response.json()
                        error_info = error_result.get('info', '')
                        error_msg = error_result.get('error', '')

                        # 如果是"消息与记账无关"，这是正常的业务逻辑
                        if '消息与记账无关' in error_info or '记账无关' in error_info:
                            self._stats['successful_requests'] += 1
                            logger.info("消息与记账无关，跳过处理")
                            self.accounting_completed.emit(True, "信息与记账无关", error_result)
                            return True, "信息与记账无关"

                        # 其他400错误
                        elif error_msg:
                            self._stats['failed_requests'] += 1
                            logger.warning(f"记账请求被拒绝: {error_msg}")
                            self.accounting_completed.emit(False, f"记账失败: {error_msg}", error_result)
                            return False, f"记账失败: {error_msg}"
                        else:
                            self._stats['failed_requests'] += 1
                            logger.warning(f"记账请求返回400: {response.text}")
                            self.accounting_completed.emit(False, "记账请求格式错误", error_result)
                            return False, "记账请求格式错误"

                    except Exception as e:
                        logger.error(f"解析400错误响应失败: {e}")
                        self._stats['failed_requests'] += 1
                        error_msg = f"记账请求失败: {response.text}"
                        self.accounting_completed.emit(False, error_msg, {})
                        return False, error_msg
                else:
                    # 其他HTTP错误
                    response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            self._stats['failed_requests'] += 1
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(error_msg)
            self.accounting_completed.emit(False, error_msg, {})
            return False, error_msg
        except Exception as e:
            self._stats['failed_requests'] += 1
            error_msg = f"智能记账失败: {str(e)}"
            logger.error(error_msg)
            self.accounting_completed.emit(False, error_msg, {})
            return False, error_msg
    
    def get_token(self) -> Optional[str]:
        """获取有效token"""
        with self._lock:
            if not self._token_info:
                # 尝试自动登录
                if self._auto_login():
                    return self._token_info.token if self._token_info else None
                return None

            if self._token_info.is_expired():
                # 尝试刷新token
                if self._refresh_token():
                    return self._token_info.token
                return None

            return self._token_info.token

    def get_account_books(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        获取账本列表
        返回: (成功状态, 消息, 账本列表)
        """
        try:
            with self._lock:
                self._stats['total_requests'] += 1

                # 检查token
                if not self._token_info or not self._token_info.token:
                    # 尝试自动登录
                    if not self._auto_login():
                        self._stats['failed_requests'] += 1
                        error_msg = "未登录且自动登录失败"
                        return False, error_msg, []

                # 检查token是否过期
                if self._token_info.is_expired():
                    if not self._refresh_token():
                        self._stats['failed_requests'] += 1
                        error_msg = "Token已过期且刷新失败"
                        return False, error_msg, []

                # 构建请求
                url = f"{self._config.server_url.rstrip('/')}/api/account-books"
                headers = {
                    'Authorization': f'Bearer {self._token_info.token}',
                    'Content-Type': 'application/json'
                }

                logger.info("获取账本列表...")

                response = self._session.get(url, headers=headers, timeout=30)

                if response.status_code == 401:
                    # 认证失败，尝试刷新token
                    if self._refresh_token():
                        # 使用新token重试
                        headers['Authorization'] = f'Bearer {self._token_info.token}'
                        response = self._session.get(url, headers=headers, timeout=30)
                    else:
                        self._stats['failed_requests'] += 1
                        error_msg = "认证失败且token刷新失败"
                        return False, error_msg, []

                response.raise_for_status()
                result = response.json()

                # 解析响应
                if 'data' in result:
                    account_books = []
                    for book_data in result['data']:
                        book = {
                            'id': book_data['id'],
                            'name': book_data['name'],
                            'description': book_data.get('description', ''),
                            'type': book_data.get('type', ''),
                            'is_default': book_data.get('isDefault', False),
                            'transaction_count': book_data.get('transactionCount', 0),
                            'category_count': book_data.get('categoryCount', 0),
                            'budget_count': book_data.get('budgetCount', 0)
                        }
                        account_books.append(book)

                    self._stats['successful_requests'] += 1
                    logger.info(f"成功获取 {len(account_books)} 个账本")
                    return True, "获取成功", account_books
                else:
                    self._stats['failed_requests'] += 1
                    error_msg = "响应格式错误"
                    return False, error_msg, []

        except requests.exceptions.RequestException as e:
            self._stats['failed_requests'] += 1
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, []
        except Exception as e:
            self._stats['failed_requests'] += 1
            error_msg = f"获取账本列表失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, []

    # 私有方法

    def _load_config(self) -> bool:
        """从新的配置管理器加载配置"""
        try:
            logger.debug(f"开始加载配置，config_manager: {self.config_manager}")

            if self.config_manager:
                # 从配置管理器获取记账配置
                logger.debug("通过配置管理器加载配置")
                accounting_config = self.config_manager.get_accounting_config()
                logger.debug(f"获取到配置对象: {accounting_config}")

                # accounting_config是AccountingConfig对象，不是字典
                self._config.server_url = accounting_config.server_url
                self._config.username = accounting_config.username
                self._config.password = accounting_config.password
                self._config.account_book_id = accounting_config.account_book_id
                self._config.auto_login = accounting_config.auto_login
                self._config.token_refresh_interval = accounting_config.token_refresh_interval

                logger.info(f"配置加载成功: server_url={self._config.server_url}, username={self._config.username}")
                return True
            else:
                # 如果没有配置管理器，尝试直接从配置文件加载
                logger.debug("没有配置管理器，直接从文件加载配置")
                return self._load_config_from_file()
        except Exception as e:
            logger.error(f"加载配置失败: {e}", exc_info=True)
            return False

    def _load_config_from_file(self) -> bool:
        """直接从配置文件加载配置"""
        try:
            import json
            from pathlib import Path

            # 配置文件路径
            project_root = Path(__file__).parent.parent.parent
            config_file = project_root / "data" / "config.json"

            if not config_file.exists():
                logger.error("配置文件不存在")
                return False

            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 加载记账配置
            accounting_config = config_data.get('accounting', {})
            self._config.server_url = accounting_config.get('server_url', '')
            self._config.username = accounting_config.get('username', '')
            self._config.password = accounting_config.get('password', '')
            self._config.account_book_id = accounting_config.get('account_book_id', '')
            self._config.auto_login = accounting_config.get('auto_login', True)
            self._config.token_refresh_interval = accounting_config.get('token_refresh_interval', 300)

            logger.info(f"从文件加载配置成功: server_url={self._config.server_url}, username={self._config.username}")
            return True

        except Exception as e:
            logger.error(f"从文件加载配置失败: {e}")
            return False

    def _save_config(self) -> bool:
        """保存配置"""
        try:
            if self.config_manager:
                # 通过配置管理器保存
                return self.config_manager.update_accounting_config(
                    server_url=self._config.server_url,
                    username=self._config.username,
                    password=self._config.password,
                    account_book_id=self._config.account_book_id,
                    auto_login=self._config.auto_login,
                    token_refresh_interval=self._config.token_refresh_interval
                )
            else:
                # 直接保存到配置文件
                return self._save_config_to_file()
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def _save_config_to_file(self) -> bool:
        """直接保存配置到文件"""
        try:
            import json
            from pathlib import Path

            # 配置文件路径
            project_root = Path(__file__).parent.parent.parent
            config_file = project_root / "data" / "config.json"

            # 读取现有配置
            config_data = {}
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

            # 更新记账配置
            if 'accounting' not in config_data:
                config_data['accounting'] = {}

            config_data['accounting'].update({
                'server_url': self._config.server_url,
                'username': self._config.username,
                'password': self._config.password,
                'account_book_id': self._config.account_book_id,
                'auto_login': self._config.auto_login,
                'token_refresh_interval': self._config.token_refresh_interval
            })

            # 保存配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            logger.info("配置保存成功")
            return True

        except Exception as e:
            logger.error(f"保存配置到文件失败: {e}")
            return False

    def _load_existing_token(self) -> bool:
        """加载已有token（从内存中，不再从文件加载）"""
        # 新的实现中，token只保存在内存中，不再持久化
        # 每次启动都会自动登录获取新的token
        return False

    def _save_token_to_state(self) -> bool:
        """保存token到状态（仅内存保存）"""
        try:
            if self._token_info:
                # 更新HTTP会话头
                self._session.headers.update({
                    'Authorization': f'Bearer {self._token_info.token}'
                })
                logger.info("Token已保存到内存")
                return True
            return False
        except Exception as e:
            logger.error(f"保存token失败: {e}")
            return False

    def _parse_token(self, token: str) -> Optional[TokenInfo]:
        """解析token"""
        try:
            # 解析JWT token
            parts = token.split('.')
            if len(parts) >= 2:
                payload = parts[1]
                # 添加padding
                payload += '=' * (4 - len(payload) % 4)
                decoded = base64.b64decode(payload)
                token_data = json.loads(decoded)

                expires_at = None
                if 'exp' in token_data:
                    expires_at = datetime.fromtimestamp(token_data['exp'])

                return TokenInfo(
                    token=token,
                    expires_at=expires_at,
                    user_id=token_data.get('id', ''),
                    email=token_data.get('email', '')
                )
            else:
                # 非JWT格式，创建简单的token信息
                return TokenInfo(token=token)

        except Exception as e:
            logger.warning(f"解析token失败: {e}")
            return TokenInfo(token=token)

    def _auto_login(self) -> Tuple[bool, str]:
        """自动登录"""
        try:
            if not all([self._config.server_url, self._config.username, self._config.password]):
                return False, "配置信息不完整"

            success, message = self.login(
                self._config.server_url,
                self._config.username,
                self._config.password
            )
            return success, message
        except Exception as e:
            error_msg = f"自动登录失败: {e}"
            logger.error(error_msg)
            return False, error_msg

    def _refresh_token(self) -> bool:
        """刷新token"""
        try:
            self._stats['token_refreshes'] += 1

            success, message = self._auto_login()
            if success:
                logger.info("Token刷新成功")
                self.token_refreshed.emit(True, "Token刷新成功")
            else:
                logger.error(f"Token刷新失败: {message}")
                self.token_refreshed.emit(False, f"Token刷新失败: {message}")

            return success
        except Exception as e:
            error_msg = f"Token刷新异常: {str(e)}"
            logger.error(error_msg)
            self.token_refreshed.emit(False, error_msg)
            return False

    def _start_token_refresh_thread(self):
        """启动token刷新线程"""
        if self._refresh_thread and self._refresh_thread.is_alive():
            return

        self._stop_refresh.clear()
        self._refresh_thread = threading.Thread(target=self._token_refresh_loop, daemon=True)
        self._refresh_thread.start()
        logger.info("Token刷新线程已启动")

    def _token_refresh_loop(self):
        """Token刷新循环"""
        while not self._stop_refresh.is_set():
            try:
                # 检查是否需要刷新token
                need_refresh = False

                if not self._token_info or not self._token_info.token:
                    logger.debug("无有效token，尝试自动登录")
                    need_refresh = True
                elif self._token_info.is_expired():
                    logger.info("检测到token过期，开始自动刷新")
                    need_refresh = True

                if need_refresh:
                    self._refresh_token()

                # 等待下次检查
                self._stop_refresh.wait(self._config.token_refresh_interval)

            except Exception as e:
                logger.error(f"Token刷新循环异常: {e}")
                self._stop_refresh.wait(60)  # 出错时等待1分钟

    def _parse_accounting_response(self, result: Dict[str, Any]) -> str:
        """
        解析记账响应（参考旧版代码，支持多种API格式）

        Args:
            result: API响应结果

        Returns:
            格式化的消息
        """
        try:
            # 检查是否有smartAccountingResult字段（智能记账API的新格式）
            if 'smartAccountingResult' in result:
                return self._format_smart_accounting_response(result)

            # 检查是否有data字段（只为记账API的格式）
            elif 'data' in result:
                return self._format_zhiwei_accounting_response(result)

            # 简单的成功响应
            else:
                return "✅ 记账成功！"

        except Exception as e:
            logger.warning(f"解析记账响应失败: {e}")
            return "✅ 记账成功！"

    def _format_smart_accounting_response(self, result: Dict[str, Any]) -> str:
        """
        格式化智能记账API响应（参考旧版代码）

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

                # 基本信息 - 使用note字段作为明细，而不是originalDescription
                # note字段包含处理后的记账明细（如"买香蕉"），originalDescription包含原始消息（如"买香蕉，27元"）
                description = smart_result.get('note', smart_result.get('description', ''))
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

                # 方向和分类信息
                # 从API响应中提取正确的字段
                direction = smart_result.get('type', smart_result.get('direction', ''))  # type字段是主要的
                category = smart_result.get('categoryName', smart_result.get('category', ''))  # categoryName是主要的

                # 添加调试日志
                logger.debug(f"格式化响应 - direction: '{direction}', category: '{category}'")

                # 获取分类图标
                category_icon = self._get_category_icon(category)

                # 获取方向信息
                type_info = self._get_direction_info(direction)

                # 构建方向和分类信息行
                direction_category_parts = []
                if direction:
                    direction_category_parts.append(f"{type_info['icon']} 方向：{type_info['text']}")
                if category:
                    direction_category_parts.append(f"分类：{category_icon}{category}")

                if direction_category_parts:
                    message_lines.append("；".join(direction_category_parts))
                elif direction:  # 只有方向没有分类
                    message_lines.append(f"{type_info['icon']} 方向：{type_info['text']}")
                elif category:  # 只有分类没有方向
                    message_lines.append(f"📂 分类：{category_icon}{category}")

                # 金额信息
                amount = smart_result.get('amount', '')
                if amount:
                    message_lines.append(f"💰 金额：{amount}元")

                # 预算信息 - 只有当budgetName等于"个人预算"时才显示所有者姓名
                budget_name = smart_result.get('budgetName', smart_result.get('budget', ''))
                budget_owner = smart_result.get('budgetOwnerName', smart_result.get('budgetOwner', ''))

                if budget_name:
                    if budget_name == "个人预算" and budget_owner:
                        message_lines.append(f"📊 预算：{budget_name}（{budget_owner}）")
                    else:
                        message_lines.append(f"📊 预算：{budget_name}")

                return "\n".join(message_lines)
            else:
                # 没有amount字段，可能是失败或其他情况
                error_msg = smart_result.get('message', '记账失败')
                return f"❌ 记账失败: {error_msg}"

        except Exception as e:
            logger.error(f"格式化智能记账响应失败: {e}")
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

    def _format_zhiwei_accounting_response(self, result: Dict[str, Any]) -> str:
        """
        格式化只为记账API响应

        Args:
            result: API响应结果

        Returns:
            格式化的消息
        """
        try:
            data = result.get('data', {})

            # 构建成功消息
            success_parts = ["✅ 记账成功！"]

            if 'description' in data:
                success_parts.append(f"📝 明细：{data['description']}")

            if 'date' in data:
                success_parts.append(f"📅 日期：{data['date']}")

            # 处理方向和分类信息
            direction = data.get('direction', '支出')
            category = data.get('category', '')

            # 添加调试日志
            logger.debug(f"只为记账格式化 - direction: '{direction}', category: '{category}'")

            # 获取分类图标和方向信息
            category_icon = self._get_category_icon(category)
            type_info = self._get_direction_info(direction)

            # 构建方向和分类信息行
            direction_category_parts = []
            if direction:
                direction_category_parts.append(f"{type_info['icon']} 方向：{type_info['text']}")
            if category:
                direction_category_parts.append(f"分类：{category_icon}{category}")

            if direction_category_parts:
                success_parts.append("；".join(direction_category_parts))

            # 处理金额信息
            amount = data.get('amount', '')
            if amount:
                success_parts.append(f"💰 金额：{amount}元")

            if 'budget' in data:
                budget_info = data['budget']
                if isinstance(budget_info, dict):
                    remaining = budget_info.get('remaining', 0)
                    success_parts.append(f"📊 预算余额：{remaining}元")
                elif isinstance(budget_info, str):
                    success_parts.append(f"📊 预算：{budget_info}")

            return "\n".join(success_parts)

        except Exception as e:
            logger.warning(f"格式化只为记账响应失败: {e}")
            return "✅ 记账成功！"

    def _get_category_icon(self, category: str) -> str:
        """
        获取分类图标

        Args:
            category: 分类名称

        Returns:
            对应的图标
        """
        category_icons = {
            '餐饮': '🍽️',
            '交通': '🚗',
            '购物': '🛒',
            '娱乐': '🎮',
            '医疗': '🏥',
            '教育': '📚',
            '学习': '📝',
            '日用': '🧴',  # 添加日用分类
            '住房': '🏠',
            '通讯': '📱',
            '服装': '👕',
            '美容': '💄',
            '运动': '⚽',
            '旅游': '✈️',
            '投资': '💰',
            '保险': '🛡️',
            '转账': '💸',
            '红包': '🧧',
            '工资': '💼',
            '奖金': '🎁',
            '兼职': '👨‍💻',
            '理财': '📈',
            '其他': '📦'
        }
        return category_icons.get(category, '📂')

    def _get_direction_info(self, direction: str) -> Dict[str, str]:
        """
        获取方向信息

        Args:
            direction: 方向（支出/收入等）

        Returns:
            包含图标和文本的字典
        """
        direction_map = {
            '支出': {'icon': '💸', 'text': '支出'},
            '收入': {'icon': '💰', 'text': '收入'},
            'expense': {'icon': '💸', 'text': '支出'},
            'EXPENSE': {'icon': '💸', 'text': '支出'},  # API返回的大写格式
            'income': {'icon': '💰', 'text': '收入'},
            'INCOME': {'icon': '💰', 'text': '收入'},   # API返回的大写格式
            'transfer': {'icon': '🔄', 'text': '转账'},
            'TRANSFER': {'icon': '🔄', 'text': '转账'}  # API返回的大写格式
        }

        # 默认值
        default_info = {'icon': '💸', 'text': direction or '支出'}

        return direction_map.get(direction.lower() if direction else '', default_info)
