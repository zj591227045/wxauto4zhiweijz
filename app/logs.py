import sys
import logging
import re
from logging.handlers import RotatingFileHandler
from app.config import Config

# 尝试导入PyQt6，如果失败则使用空的信号类
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    
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

# 创建一个内存日志处理器，用于捕获最近的错误日志
class MemoryLogHandler(logging.Handler):
    """内存日志处理器，用于捕获最近的错误日志"""

    def __init__(self, capacity=100):
        super().__init__()
        self.capacity = capacity
        self.buffer = []
        self.error_logs = []

    def emit(self, record):
        try:
            # 将日志记录添加到缓冲区
            msg = self.format(record)
            self.buffer.append(msg)

            # 如果是错误日志，单独保存
            if record.levelno >= logging.ERROR:
                self.error_logs.append(msg)

            # 如果缓冲区超过容量，移除最旧的记录
            if len(self.buffer) > self.capacity:
                self.buffer.pop(0)

            # 如果错误日志超过容量，移除最旧的记录
            if len(self.error_logs) > self.capacity:
                self.error_logs.pop(0)
                
            # 发射新日志信号
            try:
                if hasattr(log_signal_emitter, 'new_log') and log_signal_emitter.new_log:
                    level_name = record.levelname
                    log_signal_emitter.new_log.emit(msg, level_name)
            except (RuntimeError, AttributeError):
                # 忽略信号发射错误（通常发生在窗口关闭后）
                pass
                
        except Exception:
            self.handleError(record)

    def get_logs(self):
        """获取所有日志"""
        return self.buffer

    def get_error_logs(self):
        """获取错误日志"""
        return self.error_logs

    def clear(self):
        """清空日志缓冲区"""
        self.buffer = []
        self.error_logs = []

    def has_error(self, error_pattern):
        """检查是否有匹配指定模式的错误日志"""
        for log in self.error_logs:
            if error_pattern in log:
                return True

        # 如果没有找到匹配的错误日志，尝试更宽松的匹配
        for log in self.error_logs:
            if error_pattern.lower() in log.lower():
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

def setup_logger():
    # 确保日志目录存在
    Config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # 设置第三方库的日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)  # 减少werkzeug的日志
    logging.getLogger('http.server').setLevel(logging.WARNING)  # 减少HTTP服务器的日志

    # 创建logger实例
    logger = logging.getLogger('wxauto-api')
    logger.setLevel(Config.LOG_LEVEL)  # 使用配置文件中的日志级别

    # 如果logger已经有处理器，先清除
    if logger.handlers:
        logger.handlers.clear()

    # 创建格式化器，使用统一的时间戳格式
    formatter = logging.Formatter(Config.LOG_FORMAT, Config.LOG_DATE_FORMAT)

    # 创建自定义日志过滤器，只显示指定类型的日志
    specific_filter = SpecificLogFilter()

    # 添加内存日志处理器，用于捕获最近的错误日志
    memory_handler = MemoryLogHandler(capacity=100)
    memory_handler.setFormatter(formatter)
    memory_handler.setLevel(logging.DEBUG)  # 捕获所有级别的日志，但只保存错误日志
    logger.addHandler(memory_handler)

    # 添加文件处理器 - 使用大小轮转的日志文件
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(specific_filter)  # 使用新的过滤器
    # 设置为DEBUG级别，通过过滤器控制显示
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(specific_filter)  # 使用新的过滤器
    # 设置为DEBUG级别，通过过滤器控制显示
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)

    # 设置传播标志为False，避免日志重复
    logger.propagate = False

    return logger, memory_handler

# 创建基础logger实例和内存日志处理器
base_logger, memory_handler = setup_logger()

# 使用适配器包装logger，添加当前使用的库信息
logger = WeChatLibAdapter(base_logger, Config.WECHAT_LIB)

# 导出内存日志处理器，供其他模块使用
log_memory_handler = memory_handler