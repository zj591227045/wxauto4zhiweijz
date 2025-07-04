"""
消息处理器包装类

为主窗口提供统一的消息处理统计接口，解决get_processing_statistics方法缺失的问题。
该包装类整合了统一统计系统，为UI层提供一致的数据接口。
"""

from typing import Dict, Any, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal

from app.utils.unified_statistics import get_unified_statistics, MessageStatistics
import logging

logger = logging.getLogger(__name__)


class MessageProcessorWrapper(QObject):
    """
    消息处理器包装类
    
    为主窗口提供统一的消息处理统计接口，整合多个组件的统计数据。
    """
    
    # 信号定义
    statistics_updated = pyqtSignal(str, dict)  # (chat_name, statistics)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 获取统一统计系统
        self._unified_stats = get_unified_statistics()
        
        # 连接统计更新信号
        self._unified_stats.statistics_updated.connect(self._on_statistics_updated)
        
        # 聊天特定的统计数据（如果需要按聊天分组）
        self._chat_statistics: Dict[str, Dict[str, Any]] = {}
        
        logger.info("消息处理器包装类初始化完成")
    
    def get_processing_statistics(self, chat_name: str) -> Dict[str, Any]:
        """
        获取指定聊天的处理统计信息
        
        这是主窗口调用的核心方法，返回与旧版本兼容的统计数据格式。
        
        Args:
            chat_name: 聊天名称
            
        Returns:
            统计数据字典，包含以下字段：
            - total_processed: 总处理消息数
            - accounting_success: 记账成功数
            - accounting_failed: 记账失败数
            - accounting_nothing: 无关消息数（与记账无关）
        """
        try:
            # 获取全局统计数据
            global_stats = self._unified_stats.get_statistics()
            
            # 构建兼容的统计数据格式
            statistics = {
                'total_processed': global_stats.total_processed,
                'accounting_success': global_stats.accounting_success,
                'accounting_failed': global_stats.accounting_failed,
                'accounting_nothing': global_stats.accounting_irrelevant,
                'success_rate': global_stats.success_rate,
                'last_message_time': global_stats.last_message_time,
                'session_start_time': global_stats.session_start_time,
                'last_update_time': global_stats.last_update_time
            }
            
            logger.debug(f"获取 {chat_name} 统计信息: {statistics}")
            return statistics
            
        except Exception as e:
            logger.error(f"获取 {chat_name} 统计信息失败: {e}")
            # 返回默认的空统计数据
            return {
                'total_processed': 0,
                'accounting_success': 0,
                'accounting_failed': 0,
                'accounting_nothing': 0,
                'success_rate': 0.0,
                'last_message_time': None,
                'session_start_time': None,
                'last_update_time': None
            }
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """获取所有统计信息"""
        try:
            return self._unified_stats.get_statistics_dict()
        except Exception as e:
            logger.error(f"获取所有统计信息失败: {e}")
            return {}
    
    def get_global_statistics(self) -> MessageStatistics:
        """获取全局统计对象"""
        return self._unified_stats.get_statistics()
    
    def record_message_processed(self, chat_name: str, message_content: str):
        """记录消息被处理"""
        try:
            self._unified_stats.record_message_processed(chat_name, message_content)
        except Exception as e:
            logger.error(f"记录消息处理失败: {e}")
    
    def record_accounting_result(self, chat_name: str, success: bool, 
                               formatted_message: str, is_irrelevant: bool = False):
        """记录记账结果"""
        try:
            self._unified_stats.record_accounting_result(
                chat_name, success, formatted_message, is_irrelevant
            )
        except Exception as e:
            logger.error(f"记录记账结果失败: {e}")
    
    def reset_statistics(self, keep_session: bool = False):
        """重置统计数据"""
        try:
            self._unified_stats.reset_statistics(keep_session)
            self._chat_statistics.clear()
            logger.info("统计数据已重置")
        except Exception as e:
            logger.error(f"重置统计数据失败: {e}")
    
    def start_new_session(self) -> str:
        """开始新的统计会话"""
        try:
            session_id = self._unified_stats.start_new_session()
            self._chat_statistics.clear()
            logger.info(f"开始新的统计会话: {session_id}")
            return session_id
        except Exception as e:
            logger.error(f"开始新会话失败: {e}")
            return ""
    
    def get_chat_list(self) -> List[str]:
        """获取有统计数据的聊天列表"""
        return list(self._chat_statistics.keys())
    
    def _on_statistics_updated(self, stats_dict: Dict[str, Any]):
        """统计数据更新回调"""
        try:
            # 为所有已知的聊天发出更新信号
            # 由于当前是全局统计，所以对所有聊天都发出相同的统计数据
            if self._chat_statistics:
                for chat_name in self._chat_statistics.keys():
                    self.statistics_updated.emit(chat_name, stats_dict)
            else:
                # 如果没有特定聊天，发出一个通用的更新信号
                self.statistics_updated.emit("global", stats_dict)
                
        except Exception as e:
            logger.error(f"处理统计更新失败: {e}")
    
    def add_monitored_chat(self, chat_name: str):
        """添加监控的聊天"""
        if chat_name not in self._chat_statistics:
            self._chat_statistics[chat_name] = {}
            logger.debug(f"添加监控聊天: {chat_name}")
    
    def remove_monitored_chat(self, chat_name: str):
        """移除监控的聊天"""
        if chat_name in self._chat_statistics:
            del self._chat_statistics[chat_name]
            logger.debug(f"移除监控聊天: {chat_name}")
    
    def get_monitored_chats(self) -> List[str]:
        """获取监控的聊天列表"""
        return list(self._chat_statistics.keys())


# 全局消息处理器包装实例
_message_processor_wrapper: Optional[MessageProcessorWrapper] = None


def get_message_processor_wrapper() -> MessageProcessorWrapper:
    """获取全局消息处理器包装实例"""
    global _message_processor_wrapper
    if _message_processor_wrapper is None:
        _message_processor_wrapper = MessageProcessorWrapper()
    return _message_processor_wrapper


def initialize_message_processor_wrapper() -> MessageProcessorWrapper:
    """初始化全局消息处理器包装实例"""
    global _message_processor_wrapper
    _message_processor_wrapper = MessageProcessorWrapper()
    return _message_processor_wrapper
