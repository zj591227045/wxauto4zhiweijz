"""
基于序列匹配的微信消息处理器
实现消息唯一性识别和智能新消息检测
"""

import time
import hashlib
import sqlite3
import threading
import requests
import logging
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal
import sys

logger = logging.getLogger(__name__)

@dataclass
class MessageRecord:
    """消息记录"""
    message_id: str
    content: str
    sender: str
    time_context: str
    sequence_position: int
    fingerprint: str
    
    def __post_init__(self):
        if not self.fingerprint:
            self.fingerprint = self.generate_fingerprint()
    
    def generate_fingerprint(self) -> str:
        """生成消息指纹：内容+消息ID"""
        content_hash = hashlib.md5(self.content.encode('utf-8')).hexdigest()[:8]
        return f"{content_hash}|{self.message_id}"

class MessageProcessor(QObject):
    """
    基于序列匹配的微信消息处理器
    
    核心功能：
    1. 首次添加时强制标记所有现有消息为已读
    2. 基于序列匹配识别新消息
    3. 消息唯一性：内容+消息ID
    4. 智能重试和错误处理
    """
    
    # 信号定义
    message_processed = pyqtSignal(str, str, bool, str)  # 聊天对象, 消息内容, 成功状态, 结果消息
    status_changed = pyqtSignal(str, bool)  # 聊天对象, 监控状态
    error_occurred = pyqtSignal(str, str)  # 聊天对象, 错误信息
    statistics_updated = pyqtSignal(str, dict)  # 聊天对象, 统计信息
    initialization_progress = pyqtSignal(str, str, int, int)  # 聊天对象, 状态, 当前, 总数
    
    def __init__(self, api_base_url: str, api_key: str, db_path: str = None, config_path: str = None):
        """
        初始化消息处理器
        
        Args:
            api_base_url: WxAuto API基础URL
            api_key: API密钥
            db_path: SQLite数据库文件路径
            config_path: 用户配置文件路径
        """
        super().__init__()
        self.api_base_url = api_base_url.rstrip('/')
        self.api_key = api_key
        
        # 确保数据库路径正确
        if db_path is None:
            # 获取程序运行目录
            if getattr(sys, 'frozen', False):
                # 打包后的环境
                app_dir = os.path.dirname(sys.executable)
            else:
                # 开发环境
                app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            data_dir = os.path.join(app_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            self.db_path = os.path.join(data_dir, "message_processor.db")
        else:
            self.db_path = db_path
        
        # 加载用户配置
        if config_path is None:
            if getattr(sys, 'frozen', False):
                # 打包后的环境
                app_dir = os.path.dirname(sys.executable)
            else:
                # 开发环境
                app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            config_dir = os.path.join(app_dir, "data", "api", "config")
            os.makedirs(config_dir, exist_ok=True)
            self.config_path = os.path.join(config_dir, "user_config.json")
        else:
            self.config_path = config_path
            
        self.user_config = self.load_user_config()
        
        # 监控状态
        self.monitored_chats: Dict[str, bool] = {}  # 聊天对象 -> 是否正在监控
        self.monitor_threads: Dict[str, threading.Thread] = {}  # 监控线程
        self.stop_events: Dict[str, threading.Event] = {}  # 停止事件
        
        # 数据库锁
        self.db_lock = threading.Lock()
        
        # API请求头
        self.headers = {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        # 序列匹配配置
        self.SEQUENCE_MATCH_LENGTH = 3  # 用于匹配的序列长度
        self.MAX_INIT_RETRIES = 10  # 初始化最大重试次数
        self.INIT_RETRY_DELAY = 3  # 初始化重试延迟（秒）
        
        # 初始化数据库
        self.init_database()
        
        # 迁移记账状态（兼容旧数据）
        self.migrate_accounting_status()
    
    def load_user_config(self) -> Dict:
        """加载用户配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"成功加载用户配置: {self.config_path}")
                    return config
            else:
                logger.warning(f"配置文件不存在: {self.config_path}")
                return {}
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}
    
    def get_accounting_config(self) -> Dict:
        """获取记账配置"""
        return self.user_config.get('accounting', {})
    
    def init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建消息记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL UNIQUE,
                    chat_target TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    time_context TEXT NOT NULL,
                    sequence_position INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    accounting_status TEXT DEFAULT 'nothing',
                    api_response_data TEXT,
                    accounting_record_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    is_initial_mark BOOLEAN DEFAULT 0
                )
            ''')
            
            # 检查是否需要添加新字段（兼容旧数据库）
            cursor.execute("PRAGMA table_info(message_records)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'accounting_status' not in columns:
                cursor.execute('ALTER TABLE message_records ADD COLUMN accounting_status TEXT DEFAULT "nothing"')
                logger.info("已添加 accounting_status 字段到 message_records 表")
            
            if 'api_response_data' not in columns:
                cursor.execute('ALTER TABLE message_records ADD COLUMN api_response_data TEXT')
                logger.info("已添加 api_response_data 字段到 message_records 表")
            
            if 'accounting_record_id' not in columns:
                cursor.execute('ALTER TABLE message_records ADD COLUMN accounting_record_id TEXT')
                logger.info("已添加 accounting_record_id 字段到 message_records 表")
            
            # 创建聊天状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_target TEXT NOT NULL UNIQUE,
                    is_initialized BOOLEAN DEFAULT 0,
                    check_interval INTEGER DEFAULT 5,
                    max_retries INTEGER DEFAULT 3,
                    last_check_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建序列匹配历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sequence_match_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_target TEXT NOT NULL,
                    match_sequence TEXT NOT NULL,
                    match_position INTEGER NOT NULL,
                    new_messages_count INTEGER NOT NULL,
                    match_confidence REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建处理日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_target TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    error_details TEXT,
                    processing_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_records_chat_target ON message_records(chat_target)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_records_fingerprint ON message_records(fingerprint)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_records_status ON message_records(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_records_accounting_status ON message_records(accounting_status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_records_accounting_record_id ON message_records(accounting_record_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_processing_logs_chat_target ON processing_logs(chat_target)')
            
            conn.commit()
            logger.info("数据库初始化完成")
    
    def migrate_accounting_status(self):
        """
        迁移现有数据库中的记账状态
        将所有状态为'processed'且记账状态为'nothing'的初始消息更新为'initial'
        """
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 查询需要更新的记录数量
                cursor.execute('''
                    SELECT COUNT(*) FROM message_records 
                    WHERE status = 'processed' 
                    AND accounting_status = 'nothing' 
                    AND is_initial_mark = 1
                ''')
                initial_count = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(*) FROM message_records 
                    WHERE status = 'processed' 
                    AND accounting_status = 'nothing' 
                    AND is_initial_mark = 0
                    AND api_response_data IS NULL
                ''')
                unprocessed_count = cursor.fetchone()[0]
                
                if initial_count > 0:
                    # 更新初始标记的消息为'initial'状态
                    cursor.execute('''
                        UPDATE message_records 
                        SET accounting_status = 'initial', updated_at = CURRENT_TIMESTAMP
                        WHERE status = 'processed' 
                        AND accounting_status = 'nothing' 
                        AND is_initial_mark = 1
                    ''')
                    logger.info(f"已将 {initial_count} 条初始消息的记账状态更新为 'initial'")
                
                if unprocessed_count > 0:
                    # 更新未经过API处理的消息为'pending'状态
                    cursor.execute('''
                        UPDATE message_records 
                        SET accounting_status = 'pending', updated_at = CURRENT_TIMESTAMP
                        WHERE status = 'processed' 
                        AND accounting_status = 'nothing' 
                        AND is_initial_mark = 0
                        AND api_response_data IS NULL
                    ''')
                    logger.info(f"已将 {unprocessed_count} 条未处理消息的记账状态更新为 'pending'")
                
                conn.commit()
                
                if initial_count == 0 and unprocessed_count == 0:
                    logger.info("数据库中的记账状态已是最新，无需迁移")
                else:
                    logger.info(f"记账状态迁移完成：初始消息 {initial_count} 条，待处理消息 {unprocessed_count} 条")
    
    def generate_message_fingerprint(self, message: Dict, time_context: str) -> str:
        """
        生成消息指纹
        
        Args:
            message: 消息对象
            time_context: 时间上下文
            
        Returns:
            消息指纹字符串
        """
        content = message.get('content', '')
        sender = message.get('sender', '')
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
        
        # 获取消息在当前批次中的位置索引，用于区分连续相同消息
        # 这个索引会在process_messages方法中设置
        message_index = message.get('_batch_index', 0)
        
        # 使用|作为分隔符，避免时间上下文中的冒号造成问题
        return f"{sender}|{content_hash}|{time_context}|{message_index}"
    
    def add_chat_target(self, chat_target: str, check_interval: int = 5, max_retries: int = 3) -> bool:
        """
        添加聊天对象到监控列表
        
        Args:
            chat_target: 聊天对象名称
            check_interval: 检查间隔（秒）
            max_retries: 最大重试次数
            
        Returns:
            True表示添加成功，False表示已存在
        """
        if chat_target in self.monitored_chats:
            logger.warning(f"聊天对象 {chat_target} 已存在")
            return False
        
        # 添加到本地监控列表
        self.monitored_chats[chat_target] = False
        
        # 保存聊天对象状态到数据库
        self.save_chat_status(chat_target, check_interval, max_retries)
        
        logger.info(f"已添加聊天对象: {chat_target}")
        return True
    
    def save_chat_status(self, chat_target: str, check_interval: int, max_retries: int):
        """保存聊天对象状态到数据库"""
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                # 首先检查是否已存在记录
                cursor.execute('SELECT is_initialized FROM chat_status WHERE chat_target = ?', (chat_target,))
                existing_record = cursor.fetchone()
                
                if existing_record:
                    # 如果记录已存在，只更新非关键字段，保留is_initialized状态
                    cursor.execute('''
                        UPDATE chat_status 
                        SET check_interval = ?, max_retries = ?, enabled = 1, updated_at = ?
                        WHERE chat_target = ?
                    ''', (check_interval, max_retries, current_time, chat_target))
                    logger.debug(f"更新聊天状态: {chat_target} (保留初始化状态: {existing_record[0]})")
                else:
                    # 如果记录不存在，创建新记录
                    cursor.execute('''
                        INSERT INTO chat_status 
                        (chat_target, check_interval, max_retries, enabled, created_at, updated_at)
                        VALUES (?, ?, ?, 1, ?, ?)
                    ''', (chat_target, check_interval, max_retries, current_time, current_time))
                    logger.debug(f"创建新聊天状态: {chat_target}")
                
                conn.commit()
    
    def is_chat_initialized(self, chat_target: str) -> bool:
        """检查聊天对象是否已初始化"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT is_initialized FROM chat_status 
                WHERE chat_target = ?
            ''', (chat_target,))
            result = cursor.fetchone()
            return result[0] if result else False
    
    def start_monitoring(self, chat_target: str) -> bool:
        """
        开始监控指定聊天对象
        
        Args:
            chat_target: 聊天对象名称
            
        Returns:
            True表示启动成功，False表示启动失败
        """
        if chat_target not in self.monitored_chats:
            logger.error(f"聊天对象 {chat_target} 不在监控列表中")
            return False
        
        if self.monitored_chats[chat_target]:
            logger.warning(f"聊天对象 {chat_target} 已在监控中")
            return False
        
        try:
            # 1. 确保聊天对象在API监听列表中
            logger.info(f"确保 {chat_target} 在API监听列表中...")
            self.ensure_chat_in_listen_list(chat_target)
            
            # 2. 检查是否为首次初始化
            logger.debug(f"检查 {chat_target} 的初始化状态...")
            is_initialized = self.is_chat_initialized(chat_target)
            logger.debug(f"is_chat_initialized('{chat_target}') 返回: {is_initialized} (类型: {type(is_initialized)})")
            is_first_time = not is_initialized
            logger.debug(f"is_first_time = not is_initialized = {is_first_time}")
            logger.info(f"数据库路径: {self.db_path}")
            
            if is_first_time:
                logger.info(f"聊天对象 {chat_target} 首次初始化，开始标记现有消息为已读...")
                
                # 首次初始化：强制标记所有现有消息为已读
                init_success = self.initialize_chat_first_time(chat_target)
                if not init_success:
                    error_msg = f"首次初始化 {chat_target} 失败，停止监听以避免处理历史消息"
                    logger.error(error_msg)
                    self.error_occurred.emit(chat_target, error_msg)
                    return False
                
                logger.info(f"成功完成 {chat_target} 的首次初始化")
            else:
                logger.info(f"聊天对象 {chat_target} 非首次添加，开始对比合并消息...")
                
                # 非首次：对比合并，更新消息ID
                merge_success = self.merge_and_update_messages(chat_target)
                if not merge_success:
                    error_msg = f"对比合并 {chat_target} 消息失败"
                    logger.error(error_msg)
                    self.error_occurred.emit(chat_target, error_msg)
                    return False
                
                logger.info(f"成功完成 {chat_target} 的消息对比合并")
            
            # 3. 创建停止事件并启动监控线程
            stop_event = threading.Event()
            self.stop_events[chat_target] = stop_event
            
            monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(chat_target, stop_event),
                daemon=True,
                name=f"Monitor-{chat_target}"
            )
            monitor_thread.start()
            self.monitor_threads[chat_target] = monitor_thread
            
            # 4. 更新状态
            self.monitored_chats[chat_target] = True
            self.status_changed.emit(chat_target, True)
            
            logger.info(f"开始监控聊天对象: {chat_target}")
            return True
            
        except Exception as e:
            error_msg = f"启动监控失败: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(chat_target, error_msg)
            return False
    
    def initialize_chat_first_time(self, chat_target: str) -> bool:
        """
        首次初始化聊天对象（标记所有现有消息为已读）
        
        Args:
            chat_target: 聊天对象名称
            
        Returns:
            True表示初始化成功，False表示初始化失败
        """
        for attempt in range(self.MAX_INIT_RETRIES):
            try:
                logger.info(f"首次初始化 {chat_target} (尝试 {attempt + 1}/{self.MAX_INIT_RETRIES})")
                self.initialization_progress.emit(chat_target, "首次初始化中", attempt + 1, self.MAX_INIT_RETRIES)
                
                # 1. 验证API访问
                if not self.verify_chat_api_access(chat_target):
                    logger.warning(f"API无法访问聊天对象 {chat_target}，等待后重试...")
                    time.sleep(self.INIT_RETRY_DELAY * (attempt + 1))
                    continue
                
                # 2. 获取当前所有消息
                messages = self.get_messages_from_api(chat_target)
                if not messages:
                    logger.warning(f"获取 {chat_target} 的消息列表为空")
                    time.sleep(self.INIT_RETRY_DELAY)
                    continue
                
                # 3. 解析消息并标记为已读
                message_records = self.parse_messages_to_records(chat_target, messages)
                if not message_records:
                    logger.warning(f"解析 {chat_target} 的消息记录为空")
                    time.sleep(self.INIT_RETRY_DELAY)
                    continue
                
                # 4. 批量保存为已读状态（首次初始化）
                self.batch_save_initial_messages(chat_target, message_records, is_first_time=True)
                
                # 5. 标记聊天对象为已初始化
                self.mark_chat_as_initialized(chat_target, message_records)
                
                logger.info(f"成功首次初始化 {chat_target}，标记了 {len(message_records)} 条消息为已读")
                self.initialization_progress.emit(chat_target, "首次初始化完成", self.MAX_INIT_RETRIES, self.MAX_INIT_RETRIES)
                return True
                
            except Exception as e:
                logger.error(f"首次初始化 {chat_target} 失败 (尝试 {attempt + 1}/{self.MAX_INIT_RETRIES}): {e}")
                if attempt < self.MAX_INIT_RETRIES - 1:
                    wait_time = self.INIT_RETRY_DELAY * (attempt + 1)
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"所有首次初始化尝试均失败，无法初始化 {chat_target}")
                    self.initialization_progress.emit(chat_target, "首次初始化失败", 0, self.MAX_INIT_RETRIES)
        
        return False
    
    def merge_and_update_messages(self, chat_target: str) -> bool:
        """
        非首次添加：简化的消息合并处理（避免复杂的序列匹配）
        
        Args:
            chat_target: 聊天对象名称
            
        Returns:
            True表示合并成功，False表示合并失败
        """
        try:
            logger.info(f"开始简化的消息合并处理: {chat_target}")
            
            # 1. 获取当前API消息
            current_messages = self.get_messages_from_api(chat_target)
            if not current_messages:
                logger.warning(f"获取 {chat_target} 的当前消息为空")
                return True  # 空消息不算失败
            
            current_records = self.parse_messages_to_records(chat_target, current_messages)
            if not current_records:
                logger.warning(f"解析 {chat_target} 的当前消息记录为空")
                return True  # 空记录不算失败
            
            # 2. 简化处理：不进行复杂的序列匹配，直接标记所有当前消息为已知
            # 这样可以避免序列匹配算法的问题，让监控循环正常运行
            logger.info(f"简化处理：将当前 {len(current_records)} 条消息标记为已知状态")
            
            # 3. 批量保存当前消息为已处理状态（避免重复处理）
            self.batch_save_initial_messages(chat_target, current_records, is_first_time=False)
            
            logger.info(f"成功完成 {chat_target} 的简化消息合并")
            return True
                
        except Exception as e:
            logger.error(f"简化消息合并失败: {e}")
            # 即使合并失败，也不应该阻止监控启动
            logger.warning(f"合并失败但继续启动监控: {chat_target}")
            return True  # 返回True让监控继续
    
    def stop_monitoring(self, chat_target: str) -> bool:
        """
        停止监控指定聊天对象
        
        Args:
            chat_target: 聊天对象名称
            
        Returns:
            True表示停止成功，False表示停止失败
        """
        if chat_target not in self.monitored_chats:
            logger.error(f"聊天对象 {chat_target} 不在监控列表中")
            return False
        
        if not self.monitored_chats[chat_target]:
            logger.warning(f"聊天对象 {chat_target} 未在监控中")
            return False
        
        try:
            # 设置停止事件
            if chat_target in self.stop_events:
                self.stop_events[chat_target].set()
            
            # 等待线程结束
            if chat_target in self.monitor_threads:
                thread = self.monitor_threads[chat_target]
                if thread.is_alive():
                    thread.join(timeout=5)
                del self.monitor_threads[chat_target]
            
            # 清理停止事件
            if chat_target in self.stop_events:
                del self.stop_events[chat_target]
            
            # 更新状态
            self.monitored_chats[chat_target] = False
            self.status_changed.emit(chat_target, False)
            
            logger.info(f"停止监控聊天对象: {chat_target}")
            return True
            
        except Exception as e:
            error_msg = f"停止监控失败: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(chat_target, error_msg)
        return False
    
    def verify_chat_api_access(self, chat_target: str, timeout: int = 5) -> bool:
        """
        验证API是否可以访问指定的聊天对象
        
        Args:
            chat_target: 聊天对象名称
            timeout: 超时时间（秒）
            
        Returns:
            True表示可以访问，False表示无法访问
        """
        try:
            logger.debug(f"验证API对 {chat_target} 的访问权限...")
            
            # 使用HEAD请求或简单的GET请求验证
            url = f"{self.api_base_url}/api/chat-window/get-all-messages"
            params = {'who': chat_target}
            
            response = requests.get(url, headers=self.headers, params=params, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                if data['code'] == 0:
                    logger.debug(f"API可以访问 {chat_target}")
                    return True
                else:
                    logger.debug(f"API返回错误码: {data['code']} - {data.get('message', '')}")
                    return False
            elif response.status_code == 404:
                logger.debug(f"聊天对象 {chat_target} 不存在或不在监听列表中")
                return False
            else:
                logger.debug(f"API返回HTTP状态码: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.debug(f"验证 {chat_target} 访问权限超时")
            return False
        except Exception as e:
            logger.debug(f"验证 {chat_target} 访问权限异常: {e}")
            return False
    
    def get_messages_from_api(self, chat_target: str) -> List[Dict]:
        """
        从API获取消息列表（增强版，支持自动重试和自动添加监听对象）
        
        Args:
            chat_target: 聊天对象名称
            
        Returns:
            消息列表
            
        Raises:
            Exception: API调用失败时抛出异常
        """
        max_retries = 3
        timeout = 30
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"尝试获取 {chat_target} 的消息 (尝试 {attempt + 1}/{max_retries})")
                
                # 使用正确的聊天窗口消息获取端点
                url = f"{self.api_base_url}/api/chat-window/get-all-messages"
                params = {'who': chat_target}
                
                response = requests.get(url, headers=self.headers, params=params, timeout=timeout)
            
                if response.status_code == 200:
                    data = response.json()
                    if data['code'] == 0:
                        # 成功获取消息
                        messages = data['data']['messages']
                        logger.debug(f"成功获取 {chat_target} 的 {len(messages)} 条消息")
                        return messages
                    else:
                        # API返回错误码，可能是监听对象未添加
                        error_msg = data.get('message', '未知错误')
                        logger.warning(f"API返回错误 (尝试 {attempt + 1}/{max_retries}): {data['code']} - {error_msg}")
                        
                        # 检查是否是监听对象未添加的错误
                        if data['code'] == 3001 or '未在监听列表中' in error_msg:
                            logger.info(f"检测到 {chat_target} 未在监听列表中，尝试自动添加...")
                            try:
                                # 自动添加到监听列表
                                self._auto_add_to_listen_list(chat_target)
                                logger.info(f"成功添加 {chat_target} 到监听列表，继续获取消息...")
                                
                                # 添加成功后，等待一下再重试
                                time.sleep(2)
                                continue
                                
                            except Exception as add_error:
                                logger.error(f"自动添加 {chat_target} 到监听列表失败: {add_error}")
                                if attempt == max_retries - 1:
                                    raise Exception(f"无法添加 {chat_target} 到监听列表: {add_error}")
                        
                        # 其他错误，如果不是最后一次尝试则继续重试
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 2
                            logger.info(f"等待 {wait_time} 秒后重试...")
                            time.sleep(wait_time)
                            continue
                        else:
                            raise Exception(f"API返回错误: {data['code']} - {error_msg}")
                
                elif response.status_code == 404:
                    # 404错误，通常表示监听对象未添加
                    logger.warning(f"收到404错误 (尝试 {attempt + 1}/{max_retries})，{chat_target} 可能未在监听列表中")
                    
                    try:
                        # 自动添加到监听列表
                        logger.info(f"尝试自动添加 {chat_target} 到监听列表...")
                        self._auto_add_to_listen_list(chat_target)
                        logger.info(f"成功添加 {chat_target} 到监听列表，继续获取消息...")
                        
                        # 添加成功后，等待一下再重试
                        time.sleep(2)
                        continue
                        
                    except Exception as add_error:
                        logger.error(f"自动添加 {chat_target} 到监听列表失败: {add_error}")
                        if attempt == max_retries - 1:
                            raise Exception(f"无法添加 {chat_target} 到监听列表: {add_error}")
                
                else:
                    # 其他HTTP错误
                    logger.warning(f"HTTP错误 (尝试 {attempt + 1}/{max_retries}): {response.status_code}")
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        logger.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        response.raise_for_status()
                
            except requests.exceptions.Timeout:
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3  # 超时错误等待更长时间
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"获取 {chat_target} 消息超时")
            
            except requests.exceptions.ConnectionError:
                logger.warning(f"连接错误 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"无法连接到API服务器")
            
            except Exception as e:
                logger.error(f"获取消息异常 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"获取 {chat_target} 消息失败: {e}")
        
        # 如果所有重试都失败了
        raise Exception(f"所有获取 {chat_target} 消息的尝试都失败了")
    
    def _auto_add_to_listen_list(self, chat_target: str):
        """
        自动添加聊天对象到监听列表（内部方法）
        
        Args:
            chat_target: 聊天对象名称
            
        Raises:
            Exception: 添加失败时抛出异常
        """
        max_add_retries = 2
        timeout = 30
        
        for add_attempt in range(max_add_retries):
            try:
                logger.info(f"自动添加 {chat_target} 到监听列表 (尝试 {add_attempt + 1}/{max_add_retries})")
                
                url = f"{self.api_base_url}/api/message/listen/add"
                data = {
                    "who": chat_target,
                    "savepic": False,
                    "savefile": False,
                    "savevoice": False
                }
                
                response = requests.post(url, headers=self.headers, json=data, timeout=timeout)
                
                if response.status_code == 200:
                    result = response.json()
                    if result['code'] == 0:
                        logger.info(f"成功自动添加 {chat_target} 到监听列表")
                        return  # 成功
                    elif result['code'] == 3002 and '已存在' in result.get('message', ''):
                        # 已存在也算成功
                        logger.info(f"{chat_target} 已在监听列表中")
                        return
                    else:
                        error_msg = f"添加失败: {result['code']} - {result.get('message', '')}"
                        logger.warning(error_msg)
                        if add_attempt == max_add_retries - 1:
                            raise Exception(error_msg)
                else:
                    error_msg = f"HTTP错误: {response.status_code}"
                    logger.warning(error_msg)
                    if add_attempt == max_add_retries - 1:
                        raise Exception(error_msg)
                
                # 重试前等待
                if add_attempt < max_add_retries - 1:
                    wait_time = (add_attempt + 1) * 2
                    logger.info(f"等待 {wait_time} 秒后重试添加...")
                    time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"自动添加监听列表异常 (尝试 {add_attempt + 1}/{max_add_retries}): {e}")
                if add_attempt == max_add_retries - 1:
                    raise
                else:
                    wait_time = (add_attempt + 1) * 2
                    logger.info(f"等待 {wait_time} 秒后重试添加...")
                    time.sleep(wait_time)
    
    def process_new_messages(self, chat_target: str) -> List[str]:
        """
        处理新消息的主要方法
        
        Args:
            chat_target: 聊天对象名称
            
        Returns:
            处理结果列表
        """
        try:
            # 1. 获取当前所有消息
            messages = self.get_messages_from_api(chat_target)
            if not messages:
                logger.debug(f"{chat_target} 没有获取到消息")
                return []
            
            # 2. 解析消息为记录对象
            current_records = self.parse_messages_to_records(chat_target, messages)
            if not current_records:
                logger.debug(f"{chat_target} 解析后没有有效消息")
                return []
            
            # 3. 识别新消息
            new_messages = self.identify_new_messages(chat_target, current_records)
            if not new_messages:
                logger.debug(f"{chat_target} 没有新消息需要处理")
                return []
            
            # 4. 处理每条新消息
            processing_results = []
            for new_msg in new_messages:
                try:
                    success = self.handle_single_new_message(chat_target, new_msg)
                    if success:
                        processing_results.append(f"✅ 成功处理: {new_msg.sender} - {new_msg.content[:50]}... (ID:{new_msg.message_id})")
                    else:
                        processing_results.append(f"❌ 处理失败: {new_msg.sender} - {new_msg.content[:50]}... (ID:{new_msg.message_id})")
                        
                except Exception as e:
                    processing_results.append(f"💥 处理异常: {new_msg.sender} - {new_msg.content[:50]}... (ID:{new_msg.message_id}) - {str(e)}")
            
            return processing_results
            
        except Exception as e:
            error_msg = f"处理新消息时发生异常: {str(e)}"
            logger.error(f"[{chat_target}] {error_msg}")
            self.error_occurred.emit(chat_target, error_msg)
            return [f"💥 处理异常: {error_msg}"]
    
    def handle_single_new_message(self, chat_target: str, message_record: MessageRecord) -> bool:
        """
        处理单条新消息
        
        Args:
            chat_target: 聊天对象名称
            message_record: 消息记录对象
            
        Returns:
            True表示处理成功，False表示处理失败
        """
        start_time = datetime.now()
        
        try:
            timestamp = start_time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{timestamp}] 正在处理新消息: {chat_target} - {message_record.sender} - {message_record.content}")
            
            # 0. 检查是否已有记账记录ID（避免重复发送到智能记账API）
            existing_record_id = self.get_existing_accounting_record_id(chat_target, message_record.fingerprint)
            if existing_record_id:
                logger.info(f"消息已有记账记录ID {existing_record_id}，跳过智能记账API调用")
                # 标记为已处理，但不调用智能记账API
                self.save_message_record(chat_target, message_record, "processed", None, "success", None, existing_record_id)
                self.message_processed.emit(chat_target, message_record.content, True, "消息已记账，跳过重复处理")
                return True
            
            # 1. 保存消息记录为处理中状态
            self.save_message_record(chat_target, message_record, "processing")
            self.log_processing_action(chat_target, message_record.fingerprint, "start_processing", "info", 
                                     f"开始处理新消息: {message_record.content}")
            
            # 2. 调用智能记账API，传递发送者名称
            success, api_result_msg, api_response_data, accounting_record_id = self.call_smart_accounting_api(message_record.content, message_record.sender)
            
            # 3. 判断记账状态
            accounting_status = self.determine_accounting_status(success, api_result_msg)
            
            if not success:
                error_msg = f"智能记账失败: {api_result_msg}"
                logger.error(error_msg)
                self.save_message_record(chat_target, message_record, "failed", error_msg, accounting_status,
                                       api_response_data, accounting_record_id)
                self.log_processing_action(chat_target, message_record.fingerprint, "call_smart_accounting_api", "error", error_msg)
                self.message_processed.emit(chat_target, message_record.content, False, error_msg)
                return False
            
            # 4. 智能记账成功，根据记账状态决定是否发送回复到微信
            should_send_reply = True
            
            # 如果是"信息与记账无关"，不发送回复到微信
            if accounting_status == "nothing":
                logger.info(f"消息与记账无关，不发送回复到微信: {api_result_msg}")
                should_send_reply = False
            
            # 发送回复到微信（除了"信息与记账无关"的情况）
            if should_send_reply:
                reply_content = api_result_msg
                reply_success = self.send_reply_to_wechat(chat_target, reply_content)
                if not reply_success:
                    # 记账成功但回复失败，仍然认为是成功的（因为主要目标是记账）
                    logger.warning(f"记账成功但微信回复失败: {reply_content}")
                else:
                    logger.info(f"已发送回复到微信: {reply_content[:50]}...")
            
            # 5. 处理成功
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            success_msg = f"消息处理完成: {message_record.content} -> {api_result_msg} (记账状态: {accounting_status})"
            if accounting_record_id:
                success_msg += f" (记录ID: {accounting_record_id})"
            logger.info(success_msg)
            
            self.save_message_record(chat_target, message_record, "processed", None, accounting_status,
                                   api_response_data, accounting_record_id)
            self.log_processing_action(chat_target, message_record.fingerprint, "complete_processing", "success", 
                                     success_msg, processing_time_ms=processing_time)
            self.message_processed.emit(chat_target, message_record.content, True, api_result_msg)
            return True
                
        except Exception as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            error_msg = f"处理消息时发生异常: {e}"
            logger.error(error_msg)
            
            self.save_message_record(chat_target, message_record, "failed", error_msg, "failed")
            self.log_processing_action(chat_target, message_record.fingerprint, "exception", "error", 
                                     error_msg, str(e), processing_time)
            self.message_processed.emit(chat_target, message_record.content, False, error_msg)
            return False
    
    def determine_accounting_status(self, success: bool, api_result_msg: str) -> str:
        """
        根据智能记账API响应判断记账状态
        
        Args:
            success: API调用是否成功
            api_result_msg: API返回的消息
            
        Returns:
            记账状态: 'success', 'failed', 'nothing'
        """
        if not success:
            return "failed"
        
        # 检查消息内容判断是否与记账无关
        nothing_keywords = [
            "信息与记账无关",
            "消息与记账无关",
            "无法识别记账信息",
            "不是记账相关消息",
            "非记账消息",
            "无记账内容"
        ]
        
        for keyword in nothing_keywords:
            if keyword in api_result_msg:
                return "nothing"
        
        # 如果API成功且不包含"无关"关键词，认为是记账成功
        return "success"
    
    def save_message_record(self, chat_target: str, message_record: MessageRecord, 
                           status: str, error_msg: str = None, accounting_status: str = None,
                           api_response_data: Dict = None, accounting_record_id: str = None):
        """
        保存消息记录到数据库
        
        Args:
            chat_target: 聊天对象名称
            message_record: 消息记录对象
            status: 处理状态 ('processed', 'failed', 'processing')
            error_msg: 错误信息（可选）
            accounting_status: 记账状态（可选）
            api_response_data: API响应数据（可选）
            accounting_record_id: 记账记录ID（可选）
        """
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                content_hash = hashlib.md5(message_record.content.encode('utf-8')).hexdigest()[:8]
                current_time = datetime.now().isoformat()
                
                # 序列化API响应数据
                api_response_json = json.dumps(api_response_data, ensure_ascii=False) if api_response_data else None
                
                # 尝试插入新记录
                try:
                    cursor.execute('''
                        INSERT INTO message_records 
                        (fingerprint, chat_target, message_id, content, content_hash, sender, 
                         time_context, sequence_position, status, created_at, updated_at, 
                         retry_count, last_error, processed_at, is_initial_mark, accounting_status, 
                         api_response_data, accounting_record_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 0, ?, ?, ?)
                    ''', (message_record.fingerprint, chat_target, message_record.message_id, 
                          message_record.content, content_hash, message_record.sender, 
                          message_record.time_context, message_record.sequence_position, status, 
                          current_time, current_time, error_msg, 
                          current_time if status == 'processed' else None, accounting_status, 
                          api_response_json, accounting_record_id))
                
                except sqlite3.IntegrityError:
                    # 记录已存在，更新状态
                    retry_increment = 1 if status == 'failed' else 0
                    cursor.execute('''
                        UPDATE message_records 
                        SET status = ?, updated_at = ?, last_error = ?, 
                            retry_count = retry_count + ?, 
                            processed_at = ?, accounting_status = ?, 
                            api_response_data = ?, accounting_record_id = ?
                        WHERE fingerprint = ?
                    ''', (status, current_time, error_msg, retry_increment,
                          current_time if status == 'processed' else None, accounting_status, 
                          api_response_json, accounting_record_id, message_record.fingerprint))
                
                conn.commit()
    
    def _monitor_loop(self, chat_target: str, stop_event: threading.Event):
        """
        新的监控循环
        
        Args:
            chat_target: 聊天对象名称
            stop_event: 停止事件
        """
        logger.info(f"开始监控循环: {chat_target}")
        
        # 获取检查间隔
        check_interval = self.get_check_interval(chat_target)
        
        while not stop_event.is_set():
            try:
                # 处理新消息
                results = self.process_new_messages(chat_target)
                
                # 输出处理结果
                if results:
                    logger.info(f"[{chat_target}] 处理结果: {len(results)}条")
                    for result in results:
                        logger.info(f"[{chat_target}] {result}")
                
                # 更新统计信息
                self.get_processing_statistics(chat_target)
                
                # 等待下次检查
                stop_event.wait(check_interval)
                
            except Exception as e:
                error_msg = f"监控循环异常: {str(e)}"
                logger.error(f"[{chat_target}] {error_msg}")
                self.error_occurred.emit(chat_target, error_msg)
                # 发生异常时等待更长时间再重试
                stop_event.wait(10)
        
        logger.info(f"监控循环已结束: {chat_target}")
    
    def get_check_interval(self, chat_target: str) -> int:
        """获取检查间隔"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT check_interval FROM chat_status 
                WHERE chat_target = ?
            ''', (chat_target,))
            result = cursor.fetchone()
            return result[0] if result else 5
    
    def cleanup_old_records(self, days_to_keep: int = 30):
        """
        清理旧的数据库记录
        
        Args:
            days_to_keep: 保留天数
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 清理旧的成功记录
                cursor.execute('''
                    DELETE FROM message_records 
                    WHERE status = 'processed' AND created_at < ?
                ''', (cutoff_date.isoformat(),))
                
                # 清理旧的日志记录
                cursor.execute('''
                    DELETE FROM processing_logs 
                    WHERE created_at < ?
                ''', (cutoff_date.isoformat(),))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"清理了 {deleted_count} 条旧记录")
    
    def get_all_chat_targets(self) -> List[str]:
        """获取所有聊天对象列表"""
        return list(self.monitored_chats.keys())
    
    def is_monitoring(self, chat_target: str) -> bool:
        """检查是否正在监控指定聊天对象"""
        return self.monitored_chats.get(chat_target, False)

    def parse_messages_to_records(self, chat_target: str, messages: List[Dict]) -> List[MessageRecord]:
        """
        解析API消息为消息记录对象（只处理friend类型的消息）
        
        Args:
            chat_target: 聊天对象名称
            messages: API返回的消息列表
            
        Returns:
            消息记录列表
        """
        records = []
        current_time_context = "unknown"
        sequence_position = 0
        
        total_messages = len(messages)
        friend_messages = 0
        time_messages = 0
        other_messages = 0
        
        logger.debug(f"开始解析 {total_messages} 条消息")
        
        for msg in messages:
            msg_type = msg.get('type', 'unknown')
            
            if msg_type == 'time':
                current_time_context = msg.get('content', 'unknown')
                time_messages += 1
                logger.debug(f"更新时间上下文: {current_time_context}")
                continue
                
            elif msg_type == 'friend':
                # 只处理friend类型的消息
                message_id = msg.get('id', f"unknown_{sequence_position}")
                content = msg.get('content', '')
                sender = msg.get('sender', '')
                
                # 跳过空消息
                if not content.strip():
                    logger.debug(f"跳过空消息: ID={message_id}")
                    continue
                
                # 创建消息记录
                record = MessageRecord(
                    message_id=message_id,
                    content=content,
                    sender=sender,
                    time_context=current_time_context,
                    sequence_position=sequence_position,
                    fingerprint=""  # 将在__post_init__中生成
                )
                
                records.append(record)
                friend_messages += 1
                sequence_position += 1
                
                logger.debug(f"解析friend消息: {sender} - {content[:30]}... (位置:{sequence_position-1}, ID:{message_id})")
            
            else:
                # 其他类型的消息（self, sys等）
                other_messages += 1
                logger.debug(f"跳过{msg_type}类型消息: {msg.get('content', '')[:30]}...")
        
        logger.info(f"消息解析完成: 总计{total_messages}条 -> friend:{friend_messages}条, time:{time_messages}条, 其他:{other_messages}条")
        return records
    
    def batch_save_initial_messages(self, chat_target: str, message_records: List[MessageRecord], is_first_time: bool = False):
        """
        批量保存初始消息为已读状态
        
        Args:
            chat_target: 聊天对象名称
            message_records: 消息记录列表
            is_first_time: 是否为首次初始化
        """
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                # 批量插入消息记录
                for record in message_records:
                    content_hash = hashlib.md5(record.content.encode('utf-8')).hexdigest()[:8]
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO message_records 
                        (fingerprint, chat_target, message_id, content, content_hash, sender, 
                         time_context, sequence_position, status, created_at, updated_at, 
                         processed_at, is_initial_mark, accounting_status, api_response_data, accounting_record_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'processed', ?, ?, ?, ?, 'initial', NULL, NULL)
                    ''', (record.fingerprint, chat_target, record.message_id, record.content,
                          content_hash, record.sender, record.time_context, record.sequence_position,
                          current_time, current_time, current_time, is_first_time))
                
                conn.commit()
                logger.info(f"批量保存了 {len(message_records)} 条初始消息为已读状态（记账状态：initial）")
    
    def mark_chat_as_initialized(self, chat_target: str, message_records: List[MessageRecord]):
        """
        标记聊天对象为已初始化
        
        Args:
            chat_target: 聊天对象名称
            message_records: 消息记录列表
        """
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                # 获取最后一条消息的信息
                last_record = message_records[-1] if message_records else None
                last_position = last_record.sequence_position if last_record else 0
                last_fingerprint = last_record.fingerprint if last_record else None
                
                cursor.execute('''
                    UPDATE chat_status 
                    SET is_initialized = 1, 
                        last_sequence_position = ?, 
                        last_message_fingerprint = ?,
                        initialization_time = ?,
                        updated_at = ?
                    WHERE chat_target = ?
                ''', (last_position, last_fingerprint, current_time, current_time, chat_target))
                
                conn.commit()
                logger.info(f"标记 {chat_target} 为已初始化，最后位置: {last_position}")
    
    def get_latest_db_messages(self, chat_target: str, limit: int = 5) -> List[MessageRecord]:
        """
        获取数据库中最新的消息记录
        
        Args:
            chat_target: 聊天对象名称
            limit: 获取数量限制
            
        Returns:
            消息记录列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT message_id, content, sender, time_context, sequence_position, fingerprint
                FROM message_records 
                WHERE chat_target = ? AND status = 'processed'
                ORDER BY sequence_position DESC 
                LIMIT ?
            ''', (chat_target, limit))
            
            records = []
            for row in cursor.fetchall():
                record = MessageRecord(
                    message_id=row[0],
                    content=row[1],
                    sender=row[2],
                    time_context=row[3],
                    sequence_position=row[4],
                    fingerprint=row[5]
                )
                records.append(record)
            
            # 按序列位置正序排列（最旧的在前）
            records.reverse()
            return records
    
    def find_sequence_match(self, db_sequence: List[MessageRecord], current_records: List[MessageRecord]) -> Optional[Tuple[int, float]]:
        """
        在当前消息中寻找数据库序列的匹配位置
        
        Args:
            db_sequence: 数据库中的消息序列
            current_records: 当前获取的消息记录
            
        Returns:
            Tuple[匹配位置, 匹配置信度] 或 None
        """
        if len(db_sequence) > len(current_records):
            return None
        
        # 提取序列特征用于匹配
        db_features = [(r.content, r.sender) for r in db_sequence]
        
        best_match = None
        best_confidence = 0.0
        
        # 滑动窗口匹配
        for i in range(len(current_records) - len(db_sequence) + 1):
            window = current_records[i:i+len(db_sequence)]
            current_features = [(r.content, r.sender) for r in window]
            
            # 计算匹配度
            matches = sum(1 for db_feat, curr_feat in zip(db_features, current_features) if db_feat == curr_feat)
            confidence = matches / len(db_features)
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = i
        
        # 只有当匹配度足够高时才返回结果
        if best_confidence >= 0.8:  # 至少80%匹配
            return best_match, best_confidence
        
        return None
    
    def identify_new_messages(self, chat_target: str, current_records: List[MessageRecord]) -> List[MessageRecord]:
        """
        识别新消息（改进版：基于内容而不是序列匹配）
        
        Args:
            chat_target: 聊天对象名称
            current_records: 当前获取的消息记录
            
        Returns:
            新消息记录列表
        """
        try:
            # 获取数据库中已处理的消息内容和哈希
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT content, content_hash, message_id, created_at 
                    FROM message_records 
                    WHERE chat_target = ? AND status = 'processed'
                    ORDER BY created_at DESC
                    LIMIT 100
                ''', (chat_target,))
                
                db_records = cursor.fetchall()
            
            if not db_records:
                # 如果数据库为空，所有消息都是新的（但这种情况不应该发生）
                logger.warning(f"{chat_target} 数据库中没有历史消息，所有消息都将被视为新消息")
                return current_records
            
            # 创建已处理消息的内容集合（用于快速查找）
            processed_contents = set()
            processed_content_hashes = set()
            processed_message_ids = set()
            
            for content, content_hash, message_id, created_at in db_records:
                processed_contents.add(content)
                if content_hash:
                    processed_content_hashes.add(content_hash)
                if message_id:
                    processed_message_ids.add(message_id)
            
            # 识别新消息
            new_messages = []
            for record in current_records:
                is_new = True
                
                # 1. 检查消息ID是否已存在（最直接的方式）
                if record.message_id in processed_message_ids:
                    is_new = False
                    logger.debug(f"消息ID已存在，跳过: {record.message_id}")
                    continue
                
                # 2. 检查内容是否完全相同
                if record.content in processed_contents:
                    is_new = False
                    logger.debug(f"消息内容已存在，跳过: {record.content[:30]}...")
                    continue
                
                # 3. 检查内容哈希是否相同
                content_hash = hashlib.md5(record.content.encode('utf-8')).hexdigest()[:8]
                if content_hash in processed_content_hashes:
                    is_new = False
                    logger.debug(f"消息内容哈希已存在，跳过: {record.content[:30]}...")
                    continue
                
                # 4. 如果通过了所有检查，认为是新消息
                if is_new:
                    new_messages.append(record)
                    logger.debug(f"识别为新消息: {record.content[:30]}... (ID: {record.message_id})")
            
            logger.info(f"通过内容对比识别到 {len(new_messages)} 条新消息")
            
            # 如果识别到的新消息数量异常多，可能是算法有问题，使用更保守的策略
            if len(new_messages) > 10:
                logger.warning(f"识别到的新消息数量异常多({len(new_messages)}条)，使用保守策略")
                # 只处理最新的几条消息
                new_messages = new_messages[-5:]
                logger.info(f"保守策略：只处理最新的 {len(new_messages)} 条消息")
            
            return new_messages
            
        except Exception as e:
            logger.error(f"识别新消息时发生异常: {e}")
            # 发生异常时，使用备用方案
            return self.identify_new_messages_by_fingerprint(chat_target, current_records)
    
    def identify_new_messages_by_fingerprint(self, chat_target: str, current_records: List[MessageRecord]) -> List[MessageRecord]:
        """
        通过指纹识别新消息（备用方案）
        
        Args:
            chat_target: 聊天对象名称
            current_records: 当前获取的消息记录
            
        Returns:
            新消息记录列表
        """
        # 获取数据库中所有已处理的消息指纹
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT fingerprint FROM message_records 
                WHERE chat_target = ? AND status = 'processed'
            ''', (chat_target,))
            
            processed_fingerprints = {row[0] for row in cursor.fetchall()}
        
        # 找出未处理的消息
        new_messages = []
        for record in current_records:
            if record.fingerprint not in processed_fingerprints:
                new_messages.append(record)
        
        logger.info(f"通过指纹匹配找到 {len(new_messages)} 条新消息")
        return new_messages
    
    def log_sequence_match(self, chat_target: str, matched_sequence: List[MessageRecord], 
                          match_position: int, confidence: float):
        """
        记录序列匹配历史
        
        Args:
            chat_target: 聊天对象名称
            matched_sequence: 匹配的序列
            match_position: 匹配位置
            confidence: 匹配置信度
        """
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 序列化匹配的序列信息
                sequence_info = json.dumps([
                    {"content": r.content[:50], "sender": r.sender, "position": r.sequence_position}
                    for r in matched_sequence
                ])
                
                cursor.execute('''
                    INSERT INTO sequence_match_history 
                    (chat_target, match_sequence, match_position, new_messages_count, match_confidence)
                    VALUES (?, ?, ?, ?, ?)
                ''', (chat_target, sequence_info, match_position, 0, confidence))  # new_messages_count稍后更新
                
                conn.commit() 
    
    def call_smart_accounting_api(self, message_content: str, sender_name: str = None) -> Tuple[bool, str, Dict, str]:
        """
        调用智能记账API

        Args:
            message_content: 消息内容
            sender_name: 发送者名称（优先使用sender_remark，如果没有则使用sender）

        Returns:
            Tuple[bool, str, Dict, str]: (是否成功, 响应消息, 原始响应数据, 记账记录ID)
        """
        try:
            accounting_config = self.get_accounting_config()
            
            # 检查配置是否完整
            server_url = accounting_config.get('server_url')
            token = accounting_config.get('token')
            account_book_id = accounting_config.get('account_book_id')
            
            if not all([server_url, token, account_book_id]):
                missing_configs = []
                if not server_url: missing_configs.append('server_url')
                if not token: missing_configs.append('token')
                if not account_book_id: missing_configs.append('account_book_id')
                
                error_msg = f"记账配置不完整，缺少: {', '.join(missing_configs)}"
                logger.error(error_msg)
                return False, error_msg, {}, ""
            
            # 构建API请求
            api_url = f"{server_url}/api/ai/smart-accounting/direct"
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
            
            if response.status_code in [200, 201]:  # 200 OK 或 201 Created 都表示成功
                result = response.json()
                logger.info(f"智能记账API响应: {result}")
                
                # 提取记账记录ID
                accounting_record_id = self.extract_accounting_record_id(result)
                
                # 检查是否有smartAccountingResult字段（新格式）
                if 'smartAccountingResult' in result:
                    # 格式化新格式的响应
                    formatted_msg = self.format_accounting_response(result)
                    logger.info(f"记账成功，格式化响应: {formatted_msg}")
                    return True, formatted_msg, result, accounting_record_id
                
                # 兼容旧格式
                elif result.get('success', False) or result.get('code') == 0 or response.status_code == 201:
                    success_msg = "✅ 记账成功！"
                    if 'data' in result:
                        # 提取记账详情
                        data_info = result['data']
                        if isinstance(data_info, dict):
                            amount = data_info.get('amount', '')
                            category = data_info.get('category', '')
                            if amount and category:
                                success_msg = f"✅ 记账成功！\n💰 {category} {amount}元"
                            elif amount:
                                success_msg = f"✅ 记账成功！\n💰 {amount}元"
                    
                    logger.info(success_msg)
                    return True, success_msg, result, accounting_record_id
                else:
                    error_msg = result.get('message', '记账失败')
                    logger.error(f"智能记账失败: {error_msg}")
                    return False, f"❌ 记账失败: {error_msg}", result, ""
            
            elif response.status_code == 401:
                error_msg = "记账服务认证失败，请检查token是否有效"
                logger.error(error_msg)
                return False, f"🔐 {error_msg}", {}, ""
            
            elif response.status_code == 404:
                error_msg = "记账服务API不存在，请检查server_url配置"
                logger.error(error_msg)
                return False, f"🔍 {error_msg}", {}, ""
            
            else:
                error_msg = f"记账服务返回错误: HTTP {response.status_code}"
                logger.error(error_msg)
                try:
                    error_detail = response.json().get('message', '')
                    if error_detail:
                        error_msg += f" - {error_detail}"
                except:
                    pass
                return False, f"⚠️ {error_msg}", {}, ""
                
        except requests.exceptions.Timeout:
            error_msg = "记账服务请求超时"
            logger.error(error_msg)
            return False, f"⏰ {error_msg}", {}, ""
            
        except requests.exceptions.ConnectionError:
            error_msg = "无法连接到记账服务，请检查server_url配置"
            logger.error(error_msg)
            return False, f"🌐 {error_msg}", {}, ""
            
        except Exception as e:
            error_msg = f"调用智能记账API异常: {str(e)}"
            logger.error(error_msg)
            return False, f"💥 {error_msg}", {}, ""

    def extract_accounting_record_id(self, api_response: Dict) -> str:
        """
        从API响应中提取记账记录ID
        
        Args:
            api_response: API响应数据
            
        Returns:
            记账记录ID，如果没有找到则返回空字符串
        """
        try:
            # 尝试多种可能的ID字段路径
            possible_paths = [
                # 新格式路径
                ['smartAccountingResult', 'data', 'id'],
                ['smartAccountingResult', 'id'],
                # 旧格式路径
                ['data', 'id'],
                ['id'],
                # 其他可能的路径
                ['result', 'id'],
                ['record', 'id'],
                ['recordId'],
                ['accounting_id'],
                ['transactionId']
            ]
            
            for path in possible_paths:
                current = api_response
                try:
                    for key in path:
                        current = current[key]
                    if current and str(current).strip():
                        logger.debug(f"找到记账记录ID: {current} (路径: {' -> '.join(path)})")
                        return str(current)
                except (KeyError, TypeError):
                    continue
            
            logger.debug("未找到记账记录ID")
            return ""
            
        except Exception as e:
            logger.error(f"提取记账记录ID时发生异常: {e}")
            return ""
    
    def format_accounting_response(self, result: Dict) -> str:
        """
        格式化智能记账API响应
        
        Args:
            result: API响应结果
            
        Returns:
            格式化后的消息字符串
        """
        try:
            # 提取smartAccountingResult中的信息
            smart_result = result.get('smartAccountingResult', {})
            
            # 如果有data字段，优先使用data中的信息
            if 'data' in smart_result:
                data = smart_result['data']
            else:
                data = smart_result
            
            # 基本信息 - 兼容多种字段名称
            amount = data.get('amount', result.get('amount', ''))
            note = data.get('detail', data.get('note', result.get('description', '')))
            category_name = data.get('category', data.get('categoryName', ''))
            account_type = data.get('type', result.get('type', 'EXPENSE'))
            date = data.get('date', result.get('date', ''))
            confidence = data.get('confidence', 0)
            
            # 预算信息
            budget_name = data.get('budget', data.get('budgetName', ''))
            budget_owner = data.get('budgetOwner', data.get('budgetOwnerName', ''))
            
            # 账本信息
            account_name = data.get('account', data.get('accountName', ''))
            
            # 格式化日期
            formatted_date = self.format_date(date)
            
            # 获取类型图标和文字
            type_info = self.get_type_icon_and_text(account_type)
            
            # 获取分类图标
            category_icon = self.get_category_icon(category_name)
            
            # 构建格式化消息
            message_lines = [
                "✅ 记账成功！",
                f"📝 明细：{note}",
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
                
        except Exception as e:
            logger.error(f"格式化记账响应失败: {e}")
            # 返回简化版本
            amount = result.get('amount', '')
            description = result.get('description', '')
            return f"✅ 记账成功！\n💰 {description} {amount}元"
    
    def get_type_icon_and_text(self, account_type: str) -> Dict[str, str]:
        """
        根据账目类型获取图标和文字
        
        Args:
            account_type: 账目类型
            
        Returns:
            包含图标和文字的字典
        """
        type_mapping = {
            # 英文类型
            'EXPENSE': {'icon': '💸', 'text': '支出'},
            'INCOME': {'icon': '💰', 'text': '收入'},
            'TRANSFER': {'icon': '🔄', 'text': '转账'},
            'REFUND': {'icon': '↩️', 'text': '退款'},
            'INVESTMENT': {'icon': '📈', 'text': '投资'},
            'LOAN': {'icon': '🏦', 'text': '借贷'},
            # 中文类型
            '支出': {'icon': '💸', 'text': '支出'},
            '收入': {'icon': '💰', 'text': '收入'},
            '转账': {'icon': '🔄', 'text': '转账'},
            '退款': {'icon': '↩️', 'text': '退款'},
            '投资': {'icon': '📈', 'text': '投资'},
            '借贷': {'icon': '🏦', 'text': '借贷'}
        }
        
        return type_mapping.get(account_type.upper(), type_mapping.get(account_type, {'icon': '📝', 'text': '其他'}))
    
    def get_category_icon(self, category_name: str) -> str:
        """
        根据分类名称获取对应图标
        
        Args:
            category_name: 分类名称
            
        Returns:
            对应的图标
        """
        category_icons = {
            # 餐饮相关
            '餐饮': '🍽️',
            '早餐': '🥐',
            '早饭': '🥐',
            '午餐': '🍱',
            '午饭': '🍱',
            '晚餐': '🍽️',
            '晚饭': '🍽️',
            '夜宵': '🌙',
            '零食': '🍿',
            '饮料': '🥤',
            '咖啡': '☕',
            '奶茶': '🧋',
            '酒水': '🍷',
            '水果': '🍎',
            '蔬菜': '🥬',
            '肉类': '🥩',
            '海鲜': '🦐',
            
            # 交通相关
            '交通': '🚗',
            '打车': '🚕',
            '出租车': '🚕',
            '网约车': '🚕',
            '公交': '🚌',
            '公交车': '🚌',
            '地铁': '🚇',
            '火车': '🚄',
            '高铁': '🚄',
            '飞机': '✈️',
            '航班': '✈️',
            '加油': '⛽',
            '油费': '⛽',
            '停车': '🅿️',
            '停车费': '🅿️',
            '过路费': '🛣️',
            '车票': '🎫',
            '机票': '🎫',
            
            # 购物相关
            '购物': '🛍️',
            '服装': '👕',
            '衣服': '👕',
            '鞋子': '👟',
            '包包': '👜',
            '化妆品': '💄',
            '护肤品': '🧴',
            '日用品': '🧴',
            '生活用品': '🧴',
            '超市': '🛒',
            '电子产品': '📱',
            '手机': '📱',
            '电脑': '💻',
            '数码': '📱',
            '书籍': '📚',
            '文具': '✏️',
            '家具': '🪑',
            '家电': '📺',
            '礼品': '🎁',
            
            # 娱乐相关
            '娱乐': '🎮',
            '电影': '🎬',
            '游戏': '🎮',
            '旅游': '🏖️',
            '旅行': '🏖️',
            '运动': '⚽',
            '健身': '💪',
            '游泳': '🏊',
            'KTV': '🎤',
            '唱歌': '🎤',
            '音乐': '🎵',
            '演出': '🎭',
            '展览': '🖼️',
            
            # 生活相关
            '住房': '🏠',
            '房租': '🏠',
            '租金': '🏠',
            '房贷': '🏠',
            '水电': '💡',
            '电费': '💡',
            '水费': '💧',
            '燃气费': '🔥',
            '网费': '📶',
            '宽带': '📶',
            '话费': '📞',
            '手机费': '📞',
            '物业费': '🏢',
            '维修': '🔧',
            
            # 医疗健康
            '医疗': '🏥',
            '看病': '🏥',
            '药品': '💊',
            '体检': '🩺',
            '牙科': '🦷',
            '眼科': '👁️',
            '保健': '💊',
            
            # 教育学习
            '教育': '🎓',
            '学费': '🎓',
            '培训': '📖',
            '课程': '📖',
            '辅导': '👨‍🏫',
            
            # 保险理财
            '保险': '🛡️',
            '理财': '💎',
            '基金': '📊',
            '股票': '📈',
            '投资': '📈',
            '存款': '🏦',
            '贷款': '🏦',
            
            # 收入相关
            '工资': '💼',
            '薪水': '💼',
            '奖金': '🎁',
            '津贴': '💰',
            '补贴': '💰',
            '兼职': '👔',
            '外快': '💵',
            '分红': '📈',
            '利息': '🏦',
            
            # 社交人情
            '红包': '🧧',
            '礼金': '🧧',
            '请客': '🍽️',
            '聚餐': '🍽️',
            '份子钱': '💝',
            '捐赠': '❤️',
            '慈善': '❤️',
            
            # 其他
            '转账': '🔄',
            '提现': '💳',
            '充值': '💳',
            '退款': '↩️',
            '罚款': '⚠️',
            '税费': '📋',
            '手续费': '💳',
            '其他': '📝',
            '杂费': '📝',
        }
        
        # 精确匹配
        if category_name in category_icons:
            return category_icons[category_name]
        
        # 模糊匹配
        for key, icon in category_icons.items():
            if key in category_name or category_name in key:
                return icon
        
        # 默认图标
        return '📝'
    
    def format_date(self, date_str: str) -> str:
        """
        格式化日期字符串
        
        Args:
            date_str: 原始日期字符串
            
        Returns:
            格式化后的日期字符串
        """
        try:
            if not date_str:
                return datetime.now().strftime('%Y-%m-%d')
            
            # 处理ISO格式日期
            if 'T' in date_str:
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return date_obj.strftime('%Y-%m-%d')
            
            # 如果已经是YYYY-MM-DD格式
            if len(date_str) == 10 and date_str.count('-') == 2:
                return date_str
            
            return date_str
            
        except Exception as e:
            logger.warning(f"日期格式化失败: {e}")
            return datetime.now().strftime('%Y-%m-%d')
    
    def send_reply_to_wechat(self, chat_target: str, message: str) -> bool:
        """
        发送回复到微信
        
        Args:
            chat_target: 聊天对象名称
            message: 回复内容
            
        Returns:
            True表示发送成功，False表示发送失败
        """
        try:
            send_url = f"{self.api_base_url}/api/chat-window/message/send"
            data = {
                "who": chat_target,
                "message": message
            }
            
            response = requests.post(send_url, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result['code'] == 0:
                logger.info(f"回复发送成功: {message}")
                return True
            else:
                logger.error(f"回复发送失败: {result['message']}")
                return False
                
        except Exception as e:
            logger.error(f"发送回复异常: {e}")
            return False
    
    def log_processing_action(self, chat_target: str, fingerprint: str, action: str, status: str, 
                             message: str = None, error_details: str = None, 
                             processing_time_ms: int = None):
        """
        记录处理日志
        
        Args:
            chat_target: 聊天对象名称
            fingerprint: 消息指纹
            action: 操作类型
            status: 操作状态
            message: 日志消息
            error_details: 错误详情
            processing_time_ms: 处理耗时（毫秒）
        """
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO processing_logs 
                    (chat_target, fingerprint, action, status, message, error_details, processing_time_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (chat_target, fingerprint, action, status, message, error_details, processing_time_ms))
                conn.commit()
    
    def get_processing_statistics(self, chat_target: str) -> Dict:
        """
        获取处理统计信息
        
        Args:
            chat_target: 聊天对象名称
            
        Returns:
            统计信息字典
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 总处理消息数
            cursor.execute('''
                SELECT COUNT(*) FROM message_records 
                WHERE chat_target = ?
            ''', (chat_target,))
            total_processed = cursor.fetchone()[0]
            
            # 成功处理数
            cursor.execute('''
                SELECT COUNT(*) FROM message_records 
                WHERE chat_target = ? AND status = 'processed'
            ''', (chat_target,))
            success_processed = cursor.fetchone()[0]
            
            # 失败处理数
            cursor.execute('''
                SELECT COUNT(*) FROM message_records 
                WHERE chat_target = ? AND status = 'failed'
            ''', (chat_target,))
            failed_processed = cursor.fetchone()[0]
            
            # 记账成功数
            cursor.execute('''
                SELECT COUNT(*) FROM message_records 
                WHERE chat_target = ? AND accounting_status = 'success'
            ''', (chat_target,))
            accounting_success = cursor.fetchone()[0]
            
            # 记账失败数
            cursor.execute('''
                SELECT COUNT(*) FROM message_records 
                WHERE chat_target = ? AND accounting_status = 'failed'
            ''', (chat_target,))
            accounting_failed = cursor.fetchone()[0]
            
            # 无关消息数
            cursor.execute('''
                SELECT COUNT(*) FROM message_records 
                WHERE chat_target = ? AND accounting_status = 'nothing'
            ''', (chat_target,))
            accounting_nothing = cursor.fetchone()[0]
            
            # 最近处理时间
            cursor.execute('''
                SELECT MAX(processed_at) FROM message_records 
                WHERE chat_target = ? AND status = 'processed'
            ''', (chat_target,))
            last_processed_time = cursor.fetchone()[0]
            
            statistics = {
                'chat_target': chat_target,
                'total_processed': total_processed,
                'success_processed': success_processed,
                'failed_processed': failed_processed,
                'accounting_success': accounting_success,
                'accounting_failed': accounting_failed,
                'accounting_nothing': accounting_nothing,
                'last_processed_time': last_processed_time,
                'success_rate': (success_processed / total_processed * 100) if total_processed > 0 else 0,
                'accounting_success_rate': (accounting_success / total_processed * 100) if total_processed > 0 else 0
            }
            
            # 发出统计信息更新信号
            self.statistics_updated.emit(chat_target, statistics)
            
            return statistics
    
    def reset_chat_initialization(self, chat_target: str) -> bool:
        """
        重置聊天对象的初始化状态（用于重新初始化）
        
        Args:
            chat_target: 聊天对象名称
            
        Returns:
            True表示重置成功，False表示重置失败
        """
        try:
            with self.db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # 重置初始化状态
                    cursor.execute('''
                        UPDATE chat_status 
                        SET is_initialized = 0, 
                            last_sequence_position = 0, 
                            last_message_fingerprint = NULL,
                            initialization_time = NULL,
                            updated_at = ?
                        WHERE chat_target = ?
                    ''', (datetime.now().isoformat(), chat_target))
                    
                    # 删除该聊天对象的所有消息记录
                    cursor.execute('''
                        DELETE FROM message_records 
                        WHERE chat_target = ?
                    ''', (chat_target,))
                    
                    conn.commit()
                    
                    logger.info(f"成功重置 {chat_target} 的初始化状态")
                    return True
                
        except Exception as e:
            logger.error(f"重置 {chat_target} 初始化状态失败: {e}")
        return False
    
    # 兼容性方法（保持向后兼容）
    def mark_existing_messages_as_processed(self, chat_target: str):
        """将现有消息标记为已处理（已弃用）- 使用initialize_chat_with_retry替代"""
        logger.warning("mark_existing_messages_as_processed已弃用，请使用initialize_chat_with_retry")
        return self.initialize_chat_with_retry(chat_target)
    
    def generate_message_fingerprint(self, message: Dict, time_context: str) -> str:
        """
        生成消息指纹（兼容性方法）
        
        Args:
            message: 消息对象
            time_context: 时间上下文
            
        Returns:
            消息指纹字符串
        """
        # 为了兼容性，保留这个方法，但使用新的MessageRecord方式
        message_id = message.get('id', f"unknown_{message.get('_batch_index', 0)}")
        content = message.get('content', '')
        sender = message.get('sender', '')
        
        record = MessageRecord(
            message_id=message_id,
            content=content,
            sender=sender,
            time_context=time_context,
            sequence_position=message.get('_batch_index', 0),
            fingerprint=""
        )
        
        return record.fingerprint 

    def get_all_db_messages(self, chat_target: str) -> List[MessageRecord]:
        """
        获取数据库中所有消息记录
        
        Args:
            chat_target: 聊天对象名称
            
        Returns:
            消息记录列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT message_id, content, sender, time_context, sequence_position, fingerprint
                FROM message_records 
                WHERE chat_target = ? AND status = 'processed'
                ORDER BY sequence_position ASC
            ''', (chat_target,))
            
            records = []
            for row in cursor.fetchall():
                record = MessageRecord(
                    message_id=row[0],
                    content=row[1],
                    sender=row[2],
                    time_context=row[3],
                    sequence_position=row[4],
                    fingerprint=row[5]
                )
                records.append(record)
            
            return records
    
    def compare_and_merge_messages(self, db_records: List[MessageRecord], current_records: List[MessageRecord]) -> Dict:
        """
        对比数据库消息和当前消息，执行合并逻辑
        
        Args:
            db_records: 数据库中的消息记录
            current_records: 当前获取的消息记录
            
        Returns:
            合并结果字典
        """
        logger.info(f"开始对比合并：数据库 {len(db_records)} 条，当前 {len(current_records)} 条")
        
        # 提取数据库消息的内容和发送者序列（用于匹配）
        db_content_sequence = [(r.content, r.sender) for r in db_records]
        current_content_sequence = [(r.content, r.sender) for r in current_records]
        
        # 寻找最佳匹配点
        best_match = self.find_best_sequence_alignment(db_content_sequence, current_content_sequence)
        
        if not best_match:
            logger.warning("无法找到合适的序列匹配点，将所有当前消息视为新消息")
            return {
                'updated_messages': [],
                'new_messages': current_records,
                'obsolete_messages': db_records
            }
        
        db_start, current_start, match_length = best_match
        logger.info(f"找到匹配：数据库位置{db_start}，当前位置{current_start}，匹配长度{match_length}")
        
        # 分析结果
        updated_messages = []  # 需要更新ID的消息
        new_messages = []      # 全新的消息
        
        # 1. 处理匹配部分：更新消息ID
        for i in range(match_length):
            db_record = db_records[db_start + i]
            current_record = current_records[current_start + i]
            
            if db_record.message_id != current_record.message_id:
                # 需要更新ID
                updated_record = MessageRecord(
                    message_id=current_record.message_id,  # 使用新ID
                    content=db_record.content,
                    sender=db_record.sender,
                    time_context=db_record.time_context,
                    sequence_position=current_record.sequence_position,  # 使用新位置
                    fingerprint=""  # 将重新生成
                )
                updated_messages.append((db_record.fingerprint, updated_record))
                logger.debug(f"更新消息ID: {db_record.message_id} -> {current_record.message_id}")
        
        # 2. 处理新消息：匹配点之后的消息
        new_start_position = current_start + match_length
        for i in range(new_start_position, len(current_records)):
            new_messages.append(current_records[i])
            logger.debug(f"新消息: {current_records[i].content[:30]}... (ID: {current_records[i].message_id})")
        
        # 3. 处理过期消息：不在当前队列中的数据库消息
        current_content_set = set(current_content_sequence)
        obsolete_messages = []
        for db_record in db_records:
            if (db_record.content, db_record.sender) not in current_content_set:
                obsolete_messages.append(db_record)
        
        logger.info(f"对比结果：更新{len(updated_messages)}条，新增{len(new_messages)}条，过期{len(obsolete_messages)}条")
        
        return {
            'updated_messages': updated_messages,
            'new_messages': new_messages,
            'obsolete_messages': obsolete_messages,
            'match_info': {
                'db_start': db_start,
                'current_start': current_start,
                'match_length': match_length
            }
        }
    
    def find_best_sequence_alignment(self, db_sequence: List[Tuple], current_sequence: List[Tuple]) -> Optional[Tuple[int, int, int]]:
        """
        寻找两个序列的最佳对齐匹配（优化版，支持超时）
        
        Args:
            db_sequence: 数据库消息序列 [(content, sender), ...]
            current_sequence: 当前消息序列 [(content, sender), ...]
            
        Returns:
            Tuple[db_start, current_start, match_length] 或 None
        """
        import time
        start_time = time.time()
        timeout = 10  # 10秒超时
        
        if not db_sequence or not current_sequence:
            return None
        
        logger.debug(f"开始序列对齐：数据库{len(db_sequence)}条，当前{len(current_sequence)}条")
        
        best_match = None
        best_score = 0
        
        # 限制搜索范围，避免性能问题
        max_possible_length = min(len(db_sequence), len(current_sequence), 20)  # 最多匹配20条
        min_match_length = min(3, max_possible_length)  # 最少匹配3条
        
        # 优先尝试从末尾匹配（最新消息更可能匹配）
        for match_length in range(max_possible_length, min_match_length - 1, -1):
            # 检查超时
            if time.time() - start_time > timeout:
                logger.warning(f"序列对齐超时，使用当前最佳匹配")
                break
            
            # 优先从数据库末尾开始匹配
            db_search_range = min(10, len(db_sequence) - match_length + 1)  # 限制搜索范围
            for i in range(db_search_range):
                db_start = len(db_sequence) - match_length - i
                if db_start < 0:
                    break
                    
                db_segment = db_sequence[db_start:db_start + match_length]
                
                # 优先从当前序列末尾开始匹配
                current_search_range = min(10, len(current_sequence) - match_length + 1)
                for j in range(current_search_range):
                    current_start = len(current_sequence) - match_length - j
                    if current_start < 0:
                        break
                        
                    current_segment = current_sequence[current_start:current_start + match_length]
                    
                    # 计算匹配度
                    matches = sum(1 for db_item, curr_item in zip(db_segment, current_segment) if db_item == curr_item)
                    score = matches / match_length
                    
                    # 如果是完全匹配，立即返回
                    if score == 1.0:
                        logger.info(f"找到完全匹配：长度{match_length}，数据库位置{db_start}，当前位置{current_start}")
                        return (db_start, current_start, match_length)
                    
                    # 记录最佳部分匹配
                    if score > best_score and score >= 0.8:  # 至少80%匹配
                        best_score = score
                        best_match = (db_start, current_start, match_length)
                        logger.debug(f"更新最佳匹配：得分{score:.2f}，长度{match_length}")
        
        if best_match:
            logger.info(f"找到最佳匹配：得分{best_score:.2f}，位置{best_match}")
        else:
            logger.warning("未找到合适的序列匹配")
        
        elapsed_time = time.time() - start_time
        logger.debug(f"序列对齐耗时：{elapsed_time:.2f}秒")
        
        return best_match
    
    def apply_merge_result(self, chat_target: str, merge_result: Dict):
        """
        应用合并结果到数据库
        
        Args:
            chat_target: 聊天对象名称
            merge_result: 合并结果
        """
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                
                # 1. 更新消息ID
                for old_fingerprint, updated_record in merge_result['updated_messages']:
                    content_hash = hashlib.md5(updated_record.content.encode('utf-8')).hexdigest()[:8]
                    
                    cursor.execute('''
                        UPDATE message_records 
                        SET message_id = ?, 
                            fingerprint = ?,
                            sequence_position = ?,
                            updated_at = ?
                        WHERE fingerprint = ? AND chat_target = ?
                    ''', (updated_record.message_id, updated_record.fingerprint, 
                          updated_record.sequence_position, current_time, 
                          old_fingerprint, chat_target))
                
                # 2. 添加新消息（标记为待处理，记账状态为pending）
                for new_record in merge_result['new_messages']:
                    content_hash = hashlib.md5(new_record.content.encode('utf-8')).hexdigest()[:8]
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO message_records 
                        (fingerprint, chat_target, message_id, content, content_hash, sender, 
                         time_context, sequence_position, status, created_at, updated_at, 
                         is_initial_mark, accounting_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'processing', ?, ?, 0, 'pending')
                    ''', (new_record.fingerprint, chat_target, new_record.message_id, 
                          new_record.content, content_hash, new_record.sender, 
                          new_record.time_context, new_record.sequence_position,
                          current_time, current_time))
                
                # 3. 标记过期消息（可选：保留或删除）
                # 这里选择保留，但可以添加标记
                for obsolete_record in merge_result['obsolete_messages']:
                    cursor.execute('''
                        UPDATE message_records 
                        SET updated_at = ?
                        WHERE fingerprint = ? AND chat_target = ?
                    ''', (current_time, obsolete_record.fingerprint, chat_target))
                
                conn.commit()
                
                # 4. 记录合并历史（暂时注释掉，避免表不存在的问题）
                # self.log_merge_history(chat_target, merge_result)
                
                logger.info(f"成功应用合并结果: 更新{len(merge_result['updated_messages'])}条, 新增{len(merge_result['new_messages'])}条（记账状态：pending）")
    
    def log_merge_history(self, chat_target: str, merge_result: Dict):
        """
        记录合并历史
        
        Args:
            chat_target: 聊天对象名称
            merge_result: 合并结果
        """
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                match_info = merge_result.get('match_info', {})
                sequence_info = json.dumps({
                    'updated_count': len(merge_result['updated_messages']),
                    'new_count': len(merge_result['new_messages']),
                    'obsolete_count': len(merge_result['obsolete_messages']),
                    'match_info': match_info
                })
                
                cursor.execute('''
                    INSERT INTO sequence_match_history 
                    (chat_target, match_sequence, match_position, new_messages_count, match_confidence)
                    VALUES (?, ?, ?, ?, ?)
                ''', (chat_target, sequence_info, match_info.get('current_start', -1), 
                      len(merge_result['new_messages']), 1.0))
                
                conn.commit()
    
    def identify_new_messages_by_fingerprint_v2(self, chat_target: str, current_records: List[MessageRecord]) -> List[MessageRecord]:
        """
        通过指纹识别新消息（监听过程中使用：内容+ID）
        
        Args:
            chat_target: 聊天对象名称
            current_records: 当前获取的消息记录
            
        Returns:
            新消息记录列表
        """
        # 获取数据库中所有已处理的消息指纹（内容+ID）
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT fingerprint FROM message_records 
                WHERE chat_target = ? AND status = 'processed'
            ''', (chat_target,))
            
            processed_fingerprints = {row[0] for row in cursor.fetchall()}
        
        # 找出未处理的消息（基于内容+ID的指纹）
        new_messages = []
        for record in current_records:
            if record.fingerprint not in processed_fingerprints:
                new_messages.append(record)
                logger.debug(f"发现新消息: {record.content[:30]}... (ID: {record.message_id})")
        
        logger.info(f"通过指纹匹配找到 {len(new_messages)} 条新消息")
        return new_messages
    
    def identify_new_messages(self, chat_target: str, current_records: List[MessageRecord]) -> List[MessageRecord]:
        """
        识别新消息（监听过程中使用）
        
        Args:
            chat_target: 聊天对象名称
            current_records: 当前获取的消息记录
            
        Returns:
            新消息记录列表
        """
        # 在监听过程中，直接使用指纹去重（内容+ID）
        return self.identify_new_messages_by_fingerprint_v2(chat_target, current_records) 
    
    def ensure_chat_in_listen_list(self, chat_target: str):
        """
        确保聊天对象在监听列表中（兼容性方法）
        
        Args:
            chat_target: 聊天对象名称
        """
        try:
            self._auto_add_to_listen_list(chat_target)
        except Exception as e:
            logger.warning(f"确保 {chat_target} 在监听列表中失败: {e}")
            # 不抛出异常，保持原有行为
    
    def get_existing_accounting_record_id(self, chat_target: str, fingerprint: str) -> str:
        """
        获取已存在的记账记录ID
        
        Args:
            chat_target: 聊天对象名称
            fingerprint: 消息指纹
            
        Returns:
            记账记录ID，如果不存在则返回空字符串
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT accounting_record_id FROM message_records 
                    WHERE chat_target = ? AND fingerprint = ? AND accounting_record_id IS NOT NULL AND accounting_record_id != ''
                ''', (chat_target, fingerprint))
                
                result = cursor.fetchone()
                return result[0] if result else ""
                
        except Exception as e:
            logger.error(f"获取已存在的记账记录ID时发生异常: {e}")
            return ""