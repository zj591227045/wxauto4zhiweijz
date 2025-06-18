"""
Token管理器
负责记账服务的token获取、验证和自动刷新
"""

import json
import time
import threading
import requests
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
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
        return datetime.now() >= self.expires_at
    
    def will_expire_soon(self, minutes: int = 30) -> bool:
        """检查token是否即将过期"""
        if not self.expires_at:
            return False
        return datetime.now() >= (self.expires_at - timedelta(minutes=minutes))

class TokenManager:
    """Token管理器"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self._token_info: Optional[TokenInfo] = None
        self._refresh_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        
        # 从状态管理器加载现有token
        self._load_token_from_state()
        
        # 启动定时检查
        self._start_token_check()
    
    def _load_token_from_state(self):
        """从状态管理器加载token信息"""
        try:
            accounting_status = self.state_manager.get_accounting_service_status()
            token = accounting_status.get('token', '')
            
            if token:
                # 简单的token解析（JWT格式）
                try:
                    import base64
                    # 解析JWT payload
                    parts = token.split('.')
                    if len(parts) >= 2:
                        payload = parts[1]
                        # 添加padding如果需要
                        payload += '=' * (4 - len(payload) % 4)
                        decoded = base64.b64decode(payload)
                        token_data = json.loads(decoded)
                        
                        expires_at = None
                        if 'exp' in token_data:
                            expires_at = datetime.fromtimestamp(token_data['exp'])
                        
                        self._token_info = TokenInfo(
                            token=token,
                            expires_at=expires_at,
                            user_id=token_data.get('id', ''),
                            email=token_data.get('email', '')
                        )
                        
                        logger.info(f"加载已有token，过期时间: {expires_at}")
                        
                except Exception as e:
                    logger.warning(f"解析token失败: {e}")
                    self._token_info = TokenInfo(token=token)
            
        except Exception as e:
            logger.error(f"从状态加载token失败: {e}")
    
    def _start_token_check(self):
        """启动token定时检查"""
        self._schedule_next_check()
    
    def _schedule_next_check(self):
        """安排下次检查"""
        if self._refresh_timer:
            self._refresh_timer.cancel()
        
        # 每5分钟检查一次
        self._refresh_timer = threading.Timer(300, self._check_and_refresh_token)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()
    
    def _check_and_refresh_token(self):
        """检查并刷新token"""
        try:
            with self._lock:
                if self._token_info and self._token_info.will_expire_soon():
                    logger.info("Token即将过期，尝试刷新")
                    self._refresh_token()
                elif self._token_info and self._token_info.is_expired():
                    logger.warning("Token已过期，尝试重新登录")
                    self._refresh_token()
                elif not self._token_info or not self._token_info.token:
                    logger.info("无有效token，尝试自动登录")
                    self._refresh_token()
        except Exception as e:
            logger.error(f"Token检查失败: {e}")
        finally:
            # 安排下次检查
            self._schedule_next_check()
    
    def _refresh_token(self) -> bool:
        """刷新token"""
        try:
            # 获取登录凭据
            accounting_status = self.state_manager.get_accounting_service_status()
            server_url = accounting_status.get('server_url', '')
            username = accounting_status.get('username', '')
            password = accounting_status.get('password', '')
            
            if not all([server_url, username, password]):
                logger.error("缺少登录凭据，无法刷新token")
                return False
            
            # 执行登录
            success, token_info = self._login(server_url, username, password)
            if success and token_info:
                self._token_info = token_info
                
                # 更新状态管理器
                self.state_manager.update_accounting_service(
                    token=token_info.token,
                    is_logged_in=True,
                    status='connected'
                )
                
                logger.info("Token刷新成功")
                return True
            else:
                logger.error("Token刷新失败")
                return False
                
        except Exception as e:
            logger.error(f"刷新token异常: {e}")
            return False
    
    def _login(self, server_url: str, username: str, password: str) -> Tuple[bool, Optional[TokenInfo]]:
        """执行登录"""
        try:
            url = f"{server_url.rstrip('/')}/api/auth/login"
            data = {
                "email": username,
                "password": password
            }
            
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if 'token' in result and 'user' in result:
                token = result['token']
                user = result['user']
                
                # 解析token过期时间
                expires_at = None
                try:
                    import base64
                    parts = token.split('.')
                    if len(parts) >= 2:
                        payload = parts[1]
                        payload += '=' * (4 - len(payload) % 4)
                        decoded = base64.b64decode(payload)
                        token_data = json.loads(decoded)
                        
                        if 'exp' in token_data:
                            expires_at = datetime.fromtimestamp(token_data['exp'])
                except Exception as e:
                    logger.warning(f"解析token过期时间失败: {e}")
                
                token_info = TokenInfo(
                    token=token,
                    expires_at=expires_at,
                    user_id=user.get('id', ''),
                    email=user.get('email', '')
                )
                
                return True, token_info
            else:
                return False, None
                
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False, None
    
    def get_valid_token(self) -> Optional[str]:
        """获取有效的token"""
        with self._lock:
            if not self._token_info or not self._token_info.token:
                # 尝试自动登录
                if self._refresh_token():
                    return self._token_info.token if self._token_info else None
                return None
            
            if self._token_info.is_expired():
                # Token已过期，尝试刷新
                if self._refresh_token():
                    return self._token_info.token if self._token_info else None
                return None
            
            return self._token_info.token
    
    def force_refresh(self) -> bool:
        """强制刷新token"""
        with self._lock:
            return self._refresh_token()
    
    def is_token_valid(self) -> bool:
        """检查当前token是否有效"""
        with self._lock:
            if not self._token_info or not self._token_info.token:
                return False
            return not self._token_info.is_expired()
    
    def get_token_info(self) -> Optional[TokenInfo]:
        """获取token信息"""
        with self._lock:
            return self._token_info
    
    def stop(self):
        """停止token管理器"""
        if self._refresh_timer:
            self._refresh_timer.cancel()
            self._refresh_timer = None

# 全局token管理器实例
_token_manager: Optional[TokenManager] = None

def get_token_manager(state_manager=None) -> Optional[TokenManager]:
    """获取token管理器实例"""
    global _token_manager
    if _token_manager is None and state_manager:
        _token_manager = TokenManager(state_manager)
    return _token_manager

def init_token_manager(state_manager):
    """初始化token管理器"""
    global _token_manager
    if _token_manager:
        _token_manager.stop()
    _token_manager = TokenManager(state_manager)
    return _token_manager
