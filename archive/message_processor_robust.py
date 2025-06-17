"""
可靠的微信消息处理器
基于会话管理和多重标识的消息去重机制
解决连续相同消息、历史消息误处理等问题
"""

import time
import hashlib
import sqlite3
import threading
import requests
import logging
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

@dataclass
class MessageSessionManager:
    """消息监听会话管理器"""
    
    def __init__(self):
        self.current_session_id: Optional[str] = None
        self.session_start_time: Optional[datetime] = None
        self.processed_message_ids: Set[str] = set()  # 当前会话中已处理的消息ID
        self.processed_content_fingerprints: Set[str] = set()  # 内容指纹备用
        
    def start_new_session(self, chat_target: str) -> str:
        """开始新的监听会话"""
        self.current_session_id = f"{chat_target}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
        self.session_start_time = datetime.now()
        self.processed_message_ids.clear()
        self.processed_content_fingerprints.clear()
        logger.info(f"开始新的监听会话: {self.current_session_id}")
        return self.current_session_id
    
    def is_message_processed_in_session(self, message_id: str, content_fingerprint: str) -> bool:
        """检查消息是否在当前会话中已处理"""
        return (message_id in self.processed_message_ids or 
                content_fingerprint in self.processed_content_fingerprints)
    
    def mark_message_processed(self, message_id: str, content_fingerprint: str):
        """标记消息为已处理"""
        self.processed_message_ids.add(message_id)
        self.processed_content_fingerprints.add(content_fingerprint)

class RobustMessageProcessor(QObject):
    """
    可靠的微信消息处理器
    
    功能特点：
    1. 基于会话管理的消息去重
    2. 多重标识机制（消息ID + 内容指纹）
    3. 历史消息防护
    4. 连续相同消息处理
    5. 消息ID变化检测和恢复
    """
    
    # 信号定义
    message_processed = pyqtSignal(str, str, bool, str)  # 聊天对象, 消息内容, 成功状态, 结果消息
    status_changed = pyqtSignal(str, bool)  # 聊天对象, 监控状态
    error_occurred = pyqtSignal(str, str)  # 聊天对象, 错误信息
    statistics_updated = pyqtSignal(str, dict)  # 聊天对象, 统计信息
    
    def __init__(self, api_base_url: str, api_key: str, db_path: str = "message_processor_robust.db", config_path: str = None):
        super().__init__()
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.db_path = db_path
        self.config_path = config_path or "C:/Code/wxauto_for_zhiweijz/data/api/config/user_config.json"
        
        # 会话管理
        self.session_managers: Dict[str, MessageSessionManager] = {}
        self.monitored_chats: Dict[str, bool] = {}  # 聊天对象 -> 是否正在监控
        
        # 线程管理
        self.monitor_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        
        # 数据库锁
        self.db_lock = threading.Lock()
        
        # API请求头
        self.headers = {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        # 初始化数据库
        self.init_database()
        
        # 加载用户配置
        self.user_config = self.load_user_config()
    
    def load_user_config(self) -> Dict:
        """加载用户配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"成功加载用户配置: {self.config_path}")
                    return config
            else:
                logger.warning(f"用户配置文件不存在: {self.config_path}")
                return {}
        except Exception as e:
            logger.error(f"加载用户配置失败: {e}")
            return {}
    
    def get_accounting_config(self) -> Dict:
        """获取记账配置"""
        return self.user_config
    
    def init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建可靠的消息状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_status_robust (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    content_fingerprint TEXT NOT NULL,
                    session_fingerprint TEXT UNIQUE NOT NULL,
                    chat_target TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    time_window TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    error_msg TEXT,
                    processed_at TIMESTAMP
                )
            ''')
            
            # 创建聊天配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_config_robust (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_target TEXT UNIQUE NOT NULL,
                    api_base_url TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    check_interval INTEGER DEFAULT 5,
                    max_retries INTEGER DEFAULT 3,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建处理日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processing_logs_robust (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_target TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    session_fingerprint TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    error_details TEXT,
                    processing_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_robust_session_fingerprint ON message_status_robust(session_fingerprint)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_robust_message_id ON message_status_robust(message_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_robust_content_fingerprint ON message_status_robust(content_fingerprint)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_robust_chat_target ON message_status_robust(chat_target)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_robust_session_id ON message_status_robust(session_id)')
            
            conn.commit()
            logger.info("可靠消息处理器数据库初始化完成")
    
    def generate_robust_message_fingerprint(self, message: Dict, session_id: str) -> Dict[str, str]:
        """
        生成可靠的消息指纹
        
        Returns:
            包含多种标识的字典
        """
        # 1. 主要标识：消息ID（在监听期间稳定）
        message_id = message.get('id', '')
        
        # 2. 内容指纹：发送者 + 内容哈希 + 时间窗口
        content = message.get('content', '')
        sender = message.get('sender', '')
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
        
        # 3. 时间窗口：使用5分钟时间窗口，减少时间精度依赖
        now = datetime.now()
        time_window = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
        time_window_str = time_window.strftime('%Y-%m-%d %H:%M')
        
        # 4. 处理连续相同消息的序列号
        seq_num = message.get('_consecutive_seq', '')
        seq_suffix = f"|seq_{seq_num}" if seq_num != '' else ""
        
        content_fingerprint = f"{sender}|{content_hash}|{time_window_str}{seq_suffix}"
        
        # 5. 会话指纹：结合会话ID的唯一标识
        session_fingerprint = f"{session_id}|{message_id}|{content_fingerprint}"
        
        return {
            'message_id': message_id,
            'content_fingerprint': content_fingerprint,
            'session_fingerprint': session_fingerprint,
            'time_window': time_window_str
        }
    
    def add_chat_target(self, chat_target: str, check_interval: int = 5, max_retries: int = 3) -> bool:
        """添加聊天对象到监控列表"""
        if chat_target in self.monitored_chats:
            logger.warning(f"聊天对象 {chat_target} 已存在")
            return False
        
        # 添加到本地监控列表
        self.monitored_chats[chat_target] = False
        
        # 保存配置到数据库
        self.save_chat_config(chat_target, check_interval, max_retries)
        
        logger.info(f"已添加聊天对象: {chat_target}")
        return True
    
    def save_chat_config(self, chat_target: str, check_interval: int, max_retries: int):
        """保存聊天配置到数据库"""
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 确保表存在（对于内存数据库很重要）
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS chat_config_robust (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_target TEXT UNIQUE NOT NULL,
                        api_base_url TEXT NOT NULL,
                        api_key TEXT NOT NULL,
                        check_interval INTEGER DEFAULT 5,
                        max_retries INTEGER DEFAULT 3,
                        enabled BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                current_time = datetime.now().isoformat()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO chat_config_robust 
                    (chat_target, api_base_url, api_key, check_interval, max_retries,
                     enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ''', (chat_target, self.api_base_url, self.api_key, check_interval, 
                      max_retries, current_time, current_time))
                
                conn.commit()
                logger.debug(f"保存聊天配置: {chat_target}")
    
    def start_monitoring_with_session(self, chat_target: str) -> bool:
        """开始监控并创建新会话"""
        if chat_target not in self.monitored_chats:
            logger.error(f"聊天对象 {chat_target} 不在监控列表中")
            return False
        
        if self.monitored_chats[chat_target]:
            logger.warning(f"聊天对象 {chat_target} 已在监控中")
            return False
        
        try:
            # 1. 创建新的监听会话
            if chat_target not in self.session_managers:
                self.session_managers[chat_target] = MessageSessionManager()
            
            session_manager = self.session_managers[chat_target]
            session_id = session_manager.start_new_session(chat_target)
            
            # 2. 确保聊天对象在API监听列表中（这是唯一的外部调用）
            logger.info(f"添加 {chat_target} 到API监听列表...")
            self.ensure_chat_in_listen_list(chat_target)
            
            # 3. 创建停止事件并启动监控线程
            stop_event = threading.Event()
            self.stop_events[chat_target] = stop_event
            
            monitor_thread = threading.Thread(
                target=self._monitor_loop_robust,
                args=(chat_target, session_id, stop_event),
                daemon=True,
                name=f"RobustMonitor-{chat_target}"
            )
            monitor_thread.start()
            self.monitor_threads[chat_target] = monitor_thread
            
            # 4. 更新状态
            self.monitored_chats[chat_target] = True
            self.status_changed.emit(chat_target, True)
            
            logger.info(f"成功启动监控: {chat_target} (会话: {session_id})")
            return True
            
        except Exception as e:
            error_msg = f"启动监控会话失败: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(chat_target, error_msg)
            return False
    
    def detect_crash_recovery(self, chat_target: str) -> bool:
        """检测是否从崩溃中恢复"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 查找最近24小时内是否有该聊天对象的处理记录
                cutoff_time = (datetime.now() - timedelta(hours=24)).isoformat()
                cursor.execute('''
                    SELECT COUNT(*) FROM message_status_robust 
                    WHERE chat_target = ? 
                    AND status IN ('success', 'session_marked')
                    AND created_at > ?
                ''', (chat_target, cutoff_time))
                
                count = cursor.fetchone()[0]
                
                # 如果有记录但当前没有活跃会话，说明可能是崩溃恢复
                has_recent_records = count > 0
                has_active_session = (chat_target in self.session_managers and 
                                    self.session_managers[chat_target].current_session_id is not None)
                
                is_recovery = has_recent_records and not has_active_session
                
                if is_recovery:
                    logger.info(f"检测到 {chat_target} 可能从崩溃中恢复 (最近24小时有 {count} 条处理记录)")
                
                return is_recovery
                
        except Exception as e:
            logger.error(f"检测崩溃恢复失败: {e}")
            return False

    def restore_processed_messages_from_crash(self, chat_target: str, session_manager: MessageSessionManager):
        """从崩溃中恢复已处理的消息状态"""
        try:
            # 查询最近24小时内已处理的消息
            cutoff_time = (datetime.now() - timedelta(hours=24)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 获取所有已处理的内容指纹（不依赖消息ID，因为ID已变化）
                cursor.execute('''
                    SELECT DISTINCT content_fingerprint, sender, content_hash, time_window
                    FROM message_status_robust 
                    WHERE chat_target = ? 
                    AND status = 'success' 
                    AND created_at > ?
                    ORDER BY created_at DESC
                ''', (chat_target, cutoff_time))
                
                restored_count = 0
                for row in cursor.fetchall():
                    content_fingerprint, sender, content_hash, time_window = row
                    
                    # 恢复到会话管理器的内容指纹集合中
                    session_manager.processed_content_fingerprints.add(content_fingerprint)
                    
                    # 同时生成基础内容指纹（不包含时间窗口）用于更宽松的匹配
                    base_content_fingerprint = f"{sender}|{content_hash}"
                    session_manager.processed_content_fingerprints.add(base_content_fingerprint)
                    
                    restored_count += 1
                
                logger.info(f"从崩溃恢复了 {restored_count} 条已处理消息的状态")
                
                # 记录恢复操作
                cursor.execute('''
                    INSERT INTO message_status_robust 
                    (session_id, message_id, content_fingerprint, session_fingerprint,
                     chat_target, sender, content_hash, time_window, status, 
                     created_at, updated_at, error_msg)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_manager.current_session_id,
                    'CRASH_RECOVERY',
                    f'RECOVERY_{chat_target}',
                    f'{session_manager.current_session_id}|CRASH_RECOVERY',
                    chat_target,
                    'SYSTEM',
                    'RECOVERY',
                    datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'crash_recovery',
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    f'恢复了{restored_count}条消息状态'
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"恢复消息状态失败: {e}")
    
    def mark_existing_messages_in_session(self, chat_target: str, session_id: str):
        """在会话中标记现有消息为已处理"""
        try:
            messages = self.get_messages_from_api(chat_target)
            session_manager = self.session_managers[chat_target]
            
            marked_count = 0
            for msg in messages:
                if msg.get('type') == 'friend':
                    fingerprints = self.generate_robust_message_fingerprint(msg, session_id)
                    
                    # 在会话中标记为已处理
                    session_manager.mark_message_processed(
                        fingerprints['message_id'], 
                        fingerprints['content_fingerprint']
                    )
                    
                    # 同时在数据库中记录（用于跨会话持久化）
                    self.save_message_status_robust(
                        fingerprints=fingerprints,
                        chat_target=chat_target,
                        message=msg,
                        status='session_marked',
                        session_id=session_id
                    )
                    
                    marked_count += 1
            
            logger.info(f"会话 {session_id} 中标记了 {marked_count} 条现有消息")
            
        except Exception as e:
            logger.error(f"标记会话现有消息失败: {e}")
    
    def get_messages_from_api(self, chat_target: str) -> List[Dict]:
        """从API获取消息列表"""
        try:
            url = f"{self.api_base_url}/api/chat-window/get-all-messages"
            params = {'who': chat_target}
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data['code'] != 0:
                raise Exception(f"API返回错误: {data['message']}")
            
            return data['data']['messages']
            
        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            raise
    
    def ensure_chat_in_listen_list(self, chat_target: str):
        """确保聊天对象在API监听列表中"""
        try:
            url = f"{self.api_base_url}/api/message/listen/add"
            data = {"chat_name": chat_target}
            
            # 增加超时时间到30秒，因为微信操作可能比较慢
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            
            # 即使HTTP状态码不是200，也检查响应内容
            if response.status_code == 200:
                result = response.json()
                if result['code'] != 0:
                    # API返回错误，但可能实际上已经添加成功了
                    logger.warning(f"API返回错误但可能已添加成功: {result['message']}")
                else:
                    logger.debug(f"成功确保 {chat_target} 在监听列表中")
            elif response.status_code == 500:
                # 服务器内部错误，但聊天对象可能已经添加
                logger.warning(f"服务器内部错误，但 {chat_target} 可能已添加到监听列表")
            else:
                response.raise_for_status()
            
        except requests.exceptions.Timeout:
            # 超时错误，但不抛出异常，因为操作可能实际上已经成功
            logger.warning(f"添加 {chat_target} 到监听列表超时，但操作可能已成功")
        except requests.exceptions.RequestException as e:
            # 网络错误，记录但不抛出异常
            logger.warning(f"网络请求失败，但 {chat_target} 可能已在监听列表中: {e}")
        except Exception as e:
            # 其他错误，记录但不抛出异常
            logger.warning(f"确保聊天对象在监听列表时出错，但可能已成功: {e}")
    
    def process_messages_robust(self, chat_target: str, messages: List[Dict], session_id: str) -> List[str]:
        """使用可靠机制处理消息"""
        if chat_target not in self.session_managers:
            logger.error(f"聊天对象 {chat_target} 没有活跃的监听会话")
            return []
        
        session_manager = self.session_managers[chat_target]
        
        # 检测连续相同消息
        enhanced_messages = self.detect_consecutive_messages(messages)
        
        processing_results = []
        
        for msg in enhanced_messages:
            if msg.get('type') != 'friend':
                continue
                
            try:
                # 生成多重指纹
                fingerprints = self.generate_robust_message_fingerprint(msg, session_id)
                
                # 检查是否已在当前会话中处理过
                if session_manager.is_message_processed_in_session(
                    fingerprints['message_id'], 
                    fingerprints['content_fingerprint']
                ):
                    logger.debug(f"消息已在会话中处理过，跳过: {msg['content'][:30]}...")
                    continue
                
                # 检查是否是会话开始前的历史消息
                if self.is_historical_message(fingerprints, session_manager.session_start_time):
                    logger.debug(f"检测到历史消息，跳过: {msg['content'][:30]}...")
                    continue
                
                # 处理新消息
                success = self.handle_single_message_robust(
                    chat_target=chat_target,
                    message=msg,
                    fingerprints=fingerprints,
                    session_id=session_id
                )
                
                if success:
                    # 标记为已处理
                    session_manager.mark_message_processed(
                        fingerprints['message_id'], 
                        fingerprints['content_fingerprint']
                    )
                    
                    seq_info = ""
                    if '_consecutive_seq' in msg:
                        seq_info = f" (连续消息 {msg['_consecutive_seq']+1}/{msg['_consecutive_total']})"
                    
                    processing_results.append(f"✅ 成功处理: {msg['sender']} - {msg['content']}{seq_info}")
                else:
                    processing_results.append(f"❌ 处理失败: {msg['sender']} - {msg['content']}")
                    
            except Exception as e:
                processing_results.append(f"💥 处理异常: {msg['sender']} - {msg['content']} - {str(e)}")
        
        return processing_results
    
    def detect_consecutive_messages(self, messages: List[Dict]) -> List[Dict]:
        """检测并标记连续相同消息"""
        enhanced_messages = []
        content_groups = {}
        
        # 按内容分组
        for i, msg in enumerate(messages):
            if msg.get('type') != 'friend':
                enhanced_messages.append(msg)
                continue
                
            content_key = f"{msg['sender']}:{msg['content']}"
            if content_key not in content_groups:
                content_groups[content_key] = []
            content_groups[content_key].append((i, msg))
        
        # 为连续相同消息添加序列号
        for content_key, msg_list in content_groups.items():
            if len(msg_list) > 1:
                logger.info(f"检测到 {len(msg_list)} 条连续相同消息: {content_key}")
                
                for seq_num, (original_index, msg) in enumerate(msg_list):
                    enhanced_msg = msg.copy()
                    enhanced_msg['_consecutive_seq'] = seq_num
                    enhanced_msg['_consecutive_total'] = len(msg_list)
                    enhanced_messages.append(enhanced_msg)
            else:
                enhanced_messages.append(msg_list[0][1])
        
        return enhanced_messages
    
    def is_historical_message(self, fingerprints: Dict[str, str], session_start_time: datetime) -> bool:
        """判断是否为历史消息（改进版，支持崩溃恢复）"""
        try:
            # 检查数据库中是否有此消息的处理记录
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 1. 首先检查完整的内容指纹匹配
                cursor.execute('''
                    SELECT created_at FROM message_status_robust 
                    WHERE content_fingerprint = ?
                    AND status IN ('success', 'session_marked')
                    AND created_at < ?
                    ORDER BY created_at DESC LIMIT 1
                ''', (
                    fingerprints['content_fingerprint'],
                    session_start_time.isoformat()
                ))
                
                result = cursor.fetchone()
                if result:
                    logger.debug(f"通过完整内容指纹找到历史消息: {fingerprints['content_fingerprint']}")
                    return True
                
                # 2. 如果完整匹配失败，尝试基础内容匹配（不包含时间窗口）
                # 提取发送者和内容哈希
                content_parts = fingerprints['content_fingerprint'].split('|')
                if len(content_parts) >= 3:
                    sender = content_parts[0]
                    content_hash = content_parts[1]
                    base_content_pattern = f"{sender}|{content_hash}|%"
                    
                    cursor.execute('''
                        SELECT created_at FROM message_status_robust 
                        WHERE content_fingerprint LIKE ?
                        AND status IN ('success', 'session_marked')
                        AND created_at < ?
                        ORDER BY created_at DESC LIMIT 1
                    ''', (
                        base_content_pattern,
                        session_start_time.isoformat()
                    ))
                    
                    result = cursor.fetchone()
                    if result:
                        logger.debug(f"通过基础内容匹配找到历史消息: {sender}|{content_hash}")
                        return True
                
                # 3. 最后检查消息ID（虽然可能已变化，但仍然检查）
                if fingerprints['message_id']:
                    cursor.execute('''
                        SELECT created_at FROM message_status_robust 
                        WHERE message_id = ?
                        AND status IN ('success', 'session_marked')
                        AND created_at < ?
                        ORDER BY created_at DESC LIMIT 1
                    ''', (
                        fingerprints['message_id'],
                        session_start_time.isoformat()
                    ))
                    
                    result = cursor.fetchone()
                    if result:
                        logger.debug(f"通过消息ID找到历史消息: {fingerprints['message_id']}")
                        return True
                
                return False
                
        except Exception as e:
            logger.error(f"检查历史消息失败: {e}")
            # 出错时保守处理，认为是历史消息
            return True
    
    def handle_single_message_robust(self, chat_target: str, message: Dict, 
                                   fingerprints: Dict[str, str], session_id: str) -> bool:
        """处理单条消息"""
        start_time = datetime.now()
        
        try:
            timestamp = start_time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{timestamp}] 正在处理消息: {chat_target} - {message['sender']} - {message['content']}")
            
            # 记录开始处理
            self.save_message_status_robust(fingerprints, chat_target, message, "processing", session_id)
            
            # 调用智能记账API
            success, api_result_msg = self.call_smart_accounting_api(message['content'])
            if not success:
                error_msg = f"智能记账失败: {api_result_msg}"
                logger.error(error_msg)
                self.save_message_status_robust(fingerprints, chat_target, message, "failed", session_id, error_msg)
                self.message_processed.emit(chat_target, message['content'], False, error_msg)
                return False
            
            # 智能记账成功，发送回复到微信
            reply_content = api_result_msg
            reply_success = self.send_reply_to_wechat(chat_target, reply_content)
            if not reply_success:
                logger.warning(f"记账成功但微信回复失败: {reply_content}")
            
            # 处理成功
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            success_msg = f"消息处理完成: {message['content']} -> {api_result_msg}"
            logger.info(success_msg)
            
            self.save_message_status_robust(fingerprints, chat_target, message, "success", session_id)
            self.message_processed.emit(chat_target, message['content'], True, api_result_msg)
            return True
                
        except Exception as e:
            error_msg = f"处理消息时发生异常: {e}"
            logger.error(error_msg)
            
            self.save_message_status_robust(fingerprints, chat_target, message, "failed", session_id, error_msg)
            self.message_processed.emit(chat_target, message['content'], False, error_msg)
            return False
    
    def call_smart_accounting_api(self, message_content: str) -> Tuple[bool, str]:
        """调用智能记账API"""
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
                return False, error_msg
            
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
            
            logger.info(f"调用智能记账API: {api_url}")
            
            # 发送API请求
            response = requests.post(api_url, headers=headers, json=data, timeout=30)
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"智能记账API响应: {result}")
                
                if result.get('success', False) or result.get('code') == 0 or response.status_code == 201:
                    success_msg = "记账成功"
                    if 'data' in result:
                        data_info = result['data']
                        if isinstance(data_info, dict):
                            amount = data_info.get('amount', '')
                            category = data_info.get('category', '')
                            if amount and category:
                                success_msg = f"记账成功：{category} {amount}元"
                            elif amount:
                                success_msg = f"记账成功：{amount}元"
                    
                    logger.info(success_msg)
                    return True, success_msg
                else:
                    error_msg = result.get('message', '记账失败')
                    logger.error(f"智能记账失败: {error_msg}")
                    return False, f"记账失败: {error_msg}"
            
            else:
                error_msg = f"记账服务返回错误: HTTP {response.status_code}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"调用智能记账API异常: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def send_reply_to_wechat(self, chat_target: str, message: str) -> bool:
        """发送回复到微信"""
        try:
            url = f"{self.api_base_url}/api/message/send"
            data = {
                'who': chat_target,
                'msg': message
            }
            
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result['code'] != 0:
                logger.error(f"发送回复失败: {result['message']}")
                return False
            
            logger.debug(f"成功发送回复到 {chat_target}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"发送回复异常: {e}")
            return False
    
    def save_message_status_robust(self, fingerprints: Dict[str, str], chat_target: str, 
                                 message: Dict, status: str, session_id: str, error_msg: str = None):
        """保存可靠的消息状态"""
        with self.db_lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                current_time = datetime.now().isoformat()
                content_hash = hashlib.md5(message['content'].encode('utf-8')).hexdigest()[:8]
                
                try:
                    cursor.execute('''
                        INSERT INTO message_status_robust 
                        (session_id, message_id, content_fingerprint, session_fingerprint,
                         chat_target, sender, content_hash, time_window, status, 
                         created_at, updated_at, error_msg, processed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id,
                        fingerprints['message_id'],
                        fingerprints['content_fingerprint'],
                        fingerprints['session_fingerprint'],
                        chat_target,
                        message['sender'],
                        content_hash,
                        fingerprints['time_window'],
                        status,
                        current_time,
                        current_time,
                        error_msg,
                        current_time if status == 'success' else None
                    ))
                    
                except sqlite3.IntegrityError:
                    # 记录已存在，更新状态
                    cursor.execute('''
                        UPDATE message_status_robust 
                        SET status = ?, updated_at = ?, error_msg = ?,
                            processed_at = ?
                        WHERE session_fingerprint = ?
                    ''', (
                        status,
                        current_time,
                        error_msg,
                        current_time if status == 'success' else None,
                        fingerprints['session_fingerprint']
                    ))
                
                conn.commit()
    
    def _monitor_loop_robust(self, chat_target: str, session_id: str, stop_event: threading.Event):
        """可靠的监控循环"""
        logger.info(f"开始监控循环: {chat_target} (会话: {session_id})")
        
        check_interval = self.get_check_interval(chat_target)
        consecutive_errors = 0
        max_consecutive_errors = 5
        first_run = True  # 标记是否为第一次运行
        
        while not stop_event.is_set():
            try:
                # 第一次运行时的初始化处理
                if first_run:
                    logger.info(f"首次运行监控循环，进行初始化: {chat_target}")
                    
                    # 1. 检测是否从崩溃中恢复
                    is_crash_recovery = self.detect_crash_recovery(chat_target)
                    if is_crash_recovery:
                        logger.info(f"检测到崩溃恢复，恢复消息处理状态: {chat_target}")
                        session_manager = self.session_managers[chat_target]
                        self.restore_processed_messages_from_crash(chat_target, session_manager)
                    
                    # 2. 获取当前消息并标记为已处理（避免处理历史消息）
                    try:
                        logger.info(f"标记现有消息为已处理: {chat_target}")
                        self.mark_existing_messages_in_session(chat_target, session_id)
                    except Exception as e:
                        logger.warning(f"标记现有消息失败，但继续监控: {e}")
                    
                    first_run = False
                    logger.info(f"初始化完成，开始正常监控: {chat_target}")
                
                # 检测消息ID是否发生变化
                if self.detect_message_id_change(chat_target):
                    logger.warning(f"检测到消息ID变化，重新创建会话: {chat_target}")
                    # 这里应该触发会话恢复，但为了简化，我们继续使用当前会话
                
                # 获取消息并处理
                messages = self.get_messages_from_api(chat_target)
                results = self.process_messages_robust(chat_target, messages, session_id)
                
                if results:
                    for result in results:
                        logger.info(result)
                
                consecutive_errors = 0  # 重置错误计数
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"监控循环异常 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    error_msg = f"连续错误次数过多，停止监控: {chat_target}"
                    logger.error(error_msg)
                    self.error_occurred.emit(chat_target, error_msg)
                    break
                
                # 错误时等待更长时间
                time.sleep(min(check_interval * consecutive_errors, 60))
                continue
            
            # 正常等待
            stop_event.wait(check_interval)
        
        logger.info(f"监控循环结束: {chat_target}")
    
    def detect_message_id_change(self, chat_target: str) -> bool:
        """检测消息ID是否发生变化（窗口重新打开）"""
        if chat_target not in self.session_managers:
            return False
        
        try:
            # 获取当前消息
            current_messages = self.get_messages_from_api(chat_target)
            session_manager = self.session_managers[chat_target]
            
            # 检查已知的消息ID是否还存在
            current_message_ids = {msg.get('id', '') for msg in current_messages if msg.get('type') == 'friend'}
            known_message_ids = session_manager.processed_message_ids
            
            # 如果已知的消息ID完全不存在于当前消息中，说明ID发生了变化
            if known_message_ids and not (known_message_ids & current_message_ids):
                logger.warning(f"检测到消息ID变化，可能窗口被重新打开")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"检测消息ID变化失败: {e}")
            return False  # 出错时不触发恢复
    
    def get_check_interval(self, chat_target: str) -> int:
        """获取检查间隔"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT check_interval FROM chat_config_robust WHERE chat_target = ?', (chat_target,))
                result = cursor.fetchone()
                return result[0] if result else 5
        except Exception:
            return 5
    
    def stop_monitoring(self, chat_target: str) -> bool:
        """停止监控指定聊天对象"""
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
    
    def is_monitoring(self, chat_target: str) -> bool:
        """检查是否正在监控指定聊天对象"""
        return self.monitored_chats.get(chat_target, False)
    
    def get_all_chat_targets(self) -> List[str]:
        """获取所有聊天对象列表"""
        return list(self.monitored_chats.keys()) 