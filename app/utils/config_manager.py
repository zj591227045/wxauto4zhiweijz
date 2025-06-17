"""
配置管理模块
负责配置文件的加载、保存和密码加密
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
import base64
import hashlib
import sys

logger = logging.getLogger(__name__)

@dataclass
class AccountingConfig:
    """记账服务配置"""
    server_url: str = "https://api.zhiweijz.com"
    username: str = ""
    password: str = ""  # 加密存储
    token: str = ""
    account_book_id: str = ""
    account_book_name: str = ""
    
@dataclass
class WechatMonitorConfig:
    """微信监控配置"""
    monitored_chats: List[str] = None
    check_interval: int = 5
    auto_start: bool = False
    
    def __post_init__(self):
        if self.monitored_chats is None:
            self.monitored_chats = []

@dataclass
class AppConfig:
    """应用配置"""
    auto_login: bool = False
    auto_start_api: bool = False
    auto_init_wechat: bool = False
    startup_delay: int = 5
    api_port: int = 5000
    wechat_lib: str = "wxauto"

@dataclass
class UserConfig:
    """用户配置"""
    accounting: AccountingConfig = None
    wechat_monitor: WechatMonitorConfig = None
    app: AppConfig = None
    
    def __post_init__(self):
        if self.accounting is None:
            self.accounting = AccountingConfig()
        if self.wechat_monitor is None:
            self.wechat_monitor = WechatMonitorConfig()
        if self.app is None:
            self.app = AppConfig()

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = None, use_existing_config: bool = True):
        if config_dir is None:
            # 智能检测配置目录
            if getattr(sys, 'frozen', False):
                # 打包后的环境 - 使用exe文件所在目录
                app_dir = os.path.dirname(sys.executable)
                config_dir = os.path.join(app_dir, "data", "api", "config")
            else:
                # 开发环境 - 使用项目根目录
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                config_dir = os.path.join(project_root, "data", "api", "config")
        
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "user_config.json")
        self.key_file = os.path.join(config_dir, "config.key")
        self.use_existing_config = use_existing_config
        
        # 确保配置目录存在
        os.makedirs(config_dir, exist_ok=True)
        
        # 在打包环境中，如果是首次运行，强制使用空配置
        if getattr(sys, 'frozen', False) and not os.path.exists(self.config_file):
            print("🆕 检测到首次运行，将创建新的配置文件")
            self.use_existing_config = False
        
        # 初始化加密密钥
        self._init_encryption_key()
        
        # 加载配置
        self.config = self.load_config()
    
    def _init_encryption_key(self):
        """初始化加密密钥"""
        try:
            if os.path.exists(self.key_file):
                with open(self.key_file, 'rb') as f:
                    self.key = f.read()
            else:
                # 生成新密钥
                self.key = Fernet.generate_key()
                with open(self.key_file, 'wb') as f:
                    f.write(self.key)
                # 设置文件权限（仅所有者可读写）
                os.chmod(self.key_file, 0o600)
            
            self.cipher = Fernet(self.key)
            logger.info("加密密钥初始化成功")
            
        except Exception as e:
            logger.error(f"初始化加密密钥失败: {e}")
            # 使用基于机器的固定密钥作为备选
            machine_id = hashlib.sha256(os.environ.get('COMPUTERNAME', 'default').encode()).digest()
            self.key = base64.urlsafe_b64encode(machine_id)
            self.cipher = Fernet(self.key)
    
    def _encrypt_password(self, password: str) -> str:
        """加密密码"""
        if not password:
            return ""
        try:
            encrypted = self.cipher.encrypt(password.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"密码加密失败: {e}")
            return password  # 返回原密码作为备选
    
    def _decrypt_password(self, encrypted_password: str) -> str:
        """解密密码"""
        if not encrypted_password:
            return ""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"密码解密失败: {e}")
            return encrypted_password  # 返回原密码作为备选
    
    def load_config(self) -> UserConfig:
        """加载配置"""
        try:
            # 如果不使用现有配置，直接返回空配置
            if not self.use_existing_config:
                logger.info("配置为不使用现有配置，使用空配置")
                return UserConfig()
            
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 创建配置对象
                config = UserConfig()
                
                # 加载记账配置
                if 'accounting' in data:
                    acc_data = data['accounting']
                    config.accounting = AccountingConfig(
                        server_url=acc_data.get('server_url', 'https://api.zhiweijz.com'),
                        username=acc_data.get('username', ''),
                        password=self._decrypt_password(acc_data.get('password', '')),
                        token=acc_data.get('token', ''),
                        account_book_id=acc_data.get('account_book_id', ''),
                        account_book_name=acc_data.get('account_book_name', '')
                    )
                
                # 加载微信监控配置
                if 'wechat_monitor' in data:
                    wm_data = data['wechat_monitor']
                    config.wechat_monitor = WechatMonitorConfig(
                        monitored_chats=wm_data.get('monitored_chats', []),
                        check_interval=wm_data.get('check_interval', 5),
                        auto_start=wm_data.get('auto_start', False)
                    )
                
                # 加载应用配置
                if 'app' in data:
                    app_data = data['app']
                    config.app = AppConfig(
                        auto_login=app_data.get('auto_login', False),
                        auto_start_api=app_data.get('auto_start_api', False),
                        auto_init_wechat=app_data.get('auto_init_wechat', False),
                        startup_delay=app_data.get('startup_delay', 5),
                        api_port=app_data.get('api_port', 5000),
                        wechat_lib=app_data.get('wechat_lib', 'wxauto')
                    )
                
                logger.info("配置加载成功")
                return config
            else:
                logger.info("配置文件不存在，创建默认配置文件")
                # 创建默认配置
                default_config = UserConfig()
                # 保存默认配置到文件
                self.save_config(default_config)
                logger.info("默认配置文件已创建")
                return default_config
                
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            # 如果加载失败，创建并保存默认配置
            try:
                default_config = UserConfig()
                self.save_config(default_config)
                logger.info("由于加载失败，已创建新的默认配置文件")
                return default_config
            except Exception as save_error:
                logger.error(f"创建默认配置文件也失败: {save_error}")
                return UserConfig()
    
    def save_config(self, config: UserConfig = None) -> bool:
        """保存配置"""
        try:
            if config is None:
                config = self.config
            
            # 准备保存的数据
            data = {
                'accounting': {
                    'server_url': config.accounting.server_url,
                    'username': config.accounting.username,
                    'password': self._encrypt_password(config.accounting.password),
                    'token': config.accounting.token,
                    'account_book_id': config.accounting.account_book_id,
                    'account_book_name': config.accounting.account_book_name
                },
                'wechat_monitor': {
                    'monitored_chats': config.wechat_monitor.monitored_chats,
                    'check_interval': config.wechat_monitor.check_interval,
                    'auto_start': config.wechat_monitor.auto_start
                },
                'app': {
                    'auto_login': config.app.auto_login,
                    'auto_start_api': config.app.auto_start_api,
                    'auto_init_wechat': config.app.auto_init_wechat,
                    'startup_delay': config.app.startup_delay,
                    'api_port': config.app.api_port,
                    'wechat_lib': config.app.wechat_lib
                }
            }
            
            # 保存到文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 设置文件权限（仅所有者可读写）
            os.chmod(self.config_file, 0o600)
            
            logger.info("配置保存成功")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def update_accounting_config(self, server_url: str = None, username: str = None, 
                               password: str = None, token: str = None, 
                               account_book_id: str = None, account_book_name: str = None):
        """更新记账配置"""
        if server_url is not None:
            self.config.accounting.server_url = server_url
        if username is not None:
            self.config.accounting.username = username
        if password is not None:
            self.config.accounting.password = password
        if token is not None:
            self.config.accounting.token = token
        if account_book_id is not None:
            self.config.accounting.account_book_id = account_book_id
        if account_book_name is not None:
            self.config.accounting.account_book_name = account_book_name
        
        self.save_config()
    
    def update_wechat_monitor_config(self, monitored_chats: List[str] = None,
                                   check_interval: int = None, auto_start: bool = None,
                                   wechat_lib: str = None):
        """更新微信监控配置"""
        if monitored_chats is not None:
            self.config.wechat_monitor.monitored_chats = monitored_chats
        if check_interval is not None:
            self.config.wechat_monitor.check_interval = check_interval
        if auto_start is not None:
            self.config.wechat_monitor.auto_start = auto_start
        if wechat_lib is not None:
            # wechat_lib保存到app配置中
            self.config.app.wechat_lib = wechat_lib

        self.save_config()
    
    def update_app_config(self, auto_login: bool = None, auto_start_api: bool = None,
                         auto_init_wechat: bool = None, startup_delay: int = None,
                         api_port: int = None, wechat_lib: str = None):
        """更新应用配置"""
        if auto_login is not None:
            self.config.app.auto_login = auto_login
        if auto_start_api is not None:
            self.config.app.auto_start_api = auto_start_api
        if auto_init_wechat is not None:
            self.config.app.auto_init_wechat = auto_init_wechat
        if startup_delay is not None:
            self.config.app.startup_delay = startup_delay
        if api_port is not None:
            self.config.app.api_port = api_port
        if wechat_lib is not None:
            self.config.app.wechat_lib = wechat_lib
        
        self.save_config()
    
    def has_valid_config(self) -> bool:
        """检查是否有有效的配置"""
        return (self.config.accounting.username and 
                self.config.accounting.password and
                self.config.accounting.server_url)
    
    def get_config(self) -> UserConfig:
        """获取当前配置"""
        return self.config 