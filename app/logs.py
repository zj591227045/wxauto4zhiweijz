import sys
import os
import logging
import re
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# 尝试导入PyQt6，如果失败则使用空的信号类
try:
    from PyQt6.QtCore import QObject, pyqtSignal, QThread

    class LogSignalEmitter(QObject):
        """日志信号发射器"""
        new_log = pyqtSignal(str, str)  # 日志内容, 日志级别

    log_signal_emitter = LogSignalEmitter()

except ImportError:
    # 如果PyQt6不可用，创建一个空的信号发射器
    class DummySignalEmitter:
        def __init__(self):
            self.new_log = None

    log_signal_emitter = DummySignalEmitter()

# 创建一个增强的内存日志处理器
class EnhancedMemoryLogHandler(logging.Handler):
    """增强的内存日志处理器，支持实时信号发射和更好的性能"""

    def __init__(self, capacity=1000):
        super().__init__()
        self.capacity = capacity
        self.buffer = []
        self.error_logs = []
        self.stats = {
            'total_logs': 0,
            'debug_logs': 0,
            'info_logs': 0,
            'warning_logs': 0,
            'error_logs': 0,
            'critical_logs': 0
        }

    def emit(self, record):
        try:
            # 格式化日志消息
            msg = self.format(record)
            timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

            # 创建结构化日志条目
            log_entry = {
                'timestamp': timestamp,
                'level': record.levelname,
                'message': msg,
                'module': record.module,
                'funcName': record.funcName,
                'lineno': record.lineno,
                'raw_record': record
            }

            # 添加到缓冲区
            self.buffer.append(log_entry)

            # 更新统计信息
            self.stats['total_logs'] += 1
            level_key = f"{record.levelname.lower()}_logs"
            if level_key in self.stats:
                self.stats[level_key] += 1

            # 如果是错误日志，单独保存
            if record.levelno >= logging.ERROR:
                self.error_logs.append(log_entry)

            # 如果缓冲区超过容量，移除最旧的记录
            if len(self.buffer) > self.capacity:
                removed = self.buffer.pop(0)
                # 更新统计信息
                removed_level_key = f"{removed['level'].lower()}_logs"
                if removed_level_key in self.stats:
                    self.stats[removed_level_key] = max(0, self.stats[removed_level_key] - 1)
                self.stats['total_logs'] = max(0, self.stats['total_logs'] - 1)

            # 如果错误日志超过容量，移除最旧的记录
            if len(self.error_logs) > self.capacity // 2:
                self.error_logs.pop(0)

            # 发射新日志信号（在主线程中）
            try:
                if hasattr(log_signal_emitter, 'new_log') and log_signal_emitter.new_log:
                    # 使用QThread检查是否在主线程中
                    if hasattr(QThread, 'currentThread'):
                        log_signal_emitter.new_log.emit(msg, record.levelname)
                    else:
                        # 如果不在主线程，直接发射信号
                        log_signal_emitter.new_log.emit(msg, record.levelname)
            except (RuntimeError, AttributeError) as e:
                # 忽略信号发射错误（通常发生在窗口关闭后）
                pass

        except Exception as e:
            self.handleError(record)

    def get_logs(self, level_filter=None, limit=None):
        """获取日志，支持级别过滤和数量限制"""
        logs = self.buffer

        if level_filter:
            if isinstance(level_filter, str):
                level_filter = [level_filter]
            logs = [log for log in logs if log['level'] in level_filter]

        if limit:
            logs = logs[-limit:]

        return logs

    def get_formatted_logs(self, level_filter=None, limit=None):
        """获取格式化的日志字符串列表"""
        logs = self.get_logs(level_filter, limit)
        return [log['message'] for log in logs]

    def get_error_logs(self):
        """获取错误日志"""
        return self.error_logs

    def get_stats(self):
        """获取日志统计信息"""
        return self.stats.copy()

    def clear(self):
        """清空日志缓冲区"""
        self.buffer = []
        self.error_logs = []
        self.stats = {
            'total_logs': 0,
            'debug_logs': 0,
            'info_logs': 0,
            'warning_logs': 0,
            'error_logs': 0,
            'critical_logs': 0
        }

    def search_logs(self, query, case_sensitive=False):
        """搜索日志"""
        results = []
        if not case_sensitive:
            query = query.lower()

        for log in self.buffer:
            message = log['message']
            if not case_sensitive:
                message = message.lower()

            if query in message:
                results.append(log)

        return results

    def has_error(self, error_pattern):
        """检查是否有匹配指定模式的错误日志"""
        for log in self.error_logs:
            message = log['message']
            if error_pattern in message:
                return True

        # 如果没有找到匹配的错误日志，尝试更宽松的匹配
        for log in self.error_logs:
            message = log['message']
            if error_pattern.lower() in message.lower():
                return True

        return False

# 创建一个自定义的日志记录器，用于添加当前使用的库信息
class WeChatLibAdapter(logging.LoggerAdapter):
    """添加当前使用的库信息到日志记录"""

    def __init__(self, logger, lib_name='wxauto'):
        super().__init__(logger, {'wechat_lib': lib_name})

    def process(self, msg, kwargs):
        # 确保额外参数中包含当前使用的库信息
        if 'extra' not in kwargs:
            kwargs['extra'] = self.extra
        else:
            # 如果已经有extra参数，添加wechat_lib
            kwargs['extra'].update(self.extra)
        return msg, kwargs

    def set_lib_name(self, lib_name):
        """更新当前使用的库名称"""
        self.extra['wechat_lib'] = lib_name

    @classmethod
    def set_lib_name_static(cls, lib_name):
        """静态方法，用于更新全局logger的库名称"""
        global logger
        if isinstance(logger, cls):
            logger.set_lib_name(lib_name)

# 创建一个自定义的日志过滤器，只显示指定类型的日志
class SpecificLogFilter(logging.Filter):
    """只显示指定类型的日志：微信消息、API调用、发送消息、数据库操作"""

    def __init__(self):
        super().__init__()
        # 定义需要显示的日志模式
        self.allowed_patterns = [
            # 1. 获取到新的微信消息
            re.compile(r'正在处理新消息:'),
            re.compile(r'处理结果:.*条'),
            re.compile(r'成功获取.*条消息'),
            re.compile(r'通过.*识别到.*条新消息'),
            re.compile(r'通过.*匹配找到.*条新消息'),
            re.compile(r'消息解析完成:'),
            re.compile(r'识别为新消息:'),
            re.compile(r'发现新消息:'),
            re.compile(r'新消息:'),
            
            # 2. 只为记账API调用响应
            re.compile(r'调用智能记账API'),
            re.compile(r'智能记账API响应'),
            re.compile(r'智能记账.*成功'),
            re.compile(r'智能记账.*失败'),
            re.compile(r'消息已成功记账'),
            re.compile(r'消息已有记账记录ID'),
            re.compile(r'记录ID:'),
            re.compile(r'记账记录ID'),
            
            # 3. 发送消息到微信
            re.compile(r'回复发送成功'),
            re.compile(r'回复发送失败'),
            re.compile(r'发送回复异常'),
            re.compile(r'成功发送回复到'),
            re.compile(r'跳过微信转发'),
            re.compile(r'跳过微信回复'),
            re.compile(r'记账成功但微信回复失败'),
            re.compile(r'记账成功，但因为有记账记录ID而跳过微信回复'),
            
            # 4. 数据库记账记录操作信息
            re.compile(r'数据库初始化完成'),
            re.compile(r'数据库.*记录'),
            re.compile(r'批量保存了.*条.*消息'),
            re.compile(r'记账状态迁移完成'),
            re.compile(r'已将.*条.*消息.*更新'),
            re.compile(r'消息处理完成:'),
            re.compile(r'保存.*记录'),
            re.compile(r'更新.*记录'),
            
            # 重要的系统信息
            re.compile(r'开始监控循环'),
            re.compile(r'监控循环已结束'),
            re.compile(r'成功完成.*的.*合并'),
            re.compile(r'首次初始化.*成功'),
            
            # 错误和警告信息（重要）
            re.compile(r'ERROR'),
            re.compile(r'WARNING'),
            re.compile(r'错误'),
            re.compile(r'警告'),
            re.compile(r'失败'),
            re.compile(r'异常'),
        ]
        
        # 定义需要过滤掉的DEBUG日志模式
        self.debug_filter_patterns = [
            # 过滤掉消息解析的详细DEBUG日志
            re.compile(r'更新时间上下文:'),
            re.compile(r'跳过.*类型消息:'),
            re.compile(r'解析.*消息:'),
            re.compile(r'开始解析.*条消息'),
            re.compile(r'尝试获取.*的消息'),
            re.compile(r'没有新消息需要处理'),
            
            # 过滤掉HTTP请求相关的DEBUG日志
            re.compile(r'收到请求:'),
            re.compile(r'请求处理完成:'),
            
            # 过滤掉其他不重要的DEBUG信息
            re.compile(r'验证.*访问权限'),
            re.compile(r'检查.*状态'),
            re.compile(r'内部.*检查'),
            re.compile(r'缓存.*更新'),
        ]

    def filter(self, record):
        msg = record.getMessage()
        
        # 如果是DEBUG级别的日志，检查是否应该被过滤掉
        if record.levelno == logging.DEBUG:
            # 检查是否匹配需要过滤掉的DEBUG模式
            for pattern in self.debug_filter_patterns:
                if pattern.search(msg):
                    return False  # 过滤掉这些DEBUG日志
            
            # 如果DEBUG日志不匹配允许的模式，也过滤掉
            for pattern in self.allowed_patterns:
                if pattern.search(msg):
                    return True
            return False  # 过滤掉其他DEBUG日志
        
        # 对于非DEBUG级别的日志，检查是否匹配允许的模式
        for pattern in self.allowed_patterns:
            if pattern.search(msg):
                return True
        
        # 不匹配任何模式，过滤掉
        return False

def setup_enhanced_logger():
    """设置增强的日志系统"""
    # 创建日志目录
    project_root = Path(__file__).parent.parent
    logs_dir = project_root / "data" / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 设置第三方库的日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('http.server').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('comtypes').setLevel(logging.WARNING)

    # 创建主logger实例
    logger = logging.getLogger('wxauto-assistant')
    logger.setLevel(logging.DEBUG)

    # 如果logger已经有处理器，先清除
    if logger.handlers:
        logger.handlers.clear()

    # 设置根日志记录器，捕获所有日志
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 清除根日志记录器的现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建格式化器
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 创建自定义日志过滤器
    specific_filter = SpecificLogFilter()

    # 1. 添加增强的内存日志处理器到主logger和根logger
    memory_handler = EnhancedMemoryLogHandler(capacity=1000)
    memory_handler.setFormatter(detailed_formatter)
    memory_handler.setLevel(logging.DEBUG)
    logger.addHandler(memory_handler)
    root_logger.addHandler(memory_handler)  # 也添加到根logger以捕获所有日志

    # 2. 添加按天切割的文件处理器（不包含DEBUG日志）
    log_file = logs_dir / f"wxauto_assistant_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = TimedRotatingFileHandler(
        str(log_file),
        when='midnight',
        interval=1,
        backupCount=30,  # 保留30天的日志
        encoding='utf-8'
    )
    file_handler.setFormatter(detailed_formatter)
    file_handler.addFilter(specific_filter)
    file_handler.setLevel(logging.INFO)  # 文件只记录INFO及以上级别
    logger.addHandler(file_handler)
    root_logger.addHandler(file_handler)  # 也添加到根logger

    # 3. 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(simple_formatter)
    console_handler.addFilter(specific_filter)
    console_handler.setLevel(logging.INFO)  # 控制台显示INFO及以上级别
    logger.addHandler(console_handler)
    root_logger.addHandler(console_handler)  # 也添加到根logger

    # 4. 添加错误日志文件处理器
    error_log_file = logs_dir / f"error_{datetime.now().strftime('%Y%m%d')}.log"
    error_handler = TimedRotatingFileHandler(
        str(error_log_file),
        when='midnight',
        interval=1,
        backupCount=90,  # 错误日志保留90天
        encoding='utf-8'
    )
    error_handler.setFormatter(detailed_formatter)
    error_handler.setLevel(logging.ERROR)  # 只记录错误日志
    logger.addHandler(error_handler)
    root_logger.addHandler(error_handler)  # 也添加到根logger

    # 设置传播标志
    logger.propagate = False

    # 配置其他常用的logger，让它们使用我们的处理器
    for logger_name in ['app.services', 'app.utils', 'app.qt_ui', 'comtypes.client._code_cache']:
        sub_logger = logging.getLogger(logger_name)
        sub_logger.setLevel(logging.DEBUG)
        sub_logger.propagate = True  # 让它们传播到根logger

    return logger, memory_handler

# 创建增强的logger实例和内存日志处理器
base_logger, memory_handler = setup_enhanced_logger()

# 使用适配器包装logger，添加当前使用的库信息
logger = WeChatLibAdapter(base_logger, 'wxauto')  # 默认使用wxauto

# 导出内存日志处理器，供其他模块使用
log_memory_handler = memory_handler

# 创建一个print重定向器，将print输出也记录到日志
class PrintToLogRedirector:
    """将print输出重定向到日志系统"""

    def __init__(self, logger, level=logging.INFO):
        self.logger = logger
        self.level = level
        self.original_stdout = sys.stdout

    def write(self, message):
        # 过滤空消息和只有换行符的消息
        if message and message.strip():
            # 移除末尾的换行符
            message = message.rstrip('\n\r')
            if message:
                self.logger.log(self.level, f"[PRINT] {message}")

        # 同时输出到原始stdout
        self.original_stdout.write(message)

    def flush(self):
        self.original_stdout.flush()

# 设置print重定向（可选，如果需要捕获print输出）
def setup_print_redirect():
    """设置print重定向到日志系统"""
    try:
        print_redirector = PrintToLogRedirector(logger, logging.INFO)
        # 注意：这会重定向所有print输出，可能影响调试
        # sys.stdout = print_redirector
        print("✓ Print重定向器已准备就绪（未激活）")
    except Exception as e:
        print(f"设置print重定向失败: {e}")

# 初始化print重定向器（但不激活）
setup_print_redirect()

# 添加一些测试日志来验证系统工作
logger.info("增强日志系统初始化完成")
logger.debug("这是一条DEBUG日志，只在内存中显示")
logger.info("这是一条INFO日志，会保存到文件")

# 创建一个便捷函数来获取其他模块的logger
def get_logger(name):
    """获取指定名称的logger，确保它使用我们的处理器"""
    module_logger = logging.getLogger(name)
    module_logger.setLevel(logging.DEBUG)
    module_logger.propagate = True  # 确保传播到根logger
    return module_logger