"""
只为记账-微信助手 主界面
基于PyQt6的现代化界面
"""

import sys
import json
import logging
import subprocess
from typing import List, Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QTextEdit,
    QComboBox, QCheckBox, QSpinBox, QListWidget, QListWidgetItem,
    QTabWidget, QSplitter, QFrame, QMessageBox, QProgressBar,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor

from services.accounting_service import AccountingService, AccountingConfig, AccountBook, User
from services.message_monitor import MessageMonitor, MonitorConfig

logger = logging.getLogger(__name__)

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

class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("只为记账-微信助手")
        self.setMinimumSize(1200, 800)

        # 服务实例
        self.accounting_service = AccountingService()
        self.message_monitor = MessageMonitor(self.accounting_service)

        # 配置
        self.settings = QSettings("ZhiWeiJZ", "WeChatAssistant")

        # 状态变量
        self.current_user: Optional[User] = None
        self.account_books: List[AccountBook] = []
        self.selected_account_book: Optional[AccountBook] = None

        # 初始化UI
        self.init_ui()
        self.init_connections()
        self.load_settings()

        # 定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # 每5秒更新一次状态

        # 初始化时检查库状态
        QTimer.singleShot(1000, self.initial_status_check)  # 1秒后执行初始检查

    def init_ui(self):
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 标题
        title_label = QLabel("只为记账-微信助手")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                background-color: #ecf0f1;
                border-radius: 8px;
                margin-bottom: 10px;
            }
        """)
        main_layout.addWidget(title_label)

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # 左侧面板
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        # 右侧面板
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        # 设置分割器比例
        splitter.setSizes([600, 600])

        # 状态栏
        self.create_status_bar()

    def create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 只为记账服务配置
        accounting_group = self.create_accounting_config_group()
        layout.addWidget(accounting_group)

        # wxauto库管理
        wxauto_group = self.create_wxauto_management_group()
        layout.addWidget(wxauto_group)

        layout.addStretch()
        return panel

    def create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 微信状态监控
        wechat_group = self.create_wechat_monitor_group()
        layout.addWidget(wechat_group)

        # 日志管理
        log_group = self.create_log_management_group()
        layout.addWidget(log_group)

        return panel

    def create_accounting_config_group(self) -> QGroupBox:
        """创建只为记账服务配置组"""
        group = ModernGroupBox("只为记账服务配置")
        layout = QVBoxLayout(group)

        # 服务器配置
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel("服务器地址:"))
        self.server_url_edit = QLineEdit()
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
        self.chat_list_widget.setMaximumHeight(120)
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
        
        stats_layout.addWidget(QLabel("无关消息数:"), 3, 0)
        self.nothing_count_label = QLabel("0")
        stats_layout.addWidget(self.nothing_count_label, 3, 1)
        
        stats_layout.addWidget(QLabel("记账成功率:"), 4, 0)
        self.success_rate_label = QLabel("0%")
        stats_layout.addWidget(self.success_rate_label, 4, 1)
        
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
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_logs)
        level_layout.addWidget(self.clear_log_btn)
        level_layout.addStretch()
        layout.addLayout(level_layout)

        # 日志显示区域
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setMaximumHeight(300)
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
        # 消息监控信号
        self.message_monitor.message_received.connect(self.on_message_received)
        self.message_monitor.accounting_result.connect(self.on_accounting_result)
        self.message_monitor.status_changed.connect(self.on_monitor_status_changed)
        self.message_monitor.error_occurred.connect(self.on_monitor_error)

        # 统计计数器
        self.processed_count = 0
        self.success_count = 0
        self.failed_count = 0
        self.nothing_count = 0
        
        # 如果有消息处理器，连接统计信号
        if hasattr(self, 'message_processor') and self.message_processor:
            self.message_processor.statistics_updated.connect(self.on_statistics_updated)

    def load_settings(self):
        """加载设置"""
        try:
            # 加载记账服务配置
            server_url = self.settings.value("accounting/server_url", "")
            username = self.settings.value("accounting/username", "")
            account_book_id = self.settings.value("accounting/account_book_id", "")

            self.server_url_edit.setText(server_url)
            self.username_edit.setText(username)

            # 加载监控配置
            monitored_chats = self.settings.value("monitor/chats", [])
            if isinstance(monitored_chats, str):
                monitored_chats = [monitored_chats] if monitored_chats else []
            elif monitored_chats is None:
                monitored_chats = []

            for chat in monitored_chats:
                if chat:  # 确保不是空字符串
                    self.chat_list_widget.addItem(chat)

            # 加载监控间隔
            interval = self.settings.value("monitor/interval", 5, type=int)
            self.interval_spinbox.setValue(interval)

            logger.info("设置加载完成")
        except Exception as e:
            logger.error(f"加载设置失败: {str(e)}")

    def save_settings(self):
        """保存设置"""
        try:
            # 保存记账服务配置
            self.settings.setValue("accounting/server_url", self.server_url_edit.text())
            self.settings.setValue("accounting/username", self.username_edit.text())
            if self.selected_account_book:
                self.settings.setValue("accounting/account_book_id", self.selected_account_book.id)

            # 保存监控配置
            monitored_chats = []
            for i in range(self.chat_list_widget.count()):
                item = self.chat_list_widget.item(i)
                if item:
                    monitored_chats.append(item.text())
            self.settings.setValue("monitor/chats", monitored_chats)
            self.settings.setValue("monitor/interval", self.interval_spinbox.value())

            logger.info("设置保存完成")
        except Exception as e:
            logger.error(f"保存设置失败: {str(e)}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止监控
            self.stop_monitoring()

            # 保存设置
            self.save_settings()

            # 停止定时器
            if self.status_timer.isActive():
                self.status_timer.stop()

            event.accept()
        except Exception as e:
            logger.error(f"关闭窗口时出错: {str(e)}")
            event.accept()

    # 记账服务相关方法
    def login_to_accounting_service(self):
        """登录到记账服务"""
        try:
            server_url = self.server_url_edit.text().strip()
            username = self.username_edit.text().strip()
            password = self.password_edit.text().strip()

            if not all([server_url, username, password]):
                QMessageBox.warning(self, "警告", "请填写完整的服务器地址、用户名和密码")
                return

            # 禁用登录按钮
            self.login_btn.setEnabled(False)
            self.login_btn.setText("登录中...")

            # 执行登录
            success, message, user = self.accounting_service.login(server_url, username, password)

            if success and user:
                self.current_user = user
                self.user_info_label.setText(f"已登录: {user.name} ({user.email})")
                self.user_info_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                self.status_user_label.setText(f"用户: {user.name}")

                # 自动获取账本列表
                self.refresh_account_books()

                QMessageBox.information(self, "成功", f"登录成功！欢迎 {user.name}")
            else:
                QMessageBox.critical(self, "登录失败", message)

        except Exception as e:
            error_msg = f"登录过程中出错: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "错误", error_msg)
        finally:
            # 恢复登录按钮
            self.login_btn.setEnabled(True)
            self.login_btn.setText("登录")

    def refresh_account_books(self):
        """刷新账本列表"""
        try:
            if not self.current_user:
                QMessageBox.warning(self, "警告", "请先登录")
                return

            self.refresh_books_btn.setEnabled(False)
            self.refresh_books_btn.setText("刷新中...")

            success, message, account_books = self.accounting_service.get_account_books()

            if success:
                self.account_books = account_books
                self.account_book_combo.clear()

                for book in account_books:
                    display_text = f"{book.name}"
                    if book.is_default:
                        display_text += " (默认)"
                    self.account_book_combo.addItem(display_text, book)

                # 尝试选择之前保存的账本
                saved_book_id = self.settings.value("accounting/account_book_id", "")
                if saved_book_id:
                    for i, book in enumerate(account_books):
                        if book.id == saved_book_id:
                            self.account_book_combo.setCurrentIndex(i)
                            break

                logger.info(f"成功获取 {len(account_books)} 个账本")
            else:
                QMessageBox.critical(self, "获取账本失败", message)

        except Exception as e:
            error_msg = f"刷新账本时出错: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "错误", error_msg)
        finally:
            self.refresh_books_btn.setEnabled(True)
            self.refresh_books_btn.setText("刷新")

    def on_account_book_changed(self):
        """账本选择变化"""
        try:
            current_index = self.account_book_combo.currentIndex()
            if current_index >= 0:
                self.selected_account_book = self.account_book_combo.itemData(current_index)
                if self.selected_account_book:
                    # 更新记账服务配置
                    config = AccountingConfig(
                        server_url=self.server_url_edit.text(),
                        username=self.username_edit.text(),
                        token=self.accounting_service.config.token,
                        account_book_id=self.selected_account_book.id
                    )
                    self.accounting_service.update_config(config)
                    logger.info(f"选择账本: {self.selected_account_book.name}")
        except Exception as e:
            logger.error(f"账本选择变化处理失败: {str(e)}")

    # 监控相关方法
    def add_monitored_chat(self):
        """添加监控的聊天"""
        try:
            chat_name = self.chat_name_edit.text().strip()
            if not chat_name:
                QMessageBox.warning(self, "警告", "请输入聊天名称")
                return

            # 检查是否已存在
            for i in range(self.chat_list_widget.count()):
                item = self.chat_list_widget.item(i)
                if item and item.text() == chat_name:
                    QMessageBox.warning(self, "警告", "该聊天已在监控列表中")
                    return

            # 添加到列表
            self.chat_list_widget.addItem(chat_name)
            self.chat_name_edit.clear()
            logger.info(f"添加监控聊天: {chat_name}")

        except Exception as e:
            logger.error(f"添加监控聊天失败: {str(e)}")

    def remove_monitored_chat(self):
        """移除监控的聊天"""
        try:
            current_item = self.chat_list_widget.currentItem()
            if not current_item:
                QMessageBox.warning(self, "警告", "请选择要移除的聊天")
                return

            chat_name = current_item.text()
            row = self.chat_list_widget.row(current_item)
            self.chat_list_widget.takeItem(row)
            logger.info(f"移除监控聊天: {chat_name}")

        except Exception as e:
            logger.error(f"移除监控聊天失败: {str(e)}")

    def start_monitoring(self):
        """开始监控"""
        self.log_message("INFO", "开始启动监控...")
        self.start_monitor_btn.setEnabled(False)
        
        try:
            # 获取监控的聊天列表
            monitored_chats = []
            for i in range(self.chat_list_widget.count()):
                monitored_chats.append(self.chat_list_widget.item(i).text())
                
            if not monitored_chats:
                QMessageBox.warning(self, "警告", "请先添加要监控的聊天对象")
                self.start_monitor_btn.setEnabled(True)
                return

            # 初始化消息处理器（如果还没有）
            if not hasattr(self, 'message_processor') or not self.message_processor:
                from app.utils.message_processor import MessageProcessor
                self.message_processor = MessageProcessor(
                    api_base_url="http://localhost:5000",
                    api_key="test-key-2",
                    db_path="data/message_processor.db"
                )
                
                # 连接统计信号
                self.message_processor.statistics_updated.connect(self.on_statistics_updated)
                self.log_message("INFO", "消息处理器已初始化并连接统计信号")

            # 更新监控配置
            config = MonitorConfig()
            config.monitored_chats = monitored_chats
            config.check_interval = self.interval_spinbox.value()
            config.enabled = True
            self.message_monitor.update_config(config)

            # 启动监控
            success = self.message_monitor.start_monitoring()
            if success:
                self.log_message("INFO", f"监控启动成功，监控 {len(monitored_chats)} 个聊天对象")
                QMessageBox.information(self, "成功", f"成功启动监控 {len(monitored_chats)} 个聊天对象")
                
                # 更新界面状态
                self.stop_monitor_btn.setEnabled(True)
                self.monitor_status_indicator.set_status(True)
                self.monitor_status_label.setText("监控中")
                self.monitor_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                error_msg = "监控启动失败"
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
        try:
            self.message_monitor.stop_monitoring()
            self.start_monitor_btn.setEnabled(True)
            self.stop_monitor_btn.setEnabled(False)
            self.log_message("INFO", "消息监控已停止")
        except Exception as e:
            logger.error(f"停止监控失败: {str(e)}")

    # 微信和API服务相关方法
    def initialize_wechat(self):
        """初始化微信"""
        try:
            # 检查当前状态，避免重复初始化
            current_text = self.wechat_status_label.text()
            if current_text == "正在初始化":
                self.log_message("INFO", "微信正在初始化中，请稍候...")
                return
                
            self.log_message("INFO", "开始初始化微信...")
            self.init_wechat_btn.setEnabled(False)
            self.wechat_status_indicator.set_status(False)
            self.wechat_status_label.setText("正在初始化")
            self.wechat_status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.wechat_window_name_label.setText("初始化中...")
            
            # 在新线程中初始化微信
            from PyQt6.QtCore import QThread, pyqtSignal
            import time
            
            class WeChatInitThread(QThread):
                init_success = pyqtSignal(str)  # 窗口名称
                init_failed = pyqtSignal(str)   # 错误信息
                
                def __init__(self, port, api_key):
                    super().__init__()
                    self.port = port
                    self.api_key = api_key
                
                def run(self):
                    max_retries = 3
                    retry_delay = 2
                    
                    for attempt in range(1, max_retries + 1):
                        try:
                            import requests
                            response = requests.post(
                                f"http://localhost:{self.port}/api/wechat/initialize",
                                headers={"X-API-Key": self.api_key},
                                timeout=15  # 增加超时时间
                            )
                            
                            if response.status_code == 200 and response.json().get("code") == 0:
                                init_data = response.json()
                                window_name = init_data.get("data", {}).get("window_name", "")
                                print(f"[DEBUG] PyQt6 - 初始化API返回的窗口名称: {repr(window_name)}")
                                self.init_success.emit(window_name)
                                return
                            else:
                                error_msg = response.json().get("message", "未知错误") if response.status_code == 200 else f"HTTP {response.status_code}"
                                if attempt == max_retries:
                                    self.init_failed.emit(f"微信初始化失败: {error_msg}")
                                else:
                                    import time
                                    time.sleep(retry_delay)
                        except Exception as e:
                            if attempt == max_retries:
                                self.init_failed.emit(f"微信初始化请求失败: {str(e)}")
                            else:
                                import time
                                time.sleep(retry_delay)
            
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
            
            self.init_thread = WeChatInitThread(self.current_port, api_key)
            self.init_thread.init_success.connect(self.on_wechat_init_success)
            self.init_thread.init_failed.connect(self.on_wechat_init_failed)
            self.init_thread.start()
            
        except Exception as e:
            self.log_message("ERROR", f"初始化微信时出错: {str(e)}")
            self.init_wechat_btn.setEnabled(True)
            self.wechat_status_label.setText("初始化失败")

    def on_wechat_init_success(self, window_name: str):
        """微信初始化成功回调"""
        self.log_message("INFO", "微信初始化成功")
        self.wechat_status_indicator.set_status(True)
        self.wechat_status_label.setText("已连接")
        self.wechat_status_label.setStyleSheet("color: green; font-weight: bold;")
        
        # 添加调试信息并修复窗口名称更新逻辑
        print(f"[DEBUG] PyQt6 - 初始化成功，获取到的窗口名称: {repr(window_name)}")
        if window_name:
            print(f"[DEBUG] PyQt6 - 设置窗口名称为: {repr(window_name)}")
            self.wechat_window_name_label.setText(window_name)
            self.log_message("INFO", f"已连接到微信窗口: {window_name}")
        else:
            print(f"[DEBUG] PyQt6 - 窗口名称为空，设置为'获取中...'")
            self.wechat_window_name_label.setText("获取中...")
        
        self.init_wechat_btn.setEnabled(True)

    def on_wechat_init_failed(self, error_msg: str):
        """微信初始化失败回调"""
        self.log_message("ERROR", error_msg)
        self.wechat_status_indicator.set_status(False)
        self.wechat_status_label.setText("初始化失败")
        self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.wechat_window_name_label.setText("未获取")
        self.init_wechat_btn.setEnabled(True)

    def start_api_service(self):
        """启动API服务"""
        try:
            self.log_message("INFO", "正在启动API服务...")
            self.start_api_btn.setEnabled(False)
            self.api_status_label.setText("正在启动...")
            
            # 获取配置
            port = 5000  # 默认端口
            try:
                from app import config_manager
                config = config_manager.load_app_config()
                port = config.get('port', 5000)
            except:
                pass
            
            self.current_port = port
            
            # 在新线程中启动API服务
            from PyQt6.QtCore import QThread, pyqtSignal
            
            class APIServiceThread(QThread):
                service_started = pyqtSignal(int)  # 端口号
                service_failed = pyqtSignal(str)   # 错误信息
                
                def __init__(self, port):
                    super().__init__()
                    self.port = port
                    self.process = None
                
                def run(self):
                    try:
                        # 导入必要的模块
                        import sys
                        import os
                        import subprocess
                        import time
                        import requests
                        
                        # 构建启动命令 - 使用app_no_limiter.py
                        python_exe = sys.executable
                        main_script = os.path.join(os.getcwd(), "app_no_limiter.py")
                        
                        # 启动API服务进程
                        cmd = [python_exe, main_script]
                        
                        # 设置环境变量
                        env = os.environ.copy()
                        env['PORT'] = str(self.port)
                        env['WECHAT_LIB'] = 'wxauto'  # 默认使用wxauto
                        env['WXAUTO_NO_MUTEX_CHECK'] = '1'  # 禁用互斥锁检查
                        
                        self.log_message("INFO", f"启动命令: {' '.join(cmd)}")
                        self.log_message("INFO", f"环境变量: PORT={self.port}, WECHAT_LIB=wxauto")
                        self.log_message("INFO", f"工作目录: {os.getcwd()}")
                        
                        # 首先测试基本的Python模块导入
                        self.log_message("INFO", "正在检查Python环境和依赖...")
                        try:
                            # 测试基本导入
                            test_cmd = [python_exe, "-c", "import flask, requests, psutil; print('基本依赖检查通过')"]
                            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                            if result.returncode == 0:
                                self.log_message("INFO", "✓ 基本依赖检查通过")
                            else:
                                self.log_message("ERROR", f"✗ 基本依赖检查失败: {result.stderr}")
                                self.service_failed.emit(f"基本依赖检查失败: {result.stderr}")
                                return
                        except Exception as e:
                            self.log_message("ERROR", f"依赖检查异常: {str(e)}")
                        
                        # 测试Flask应用创建
                        self.log_message("INFO", "正在测试Flask应用创建...")
                        try:
                            test_flask_cmd = [
                                python_exe, "-c", 
                                "import sys; sys.path.insert(0, '.'); "
                                "from app import create_app; "
                                "app = create_app(); "
                                "print('Flask应用创建成功')"
                            ]
                            result = subprocess.run(test_flask_cmd, capture_output=True, text=True, timeout=15)
                            if result.returncode == 0:
                                self.log_message("INFO", "✓ Flask应用创建测试通过")
                            else:
                                self.log_message("WARNING", f"Flask应用创建测试失败: {result.stderr}")
                                self.log_message("INFO", "将尝试使用最小化Flask应用启动")
                        except Exception as e:
                            self.log_message("WARNING", f"Flask应用创建测试异常: {str(e)}")
                        
                        # 启动进程
                        self.log_message("INFO", "正在启动API服务进程...")
                        self.process = subprocess.Popen(
                            cmd,
                            env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,  # 合并stderr到stdout
                            text=True,
                            encoding='utf-8',
                            bufsize=1,  # 行缓冲
                            universal_newlines=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                        )
                        
                        self.log_message("INFO", f"API服务进程已启动，PID: {self.process.pid}")
                        
                        # 实时监控进程输出
                        import threading
                        def monitor_output():
                            try:
                                for line in iter(self.process.stdout.readline, ''):
                                    if line.strip():
                                        self.log_message("INFO", f"[API进程] {line.strip()}")
                            except Exception as e:
                                self.log_message("ERROR", f"监控进程输出异常: {str(e)}")
                        
                        output_thread = threading.Thread(target=monitor_output, daemon=True)
                        output_thread.start()
                        
                        # 等待服务启动
                        max_wait_time = 60  # 增加到60秒
                        check_interval = 2  # 每2秒检查一次
                        
                        for i in range(max_wait_time // check_interval):
                            # 检查进程是否还在运行
                            poll_result = self.process.poll()
                            if poll_result is not None:
                                # 进程已退出，等待输出线程完成
                                time.sleep(1)
                                
                                self.log_message("ERROR", f"API服务进程意外退出，退出码: {poll_result}")
                                
                                error_msg = f"API服务进程意外退出 (退出码: {poll_result})"
                                self.service_failed.emit(error_msg)
                                return
                            
                            # 尝试连接健康检查端点
                            try:
                                self.log_message("INFO", f"尝试连接健康检查端点 (第{i+1}次)")
                                response = requests.get(f"http://localhost:{self.port}/health", timeout=3)
                                if response.status_code == 200:
                                    self.log_message("INFO", f"✓ API服务健康检查通过，服务已启动")
                                    self.log_message("INFO", f"健康检查响应: {response.text}")
                                    self.service_started.emit(self.port)
                                    return
                                else:
                                    self.log_message("WARNING", f"健康检查返回状态码: {response.status_code}")
                            except requests.exceptions.ConnectionError:
                                self.log_message("INFO", f"连接被拒绝，服务可能还在启动中...")
                            except requests.exceptions.Timeout:
                                self.log_message("WARNING", f"健康检查超时")
                            except requests.exceptions.RequestException as e:
                                self.log_message("WARNING", f"健康检查请求失败: {str(e)}")
                            except Exception as e:
                                self.log_message("ERROR", f"健康检查异常: {str(e)}")
                            
                            time.sleep(check_interval)
                        
                        # 如果60秒后仍未启动成功，收集最终的进程信息
                        self.log_message("ERROR", "API服务启动超时，正在收集诊断信息...")
                        
                        # 检查进程状态
                        if self.process.poll() is None:
                            self.log_message("INFO", "进程仍在运行，但服务未响应")
                            
                            # 尝试读取进程输出
                            try:
                                # 发送终止信号
                                self.process.terminate()
                                time.sleep(2)
                                if self.process.poll() is None:
                                    self.process.kill()
                                self.log_message("INFO", "已终止API服务进程")
                            except Exception as e:
                                self.log_message("ERROR", f"终止进程失败: {str(e)}")
                        else:
                            self.log_message("ERROR", f"进程已退出，退出码: {self.process.poll()}")
                        
                        # 检查端口占用情况
                        try:
                            import psutil
                            connections = psutil.net_connections(kind='inet')
                            port_in_use = any(conn.laddr.port == self.port for conn in connections if conn.laddr)
                            if port_in_use:
                                self.log_message("WARNING", f"端口 {self.port} 被其他进程占用")
                            else:
                                self.log_message("INFO", f"端口 {self.port} 未被占用")
                        except Exception as e:
                            self.log_message("WARNING", f"检查端口占用失败: {str(e)}")
                        
                        self.service_failed.emit("API服务启动超时，请检查日志获取详细信息")
                        
                    except Exception as e:
                        self.log_message("ERROR", f"启动API服务异常: {str(e)}")
                        import traceback
                        self.log_message("ERROR", f"异常堆栈: {traceback.format_exc()}")
                        self.service_failed.emit(f"启动API服务失败: {str(e)}")
                
                def log_message(self, level, message):
                    """线程安全的日志记录"""
                    import logging
                    logger = logging.getLogger(__name__)
                    if level == "INFO":
                        logger.info(message)
                    elif level == "ERROR":
                        logger.error(message)
                    elif level == "WARNING":
                        logger.warning(message)
            
            self.api_thread = APIServiceThread(port)
            self.api_thread.service_started.connect(self.on_api_service_started)
            self.api_thread.service_failed.connect(self.on_api_service_failed)
            self.api_thread.start()
            
        except Exception as e:
            self.log_message("ERROR", f"启动API服务时出错: {str(e)}")
            self.start_api_btn.setEnabled(True)
            self.api_status_label.setText("启动失败")

    def on_api_service_started(self, port: int):
        """API服务启动成功回调"""
        self.log_message("INFO", f"API服务已启动，端口: {port}")
        self.api_status_indicator.set_status(True)
        self.api_status_label.setText("运行中")
        self.api_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.api_address_label.setText(f"localhost:{port}")

        self.start_api_btn.setEnabled(False)
        self.stop_api_btn.setEnabled(True)
        
        # 保存当前端口
        self.current_port = port

    def on_api_service_failed(self, error_msg: str):
        """API服务启动失败回调"""
        self.log_message("ERROR", error_msg)
        self.api_status_indicator.set_status(False)
        self.api_status_label.setText("启动失败")
        self.api_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.api_address_label.setText("未启动")
        
        self.start_api_btn.setEnabled(True)

    def stop_api_service(self):
        """停止API服务"""
        try:
            self.log_message("INFO", "正在停止API服务...")
            
            # 停止API服务进程
            if hasattr(self, 'api_thread') and hasattr(self.api_thread, 'process') and self.api_thread.process:
                try:
                    process = self.api_thread.process
                    if process.poll() is None:  # 进程仍在运行
                        self.log_message("INFO", f"正在终止API服务进程 (PID: {process.pid})")
                        
                        # 尝试优雅地终止进程
                        process.terminate()
                        
                        # 等待进程结束，最多等待5秒
                        try:
                            process.wait(timeout=5)
                            self.log_message("INFO", "API服务进程已优雅终止")
                        except subprocess.TimeoutExpired:
                            # 如果5秒后进程仍未结束，强制杀死
                            self.log_message("WARNING", "API服务进程未响应终止信号，强制杀死")
                            process.kill()
                            process.wait()
                            self.log_message("INFO", "API服务进程已强制终止")
                    else:
                        self.log_message("INFO", "API服务进程已经退出")
                except Exception as e:
                    self.log_message("ERROR", f"终止API服务进程时出错: {str(e)}")
            
            # 停止API线程
            if hasattr(self, 'api_thread') and self.api_thread.isRunning():
                try:
                    self.api_thread.quit()
                    self.api_thread.wait(3000)  # 等待3秒
                    if self.api_thread.isRunning():
                        self.api_thread.terminate()
                        self.api_thread.wait(2000)  # 再等待2秒
                    self.log_message("INFO", "API线程已停止")
                except Exception as e:
                    self.log_message("ERROR", f"停止API线程时出错: {str(e)}")
            
            # 更新状态
            self.api_status_indicator.set_status(False)
            self.api_status_label.setText("已停止")
            self.api_status_label.setStyleSheet("color: #7f8c8d; font-weight: bold;")
            self.api_address_label.setText("未启动")
            
            # 更新按钮状态
            self.start_api_btn.setEnabled(True)
            self.stop_api_btn.setEnabled(False)
            
            # 清除端口信息
            if hasattr(self, 'current_port'):
                delattr(self, 'current_port')
            
            # 重置微信状态
            self.wechat_status_indicator.set_status(False)
            self.wechat_status_label.setText("未连接")
            self.wechat_status_label.setStyleSheet("color: #7f8c8d; font-weight: bold;")
            self.wechat_window_name_label.setText("未获取")
            
            # 清除状态属性
            if hasattr(self.api_status_indicator, 'connected'):
                self.api_status_indicator.setProperty("connected", False)
            if hasattr(self.wechat_status_indicator, 'connected'):
                self.wechat_status_indicator.setProperty("connected", False)
            
            self.log_message("INFO", "API服务已停止")

        except Exception as e:
            error_msg = f"停止API服务时出错: {str(e)}"
            self.log_message("ERROR", error_msg)
            logger.error(error_msg)

    # wxauto库管理相关方法
    def install_wxautox(self):
        """安装wxautox"""
        try:
            QMessageBox.information(self, "提示", "wxautox安装功能待实现")
        except Exception as e:
            logger.error(f"安装wxautox失败: {str(e)}")

    def reload_wechat_config(self):
        """重载微信配置"""
        try:
            QMessageBox.information(self, "提示", "微信配置重载功能待实现")
        except Exception as e:
            logger.error(f"重载微信配置失败: {str(e)}")

    # 信号处理方法
    def on_message_received(self, chat_name: str, message_content: str):
        """处理接收到的消息信号"""
        try:
            self.processed_count += 1
            self.processed_count_label.setText(str(self.processed_count))

            # 记录到日志
            self.log_message("INFO", f"收到消息 [{chat_name}]: {message_content[:50]}...")

        except Exception as e:
            logger.error(f"处理消息接收信号失败: {str(e)}")

    def on_accounting_result(self, chat_name: str, success: bool, message: str):
        """处理记账结果信号"""
        try:
            if success:
                self.success_count += 1
                self.success_count_label.setText(str(self.success_count))
                self.log_message("INFO", f"记账成功 [{chat_name}]: {message}")
            else:
                self.failed_count += 1
                self.failed_count_label.setText(str(self.failed_count))
                self.log_message("ERROR", f"记账失败 [{chat_name}]: {message}")

        except Exception as e:
            logger.error(f"处理记账结果信号失败: {str(e)}")

    def on_statistics_updated(self, chat_target: str, statistics: dict):
        """处理统计信息更新信号"""
        try:
            # 更新统计显示
            self.processed_count_label.setText(str(statistics.get('total_processed', 0)))
            self.success_count_label.setText(str(statistics.get('accounting_success', 0)))
            self.failed_count_label.setText(str(statistics.get('accounting_failed', 0)))
            self.nothing_count_label.setText(str(statistics.get('accounting_nothing', 0)))
            
            # 更新成功率
            success_rate = statistics.get('accounting_success_rate', 0)
            self.success_rate_label.setText(f"{success_rate:.1f}%")
            
            # 根据成功率设置颜色
            if success_rate >= 80:
                color = "color: #27ae60; font-weight: bold;"  # 绿色
            elif success_rate >= 60:
                color = "color: #f39c12; font-weight: bold;"  # 橙色
            else:
                color = "color: #e74c3c; font-weight: bold;"  # 红色
            
            self.success_rate_label.setStyleSheet(color)
            
            # 记录日志
            self.log_message("DEBUG", f"统计更新 [{chat_target}]: 总计{statistics.get('total_processed', 0)}, "
                           f"成功{statistics.get('accounting_success', 0)}, "
                           f"失败{statistics.get('accounting_failed', 0)}, "
                           f"无关{statistics.get('accounting_nothing', 0)}")
            
        except Exception as e:
            logger.error(f"处理统计信息更新失败: {str(e)}")

    def on_monitor_status_changed(self, is_running: bool):
        """处理监控状态变化信号"""
        try:
            self.monitor_status_indicator.set_status(is_running)
            status_text = "运行中" if is_running else "已停止"
            self.monitor_status_label.setText(status_text)

        except Exception as e:
            logger.error(f"处理监控状态变化信号失败: {str(e)}")

    def on_monitor_error(self, error_message: str):
        """处理监控错误信号"""
        try:
            self.log_message("ERROR", f"监控错误: {error_message}")
            QMessageBox.critical(self, "监控错误", error_message)

        except Exception as e:
            logger.error(f"处理监控错误信号失败: {str(e)}")

    # 日志管理方法
    def log_message(self, level: str, message: str):
        """添加日志消息"""
        try:
            from datetime import datetime
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
            logger.error(f"添加日志消息失败: {str(e)}")

    def clear_logs(self):
        """清空日志"""
        try:
            self.log_text_edit.clear()
            self.log_message("INFO", "日志已清空")
        except Exception as e:
            logger.error(f"清空日志失败: {str(e)}")

    # 状态更新方法
    def update_status(self):
        """更新状态信息"""
        try:
            # 更新wxauto库状态
            self.update_current_lib_status()
            
            # 检查微信连接状态
            self.check_wechat_connection_status()
            
            # 更新记账服务状态
            if self.current_user:
                self.status_user_label.setText(f"用户: {self.current_user.email}")
                self.status_connection_label.setText("已连接")
            else:
                self.status_user_label.setText("未登录")
                self.status_connection_label.setText("未连接")
                
        except Exception as e:
            logger.error(f"更新状态失败: {str(e)}")

    def check_wechat_connection_status(self):
        """检查微信连接状态"""
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
            
            response = requests.get(
                f"http://localhost:{self.current_port}/api/wechat/status",
                headers={"X-API-Key": api_key},
                timeout=2
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    status = data.get("data", {}).get("status", "")
                    window_name = data.get("data", {}).get("window_name", "")
                    
                    # 添加调试信息
                    print(f"[DEBUG] PyQt6 - 获取到的状态: {status}")
                    print(f"[DEBUG] PyQt6 - 获取到的窗口名称: {repr(window_name)}")
                    
                    if status == "online":
                        # 微信已连接
                        if not self.wechat_status_indicator.property("connected"):
                            self.wechat_status_indicator.set_status(True)
                            self.wechat_status_label.setText("已连接")
                            self.wechat_status_label.setStyleSheet("color: green; font-weight: bold;")
                            self.wechat_status_indicator.setProperty("connected", True)
                        
                        # 更新窗口名称 - 修复逻辑
                        if window_name:
                            current_text = self.wechat_window_name_label.text()
                            print(f"[DEBUG] PyQt6 - 当前显示的窗口名称: {repr(current_text)}")
                            print(f"[DEBUG] PyQt6 - 准备更新为: {repr(window_name)}")
                            self.wechat_window_name_label.setText(window_name)
                            print(f"[DEBUG] PyQt6 - 窗口名称已更新")
                        else:
                            # 如果没有窗口名称但状态是在线，显示"获取中..."
                            current_text = self.wechat_window_name_label.text()
                            if current_text in ["", "未获取"]:
                                self.wechat_window_name_label.setText("获取中...")
                    else:
                        # 微信状态为offline或其他
                        if self.wechat_status_indicator.property("connected") != False:
                            self.wechat_status_indicator.set_status(False)
                            self.wechat_status_label.setText("未连接")
                            self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
                            self.wechat_window_name_label.setText("未获取")
                            self.wechat_status_indicator.setProperty("connected", False)
                else:
                    # API返回错误
                    if self.wechat_status_indicator.property("connected") != False:
                        self.wechat_status_indicator.set_status(False)
                        self.wechat_status_label.setText("API错误")
                        self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
                        self.wechat_window_name_label.setText("未获取")
                        self.wechat_status_indicator.setProperty("connected", False)
                        
            elif response.status_code == 400:
                # 微信未初始化
                current_text = self.wechat_status_label.text()
                if current_text != "正在初始化":
                    self.wechat_status_indicator.set_status(False)
                    self.wechat_status_label.setText("未初始化")
                    self.wechat_status_label.setStyleSheet("color: orange; font-weight: bold;")
                    self.wechat_window_name_label.setText("未获取")
                    self.wechat_status_indicator.setProperty("connected", False)
            else:
                # 其他HTTP错误
                if self.wechat_status_indicator.property("connected") != False:
                    self.wechat_status_indicator.set_status(False)
                    self.wechat_status_label.setText(f"HTTP {response.status_code}")
                    self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
                    self.wechat_window_name_label.setText("未获取")
                    self.wechat_status_indicator.setProperty("connected", False)
        except requests.exceptions.Timeout:
            # 请求超时
            if self.wechat_status_indicator.property("connected") != False:
                self.wechat_status_indicator.set_status(False)
                self.wechat_status_label.setText("连接超时")
                self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.wechat_window_name_label.setText("未获取")
                self.wechat_status_indicator.setProperty("connected", False)
        except Exception as e:
            # 其他异常
            logger.error(f"检查微信连接状态失败: {str(e)}")
            if self.wechat_status_indicator.property("connected") != False:
                self.wechat_status_indicator.set_status(False)
                self.wechat_status_label.setText("连接错误")
                self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.wechat_window_name_label.setText("未获取")
                self.wechat_status_indicator.setProperty("connected", False)

    def update_current_lib_status(self):
        """更新当前使用的库状态"""
        try:
            # 从配置文件或环境变量获取当前使用的库
            import os
            current_lib = os.environ.get('WECHAT_LIB', 'wxauto')
            
            # 检查配置文件
            try:
                from app import config_manager
                config = config_manager.load_app_config()
                current_lib = config.get('wechat_lib', current_lib)
            except:
                pass
            
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

    def check_wxauto_status(self):
        """检查wxauto库的安装状态"""
        try:
            # 使用wxauto_wrapper模块确保wxauto库能够被正确导入
            from app.wxauto_wrapper import get_wxauto
            wxauto = get_wxauto()
            if wxauto:
                self.wxauto_status_indicator.set_status(True)
                self.wxauto_status_label.setText("已安装")
                self.wxauto_status_label.setStyleSheet("color: green; font-weight: bold;")
                
                # 尝试导入wxauto包装器
                try:
                    from app.wxauto_wrapper.wrapper import get_wrapper
                    wrapper = get_wrapper()
                    self.log_message("INFO", "wxauto包装器初始化成功")
                except Exception as e:
                    self.log_message("ERROR", f"初始化wxauto包装器失败: {str(e)}")
                
                return True
            else:
                self.wxauto_status_indicator.set_status(False)
                self.wxauto_status_label.setText("未安装")
                self.wxauto_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.log_message("ERROR", "wxauto库导入失败")
                return False
        except ImportError as e:
            self.wxauto_status_indicator.set_status(False)
            self.wxauto_status_label.setText("未安装")
            self.wxauto_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.log_message("ERROR", f"导入wxauto_wrapper模块失败: {str(e)}")
            return False
        except Exception as e:
            self.wxauto_status_indicator.set_status(False)
            self.wxauto_status_label.setText("检查失败")
            self.wxauto_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.log_message("ERROR", f"检查wxauto状态时出现未知错误: {str(e)}")
            return False

    def check_wxautox_status(self):
        """检查wxautox库的安装状态"""
        # 首先尝试使用动态包管理器检查
        try:
            from app.dynamic_package_manager import get_package_manager
            package_manager = get_package_manager()
            
            if package_manager.is_package_installed("wxautox"):
                self.wxautox_status_indicator.set_status(True)
                self.wxautox_status_label.setText("已安装")
                self.wxautox_status_label.setStyleSheet("color: green; font-weight: bold;")
                return True
        except ImportError:
            self.log_message("WARNING", "无法导入动态包管理器，使用传统方法检查wxautox状态")

        # 如果动态包管理器不可用或报告未安装，尝试直接导入
        try:
            import wxautox
            self.wxautox_status_indicator.set_status(True)
            self.wxautox_status_label.setText("已安装")
            self.wxautox_status_label.setStyleSheet("color: green; font-weight: bold;")
            return True
        except ImportError:
            self.wxautox_status_indicator.set_status(False)
            self.wxautox_status_label.setText("未安装")
            self.wxautox_status_label.setStyleSheet("color: red; font-weight: bold;")
            return False

    def initial_status_check(self):
        """初始状态检查"""
        try:
            self.log_message("INFO", "正在检查wxauto/wxautox库状态...")
            
            # 检查wxauto状态
            wxauto_ok = self.check_wxauto_status()
            
            # 检查wxautox状态  
            wxautox_ok = self.check_wxautox_status()
            
            # 更新当前库状态
            self.update_current_lib_status()
            
            # 记录检查结果
            if wxauto_ok:
                self.log_message("INFO", "wxauto库检查完成 - 已安装")
            else:
                self.log_message("WARNING", "wxauto库检查完成 - 未安装或无法导入")
                
            if wxautox_ok:
                self.log_message("INFO", "wxautox库检查完成 - 已安装")
            else:
                self.log_message("INFO", "wxautox库检查完成 - 未安装")
                
        except Exception as e:
            self.log_message("ERROR", f"初始状态检查失败: {str(e)}")


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
        QLineEdit, QComboBox, QSpinBox {
            padding: 6px;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            background-color: white;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
            border-color: #3498db;
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

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
