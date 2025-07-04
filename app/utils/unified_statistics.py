"""
统一的统计计数系统

该模块提供统一的统计计数机制，确保在正确的时间点进行计数，
避免重复计数和数据不一致的问题。

核心原则：
1. 计数的核心时间点是智能记账API返回响应，在格式化回执的时候
2. 所有统计数据都通过这个统一的系统进行管理
3. 提供数据持久化和恢复机制
4. 确保线程安全
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from PyQt6.QtCore import QObject, pyqtSignal

import logging

logger = logging.getLogger(__name__)


@dataclass
class MessageStatistics:
    """消息统计数据结构"""
    # 基础计数
    total_processed: int = 0        # 总处理消息数
    accounting_success: int = 0     # 记账成功数
    accounting_failed: int = 0      # 记账失败数
    accounting_irrelevant: int = 0  # 无关消息数
    
    # 时间信息
    session_start_time: Optional[str] = None
    last_message_time: Optional[str] = None
    last_update_time: Optional[str] = None
    
    # 会话信息
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageStatistics':
        """从字典创建实例"""
        return cls(**data)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_processed == 0:
            return 0.0
        return (self.accounting_success / self.total_processed) * 100
    
    @property
    def total_accounting_attempts(self) -> int:
        """总记账尝试次数（不包括无关消息）"""
        return self.accounting_success + self.accounting_failed


class UnifiedStatistics(QObject):
    """统一统计系统"""
    
    # 信号定义
    statistics_updated = pyqtSignal(dict)  # 统计数据更新信号
    
    def __init__(self, data_dir: str = "data", parent=None):
        super().__init__(parent)

        self._lock = threading.RLock()
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(exist_ok=True)
        self._stats_file = self._data_dir / "unified_statistics.json"

        # 统计数据
        self._statistics = MessageStatistics()

        # 回调函数列表
        self._update_callbacks: list[Callable[[MessageStatistics], None]] = []

        # 定期保存计数器
        self._save_counter = 0
        self._save_interval = 20  # 每20次更新保存一次（减少保存频率）

        # 加载已有数据
        self._load_statistics()

        # 注册应用退出时的保存
        import atexit
        atexit.register(self._save_on_exit)

        logger.info("统一统计系统初始化完成")
    
    def add_update_callback(self, callback: Callable[[MessageStatistics], None]):
        """添加统计更新回调"""
        with self._lock:
            if callback not in self._update_callbacks:
                self._update_callbacks.append(callback)
    
    def remove_update_callback(self, callback: Callable[[MessageStatistics], None]):
        """移除统计更新回调"""
        with self._lock:
            if callback in self._update_callbacks:
                self._update_callbacks.remove(callback)
    
    def start_new_session(self) -> str:
        """开始新的统计会话"""
        with self._lock:
            session_id = f"session_{int(time.time())}"
            self._statistics.session_id = session_id
            self._statistics.session_start_time = datetime.now().isoformat()
            self._statistics.last_update_time = datetime.now().isoformat()
            
            self._save_statistics()
            self._notify_update()
            
            logger.info(f"开始新的统计会话: {session_id}")
            return session_id
    
    def record_message_processed(self, chat_name: str, message_content: str):
        """记录消息被处理（消息接收时调用）"""
        with self._lock:
            self._statistics.total_processed += 1
            self._statistics.last_message_time = datetime.now().isoformat()
            self._statistics.last_update_time = datetime.now().isoformat()
            
            logger.debug(f"记录消息处理: {chat_name} - 总处理数: {self._statistics.total_processed}")

            # 定期保存
            self._save_counter += 1
            if self._save_counter >= self._save_interval:
                self._save_statistics()
                self._save_counter = 0

            self._notify_update()
    
    def record_accounting_result(self, chat_name: str, success: bool, 
                               formatted_message: str, is_irrelevant: bool = False):
        """
        记录记账结果（在格式化回执后调用）
        
        这是统计计数的核心时间点！
        
        Args:
            chat_name: 聊天名称
            success: 记账是否成功
            formatted_message: 格式化后的回执消息
            is_irrelevant: 是否为无关消息
        """
        with self._lock:
            self._statistics.last_update_time = datetime.now().isoformat()
            
            if is_irrelevant:
                # 无关消息不计入成功或失败，单独统计
                self._statistics.accounting_irrelevant += 1
                logger.debug(f"记录无关消息: {chat_name} - 无关消息数: {self._statistics.accounting_irrelevant}")
            elif success:
                # 只有非无关的成功才计入成功数
                self._statistics.accounting_success += 1
                logger.info(f"记录记账成功: {chat_name} - 成功数: {self._statistics.accounting_success}")
            else:
                # 只有非无关的失败才计入失败数
                self._statistics.accounting_failed += 1
                logger.info(f"记录记账失败: {chat_name} - 失败数: {self._statistics.accounting_failed}")
            
            # 立即保存重要的计数变化
            self._save_statistics()
            self._save_counter = 0  # 重置计数器
            self._notify_update()
    
    def get_statistics(self) -> MessageStatistics:
        """获取当前统计数据"""
        with self._lock:
            return MessageStatistics.from_dict(self._statistics.to_dict())
    
    def get_statistics_dict(self) -> Dict[str, Any]:
        """获取统计数据字典格式"""
        with self._lock:
            return self._statistics.to_dict()
    
    def reset_statistics(self, keep_session: bool = False):
        """重置统计数据"""
        with self._lock:
            old_session_id = self._statistics.session_id if keep_session else None
            old_session_start = self._statistics.session_start_time if keep_session else None
            
            self._statistics = MessageStatistics()
            
            if keep_session:
                self._statistics.session_id = old_session_id
                self._statistics.session_start_time = old_session_start
            
            self._statistics.last_update_time = datetime.now().isoformat()
            
            self._save_statistics()
            self._notify_update()
            
            logger.info("统计数据已重置")
    
    def _load_statistics(self):
        """加载统计数据"""
        try:
            if self._stats_file.exists():
                with open(self._stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._statistics = MessageStatistics.from_dict(data)
                    logger.info(f"加载统计数据成功: 处理={self._statistics.total_processed}, "
                              f"成功={self._statistics.accounting_success}, "
                              f"失败={self._statistics.accounting_failed}")
            else:
                # 尝试从备份文件恢复
                backup_file = self._stats_file.with_suffix('.json.backup')
                if backup_file.exists():
                    logger.warning("主统计文件不存在，尝试从备份恢复")
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self._statistics = MessageStatistics.from_dict(data)
                        # 立即保存到主文件
                        self._save_statistics()
                        logger.info(f"从备份恢复统计数据成功: 处理={self._statistics.total_processed}, "
                                  f"成功={self._statistics.accounting_success}, "
                                  f"失败={self._statistics.accounting_failed}")
                else:
                    logger.info("统计数据文件不存在，使用默认值")
        except Exception as e:
            logger.error(f"加载统计数据失败: {e}")
            # 尝试从备份文件恢复
            try:
                backup_file = self._stats_file.with_suffix('.json.backup')
                if backup_file.exists():
                    logger.warning("尝试从备份文件恢复")
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self._statistics = MessageStatistics.from_dict(data)
                        logger.info("从备份文件恢复成功")
                        return
            except Exception as backup_e:
                logger.error(f"从备份文件恢复也失败: {backup_e}")

            # 所有恢复尝试都失败，使用默认值
            self._statistics = MessageStatistics()
    
    def _save_statistics(self):
        """保存统计数据"""
        try:
            # 确保数据目录存在
            self._data_dir.mkdir(exist_ok=True)

            # 创建备份文件
            backup_file = self._stats_file.with_suffix('.json.backup')

            # 先写入临时文件
            temp_file = self._stats_file.with_suffix('.json.tmp')

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._statistics.to_dict(), f, ensure_ascii=False, indent=2)

            # 如果原文件存在，创建备份
            if self._stats_file.exists():
                import shutil
                shutil.copy2(self._stats_file, backup_file)

            # 原子性替换
            temp_file.replace(self._stats_file)

            logger.debug("统计数据保存成功")
        except Exception as e:
            logger.error(f"保存统计数据失败: {e}")
            # 尝试简单保存（回退方案）
            try:
                with open(self._stats_file, 'w', encoding='utf-8') as f:
                    json.dump(self._statistics.to_dict(), f, ensure_ascii=False, indent=2)
                logger.debug("使用回退方案保存成功")
            except Exception as e2:
                logger.error(f"回退保存也失败: {e2}")
                # 清理临时文件
                try:
                    temp_file = self._stats_file.with_suffix('.json.tmp')
                    if temp_file.exists():
                        temp_file.unlink()
                except:
                    pass
    
    def _notify_update(self):
        """通知统计数据更新"""
        try:
            # 发射Qt信号
            self.statistics_updated.emit(self._statistics.to_dict())
            
            # 调用回调函数
            stats_copy = self.get_statistics()
            for callback in self._update_callbacks:
                try:
                    callback(stats_copy)
                except Exception as e:
                    logger.error(f"统计更新回调失败: {e}")
                    
        except Exception as e:
            logger.error(f"通知统计更新失败: {e}")

    def _save_on_exit(self):
        """应用退出时保存统计数据"""
        try:
            logger.info("应用退出，保存统计数据")
            self._save_statistics()
        except Exception as e:
            logger.error(f"退出时保存统计数据失败: {e}")

    def force_save(self):
        """强制保存统计数据"""
        try:
            self._save_statistics()
            self._save_counter = 0
            logger.info("强制保存统计数据完成")
        except Exception as e:
            logger.error(f"强制保存统计数据失败: {e}")


# 全局统一统计实例
_unified_stats: Optional[UnifiedStatistics] = None


def get_unified_statistics() -> UnifiedStatistics:
    """获取全局统一统计实例"""
    global _unified_stats
    if _unified_stats is None:
        _unified_stats = UnifiedStatistics()
    return _unified_stats


def initialize_unified_statistics(data_dir: str = "data") -> UnifiedStatistics:
    """初始化全局统一统计实例"""
    global _unified_stats
    _unified_stats = UnifiedStatistics(data_dir)
    return _unified_stats
