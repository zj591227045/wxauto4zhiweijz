#!/usr/bin/env python3
"""
服务健康检查器
为三个核心服务提供具体的健康检查实现
"""

import time
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.utils.service_health_monitor import HealthCheckResult, ServiceStatus

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class AccountingServiceHealthChecker:
    """记账服务健康检查器"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
    
    def check_health(self) -> HealthCheckResult:
        """检查记账服务健康状态"""
        try:
            start_time = time.time()
            
            # 获取记账服务配置
            config = self.state_manager.get_accounting_service_status()
            
            # 检查基本配置
            if not config.get('server_url') or not config.get('token'):
                return HealthCheckResult(
                    status=ServiceStatus.UNHEALTHY,
                    message="记账服务配置不完整",
                    details={'missing': '服务器地址或令牌'}
                )
            
            # 检查登录状态
            if not config.get('is_logged_in'):
                return HealthCheckResult(
                    status=ServiceStatus.UNHEALTHY,
                    message="记账服务未登录",
                    details={'login_status': False}
                )
            
            # 检查服务器连接
            server_url = config['server_url'].rstrip('/')
            health_url = f"{server_url}/api/health"
            
            try:
                response = requests.get(
                    health_url,
                    headers={'Authorization': f'Bearer {config["token"]}'},
                    timeout=5
                )
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    return HealthCheckResult(
                        status=ServiceStatus.HEALTHY,
                        message="记账服务运行正常",
                        details={
                            'server_url': server_url,
                            'response_code': response.status_code,
                            'account_book': config.get('selected_account_book_name', '未选择')
                        },
                        response_time=response_time
                    )
                else:
                    return HealthCheckResult(
                        status=ServiceStatus.DEGRADED,
                        message=f"记账服务响应异常: HTTP {response.status_code}",
                        details={
                            'server_url': server_url,
                            'response_code': response.status_code
                        },
                        response_time=response_time
                    )
                    
            except requests.exceptions.Timeout:
                return HealthCheckResult(
                    status=ServiceStatus.UNHEALTHY,
                    message="记账服务连接超时",
                    details={'server_url': server_url, 'timeout': True}
                )
                
            except requests.exceptions.ConnectionError:
                return HealthCheckResult(
                    status=ServiceStatus.UNHEALTHY,
                    message="无法连接到记账服务器",
                    details={'server_url': server_url, 'connection_error': True}
                )
                
        except Exception as e:
            return HealthCheckResult(
                status=ServiceStatus.UNHEALTHY,
                message=f"记账服务健康检查异常: {str(e)}",
                details={'exception': str(e)}
            )

class WechatServiceHealthChecker:
    """微信服务健康检查器"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.last_message_check = datetime.now()
    
    def check_health(self) -> HealthCheckResult:
        """检查微信服务健康状态"""
        try:
            start_time = time.time()

            # 获取微信状态
            wechat_status = self.state_manager.get_wechat_status()

            # 使用 wx.IsOnline() 方法检查微信在线状态
            wx_instance = None
            is_online = False
            my_info = None

            try:
                # 获取微信实例
                from app.wechat import wechat_manager
                if wechat_manager.get_instance():
                    wx_instance = wechat_manager.get_instance()

                    # 检查微信是否在线
                    is_online = wx_instance.IsOnline()

                    # 如果在线，获取我的信息
                    if is_online:
                        try:
                            my_info = wx_instance.GetMyInfo()
                        except Exception as e:
                            # GetMyInfo 失败不影响在线状态判断
                            pass

            except Exception as e:
                return HealthCheckResult(
                    status=ServiceStatus.UNHEALTHY,
                    message=f"无法获取微信实例: {str(e)}",
                    details={'wx_instance_error': str(e)}
                )

            # 检查微信在线状态
            if not wx_instance:
                return HealthCheckResult(
                    status=ServiceStatus.UNHEALTHY,
                    message="微信实例未初始化",
                    details={'wx_instance': False}
                )

            if not is_online:
                return HealthCheckResult(
                    status=ServiceStatus.UNHEALTHY,
                    message="微信未在线",
                    details={
                        'is_online': is_online,
                        'wx_instance': True
                    }
                )

            # 获取微信窗口信息（可选）
            window_name = wechat_status.get('window_name', '')

            # 获取我的微信信息（如果可用）
            my_wechat_info = {}
            if my_info and isinstance(my_info, dict):
                my_wechat_info = {
                    'nickname': my_info.get('nickname', ''),
                    'wxid': my_info.get('wxid', ''),
                    'mobile': my_info.get('mobile', '')
                }
            
            # 检查监控状态
            monitoring_status = self.state_manager.get_monitoring_status()
            is_monitoring = monitoring_status.get('is_active', False)
            
            if not is_monitoring:
                return HealthCheckResult(
                    status=ServiceStatus.DEGRADED,
                    message="微信监控未激活",
                    details={
                        'monitoring_active': is_monitoring,
                        'monitored_chats': monitoring_status.get('monitored_chats', [])
                    }
                )
            
            # 检查最后检查时间
            last_check_str = monitoring_status.get('last_check_time')
            if last_check_str:
                try:
                    last_check = datetime.fromisoformat(last_check_str)
                    time_since_check = (datetime.now() - last_check).total_seconds()
                    
                    # 如果超过检查间隔的3倍时间没有检查，认为可能有问题
                    check_interval = monitoring_status.get('check_interval', 5)
                    if time_since_check > check_interval * 3:
                        return HealthCheckResult(
                            status=ServiceStatus.DEGRADED,
                            message=f"微信监控检查超时: {time_since_check:.1f}秒前",
                            details={
                                'last_check': last_check_str,
                                'time_since_check': time_since_check,
                                'check_interval': check_interval
                            }
                        )
                except Exception:
                    pass
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                status=ServiceStatus.HEALTHY,
                message="微信服务运行正常",
                details={
                    'is_online': is_online,
                    'window_name': window_name,
                    'monitoring_active': is_monitoring,
                    'monitored_chats_count': len(monitoring_status.get('monitored_chats', [])),
                    'library_type': wechat_status.get('library_type', 'unknown'),
                    'my_info': my_wechat_info,
                    'wx_instance_available': wx_instance is not None
                },
                response_time=response_time
            )
            
        except Exception as e:
            return HealthCheckResult(
                status=ServiceStatus.UNHEALTHY,
                message=f"微信服务健康检查异常: {str(e)}",
                details={'exception': str(e)}
            )

class MessageProcessingHealthChecker:
    """消息处理健康检查器"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.last_stats_check = None
        self.last_message_count = 0
    
    def check_health(self) -> HealthCheckResult:
        """检查消息处理健康状态"""
        try:
            start_time = time.time()
            
            # 获取统计数据
            stats = self.state_manager.get_stats()
            
            # 检查消息处理统计
            processed_messages = stats.get('processed_messages', 0)
            successful_records = stats.get('successful_records', 0)
            failed_records = stats.get('failed_records', 0)
            
            # 计算成功率
            total_attempts = successful_records + failed_records
            if total_attempts > 0:
                success_rate = (successful_records / total_attempts * 100)
            else:
                # 如果没有任何尝试，认为是健康的（还没有开始处理消息）
                success_rate = 100
            
            # 检查最后消息时间
            last_message_str = stats.get('last_message_time')
            time_since_last_message = None
            
            if last_message_str:
                try:
                    last_message_time = datetime.fromisoformat(last_message_str)
                    time_since_last_message = (datetime.now() - last_message_time).total_seconds()
                except Exception:
                    pass
            
            # 检查消息处理是否有进展
            current_time = datetime.now()
            if self.last_stats_check:
                time_diff = (current_time - self.last_stats_check).total_seconds()
                message_diff = processed_messages - self.last_message_count
                
                # 如果监控激活但长时间没有处理新消息，可能有问题
                monitoring_status = self.state_manager.get_monitoring_status()
                is_monitoring = monitoring_status.get('is_active', False)
                
                if is_monitoring and time_diff > 300 and message_diff == 0:  # 5分钟没有新消息
                    # 但这可能是正常的（没有新消息），所以只标记为降级
                    pass
            
            self.last_stats_check = current_time
            self.last_message_count = processed_messages
            
            # 判断健康状态
            if total_attempts == 0:
                # 没有任何记账尝试，认为是正常的（可能还没有收到需要记账的消息）
                status = ServiceStatus.HEALTHY
                message = "消息处理运行正常（暂无记账请求）"
            elif success_rate < 50:  # 成功率低于50%
                status = ServiceStatus.UNHEALTHY
                message = f"消息处理成功率过低: {success_rate:.1f}%"
            elif success_rate < 80:  # 成功率低于80%
                status = ServiceStatus.DEGRADED
                message = f"消息处理成功率较低: {success_rate:.1f}%"
            elif failed_records > 10:  # 失败记录过多
                status = ServiceStatus.DEGRADED
                message = f"失败记录较多: {failed_records}条"
            else:
                status = ServiceStatus.HEALTHY
                message = "消息处理运行正常"
            
            response_time = time.time() - start_time
            
            details = {
                'processed_messages': processed_messages,
                'successful_records': successful_records,
                'failed_records': failed_records,
                'success_rate': round(success_rate, 1),
                'total_attempts': total_attempts
            }
            
            if time_since_last_message is not None:
                details['time_since_last_message'] = round(time_since_last_message, 1)
            
            return HealthCheckResult(
                status=status,
                message=message,
                details=details,
                response_time=response_time
            )
            
        except Exception as e:
            return HealthCheckResult(
                status=ServiceStatus.UNHEALTHY,
                message=f"消息处理健康检查异常: {str(e)}",
                details={'exception': str(e)}
            )

class LogSystemHealthChecker:
    """日志系统健康检查器"""
    
    def __init__(self):
        self.last_log_count = 0
        self.last_check_time = datetime.now()
    
    def check_health(self) -> HealthCheckResult:
        """检查日志系统健康状态"""
        try:
            start_time = time.time()
            
            # 检查日志处理器
            try:
                from app.logs import log_memory_handler
                
                if not log_memory_handler:
                    return HealthCheckResult(
                        status=ServiceStatus.UNHEALTHY,
                        message="日志内存处理器不可用",
                        details={'memory_handler': False}
                    )
                
                # 获取日志统计
                stats = log_memory_handler.get_stats()
                total_logs = stats.get('total_logs', 0)
                error_logs = stats.get('error_logs', 0)
                
                # 检查日志增长
                current_time = datetime.now()
                time_diff = (current_time - self.last_check_time).total_seconds()
                log_diff = total_logs - self.last_log_count
                
                self.last_check_time = current_time
                self.last_log_count = total_logs
                
                # 检查日志文件
                import os
                from pathlib import Path
                
                project_root = Path(__file__).parent.parent.parent
                logs_dir = project_root / "data" / "Logs"
                
                log_files_exist = logs_dir.exists() and any(logs_dir.glob("*.log"))
                
                # 判断健康状态
                if not log_files_exist:
                    status = ServiceStatus.DEGRADED
                    message = "日志文件不存在或无法访问"
                elif error_logs > total_logs * 0.1:  # 错误日志超过10%
                    status = ServiceStatus.DEGRADED
                    message = f"错误日志比例过高: {error_logs}/{total_logs}"
                else:
                    status = ServiceStatus.HEALTHY
                    message = "日志系统运行正常"
                
                response_time = time.time() - start_time
                
                return HealthCheckResult(
                    status=status,
                    message=message,
                    details={
                        'total_logs': total_logs,
                        'error_logs': error_logs,
                        'log_files_exist': log_files_exist,
                        'logs_dir': str(logs_dir),
                        'log_growth': log_diff if time_diff > 0 else 0
                    },
                    response_time=response_time
                )
                
            except ImportError:
                return HealthCheckResult(
                    status=ServiceStatus.UNHEALTHY,
                    message="无法导入日志模块",
                    details={'import_error': True}
                )
                
        except Exception as e:
            return HealthCheckResult(
                status=ServiceStatus.UNHEALTHY,
                message=f"日志系统健康检查异常: {str(e)}",
                details={'exception': str(e)}
            )

def create_health_checkers(state_manager):
    """创建所有健康检查器"""
    return {
        'accounting_service': AccountingServiceHealthChecker(state_manager),
        'wechat_service': WechatServiceHealthChecker(state_manager),
        'message_processing': MessageProcessingHealthChecker(state_manager),
        'log_system': LogSystemHealthChecker()
    }
