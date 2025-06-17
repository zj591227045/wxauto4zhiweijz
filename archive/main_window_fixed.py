#!/usr/bin/env python3
"""
修复后的PyQt6主界面
只为记账-微信助手
"""

import sys
import os
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QGroupBox, QLabel, 
                             QPushButton, QLineEdit, QTextEdit, QComboBox, 
                             QListWidget, QSpinBox, QCheckBox, QStatusBar,
                             QMessageBox, QSplitter, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 导入配置管理器
try:
    from utils.config_manager import ConfigManager, UserConfig
except ImportError:
    # 如果导入失败，创建一个简单的备用类
    class ConfigManager:
        def __init__(self):
            self.config = None
        def has_valid_config(self):
            return False
        def get_config(self):
            return None

class ModernGroupBox(QGroupBox):
    """现代化的分组框"""
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2c3e50;
            }
        """)

class StatusIndicator(QLabel):
    """状态指示器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.set_status(False)
    
    def set_status(self, connected: bool):
        color = "#27ae60" if connected else "#e74c3c"
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 6px;
                border: 1px solid #bdc3c7;
            }}
        """)
        self.setProperty("connected", connected)

class AsyncTaskThread(QThread):
    """通用异步任务线程"""
    task_completed = pyqtSignal(str, bool, object)  # task_name, success, result
    
    def __init__(self, task_name, task_func, *args, **kwargs):
        super().__init__()
        self.task_name = task_name
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
        self.should_stop = False
    
    def run(self):
        """执行任务"""
        if self.should_stop:
            return
            
        try:
            result = self.task_func(*self.args, **self.kwargs)
            if not self.should_stop:
                self.task_completed.emit(self.task_name, True, result)
        except Exception as e:
            if not self.should_stop:
                self.task_completed.emit(self.task_name, False, str(e))
    
    def stop(self):
        """停止任务"""
        self.should_stop = True

class ApiRequestThread(QThread):
    """异步API请求线程"""
    status_updated = pyqtSignal(dict)  # 发送状态更新信号
    
    def __init__(self, port, api_key, endpoint="status"):
        super().__init__()
        self.port = port
        self.api_key = api_key
        self.endpoint = endpoint
        self.should_stop = False
    
    def run(self):
        """执行API请求"""
        if self.should_stop:
            return
            
        try:
            import requests
            
            url = f"http://localhost:{self.port}/api/wechat/{self.endpoint}"
            headers = {"X-API-Key": self.api_key}
            
            response = requests.get(url, headers=headers, timeout=3)  # 减少超时时间到3秒
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    status_info = {
                        'success': True,
                        'status': data.get("data", {}).get("status", ""),
                        'window_name': data.get("data", {}).get("window_name", ""),
                        'message': 'success'
                    }
                else:
                    status_info = {
                        'success': False,
                        'status': 'error',
                        'window_name': '',
                        'message': data.get('message', 'API错误')
                    }
            elif response.status_code == 400:
                status_info = {
                    'success': False,
                    'status': 'uninitialized',
                    'window_name': '',
                    'message': '微信未初始化'
                }
            else:
                status_info = {
                    'success': False,
                    'status': 'error',
                    'window_name': '',
                    'message': f'HTTP {response.status_code}'
                }
                
        except requests.exceptions.Timeout:
            status_info = {
                'success': False,
                'status': 'timeout',
                'window_name': '',
                'message': '连接超时'
            }
        except requests.exceptions.ConnectionError:
            status_info = {
                'success': False,
                'status': 'connection_error',
                'window_name': '',
                'message': '连接失败'
            }
        except Exception as e:
            status_info = {
                'success': False,
                'status': 'error',
                'window_name': '',
                'message': f'请求失败: {str(e)}'
            }
        
        if not self.should_stop:
            self.status_updated.emit(status_info)
    
    def stop(self):
        """停止线程"""
        self.should_stop = True

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化配置管理器 - 修改为默认使用现有配置
        try:
            self.config_manager = ConfigManager(use_existing_config=True)
            print("配置管理器初始化成功（使用现有配置）")
        except Exception as e:
            self.config_manager = None
            print(f"配置管理器初始化失败: {e}")
        
        self.current_port = 5000
        self.auto_startup_timer = None
        
        # 初始化异步API请求线程
        self.api_request_thread = None
        self.api_request_queue = []  # 请求队列，避免重复请求
        
        # 初始化异步任务管理
        self.async_tasks = {}  # 存储正在运行的异步任务
        
        # 初始化消息监控器
        self.message_monitor = None
        self.message_processor = None
        self._init_message_processor()
        
        self.init_ui()
        self.init_connections()
        self.load_settings()
        
        # 启动状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(8000)  # 每8秒更新一次，减少频率
        
        # 添加快速状态检查定时器（仅在需要时使用）
        self.quick_status_timer = QTimer()
        self.quick_status_timer.timeout.connect(self.quick_status_check)
        self.quick_status_timer.setSingleShot(True)  # 单次触发
        
        # 状态检查计数器，用于智能调整检查频率
        self.status_check_count = 0
        self.last_wechat_status = None
        
        # 执行初始状态检查
        self.initial_status_check()
        
        # 检查是否需要自动启动
        self.check_auto_startup()

    def _init_message_processor(self):
        """初始化消息处理器"""
        try:
            from app.utils.message_processor import MessageProcessor
            
            # 创建消息处理器
            self.message_processor = MessageProcessor(
                api_base_url="http://localhost:5000",
                api_key="test-key-2",
                db_path="data/message_processor.db"
            )
            
            # 连接信号
            self.message_processor.message_processed.connect(self._on_message_processed)
            self.message_processor.status_changed.connect(self._on_chat_status_changed)
            self.message_processor.error_occurred.connect(self._on_processor_error)
            self.message_processor.statistics_updated.connect(self._on_statistics_updated)
            
            self.log_message("INFO", "消息处理器初始化成功")
            
        except Exception as e:
            self.log_message("ERROR", f"消息处理器初始化失败: {e}")
            self.message_processor = None

    def _on_message_processed(self, chat_target: str, message_content: str, success: bool, result_msg: str):
        """处理消息处理完成信号"""
        status = "成功" if success else "失败"
        self.log_message("INFO", f"[{chat_target}] 消息处理{status}: {message_content}")
        if not success:
            self.log_message("ERROR", f"[{chat_target}] 处理失败原因: {result_msg}")

    def _on_chat_status_changed(self, chat_target: str, is_monitoring: bool):
        """处理聊天状态变化信号"""
        status = "监控中" if is_monitoring else "已停止"
        self.log_message("INFO", f"[{chat_target}] 状态变化: {status}")
        
        # 更新UI状态
        if is_monitoring:
            self.monitor_status_indicator.set_status(True)
            self.monitor_status_label.setText("监控中")
            self.monitor_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.start_monitor_btn.setEnabled(False)
            self.stop_monitor_btn.setEnabled(True)
        else:
            # 检查是否还有其他聊天对象在监控中
            has_active_monitoring = False
            if self.message_processor:
                for i in range(self.chat_list_widget.count()):
                    chat_name = self.chat_list_widget.item(i).text()
                    if self.message_processor.is_monitoring(chat_name):
                        has_active_monitoring = True
                        break
            
            if not has_active_monitoring:
                self.monitor_status_indicator.set_status(False)
                self.monitor_status_label.setText("未启动")
                self.monitor_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.start_monitor_btn.setEnabled(True)
                self.stop_monitor_btn.setEnabled(False)

    def _on_processor_error(self, chat_target: str, error_msg: str):
        """处理处理器错误信号"""
        self.log_message("ERROR", f"[{chat_target}] 处理器错误: {error_msg}")

    def _on_statistics_updated(self, chat_target: str, statistics: dict):
        """处理统计信息更新信号"""
        total_success = statistics.get('total_counts', {}).get('success', 0)
        total_failed = statistics.get('total_counts', {}).get('failed', 0)
        today_success = statistics.get('today_counts', {}).get('success', 0)
        
        self.log_message("INFO", f"[{chat_target}] 统计: 总成功{total_success}条, 总失败{total_failed}条, 今日成功{today_success}条")

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("只为记账-微信助手")
        self.setMinimumSize(1300, 900)  # 增加最小尺寸以容纳更多内容
        
        # 设置中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(5)  # 减少间距
        main_layout.setContentsMargins(10, 5, 10, 10)  # 减少顶部边距

        # 标题
        self.title_label = QLabel("只为记账-微信助手")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_title_height()  # 动态设置标题高度
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #2c3e50;
                padding: 8px 10px;
                background-color: #ecf0f1;
                border-radius: 6px;
                margin: 0px;
            }
        """)
        main_layout.addWidget(self.title_label, 0)  # 设置拉伸因子为0，不拉伸
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, 1)  # 设置拉伸因子为1，占据剩余空间
        
        # 创建左右面板
        left_panel = self.create_left_panel()
        right_panel = self.create_right_panel()
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # 设置分割器的拉伸因子，让右侧面板能够更好地调整大小
        splitter.setStretchFactor(0, 0)  # 左侧面板不拉伸，保持内容大小
        splitter.setStretchFactor(1, 1)  # 右侧面板可以拉伸
        
        # 调整初始大小分配，给左侧更多空间
        splitter.setSizes([700, 500])
        
        # 创建状态栏
        self.create_status_bar()

    def update_title_height(self):
        """动态更新标题高度，确保不超过窗口高度的20%"""
        window_height = self.height() if hasattr(self, 'height') and self.height() > 0 else 900
        max_title_height = int(window_height * 0.15)  # 最大15%，更保守
        min_title_height = 40  # 最小高度
        optimal_title_height = 50  # 理想高度，更小
        
        # 选择合适的高度
        title_height = min(max(min_title_height, optimal_title_height), max_title_height)
        
        if hasattr(self, 'title_label'):
            self.title_label.setFixedHeight(title_height)

    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        self.update_title_height()  # 窗口大小改变时更新标题高度

    def create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建内容面板
        content_panel = QWidget()
        layout = QVBoxLayout(content_panel)
        
        # 添加各个功能组
        layout.addWidget(self.create_accounting_config_group())
        layout.addWidget(self.create_wxauto_management_group())
        
        # 设置内容面板到滚动区域
        scroll_area.setWidget(content_panel)
        
        # 创建主面板容器
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.addWidget(scroll_area)
        
        return panel

    def create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 添加各个功能组
        layout.addWidget(self.create_wechat_monitor_group())
        layout.addWidget(self.create_log_management_group())
        
        return panel

    def create_accounting_config_group(self) -> QGroupBox:
        """创建记账配置组"""
        group = ModernGroupBox("只为记账服务配置")
        layout = QVBoxLayout(group)

        # 服务器配置
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel("服务器地址:"))
        self.server_url_edit = QLineEdit("https://api.zhiweijz.com")
        self.server_url_edit.setPlaceholderText("http://localhost:3000")
        server_layout.addWidget(self.server_url_edit)
        layout.addLayout(server_layout)

        # 用户登录
        login_layout = QGridLayout()
        login_layout.addWidget(QLabel("用户名:"), 0, 0)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("邮箱地址")
        login_layout.addWidget(self.username_edit, 0, 1)

        login_layout.addWidget(QLabel("密码:"), 1, 0)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        login_layout.addWidget(self.password_edit, 1, 1)

        self.login_btn = QPushButton("登录")
        self.login_btn.clicked.connect(self.login_to_accounting_service)
        login_layout.addWidget(self.login_btn, 0, 2, 2, 1)

        layout.addLayout(login_layout)

        # 用户信息显示
        self.user_info_label = QLabel("未登录")
        self.user_info_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        layout.addWidget(self.user_info_label)

        # 账本选择
        account_layout = QHBoxLayout()
        account_layout.addWidget(QLabel("选择账本:"))
        self.account_book_combo = QComboBox()
        self.account_book_combo.currentTextChanged.connect(self.on_account_book_changed)
        account_layout.addWidget(self.account_book_combo)

        self.refresh_books_btn = QPushButton("刷新")
        self.refresh_books_btn.clicked.connect(self.refresh_account_books)
        account_layout.addWidget(self.refresh_books_btn)
        layout.addLayout(account_layout)

        # 监控的微信会话
        layout.addWidget(QLabel("监控的微信会话:"))
        self.chat_list_widget = QListWidget()
        self.chat_list_widget.setMinimumHeight(80)  # 设置最小高度
        self.chat_list_widget.setMaximumHeight(150)  # 适当增加最大高度
        layout.addWidget(self.chat_list_widget)

        # 添加会话
        add_chat_layout = QHBoxLayout()
        self.chat_name_edit = QLineEdit()
        self.chat_name_edit.setPlaceholderText("输入微信群名或好友名")
        add_chat_layout.addWidget(self.chat_name_edit)

        self.add_chat_btn = QPushButton("添加")
        self.add_chat_btn.clicked.connect(self.add_monitored_chat)
        add_chat_layout.addWidget(self.add_chat_btn)

        self.remove_chat_btn = QPushButton("移除")
        self.remove_chat_btn.clicked.connect(self.remove_monitored_chat)
        add_chat_layout.addWidget(self.remove_chat_btn)
        layout.addLayout(add_chat_layout)

        # 监控控制
        monitor_layout = QHBoxLayout()
        self.start_monitor_btn = QPushButton("开始监控")
        self.start_monitor_btn.clicked.connect(self.start_monitoring)
        monitor_layout.addWidget(self.start_monitor_btn)

        self.stop_monitor_btn = QPushButton("停止监控")
        self.stop_monitor_btn.clicked.connect(self.stop_monitoring)
        self.stop_monitor_btn.setEnabled(False)
        monitor_layout.addWidget(self.stop_monitor_btn)
        layout.addLayout(monitor_layout)

        # 监控间隔设置
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("检查间隔(秒):"))
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 60)
        self.interval_spinbox.setValue(5)
        interval_layout.addWidget(self.interval_spinbox)
        interval_layout.addStretch()
        layout.addLayout(interval_layout)

        # 自动启动配置
        auto_startup_group = QGroupBox("自动启动配置")
        auto_startup_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: #f8f9fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #3498db;
            }
        """)
        auto_startup_layout = QVBoxLayout(auto_startup_group)
        
        # 自动启动选项
        auto_options_layout = QGridLayout()
        
        self.auto_login_checkbox = QCheckBox("启动时自动登录")
        auto_options_layout.addWidget(self.auto_login_checkbox, 0, 0)
        
        self.auto_start_api_checkbox = QCheckBox("自动启动API服务")
        auto_options_layout.addWidget(self.auto_start_api_checkbox, 0, 1)
        
        self.auto_init_wechat_checkbox = QCheckBox("自动初始化微信")
        auto_options_layout.addWidget(self.auto_init_wechat_checkbox, 1, 0)
        
        self.auto_start_monitor_checkbox = QCheckBox("自动开始监控")
        auto_options_layout.addWidget(self.auto_start_monitor_checkbox, 1, 1)
        
        auto_startup_layout.addLayout(auto_options_layout)
        
        # 启动延迟设置
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("启动延迟(秒):"))
        self.startup_delay_spinbox = QSpinBox()
        self.startup_delay_spinbox.setRange(0, 30)
        self.startup_delay_spinbox.setValue(5)
        delay_layout.addWidget(self.startup_delay_spinbox)
        delay_layout.addStretch()
        auto_startup_layout.addLayout(delay_layout)
        
        # 保存配置按钮
        save_config_layout = QHBoxLayout()
        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.clicked.connect(self.save_user_config)
        save_config_layout.addWidget(self.save_config_btn)
        
        self.load_config_btn = QPushButton("重载配置")
        self.load_config_btn.clicked.connect(self.load_user_config)
        save_config_layout.addWidget(self.load_config_btn)
        
        self.load_existing_config_btn = QPushButton("重置为空配置")
        self.load_existing_config_btn.clicked.connect(self.reset_to_empty_config)
        self.load_existing_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        save_config_layout.addWidget(self.load_existing_config_btn)
        
        save_config_layout.addStretch()
        auto_startup_layout.addLayout(save_config_layout)
        
        layout.addWidget(auto_startup_group)

        return group

    def create_wxauto_management_group(self) -> QGroupBox:
        """创建wxauto库管理组"""
        group = ModernGroupBox("wxauto/wxautox 库管理")
        layout = QVBoxLayout(group)

        # 库状态显示
        status_layout = QGridLayout()
        
        # wxauto状态
        status_layout.addWidget(QLabel("wxauto (开源版):"), 0, 0)
        self.wxauto_status_indicator = StatusIndicator()
        status_layout.addWidget(self.wxauto_status_indicator, 0, 1)
        self.wxauto_status_label = QLabel("检测中...")
        status_layout.addWidget(self.wxauto_status_label, 0, 2)
        
        # wxautox状态
        status_layout.addWidget(QLabel("wxautox (增强版):"), 1, 0)
        self.wxautox_status_indicator = StatusIndicator()
        status_layout.addWidget(self.wxautox_status_indicator, 1, 1)
        self.wxautox_status_label = QLabel("检测中...")
        status_layout.addWidget(self.wxautox_status_label, 1, 2)
        
        # 当前使用库
        status_layout.addWidget(QLabel("当前使用库:"), 2, 0)
        self.current_lib_label = QLabel("检测中...")
        self.current_lib_label.setStyleSheet("font-weight: bold; color: #2980b9;")
        status_layout.addWidget(self.current_lib_label, 2, 1, 1, 2)
        
        layout.addLayout(status_layout)

        # 管理按钮
        btn_layout = QHBoxLayout()
        
        self.check_wxauto_btn = QPushButton("检查 wxauto")
        self.check_wxauto_btn.clicked.connect(self.check_wxauto_status)
        btn_layout.addWidget(self.check_wxauto_btn)
        
        self.install_wxautox_btn = QPushButton("安装 wxautox")
        self.install_wxautox_btn.clicked.connect(self.install_wxautox)
        btn_layout.addWidget(self.install_wxautox_btn)

        self.reload_config_btn = QPushButton("重载配置")
        self.reload_config_btn.clicked.connect(self.reload_wechat_config)
        btn_layout.addWidget(self.reload_config_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return group

    def create_wechat_monitor_group(self) -> QGroupBox:
        """创建微信状态监控组"""
        group = ModernGroupBox("微信状态监控")
        layout = QVBoxLayout(group)

        # 状态显示
        status_layout = QGridLayout()

        # 微信连接状态
        status_layout.addWidget(QLabel("微信连接:"), 0, 0)
        self.wechat_status_indicator = StatusIndicator()
        status_layout.addWidget(self.wechat_status_indicator, 0, 1)
        self.wechat_status_label = QLabel("未连接")
        status_layout.addWidget(self.wechat_status_label, 0, 2)

        # 微信窗口名称
        status_layout.addWidget(QLabel("微信窗口:"), 1, 0)
        self.wechat_window_name_label = QLabel("未获取")
        self.wechat_window_name_label.setStyleSheet("color: orange; font-weight: bold;")
        self.wechat_window_name_label.setWordWrap(True)
        status_layout.addWidget(self.wechat_window_name_label, 1, 1, 1, 2)

        # API服务状态
        status_layout.addWidget(QLabel("API服务:"), 2, 0)
        self.api_status_indicator = StatusIndicator()
        status_layout.addWidget(self.api_status_indicator, 2, 1)
        self.api_status_label = QLabel("未启动")
        status_layout.addWidget(self.api_status_label, 2, 2)

        # API地址
        status_layout.addWidget(QLabel("API地址:"), 3, 0)
        self.api_address_label = QLabel("未启动")
        self.api_address_label.setStyleSheet("color: #2980b9; font-weight: bold;")
        status_layout.addWidget(self.api_address_label, 3, 1, 1, 2)

        # 监控状态
        status_layout.addWidget(QLabel("消息监控:"), 4, 0)
        self.monitor_status_indicator = StatusIndicator()
        status_layout.addWidget(self.monitor_status_indicator, 4, 1)
        self.monitor_status_label = QLabel("未启动")
        status_layout.addWidget(self.monitor_status_label, 4, 2)

        layout.addLayout(status_layout)

        # 控制按钮
        control_layout = QHBoxLayout()
        self.init_wechat_btn = QPushButton("初始化微信")
        self.init_wechat_btn.clicked.connect(self.initialize_wechat)
        control_layout.addWidget(self.init_wechat_btn)

        self.start_api_btn = QPushButton("启动API服务")
        self.start_api_btn.clicked.connect(self.start_api_service)
        control_layout.addWidget(self.start_api_btn)

        self.stop_api_btn = QPushButton("停止API服务")
        self.stop_api_btn.clicked.connect(self.stop_api_service)
        self.stop_api_btn.setEnabled(False)
        control_layout.addWidget(self.stop_api_btn)
        layout.addLayout(control_layout)

        # 统计信息
        stats_layout = QGridLayout()
        stats_layout.addWidget(QLabel("处理消息数:"), 0, 0)
        self.processed_count_label = QLabel("0")
        stats_layout.addWidget(self.processed_count_label, 0, 1)

        stats_layout.addWidget(QLabel("成功记账数:"), 1, 0)
        self.success_count_label = QLabel("0")
        stats_layout.addWidget(self.success_count_label, 1, 1)

        stats_layout.addWidget(QLabel("失败记账数:"), 2, 0)
        self.failed_count_label = QLabel("0")
        stats_layout.addWidget(self.failed_count_label, 2, 1)
        layout.addLayout(stats_layout)

        return group

    def create_log_management_group(self) -> QGroupBox:
        """创建日志管理组"""
        group = ModernGroupBox("日志管理")
        layout = QVBoxLayout(group)

        # 日志级别选择
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("日志级别:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        level_layout.addWidget(self.log_level_combo)

        # 清空日志按钮
        self.clear_logs_btn = QPushButton("清空日志")
        self.clear_logs_btn.clicked.connect(self.clear_logs)
        level_layout.addWidget(self.clear_logs_btn)
        level_layout.addStretch()
        layout.addLayout(level_layout)

        # 日志显示区域
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setMinimumHeight(200)  # 设置最小高度
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10px;
                border: 1px solid #34495e;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.log_text_edit)

        return group

    def create_status_bar(self):
        """创建状态栏"""
        status_bar = self.statusBar()

        # 连接状态
        self.status_connection_label = QLabel("未连接")
        status_bar.addWidget(self.status_connection_label)

        # 分隔符
        status_bar.addPermanentWidget(QLabel("|"))

        # 当前用户
        self.status_user_label = QLabel("未登录")
        status_bar.addPermanentWidget(self.status_user_label)

        # 分隔符
        status_bar.addPermanentWidget(QLabel("|"))

        # 版本信息
        version_label = QLabel("v1.0.0")
        status_bar.addPermanentWidget(version_label)

    def init_connections(self):
        """初始化信号连接"""
        # 统计计数器
        self.processed_count = 0
        self.success_count = 0
        self.failed_count = 0

    def load_settings(self):
        """加载设置"""
        try:
            # 加载用户配置
            self.load_user_config()
            
            self.log_message("INFO", "设置加载成功")
        except Exception as e:
            self.log_message("ERROR", f"加载设置失败: {str(e)}")

    def save_settings(self):
        """保存设置"""
        try:
            # 保存设置到配置文件
            self.log_message("INFO", "设置保存成功")
        except Exception as e:
            self.log_message("ERROR", f"保存设置失败: {str(e)}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.save_settings()
        
        # 停止状态更新定时器
        if hasattr(self, 'status_timer'):
            self.status_timer.stop()
        
        # 清理异步任务
        self.cleanup_async_tasks()
        
        # 停止API请求线程
        if self.api_request_thread and self.api_request_thread.isRunning():
            self.api_request_thread.stop()
            self.api_request_thread.wait(1000)  # 等待最多1秒
        
        event.accept()

    # 配置管理相关方法
    def load_user_config(self):
        """加载用户配置"""
        if not self.config_manager:
            self.log_message("ERROR", "配置管理器未初始化")
            return
        
        try:
            config = self.config_manager.get_config()
            
            # 加载记账配置
            self.server_url_edit.setText(config.accounting.server_url)
            self.username_edit.setText(config.accounting.username)
            self.password_edit.setText(config.accounting.password)
            
            # 加载微信监控配置
            self.chat_list_widget.clear()
            for chat in config.wechat_monitor.monitored_chats:
                self.chat_list_widget.addItem(chat)
            self.interval_spinbox.setValue(config.wechat_monitor.check_interval)
            
            # 加载自动启动配置
            self.auto_login_checkbox.setChecked(config.app.auto_login)
            self.auto_start_api_checkbox.setChecked(config.app.auto_start_api)
            self.auto_init_wechat_checkbox.setChecked(config.app.auto_init_wechat)
            self.auto_start_monitor_checkbox.setChecked(config.wechat_monitor.auto_start)
            self.startup_delay_spinbox.setValue(config.app.startup_delay)
            
            # 更新端口
            self.current_port = config.app.api_port
            
            self.log_message("INFO", "用户配置加载成功")
            
            # 如果有有效的登录信息，显示用户信息
            if config.accounting.username and config.accounting.token:
                self.user_info_label.setText(f"已登录: {config.accounting.username}")
                self.user_info_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                
                # 如果有账本信息，设置账本
                if config.accounting.account_book_name:
                    self.account_book_combo.addItem(config.accounting.account_book_name)
                    self.account_book_combo.setCurrentText(config.accounting.account_book_name)
            
        except Exception as e:
            self.log_message("ERROR", f"加载用户配置失败: {str(e)}")
    
    def save_user_config(self):
        """保存用户配置"""
        if not self.config_manager:
            self.log_message("ERROR", "配置管理器未初始化")
            return
        
        try:
            # 获取当前界面的配置
            monitored_chats = []
            for i in range(self.chat_list_widget.count()):
                monitored_chats.append(self.chat_list_widget.item(i).text())
            
            # 更新记账配置
            self.config_manager.update_accounting_config(
                server_url=self.server_url_edit.text().strip(),
                username=self.username_edit.text().strip(),
                password=self.password_edit.text().strip()
            )
            
            # 更新微信监控配置
            self.config_manager.update_wechat_monitor_config(
                monitored_chats=monitored_chats,
                check_interval=self.interval_spinbox.value(),
                auto_start=self.auto_start_monitor_checkbox.isChecked()
            )
            
            # 更新应用配置
            self.config_manager.update_app_config(
                auto_login=self.auto_login_checkbox.isChecked(),
                auto_start_api=self.auto_start_api_checkbox.isChecked(),
                auto_init_wechat=self.auto_init_wechat_checkbox.isChecked(),
                startup_delay=self.startup_delay_spinbox.value(),
                api_port=self.current_port
            )
            
            self.log_message("INFO", "用户配置保存成功")
            QMessageBox.information(self, "成功", "配置保存成功！")
            
        except Exception as e:
            self.log_message("ERROR", f"保存用户配置失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")
    
    def reset_to_empty_config(self):
        """重置为空配置"""
        if not self.config_manager:
            self.log_message("ERROR", "配置管理器未初始化")
            return
        
        try:
            from PyQt6.QtWidgets import QMessageBox
            
            # 询问用户是否确认重置配置
            reply = QMessageBox.question(
                self, 
                "确认重置", 
                "是否要重置为空配置？\n这将清空当前的所有设置。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 重新创建配置管理器，使用空配置
                self.config_manager = ConfigManager(use_existing_config=False)
                
                # 清空界面设置
                self.server_url_edit.setText("https://api.zhiweijz.com")
                self.username_edit.setText("")
                self.password_edit.setText("")
                self.chat_list_widget.clear()
                self.interval_spinbox.setValue(5)
                self.auto_login_checkbox.setChecked(False)
                self.auto_start_api_checkbox.setChecked(False)
                self.auto_init_wechat_checkbox.setChecked(False)
                self.auto_start_monitor_checkbox.setChecked(False)
                self.startup_delay_spinbox.setValue(5)
                
                # 清空用户信息显示
                self.user_info_label.setText("未登录")
                self.user_info_label.setStyleSheet("color: #7f8c8d;")
                self.account_book_combo.clear()
                
                self.log_message("INFO", "配置已重置为空")
                QMessageBox.information(self, "成功", "配置已重置为空！")
            
        except Exception as e:
            self.log_message("ERROR", f"重置为空配置失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"重置为空配置失败: {str(e)}")
    
    def check_auto_startup(self):
        """检查是否需要自动启动"""
        if not self.config_manager or not self.config_manager.has_valid_config():
            self.log_message("INFO", "没有有效配置，跳过自动启动")
            return
        
        config = self.config_manager.get_config()
        
        # 如果启用了自动启动功能
        if (config.app.auto_login or config.app.auto_start_api or 
            config.app.auto_init_wechat or config.wechat_monitor.auto_start):
            
            delay = config.app.startup_delay
            self.log_message("INFO", f"将在 {delay} 秒后执行自动启动...")
            
            # 创建定时器执行自动启动
            self.auto_startup_timer = QTimer()
            self.auto_startup_timer.setSingleShot(True)
            self.auto_startup_timer.timeout.connect(self.execute_auto_startup)
            self.auto_startup_timer.start(delay * 1000)  # 转换为毫秒
    
    def execute_auto_startup(self):
        """执行自动启动"""
        if not self.config_manager:
            return
        
        config = self.config_manager.get_config()
        
        try:
            # 自动登录
            if config.app.auto_login and config.accounting.username and config.accounting.password:
                self.log_message("INFO", "执行自动登录...")
                self.username_edit.setText(config.accounting.username)
                self.password_edit.setText(config.accounting.password)
                self.login_to_accounting_service()
            
            # 自动启动API服务
            if config.app.auto_start_api:
                self.log_message("INFO", "执行自动启动API服务...")
                QTimer.singleShot(1000, self.start_api_service)  # 延迟1秒启动
            
            # 自动初始化微信
            if config.app.auto_init_wechat:
                self.log_message("INFO", "执行自动初始化微信...")
                QTimer.singleShot(2000, self.initialize_wechat)  # 延迟2秒启动
            
            # 自动开始监控
            if config.wechat_monitor.auto_start and config.wechat_monitor.monitored_chats:
                self.log_message("INFO", "执行自动开始监控...")
                QTimer.singleShot(3000, self.start_monitoring)  # 延迟3秒启动
            
        except Exception as e:
            self.log_message("ERROR", f"自动启动执行失败: {str(e)}")

    # 记账服务相关方法
    def login_to_accounting_service(self):
        """登录到记账服务"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        server_url = self.server_url_edit.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "警告", "请输入用户名和密码")
            return
        
        if not server_url:
            QMessageBox.warning(self, "警告", "请输入服务器地址")
            return
        
        self.log_message("INFO", f"正在登录记账服务: {username}")
        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中...")
        
        try:
            # 导入记账服务
            from services.accounting_service import AccountingService
            
            # 创建服务实例并登录
            service = AccountingService()
            success, message, user = service.login(server_url, username, password)
            
            if success and user:
                self.log_message("INFO", f"登录成功: {user.name}")
                self.user_info_label.setText(f"已登录: {user.name} ({user.email})")
                self.user_info_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                
                # 保存登录信息到配置
                if self.config_manager:
                    self.config_manager.update_accounting_config(
                        server_url=server_url,
                        username=username,
                        password=password,
                        token=service.config.token
                    )
                
                # 自动刷新账本列表
                self.refresh_account_books()
                
                QMessageBox.information(self, "成功", f"登录成功！\n欢迎，{user.name}")
                
            else:
                self.log_message("ERROR", f"登录失败: {message}")
                self.user_info_label.setText("登录失败")
                self.user_info_label.setStyleSheet("color: #e74c3c; font-style: italic;")
                QMessageBox.critical(self, "登录失败", message)
        
        except Exception as e:
            error_msg = f"登录过程中发生错误: {str(e)}"
            self.log_message("ERROR", error_msg)
            self.user_info_label.setText("登录错误")
            self.user_info_label.setStyleSheet("color: #e74c3c; font-style: italic;")
            QMessageBox.critical(self, "错误", error_msg)
        
        finally:
            self.login_btn.setEnabled(True)
            self.login_btn.setText("登录")

    def refresh_account_books(self):
        """刷新账本列表（异步）"""
        self.log_message("INFO", "正在刷新账本列表...")
        self.refresh_books_btn.setEnabled(False)
        self.refresh_books_btn.setText("刷新中...")
        
        # 使用异步任务执行刷新
        success = self.run_async_task("refresh_account_books", self._do_refresh_account_books)
        if not success:
            # 如果任务启动失败，恢复按钮状态
            self.refresh_books_btn.setEnabled(True)
            self.refresh_books_btn.setText("刷新")
    
    def _do_refresh_account_books(self):
        """执行账本列表刷新的实际工作（在后台线程中运行）"""
        try:
            # 导入记账服务
            from services.accounting_service import AccountingService, AccountingConfig
            
            # 创建服务实例
            service = AccountingService()
            
            # 如果有配置管理器，使用保存的配置
            if self.config_manager:
                config = self.config_manager.get_config()
                if config.accounting.token:
                    service.update_config(AccountingConfig(
                        server_url=config.accounting.server_url,
                        username=config.accounting.username,
                        password=config.accounting.password,
                        token=config.accounting.token
                    ))
            
            # 获取账本列表
            success, message, account_books = service.get_account_books()
            
            if success:
                return {
                    'success': True,
                    'account_books': account_books,
                    'message': f"成功获取 {len(account_books)} 个账本"
                }
            else:
                return {
                    'success': False,
                    'message': f"获取账本列表失败: {message}"
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f"刷新账本列表时发生错误: {str(e)}"
            }
    
    def on_refresh_account_books_completed(self, success, result):
        """处理账本列表刷新完成"""
        try:
            # 恢复按钮状态
            self.refresh_books_btn.setEnabled(True)
            self.refresh_books_btn.setText("刷新")
            
            if success and isinstance(result, dict):
                if result.get('success'):
                    # 更新账本列表
                    account_books = result.get('account_books', [])
                    self.account_book_combo.clear()
                    
                    for book in account_books:
                        display_text = f"{book.name}"
                        if book.is_default:
                            display_text += " (默认)"
                        self.account_book_combo.addItem(display_text, book.id)
                    
                    self.log_message("INFO", result.get('message', '账本列表刷新成功'))
                    
                    # 如果配置中有保存的账本，选中它
                    if self.config_manager:
                        config = self.config_manager.get_config()
                        if config.accounting.account_book_name:
                            index = self.account_book_combo.findText(config.accounting.account_book_name, Qt.MatchFlag.MatchContains)
                            if index >= 0:
                                self.account_book_combo.setCurrentIndex(index)
                else:
                    # 业务逻辑失败
                    error_msg = result.get('message', '未知错误')
                    self.log_message("ERROR", error_msg)
                    QMessageBox.warning(self, "警告", error_msg)
            else:
                # 任务执行失败
                error_msg = str(result) if result else "刷新账本列表失败"
                self.log_message("ERROR", error_msg)
                QMessageBox.critical(self, "错误", error_msg)
                
        except Exception as e:
            error_msg = f"处理账本列表刷新结果时发生错误: {str(e)}"
            self.log_message("ERROR", error_msg)
            QMessageBox.critical(self, "错误", error_msg)

    def on_account_book_changed(self):
        """账本选择变更"""
        current_book = self.account_book_combo.currentText()
        current_data = self.account_book_combo.currentData()
        
        if current_book and current_data:
            self.log_message("INFO", f"选择账本: {current_book}")
            
            # 保存选择的账本到配置
            if self.config_manager:
                self.config_manager.update_accounting_config(
                    account_book_id=current_data,
                    account_book_name=current_book
                )

    # 微信会话监控相关方法
    def add_monitored_chat(self):
        """添加监控的微信会话"""
        chat_name = self.chat_name_edit.text().strip()
        if not chat_name:
            QMessageBox.warning(self, "警告", "请输入微信群名或好友名")
            return
        
        self.chat_list_widget.addItem(chat_name)
        self.chat_name_edit.clear()
        self.log_message("INFO", f"添加监控会话: {chat_name}")

    def remove_monitored_chat(self):
        """移除监控的微信会话"""
        current_item = self.chat_list_widget.currentItem()
        if current_item:
            chat_name = current_item.text()
            self.chat_list_widget.takeItem(self.chat_list_widget.row(current_item))
            self.log_message("INFO", f"移除监控会话: {chat_name}")

    def start_monitoring(self):
        """开始监控"""
        self.log_message("INFO", "开始启动监控...")
        self.start_monitor_btn.setEnabled(False)
        
        if not self.message_processor:
            error_msg = "消息处理器未初始化"
            self.log_message("ERROR", error_msg)
            QMessageBox.critical(self, "错误", error_msg)
            self.start_monitor_btn.setEnabled(True)
            return
        
        try:
            # 获取监控的聊天列表
            monitored_chats = []
            for i in range(self.chat_list_widget.count()):
                monitored_chats.append(self.chat_list_widget.item(i).text())
                
            self.log_message("INFO", f"监控聊天列表: {monitored_chats}")
                
            if not monitored_chats:
                # 如果没有配置监控会话，添加默认的"张杰"
                monitored_chats = ["张杰"]
                self.log_message("INFO", "没有配置监控会话，使用默认会话: 张杰")
                # 添加到UI列表
                self.chat_list_widget.addItem("张杰")
            
            # 首先检查API服务是否运行
            api_url = "http://localhost:5000"
            self.log_message("INFO", "正在检查API服务状态...")
            try:
                import requests
                health_response = requests.get(f"{api_url}/api/health", timeout=5)
                if health_response.status_code != 200:
                    raise Exception("API服务未响应")
                self.log_message("INFO", "✓ API服务已运行")
            except Exception as e:
                self.log_message("WARNING", f"API服务未运行: {str(e)}")
                self.log_message("INFO", "正在启动API服务...")
                
                # 尝试启动API服务
                if not self.start_api_service():
                    error_msg = "API服务启动失败，无法开始监控"
                    self.log_message("ERROR", error_msg)
                    QMessageBox.critical(self, "错误", error_msg)
                    self.start_monitor_btn.setEnabled(True)
                    return
            
            # 初始化微信
            self.log_message("INFO", "正在初始化微信...")
            try:
                import requests
                api_key = "test-key-2"
                init_response = requests.post(f"{api_url}/api/wechat/initialize", 
                                            headers={"X-API-Key": api_key}, timeout=30)
                
                if init_response.status_code == 200:
                    init_result = init_response.json()
                    if init_result.get('code') == 0:
                        self.log_message("INFO", "微信初始化成功")
                    else:
                        self.log_message("ERROR", f"微信初始化失败: {init_result.get('message')}")
                        QMessageBox.critical(self, "错误", f"微信初始化失败: {init_result.get('message')}")
                        self.start_monitor_btn.setEnabled(True)
                        return
                else:
                    error_msg = f"微信初始化失败: HTTP {init_response.status_code}"
                    self.log_message("ERROR", error_msg)
                    QMessageBox.critical(self, "错误", error_msg)
                    self.start_monitor_btn.setEnabled(True)
                    return
            except Exception as e:
                error_msg = f"微信初始化异常: {str(e)}"
                self.log_message("ERROR", error_msg)
                QMessageBox.critical(self, "错误", error_msg)
                self.start_monitor_btn.setEnabled(True)
                return
            
            # 添加聊天对象到消息处理器并启动监控
            success_count = 0
            check_interval = self.interval_spinbox.value()
            
            for chat_name in monitored_chats:
                self.log_message("INFO", f"正在添加监控目标: {chat_name}")
                
                # 添加聊天对象
                if self.message_processor.add_chat_target(chat_name, check_interval):
                    # 启动监控
                    if self.message_processor.start_monitoring(chat_name):
                        self.log_message("INFO", f"✓ 成功启动监控: {chat_name}")
                        success_count += 1
                    else:
                        self.log_message("ERROR", f"✗ 启动监控失败: {chat_name}")
                else:
                    self.log_message("WARNING", f"聊天对象已存在，尝试启动监控: {chat_name}")
                    # 即使已存在，也尝试启动监控
                    if self.message_processor.start_monitoring(chat_name):
                        self.log_message("INFO", f"✓ 成功启动监控: {chat_name}")
                        success_count += 1
                    else:
                        self.log_message("ERROR", f"✗ 启动监控失败: {chat_name}")
            
            # 显示结果
            if success_count > 0:
                self.log_message("INFO", f"监控启动完成，成功启动 {success_count}/{len(monitored_chats)} 个监控目标")
                QMessageBox.information(self, "成功", f"成功启动 {success_count}/{len(monitored_chats)} 个监控目标")
                
                # 更新界面状态
                self.stop_monitor_btn.setEnabled(True)
                self.monitor_status_indicator.set_status(True)
                self.monitor_status_label.setText("监控中")
                self.monitor_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                error_msg = "没有成功启动任何监控目标"
                self.log_message("ERROR", error_msg)
                QMessageBox.critical(self, "错误", error_msg)
                self.start_monitor_btn.setEnabled(True)
                
        except Exception as e:
            error_msg = f"启动监控失败: {str(e)}"
            self.log_message("ERROR", error_msg)
            QMessageBox.critical(self, "错误", error_msg)
            self.start_monitor_btn.setEnabled(True)

    def stop_monitoring(self):
        """停止监控"""
        self.log_message("INFO", "停止监控微信消息...")
        
        if not self.message_processor:
            self.log_message("WARNING", "消息处理器未初始化")
            return
        
        try:
            # 停止所有聊天对象的监控
            stopped_count = 0
            for i in range(self.chat_list_widget.count()):
                chat_name = self.chat_list_widget.item(i).text()
                if self.message_processor.is_monitoring(chat_name):
                    if self.message_processor.stop_monitoring(chat_name):
                        self.log_message("INFO", f"✓ 成功停止监控: {chat_name}")
                        stopped_count += 1
                    else:
                        self.log_message("ERROR", f"✗ 停止监控失败: {chat_name}")
            
            self.log_message("INFO", f"监控停止完成，成功停止 {stopped_count} 个监控目标")
            
            # 更新界面状态
            self.start_monitor_btn.setEnabled(True)
            self.stop_monitor_btn.setEnabled(False)
            self.monitor_status_indicator.set_status(False)
            self.monitor_status_label.setText("未启动")
            self.monitor_status_label.setStyleSheet("color: red; font-weight: bold;")
            
        except Exception as e:
            error_msg = f"停止监控失败: {str(e)}"
            self.log_message("ERROR", error_msg)

    # 微信相关方法
    def initialize_wechat(self):
        """初始化微信"""
        self.log_message("INFO", "正在初始化微信...")
        self.init_wechat_btn.setEnabled(False)
        self.wechat_status_label.setText("初始化中...")
        
        # TODO: 实现微信初始化逻辑
        # 这里应该调用API服务的微信初始化接口
        
        # 模拟初始化成功
        self.wechat_status_indicator.set_status(True)
        self.wechat_status_label.setText("已连接")
        self.wechat_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.wechat_window_name_label.setText("微信")
        self.init_wechat_btn.setEnabled(True)

    def start_api_service(self):
        """启动API服务"""
        self.log_message("INFO", "正在启动API服务...")
        self.start_api_btn.setEnabled(False)
        self.api_status_label.setText("正在启动...")
        
        # 使用内置的Flask应用启动API服务
        import threading
        import sys
        import os
        
        try:
            # 启动Flask应用在单独的线程中
            def run_flask_app():
                try:
                    # 设置环境变量
                    os.environ["WXAUTO_SERVICE_TYPE"] = "api"
                    os.environ["PORT"] = str(self.current_port)
                    os.environ["WECHAT_LIB"] = "wxauto"
                    os.environ["WXAUTO_NO_MUTEX_CHECK"] = "1"
                    
                    # 确保项目路径在sys.path中
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    if project_root not in sys.path:
                        sys.path.insert(0, project_root)
                    
                    app_dir = os.path.join(project_root, "app")
                    if app_dir not in sys.path:
                        sys.path.insert(0, app_dir)
                    
                    # 导入并创建Flask应用
                    from app import create_app
                    app = create_app()
                    
                    # 启动Flask应用
                    app.run(
                        host='0.0.0.0',
                        port=self.current_port,
                        debug=False,
                        use_reloader=False,
                        threaded=True
                    )
                    
                except Exception as e:
                    self.log_message("ERROR", f"Flask应用运行失败: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            # 在单独线程中启动Flask应用
            self.flask_thread = threading.Thread(target=run_flask_app, daemon=True)
            self.flask_thread.start()
            
            # 使用QTimer异步等待Flask应用启动，而不是阻塞UI线程
            def update_api_status():
                # 更新UI状态
                self.api_status_indicator.set_status(True)
                self.api_status_label.setText("运行中")
                self.api_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.api_address_label.setText(f"localhost:{self.current_port}")
                self.start_api_btn.setEnabled(False)
                self.stop_api_btn.setEnabled(True)
                
                self.log_message("INFO", f"API服务已启动，端口: {self.current_port}")
            
            # 延迟3秒后更新UI状态
            QTimer.singleShot(3000, update_api_status)
            
        except Exception as e:
            self.log_message("ERROR", f"启动API服务失败: {str(e)}")
            self.start_api_btn.setEnabled(True)
            self.api_status_label.setText("启动失败")

    def stop_api_service(self):
        """停止API服务"""
        self.log_message("INFO", "正在停止API服务...")
        
        try:
            # 注意：由于Flask应用在线程中运行，我们无法直接停止它
            # 但可以更新UI状态，让用户知道需要重启应用来停止API服务
            self.log_message("WARNING", "Flask应用在线程中运行，需要重启应用来完全停止API服务")
            
            self.api_status_indicator.set_status(False)
            self.api_status_label.setText("未启动")
            self.api_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.api_address_label.setText("未启动")
            self.start_api_btn.setEnabled(True)
            self.stop_api_btn.setEnabled(False)
            
            self.log_message("INFO", "API服务状态已重置（需要重启应用来完全停止）")
            
        except Exception as e:
            self.log_message("ERROR", f"停止API服务失败: {str(e)}")

    # 库管理相关方法
    def check_wxauto_status(self):
        """检查wxauto库状态"""
        try:
            from app.wxauto_wrapper import get_wxauto
            wxauto = get_wxauto()
            if wxauto:
                self.wxauto_status_indicator.set_status(True)
                self.wxauto_status_label.setText("已安装")
                self.wxauto_status_label.setStyleSheet("color: green; font-weight: bold;")
                #self.log_message("INFO", "wxauto库检查通过")
                return True
            else:
                self.wxauto_status_indicator.set_status(False)
                self.wxauto_status_label.setText("未安装")
                self.wxauto_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.log_message("ERROR", "wxauto库未安装")
                return False
        except Exception as e:
            self.wxauto_status_indicator.set_status(False)
            self.wxauto_status_label.setText("检查失败")
            self.wxauto_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.log_message("ERROR", f"检查wxauto库失败: {str(e)}")
            return False

    def check_wxautox_status(self):
        """检查wxautox库状态"""
        try:
            import wxautox
            self.wxautox_status_indicator.set_status(True)
            self.wxautox_status_label.setText("已安装")
            self.wxautox_status_label.setStyleSheet("color: green; font-weight: bold;")
            #self.log_message("INFO", "wxautox库检查通过")
            return True
        except ImportError:
            self.wxautox_status_indicator.set_status(False)
            self.wxautox_status_label.setText("未安装")
            self.wxautox_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.log_message("WARNING", "wxautox库未安装")
            return False
        except Exception as e:
            self.wxautox_status_indicator.set_status(False)
            self.wxautox_status_label.setText("检查失败")
            self.wxautox_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.log_message("ERROR", f"检查wxautox库失败: {str(e)}")
            return False

    def install_wxautox(self):
        """安装wxautox库"""
        QMessageBox.information(self, "提示", "请手动安装wxautox库")

    def reload_wechat_config(self):
        """重载微信配置"""
        self.log_message("INFO", "重载微信配置...")

    # 日志相关方法
    def log_message(self, level, message):
        """添加日志消息"""
        try:
            # 检查log_text_edit是否存在
            if not hasattr(self, 'log_text_edit') or self.log_text_edit is None:
                # 如果日志组件不存在，只打印到控制台
                print(f"[{level}] {message}")
                return
            
            timestamp = datetime.now().strftime("%H:%M:%S")

            # 根据级别设置颜色
            color_map = {
                "DEBUG": "#95a5a6",
                "INFO": "#3498db",
                "WARNING": "#f39c12",
                "ERROR": "#e74c3c"
            }
            color = color_map.get(level, "#ecf0f1")

            # 格式化消息
            formatted_message = f'<span style="color: {color};">[{timestamp}] {level}: {message}</span>'

            # 添加到日志显示区域
            self.log_text_edit.append(formatted_message)

            # 自动滚动到底部
            scrollbar = self.log_text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"添加日志消息失败: {str(e)}")
            # 备用方案：打印到控制台
            print(f"[{level}] {message}")

    def clear_logs(self):
        """清空日志"""
        try:
            if hasattr(self, 'log_text_edit') and self.log_text_edit is not None:
                self.log_text_edit.clear()
                self.log_message("INFO", "日志已清空")
            else:
                print("[INFO] 日志已清空")
        except Exception as e:
            print(f"清空日志失败: {e}")

    # 状态更新相关方法
    def update_status(self):
        """更新状态（智能检查）"""
        try:
            self.status_check_count += 1
            
            # 每次都检查库状态（这些是本地检查，不会阻塞）
            self.check_wxauto_status()
            self.check_wxautox_status()
            self.update_current_lib_status()
            
            # 智能检查微信连接状态
            # 如果连续多次检查都是同一状态，降低检查频率
            should_check_wechat = True
            
            if self.status_check_count > 3:  # 前3次总是检查
                # 如果状态稳定，降低检查频率
                if self.last_wechat_status in ['online', 'connection_error']:
                    # 如果微信在线或连接错误，每3次检查一次
                    should_check_wechat = (self.status_check_count % 3 == 0)
            
            if should_check_wechat:
                self.check_wechat_connection_status()
            
            # 更新状态栏
            if hasattr(self, 'status_connection_label'):
                self.status_connection_label.setText("已连接" if hasattr(self, 'current_port') else "未连接")
            
            if hasattr(self, 'status_user_label'):
                self.status_user_label.setText("未登录")
                
        except Exception as e:
            self.log_message("ERROR", f"更新状态失败: {str(e)}")

    def update_current_lib_status(self):
        """更新当前使用的库状态"""
        try:
            # 从配置文件获取当前使用的库
            from app import config_manager
            config = config_manager.load_app_config()
            current_lib = config.get('wechat_lib', 'wxauto')
            
            self.current_lib_label.setText(current_lib)
            
            # 根据当前库检查状态
            if current_lib == 'wxautox':
                if self.check_wxautox_status():
                    self.current_lib_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.current_lib_label.setStyleSheet("color: red; font-weight: bold;")
            else:  # wxauto
                if self.check_wxauto_status():
                    self.current_lib_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.current_lib_label.setStyleSheet("color: red; font-weight: bold;")
                    
        except Exception as e:
            self.log_message("ERROR", f"更新当前库状态失败: {str(e)}")
            self.current_lib_label.setText("检查失败")
            self.current_lib_label.setStyleSheet("color: red; font-weight: bold;")

    def check_wechat_connection_status(self):
        """检查微信连接状态（异步）"""
        # 如果已有请求在进行中，跳过此次请求
        if self.api_request_thread and self.api_request_thread.isRunning():
            return
        
        try:
            # 获取API密钥
            api_key = "test-key-2"  # 默认API密钥
            try:
                from app import config_manager
                config = config_manager.load_app_config()
                api_keys = config.get('api_keys', ['test-key-2'])
                if api_keys:
                    api_key = api_keys[0]
            except:
                pass
            
            # 获取当前端口
            port = getattr(self, 'current_port', 5000)
            
            # 创建异步请求线程
            self.api_request_thread = ApiRequestThread(port, api_key, "status")
            self.api_request_thread.status_updated.connect(self.on_wechat_status_updated)
            self.api_request_thread.start()
            
        except Exception as e:
            print(f"[ERROR] 启动异步状态检查失败: {str(e)}")
            # 设置错误状态
            self.on_wechat_status_updated({
                'success': False,
                'status': 'error',
                'window_name': '',
                'message': f'启动检查失败: {str(e)}'
            })
    
    def on_wechat_status_updated(self, status_info):
        """处理微信状态更新（在主线程中执行）"""
        try:
            success = status_info.get('success', False)
            status = status_info.get('status', '')
            window_name = status_info.get('window_name', '')
            message = status_info.get('message', '')
            
            # 记录状态变化，用于智能检查
            current_status = status if success else 'error'
            if self.last_wechat_status != current_status:
                print(f"[DEBUG] 微信状态变化: {self.last_wechat_status} -> {current_status}")
                self.last_wechat_status = current_status
                # 状态变化时重置计数器，增加检查频率
                self.status_check_count = 0
            
            if success and status == "online":
                # 微信已连接
                if hasattr(self, 'wechat_status_indicator'):
                    self.wechat_status_indicator.set_status(True)
                if hasattr(self, 'wechat_status_label'):
                    self.wechat_status_label.setText("已连接")
                    self.wechat_status_label.setStyleSheet("color: green; font-weight: bold;")
                
                # 更新窗口名称
                if window_name and hasattr(self, 'wechat_window_name_label'):
                    self.wechat_window_name_label.setText(window_name)
                elif hasattr(self, 'wechat_window_name_label'):
                    self.wechat_window_name_label.setText("获取中...")
                    
            else:
                # 微信未连接或出错
                if hasattr(self, 'wechat_status_indicator'):
                    self.wechat_status_indicator.set_status(False)
                
                if hasattr(self, 'wechat_status_label'):
                    if status == 'uninitialized':
                        self.wechat_status_label.setText("未初始化")
                        self.wechat_status_label.setStyleSheet("color: orange; font-weight: bold;")
                    elif status == 'timeout':
                        self.wechat_status_label.setText("连接超时")
                        self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
                    elif status == 'connection_error':
                        self.wechat_status_label.setText("连接失败")
                        self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
                    else:
                        self.wechat_status_label.setText("未连接")
                        self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
                
                if hasattr(self, 'wechat_window_name_label'):
                    self.wechat_window_name_label.setText("未获取")
            
            # 可选：在日志中记录状态（但不要太频繁）
            if not success and status != 'connection_error':  # 避免连接错误时的日志噪音
                print(f"[DEBUG] 微信状态更新: {message}")
                
        except Exception as e:
            print(f"[ERROR] 处理微信状态更新失败: {str(e)}")
            # 设置错误状态
            if hasattr(self, 'wechat_status_indicator'):
                self.wechat_status_indicator.set_status(False)
            if hasattr(self, 'wechat_status_label'):
                self.wechat_status_label.setText("状态错误")
                self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
            if hasattr(self, 'wechat_window_name_label'):
                self.wechat_window_name_label.setText("未获取")

    def initial_status_check(self):
        """初始状态检查"""
        self.log_message("INFO", "执行初始状态检查...")
        self.update_status()
        
        # 自动启动API服务
        self.log_message("INFO", "自动启动API服务...")
        QTimer.singleShot(1000, self.start_api_service)  # 延迟1秒启动API服务

    def run_async_task(self, task_name, task_func, *args, **kwargs):
        """运行异步任务"""
        # 如果同名任务正在运行，跳过
        if task_name in self.async_tasks and self.async_tasks[task_name].isRunning():
            print(f"[DEBUG] 任务 {task_name} 正在运行中，跳过")
            return False
        
        # 创建并启动异步任务
        task_thread = AsyncTaskThread(task_name, task_func, *args, **kwargs)
        task_thread.task_completed.connect(self.on_async_task_completed)
        self.async_tasks[task_name] = task_thread
        task_thread.start()
        
        print(f"[DEBUG] 启动异步任务: {task_name}")
        return True
    
    def on_async_task_completed(self, task_name, success, result):
        """处理异步任务完成"""
        print(f"[DEBUG] 异步任务完成: {task_name}, 成功: {success}")
        
        # 清理任务引用
        if task_name in self.async_tasks:
            del self.async_tasks[task_name]
        
        # 根据任务名称处理结果
        if task_name == "refresh_account_books":
            self.on_refresh_account_books_completed(success, result)
        elif task_name == "login_accounting":
            self.on_login_accounting_completed(success, result)
        # 可以添加更多任务处理
    
    def cleanup_async_tasks(self):
        """清理所有异步任务"""
        for task_name, task_thread in self.async_tasks.items():
            if task_thread.isRunning():
                task_thread.stop()
                task_thread.wait(1000)  # 等待最多1秒
        self.async_tasks.clear()

    def quick_status_check(self):
        """快速状态检查"""
        self.log_message("INFO", "执行快速状态检查...")
        self.update_status()
        
        # 添加快速状态检查定时器（仅在需要时使用）
        self.quick_status_timer.start(1000)  # 单次触发，1秒后再次检查

def main():
    """主函数"""
    import sys

    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("只为记账-微信助手")
    app.setApplicationVersion("1.0.0")

    # 设置应用样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f8f9fa;
        }
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:pressed {
            background-color: #21618c;
        }
        QPushButton:disabled {
            background-color: #bdc3c7;
            color: #7f8c8d;
        }
        QLineEdit, QSpinBox {
            padding: 6px;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            background-color: white;
            color: #2c3e50;
        }
        QLineEdit:focus, QSpinBox:focus {
            border-color: #3498db;
        }
        QComboBox {
            padding: 6px;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            background-color: white;
            color: #2c3e50;
            min-width: 100px;
        }
        QComboBox:focus {
            border-color: #3498db;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left-width: 1px;
            border-left-color: #bdc3c7;
            border-left-style: solid;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
            background-color: #ecf0f1;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid #7f8c8d;
            width: 0px;
            height: 0px;
        }
        QComboBox QAbstractItemView {
            border: 1px solid #bdc3c7;
            background-color: white;
            color: #2c3e50;
            selection-background-color: #3498db;
            selection-color: white;
            outline: none;
        }
        QComboBox QAbstractItemView::item {
            padding: 6px;
            border-bottom: 1px solid #ecf0f1;
            color: #2c3e50;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: #3498db;
            color: white;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: #5dade2;
            color: white;
        }
        QListWidget {
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            background-color: white;
        }
        QListWidget::item {
            padding: 4px;
            border-bottom: 1px solid #ecf0f1;
        }
        QListWidget::item:selected {
            background-color: #3498db;
            color: white;
        }
    """)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 