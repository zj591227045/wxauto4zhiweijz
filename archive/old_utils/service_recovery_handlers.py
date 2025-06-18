#!/usr/bin/env python3
"""
服务恢复处理器
为三个核心服务提供自动恢复功能
"""

import time
import logging
from typing import Optional, Any
from datetime import datetime

# 使用统一的日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class AccountingServiceRecoveryHandler:
    """记账服务恢复处理器"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
    
    def recover(self) -> bool:
        """恢复记账服务"""
        try:
            logger.info("开始恢复记账服务...")
            
            # 获取当前配置
            config = self.state_manager.get_accounting_service_status()
            
            # 检查基本配置
            server_url = config.get('server_url', '')
            username = config.get('username', '')
            password = config.get('password', '')
            
            if not all([server_url, username, password]):
                logger.error("记账服务配置不完整，无法自动恢复")
                return False
            
            # 尝试重新登录
            try:
                from app.services.accounting_service import AccountingService
                
                service = AccountingService()
                success, message, user = service.login(server_url, username, password)
                
                if success and user:
                    # 获取账本列表
                    success_books, message_books, account_books = service.get_account_books()
                    
                    if success_books:
                        # 转换账本格式
                        books_data = []
                        for book in account_books:
                            books_data.append({
                                'id': book.id,
                                'name': book.name,
                                'is_default': book.is_default
                            })
                        
                        # 更新状态管理器
                        self.state_manager.update_accounting_service(
                            token=service.config.token,
                            username=username,
                            password=password,
                            server_url=server_url,
                            account_books=books_data,
                            is_logged_in=True,
                            status='connected'
                        )
                        
                        logger.info("记账服务恢复成功")
                        return True
                    else:
                        logger.error(f"获取账本失败: {message_books}")
                        return False
                else:
                    logger.error(f"登录失败: {message}")
                    return False
                    
            except Exception as e:
                logger.error(f"记账服务恢复异常: {e}")
                return False
                
        except Exception as e:
            logger.error(f"记账服务恢复处理器异常: {e}")
            return False

class WechatServiceRecoveryHandler:
    """微信服务恢复处理器"""
    
    def __init__(self, state_manager, async_wechat_api=None):
        self.state_manager = state_manager
        self.async_wechat_api = async_wechat_api
    
    def recover(self) -> bool:
        """恢复微信服务"""
        try:
            logger.info("开始恢复微信服务...")
            
            # 方法1: 如果有异步API，使用异步方式
            if self.async_wechat_api:
                try:
                    # 重新初始化微信
                    self.async_wechat_api.initialize_wechat()
                    
                    # 等待一段时间让初始化完成
                    time.sleep(3)
                    
                    # 检查状态
                    wechat_status = self.state_manager.get_wechat_status()
                    if wechat_status.get('status') == 'online':
                        logger.info("微信服务异步恢复成功")
                        return True
                    
                except Exception as e:
                    logger.warning(f"异步恢复失败，尝试同步方式: {e}")
            
            # 方法2: 使用同步方式恢复
            try:
                from app.wechat import wechat_manager
                
                # 重新初始化微信
                success = wechat_manager.initialize()
                
                if success:
                    wx_instance = wechat_manager.get_instance()
                    if wx_instance:
                        # 更新状态
                        self.state_manager.update_wechat_status(
                            status='online',
                            window_name=getattr(wx_instance, 'window_name', '微信'),
                            error_message=''
                        )
                        
                        logger.info("微信服务同步恢复成功")
                        return True
                    else:
                        logger.error("微信实例获取失败")
                        return False
                else:
                    logger.error("微信初始化失败")
                    return False
                    
            except Exception as e:
                logger.error(f"微信服务同步恢复异常: {e}")
                return False
                
        except Exception as e:
            logger.error(f"微信服务恢复处理器异常: {e}")
            return False

class MessageProcessingRecoveryHandler:
    """消息处理恢复处理器"""
    
    def __init__(self, state_manager, message_monitor=None):
        self.state_manager = state_manager
        self.message_monitor = message_monitor
    
    def recover(self) -> bool:
        """恢复消息处理服务"""
        try:
            logger.info("开始恢复消息处理服务...")
            
            # 重置统计数据中的失败计数（但保留总体统计）
            stats = self.state_manager.get_stats()
            
            # 如果失败率过高，重置失败计数给服务一个新的开始
            failed_records = stats.get('failed_records', 0)
            successful_records = stats.get('successful_records', 0)
            total_attempts = failed_records + successful_records
            
            if total_attempts > 0:
                failure_rate = failed_records / total_attempts
                if failure_rate > 0.5:  # 失败率超过50%
                    logger.info("重置消息处理失败计数")
                    self.state_manager.update_stats(failed_records=0)
            
            # 如果有消息监控器，尝试重启监控
            if self.message_monitor:
                try:
                    # 检查监控状态
                    monitoring_status = self.state_manager.get_monitoring_status()
                    monitored_chats = monitoring_status.get('monitored_chats', [])
                    
                    if monitored_chats:
                        # 停止当前监控
                        if hasattr(self.message_monitor, 'stop_monitoring'):
                            self.message_monitor.stop_monitoring()
                            time.sleep(1)
                        
                        # 重新启动监控
                        if hasattr(self.message_monitor, 'start_monitoring'):
                            success = self.message_monitor.start_monitoring(monitored_chats)
                            if success:
                                logger.info("消息监控重启成功")
                                return True
                            else:
                                logger.error("消息监控重启失败")
                                return False
                        
                except Exception as e:
                    logger.error(f"重启消息监控异常: {e}")
            
            # 如果没有消息监控器，只是重置状态
            logger.info("消息处理服务状态已重置")
            return True
            
        except Exception as e:
            logger.error(f"消息处理恢复处理器异常: {e}")
            return False

class LogSystemRecoveryHandler:
    """日志系统恢复处理器"""
    
    def __init__(self):
        pass
    
    def recover(self) -> bool:
        """恢复日志系统"""
        try:
            logger.info("开始恢复日志系统...")
            
            # 检查并创建日志目录
            import os
            from pathlib import Path
            
            project_root = Path(__file__).parent.parent.parent
            logs_dir = project_root / "data" / "Logs"
            
            try:
                logs_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"日志目录已确保存在: {logs_dir}")
            except Exception as e:
                logger.error(f"创建日志目录失败: {e}")
                return False
            
            # 检查日志处理器
            try:
                from app.logs import log_memory_handler, setup_enhanced_logger
                
                if not log_memory_handler:
                    logger.warning("内存日志处理器不可用，尝试重新初始化")
                    # 重新设置日志系统
                    setup_enhanced_logger()
                
                # 测试日志写入
                test_logger = logging.getLogger('test_recovery')
                test_logger.info("日志系统恢复测试")
                
                logger.info("日志系统恢复成功")
                return True
                
            except Exception as e:
                logger.error(f"日志系统恢复异常: {e}")
                return False
                
        except Exception as e:
            logger.error(f"日志系统恢复处理器异常: {e}")
            return False

class CompositeRecoveryHandler:
    """复合恢复处理器 - 用于需要多个服务协同恢复的情况"""
    
    def __init__(self, state_manager, async_wechat_api=None, message_monitor=None):
        self.state_manager = state_manager
        self.accounting_handler = AccountingServiceRecoveryHandler(state_manager)
        self.wechat_handler = WechatServiceRecoveryHandler(state_manager, async_wechat_api)
        self.message_handler = MessageProcessingRecoveryHandler(state_manager, message_monitor)
        self.log_handler = LogSystemRecoveryHandler()
    
    def recover_all_services(self) -> bool:
        """恢复所有服务"""
        try:
            logger.info("开始全面服务恢复...")
            
            recovery_results = {}
            
            # 按依赖顺序恢复服务
            # 1. 首先恢复日志系统
            recovery_results['log_system'] = self.log_handler.recover()
            
            # 2. 恢复微信服务
            recovery_results['wechat_service'] = self.wechat_handler.recover()
            
            # 3. 恢复记账服务
            recovery_results['accounting_service'] = self.accounting_handler.recover()
            
            # 4. 最后恢复消息处理
            recovery_results['message_processing'] = self.message_handler.recover()
            
            # 统计恢复结果
            successful_recoveries = sum(1 for success in recovery_results.values() if success)
            total_services = len(recovery_results)
            
            logger.info(f"服务恢复完成: {successful_recoveries}/{total_services} 个服务恢复成功")
            
            # 如果大部分服务恢复成功，认为整体恢复成功
            return successful_recoveries >= total_services * 0.75
            
        except Exception as e:
            logger.error(f"全面服务恢复异常: {e}")
            return False

def create_recovery_handlers(state_manager, async_wechat_api=None, message_monitor=None):
    """创建所有恢复处理器"""
    return {
        'accounting_service': AccountingServiceRecoveryHandler(state_manager).recover,
        'wechat_service': WechatServiceRecoveryHandler(state_manager, async_wechat_api).recover,
        'message_processing': MessageProcessingRecoveryHandler(state_manager, message_monitor).recover,
        'log_system': LogSystemRecoveryHandler().recover,
        'all_services': CompositeRecoveryHandler(state_manager, async_wechat_api, message_monitor).recover_all_services
    }
