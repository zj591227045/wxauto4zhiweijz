#!/usr/bin/env python3
"""
旧版UI界面集成新模块化架构
保持旧版UI界面和操作逻辑，底层使用新的模块化架构
"""

import sys
import os
import logging
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QLabel, QPushButton,
                             QFrame, QDialog, QLineEdit, QComboBox, QMessageBox,
                             QCheckBox, QSpinBox, QTextEdit, QRadioButton, QButtonGroup,
                             QSplitter, QGroupBox, QListWidget, QScrollArea, QStatusBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QPen, QBrush, QLinearGradient, QIcon

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 导入新的模块化组件
from app.modules import (
    ConfigManager, AccountingManager, WechatServiceManager, 
    WxautoManager, MessageListener, MessageDelivery, 
    LogManager, ServiceMonitor
)

# 导入增强版UI组件（美化版本）
from app.qt_ui.enhanced_ui_components import (EnhancedCircularButton, EnhancedStatusIndicator,
                                              EnhancedStatCard, EnhancedButton, TexturedBackground)

# 导入日志窗口
from app.qt_ui.enhanced_log_window import EnhancedLogWindow

# 导入统一统计系统
from app.utils.unified_statistics import get_unified_statistics

logger = logging.getLogger(__name__)


class LoginThread(QThread):
    """登录线程 - 使用新的记账管理器"""
    login_success = pyqtSignal(object)  # 登录成功信号
    login_failed = pyqtSignal(str)      # 登录失败信号
    
    def __init__(self, accounting_manager, server_url, username, password):
        super().__init__()
        self.accounting_manager = accounting_manager
        self.server_url = server_url
        self.username = username
        self.password = password
    
    def run(self):
        """执行登录操作"""
        try:
            # 使用新的记账管理器登录
            success, message = self.accounting_manager.login(
                self.server_url, self.username, self.password
            )
            
            if success:
                # 登录成功，构建登录数据
                login_data = {
                    'token': self.accounting_manager.get_token(),
                    'username': self.username,
                    'password': self.password,
                    'server_url': self.server_url,
                    'books': []  # 新架构中暂时不需要账本列表
                }
                self.login_success.emit(login_data)
            else:
                self.login_failed.emit(message)
                
        except Exception as e:
            self.login_failed.emit(f"登录过程中发生错误: {str(e)}")


class ConfigDialog(QDialog):
    """配置对话框 - 保持旧版样式"""
    
    def __init__(self, config_type, config_manager=None, accounting_manager=None, 
                 wechat_service_manager=None, parent=None):
        super().__init__(parent)
        self.config_type = config_type
        self.config_manager = config_manager
        self.accounting_manager = accounting_manager
        self.wechat_service_manager = wechat_service_manager
        
        self.setWindowTitle(f"{config_type}配置")
        self.setMinimumSize(450, 400)
        # 不设置固定大小，让对话框根据内容自动调整
        
        # 保持旧版样式
        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
                color: white;
            }
            QLabel {
                color: white;
                font-size: 12px;
                margin: 4px 0;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #334155;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 8px;
                color: white;
                font-size: 12px;
                min-height: 20px;
            }
            QCheckBox {
                color: white;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #475569;
                border-radius: 3px;
                background-color: #334155;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
            QRadioButton {
                color: white;
                font-size: 14px;
                font-weight: bold;
                spacing: 8px;
                padding: 4px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #475569;
                border-radius: 8px;
                background-color: #334155;
            }
            QRadioButton::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
            QPushButton {
                background-color: #3b82f6;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #6b7280;
                color: #9ca3af;
            }
            QTextEdit {
                background-color: #334155;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 8px;
                color: white;
                font-size: 12px;
            }
        """)
        
        self.setup_ui()

        # 设置窗口自适应内容
        self.adjustSize()

        # 确保窗口不会太小
        if self.height() < 500:
            self.resize(self.width(), 500)
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        if self.config_type == "只为记账服务":
            self.setup_accounting_ui(layout)
        elif self.config_type == "微信监控服务":
            self.setup_wechat_ui(layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        
        self.save_btn.clicked.connect(self.save_config)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # 加载配置并调整大小
        self.load_current_config()
        # 调整对话框大小以适应内容
        self.adjustSize()
    
    def setup_accounting_ui(self, layout):
        """设置记账服务UI"""
        # 服务器地址
        layout.addWidget(QLabel("服务器地址:"))
        self.server_edit = QLineEdit()
        layout.addWidget(self.server_edit)

        # 用户名
        layout.addWidget(QLabel("用户名(邮箱):"))
        self.username_edit = QLineEdit()
        layout.addWidget(self.username_edit)

        # 密码
        layout.addWidget(QLabel("密码:"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_edit)

        # 登录按钮
        login_layout = QHBoxLayout()
        self.login_btn = QPushButton("测试连接")
        self.login_btn.clicked.connect(self.test_accounting_connection)
        login_layout.addWidget(self.login_btn)
        login_layout.addStretch()
        layout.addLayout(login_layout)

        # 状态显示
        self.status_label = QLabel("状态: 未连接")
        self.status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
        layout.addWidget(self.status_label)

        # 账本选择区域
        layout.addWidget(QLabel("选择账本:"))
        account_layout = QHBoxLayout()

        self.account_book_combo = QComboBox()
        self.account_book_combo.currentTextChanged.connect(self.on_account_book_changed)
        account_layout.addWidget(self.account_book_combo)

        self.refresh_books_btn = QPushButton("刷新账本")
        self.refresh_books_btn.clicked.connect(self.refresh_account_books)
        self.refresh_books_btn.setEnabled(False)  # 初始状态禁用，登录成功后启用
        account_layout.addWidget(self.refresh_books_btn)

        layout.addLayout(account_layout)

        # 账本状态显示
        self.account_status_label = QLabel("账本: 未选择")
        self.account_status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(self.account_status_label)
    
    def setup_wechat_ui(self, layout):
        """设置微信配置UI - 基于旧版本的完整功能"""
        # 1. 自动化库选择功能
        layout.addWidget(QLabel("微信自动化库选择:"))

        # 创建单选框组
        self.library_group = QButtonGroup()
        library_layout = QHBoxLayout()

        self.wxauto_radio = QRadioButton("wxauto (开源版)")
        self.wxautox_radio = QRadioButton("wxautox (Plus版)")

        # 设置单选框样式
        radio_style = """
            QRadioButton {
                color: white;
                font-size: 14px;
                font-weight: bold;
                spacing: 8px;
                padding: 4px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #64748b;
                background-color: transparent;
            }
            QRadioButton::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
            QRadioButton::indicator:hover {
                border-color: #64748b;
            }
        """

        self.wxauto_radio.setStyleSheet(radio_style)
        self.wxautox_radio.setStyleSheet(radio_style)

        self.library_group.addButton(self.wxauto_radio, 0)
        self.library_group.addButton(self.wxautox_radio, 1)

        # 连接信号
        self.wxauto_radio.toggled.connect(self.on_library_changed)
        self.wxautox_radio.toggled.connect(self.on_library_changed)

        library_layout.addWidget(self.wxauto_radio)
        library_layout.addWidget(self.wxautox_radio)
        library_layout.addStretch()

        library_widget = QWidget()
        library_widget.setLayout(library_layout)
        layout.addWidget(library_widget)

        # 显示库状态
        self.wxauto_status_label = QLabel("检查中...")
        self.wxautox_status_label = QLabel("检查中...")

        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("wxauto状态:"))
        status_layout.addWidget(self.wxauto_status_label)
        status_layout.addWidget(QLabel("wxautox状态:"))
        status_layout.addWidget(self.wxautox_status_label)
        status_layout.addStretch()

        status_widget = QWidget()
        status_widget.setLayout(status_layout)
        layout.addWidget(status_widget)

        # 检查库状态
        self.check_library_status()

        # 2. wxautox激活功能区域
        self.activation_widget = QWidget()
        activation_layout = QVBoxLayout(self.activation_widget)

        activation_layout.addWidget(QLabel("wxautox激活码:"))

        activation_input_layout = QHBoxLayout()
        self.activation_code_edit = QLineEdit()
        self.activation_code_edit.setPlaceholderText("请输入wxautox激活码")
        self.activation_btn = QPushButton("激活")
        self.activation_btn.clicked.connect(self.activate_wxautox)

        activation_input_layout.addWidget(self.activation_code_edit)
        activation_input_layout.addWidget(self.activation_btn)

        activation_layout.addLayout(activation_input_layout)

        # 激活状态显示
        self.activation_status_label = QLabel("")
        activation_layout.addWidget(self.activation_status_label)

        layout.addWidget(self.activation_widget)

        # 默认隐藏激活区域
        self.activation_widget.setVisible(False)

        # 3. 监听会话管理
        layout.addWidget(QLabel("监听会话管理:"))

        # 会话列表和操作按钮
        sessions_layout = QHBoxLayout()

        # 左侧：会话列表
        sessions_left_layout = QVBoxLayout()
        sessions_left_layout.addWidget(QLabel("当前监听会话:"))

        self.sessions_list = QListWidget()
        self.sessions_list.setMaximumHeight(120)
        sessions_left_layout.addWidget(self.sessions_list)

        # 右侧：操作按钮
        sessions_right_layout = QVBoxLayout()

        # 添加会话
        add_session_layout = QHBoxLayout()
        self.session_input = QLineEdit()
        self.session_input.setPlaceholderText("输入会话名称")
        self.add_session_btn = QPushButton("添加会话")
        self.add_session_btn.clicked.connect(self.add_session)

        add_session_layout.addWidget(self.session_input)
        add_session_layout.addWidget(self.add_session_btn)
        sessions_right_layout.addLayout(add_session_layout)

        # 删除会话
        self.remove_session_btn = QPushButton("删除选中会话")
        self.remove_session_btn.clicked.connect(self.remove_session)
        sessions_right_layout.addWidget(self.remove_session_btn)

        sessions_right_layout.addStretch()

        sessions_layout.addLayout(sessions_left_layout, 2)
        sessions_layout.addLayout(sessions_right_layout, 1)

        sessions_widget = QWidget()
        sessions_widget.setLayout(sessions_layout)
        layout.addWidget(sessions_widget)

        # 4. 监听间隔设置
        layout.addWidget(QLabel("监听间隔设置:"))

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("检查间隔:"))

        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 300)
        self.interval_spinbox.setValue(5)
        self.interval_spinbox.setSuffix(" 秒")

        interval_layout.addWidget(self.interval_spinbox)
        interval_layout.addStretch()

        interval_widget = QWidget()
        interval_widget.setLayout(interval_layout)
        layout.addWidget(interval_widget)

        # 5. 其他配置选项
        self.enabled_check = QCheckBox("启用微信监控")
        layout.addWidget(self.enabled_check)

        self.auto_reply_check = QCheckBox("启用自动回复")
        layout.addWidget(self.auto_reply_check)

        layout.addWidget(QLabel("回复模板:"))
        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("自动回复的消息模板")
        layout.addWidget(self.template_edit)

    def check_library_status(self):
        """检查wxauto和wxautox库的安装状态"""
        try:
            # 检查wxauto
            try:
                import wxauto
                self.wxauto_status_label.setText("✓ 已安装")
                self.wxauto_status_label.setStyleSheet("color: #10b981; font-weight: bold;")
            except ImportError:
                self.wxauto_status_label.setText("✗ 未安装")
                self.wxauto_status_label.setStyleSheet("color: #ef4444; font-weight: bold;")

            # 检查wxautox
            try:
                import wxautox
                self.wxautox_status_label.setText("✓ 已安装")
                self.wxautox_status_label.setStyleSheet("color: #10b981; font-weight: bold;")
            except ImportError:
                self.wxautox_status_label.setText("✗ 未安装")
                self.wxautox_status_label.setStyleSheet("color: #ef4444; font-weight: bold;")

        except Exception as e:
            logger.error(f"检查库状态失败: {e}")

    def on_library_changed(self):
        """库选择变化时的处理"""
        if hasattr(self, 'wxautox_radio') and self.wxautox_radio.isChecked():
            # 选择wxautox时显示激活区域
            self.activation_widget.setVisible(True)
        else:
            # 选择wxauto时隐藏激活区域
            self.activation_widget.setVisible(False)

        # 调整对话框大小以适应内容
        self.adjustSize()

    def activate_wxautox(self):
        """激活wxautox"""
        activation_code = self.activation_code_edit.text().strip()
        if not activation_code:
            QMessageBox.warning(self, "警告", "请输入激活码")
            return

        try:
            import subprocess
            import sys

            # 执行激活命令
            self.activation_btn.setEnabled(False)
            self.activation_btn.setText("激活中...")
            self.activation_status_label.setText("正在激活...")
            self.activation_status_label.setStyleSheet("color: #fbbf24;")

            # 使用subprocess执行激活命令
            result = subprocess.run(
                [sys.executable, "-m", "wxautox", "-a", activation_code],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                self.activation_status_label.setText("✓ 激活成功")
                self.activation_status_label.setStyleSheet("color: #10b981; font-weight: bold;")
                QMessageBox.information(self, "成功", "wxautox激活成功！")
            else:
                error_msg = result.stderr or result.stdout or "激活失败"
                self.activation_status_label.setText(f"✗ 激活失败: {error_msg}")
                self.activation_status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
                QMessageBox.warning(self, "失败", f"激活失败: {error_msg}")

        except subprocess.TimeoutExpired:
            self.activation_status_label.setText("✗ 激活超时")
            self.activation_status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
            QMessageBox.warning(self, "超时", "激活请求超时，请检查网络连接")
        except Exception as e:
            self.activation_status_label.setText(f"✗ 激活错误: {str(e)}")
            self.activation_status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
            QMessageBox.critical(self, "错误", f"激活过程中发生错误: {str(e)}")
        finally:
            self.activation_btn.setEnabled(True)
            self.activation_btn.setText("激活")

    def add_session(self):
        """添加监控会话"""
        session_name = self.session_input.text().strip()
        if not session_name:
            QMessageBox.warning(self, "警告", "请输入会话名称")
            return

        # 检查是否已存在
        for i in range(self.sessions_list.count()):
            if self.sessions_list.item(i).text() == session_name:
                QMessageBox.warning(self, "警告", "该会话已存在")
                return

        # 添加到列表
        self.sessions_list.addItem(session_name)
        self.session_input.clear()
        logger.info(f"添加监控会话: {session_name}")

    def remove_session(self):
        """删除选中的会话"""
        current_item = self.sessions_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请选择要删除的会话")
            return

        session_name = current_item.text()
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除会话 '{session_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            row = self.sessions_list.row(current_item)
            self.sessions_list.takeItem(row)
            logger.info(f"删除监控会话: {session_name}")

    def load_current_config(self):
        """加载当前配置"""
        if not self.config_manager:
            return

        try:
            if self.config_type == "只为记账服务":
                config = self.config_manager.get_accounting_config()
                self.server_edit.setText(config.server_url)
                self.username_edit.setText(config.username)
                self.password_edit.setText(config.password)

                # 检查连接状态
                if self.accounting_manager and self.accounting_manager.get_token():
                    self.status_label.setText("状态: 已连接")
                    self.status_label.setStyleSheet("color: #22c55e; font-weight: bold;")

                    # 如果已连接，启用账本刷新按钮并尝试加载账本
                    if hasattr(self, 'refresh_books_btn'):
                        self.refresh_books_btn.setEnabled(True)
                        # 如果有保存的账本信息，显示在状态中
                        if hasattr(config, 'account_book_name') and config.account_book_name:
                            self.account_status_label.setText(f"账本: {config.account_book_name}")
                            self.account_status_label.setStyleSheet("color: #22c55e; font-size: 11px;")

            elif self.config_type == "微信监控服务":
                # 加载微信监控配置
                wechat_config = self.config_manager.get_wechat_monitor_config()
                wxauto_config = self.config_manager.get_wxauto_config()

                # 设置库选择
                library_type = wxauto_config.library_type
                if library_type == "wxauto":
                    self.wxauto_radio.setChecked(True)
                else:
                    self.wxautox_radio.setChecked(True)

                # 触发库选择变化事件
                self.on_library_changed()

                # 加载监控会话列表
                self.sessions_list.clear()
                for chat in wechat_config.monitored_chats:
                    self.sessions_list.addItem(chat)

                # 设置监听间隔（从服务监控配置获取）
                service_config = self.config_manager.get_service_monitor_config()
                self.interval_spinbox.setValue(service_config.message_check_interval)

                # 设置其他配置
                self.enabled_check.setChecked(wechat_config.enabled)
                self.auto_reply_check.setChecked(wechat_config.auto_reply)
                self.template_edit.setText(wechat_config.reply_template)

        except Exception as e:
            logger.error(f"加载配置失败: {e}")
    
    def test_accounting_connection(self):
        """测试记账连接"""
        try:
            server_url = self.server_edit.text().strip()
            username = self.username_edit.text().strip()
            password = self.password_edit.text().strip()
            
            if not all([server_url, username, password]):
                QMessageBox.warning(self, "警告", "请填写完整的连接信息")
                return
            
            self.login_btn.setEnabled(False)
            self.login_btn.setText("连接中...")
            
            # 创建登录线程
            self.login_thread = LoginThread(
                self.accounting_manager, server_url, username, password
            )
            self.login_thread.login_success.connect(self.on_login_success)
            self.login_thread.login_failed.connect(self.on_login_failed)
            self.login_thread.start()
            
        except Exception as e:
            logger.error(f"测试连接失败: {e}")
            QMessageBox.warning(self, "错误", f"测试连接失败: {str(e)}")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("测试连接")
    
    def on_login_success(self, login_data):
        """登录成功"""
        self.status_label.setText("状态: 连接成功")
        self.status_label.setStyleSheet("color: #22c55e; font-weight: bold;")
        self.login_btn.setEnabled(True)
        self.login_btn.setText("测试连接")

        # 启用账本刷新按钮
        if hasattr(self, 'refresh_books_btn'):
            self.refresh_books_btn.setEnabled(True)
            # 自动刷新账本列表
            self.refresh_account_books()

        QMessageBox.information(self, "成功", "连接测试成功！")
    
    def on_login_failed(self, error_message):
        """登录失败"""
        self.status_label.setText("状态: 连接失败")
        self.status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
        self.login_btn.setEnabled(True)
        self.login_btn.setText("测试连接")

        # 禁用账本刷新按钮
        if hasattr(self, 'refresh_books_btn'):
            self.refresh_books_btn.setEnabled(False)

        QMessageBox.warning(self, "失败", f"连接测试失败: {error_message}")

    def refresh_account_books(self):
        """刷新账本列表"""
        try:
            if not self.accounting_manager:
                QMessageBox.warning(self, "错误", "记账管理器未初始化")
                return

            # 检查是否已登录
            if not self.accounting_manager.get_token():
                QMessageBox.warning(self, "错误", "请先测试连接并登录")
                return

            self.refresh_books_btn.setEnabled(False)
            self.refresh_books_btn.setText("刷新中...")

            # 获取账本列表
            success, message, account_books = self.accounting_manager.get_account_books()

            if success and account_books:
                # 清空现有选项
                self.account_book_combo.clear()

                # 添加账本选项
                for book in account_books:
                    display_text = book['name']
                    if book['is_default']:
                        display_text += " (默认)"
                    self.account_book_combo.addItem(display_text, book['id'])

                # 尝试选择之前保存的账本
                if self.config_manager:
                    config = self.config_manager.get_accounting_config()
                    if hasattr(config, 'account_book_id') and config.account_book_id:
                        index = self.account_book_combo.findData(config.account_book_id)
                        if index >= 0:
                            self.account_book_combo.setCurrentIndex(index)

                self.account_status_label.setText(f"账本: 已加载 {len(account_books)} 个账本")
                self.account_status_label.setStyleSheet("color: #22c55e; font-size: 11px;")
                logger.info(f"成功获取 {len(account_books)} 个账本")

            else:
                self.account_status_label.setText("账本: 获取失败")
                self.account_status_label.setStyleSheet("color: #ef4444; font-size: 11px;")
                QMessageBox.warning(self, "获取账本失败", message or "未知错误")

        except Exception as e:
            logger.error(f"刷新账本列表失败: {e}")
            self.account_status_label.setText("账本: 刷新失败")
            self.account_status_label.setStyleSheet("color: #ef4444; font-size: 11px;")
            QMessageBox.warning(self, "错误", f"刷新账本列表失败: {str(e)}")
        finally:
            self.refresh_books_btn.setEnabled(True)
            self.refresh_books_btn.setText("刷新账本")

    def on_account_book_changed(self):
        """账本选择变更"""
        try:
            current_text = self.account_book_combo.currentText()
            current_data = self.account_book_combo.currentData()

            if current_text and current_data:
                # 更新状态显示
                self.account_status_label.setText(f"账本: {current_text}")
                self.account_status_label.setStyleSheet("color: #22c55e; font-size: 11px;")

                # 保存选择的账本到配置
                if self.config_manager:
                    self.config_manager.update_accounting_config(
                        account_book_id=current_data,
                        account_book_name=current_text.replace(" (默认)", "")
                    )

                logger.info(f"选择账本: {current_text}")
            else:
                self.account_status_label.setText("账本: 未选择")
                self.account_status_label.setStyleSheet("color: #64748b; font-size: 11px;")

        except Exception as e:
            logger.error(f"账本选择变更处理失败: {e}")
    
    def save_config(self):
        """保存配置"""
        try:
            if self.config_type == "只为记账服务":
                # 保存记账配置
                config_data = {
                    'server_url': self.server_edit.text().strip(),
                    'username': self.username_edit.text().strip(),
                    'password': self.password_edit.text().strip()
                }

                # 如果有选择账本，也保存账本信息
                if hasattr(self, 'account_book_combo') and self.account_book_combo.currentData():
                    config_data['account_book_id'] = self.account_book_combo.currentData()
                    config_data['account_book_name'] = self.account_book_combo.currentText().replace(" (默认)", "")

                success = self.config_manager.update_accounting_config(**config_data)

                if success:
                    QMessageBox.information(self, "成功", "记账服务配置保存成功！")
                    self.accept()
                else:
                    QMessageBox.warning(self, "失败", "配置保存失败")
                    
            elif self.config_type == "微信监控服务":
                # 保存微信配置
                # 获取监控会话列表
                monitored_chats = []
                for i in range(self.sessions_list.count()):
                    monitored_chats.append(self.sessions_list.item(i).text())

                # 获取选中的库类型
                library_type = 'wxauto' if self.wxauto_radio.isChecked() else 'wxautox'

                # 保存wxauto配置
                wxauto_success = self.config_manager.update_wxauto_config(
                    library_type=library_type
                )

                # 保存微信监控配置
                wechat_success = self.config_manager.update_wechat_monitor_config(
                    enabled=self.enabled_check.isChecked(),
                    monitored_chats=monitored_chats,
                    auto_reply=self.auto_reply_check.isChecked(),
                    reply_template=self.template_edit.text().strip()
                )

                # 保存监听间隔到服务监控配置
                service_success = self.config_manager.update_service_monitor_config(
                    message_check_interval=self.interval_spinbox.value()
                )

                success = wxauto_success and wechat_success and service_success
                
                if success:
                    QMessageBox.information(self, "成功", "微信监控配置保存成功！")
                    self.accept()
                else:
                    QMessageBox.warning(self, "失败", "配置保存失败")
                    
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.warning(self, "错误", f"保存配置失败: {str(e)}")


class LegacyMainWindow(QMainWindow):
    """旧版主窗口 - 集成新模块化架构"""
    
    def __init__(self):
        super().__init__()
        
        # 核心模块管理器
        self.config_manager = None
        self.accounting_manager = None
        self.wechat_service_manager = None
        self.wxauto_manager = None
        self.message_listener = None
        self.message_delivery = None
        self.log_manager = None
        self.service_monitor = None
        
        # UI状态
        self.is_monitoring = False
        self.monitored_chats = []
        
        # 统计数据
        self.stats = {
            'total_processed': 0,
            'successful_accounting': 0,
            'failed_accounting': 0,
            'irrelevant_messages': 0
        }
        
        # 初始化
        self.init_modules()
        self.init_ui()
        self.setup_connections()
        self.start_modules()

        # 加载统一统计数据
        self.load_unified_statistics()

        logger.info("旧版UI主窗口初始化完成（使用新模块化架构）")

    def load_unified_statistics(self):
        """从统一统计系统加载初始统计数据"""
        try:
            # 获取统一统计系统
            unified_stats = get_unified_statistics()
            stats = unified_stats.get_statistics()

            # 更新本地统计数据
            self.stats['total_processed'] = stats.total_processed
            self.stats['successful_accounting'] = stats.accounting_success
            self.stats['failed_accounting'] = stats.accounting_failed
            self.stats['irrelevant_messages'] = stats.accounting_irrelevant

            # 更新UI显示
            self.update_stats_display()

            logger.info(f"加载统一统计数据: 处理={stats.total_processed}, 成功={stats.accounting_success}, 失败={stats.accounting_failed}, 无关={stats.accounting_irrelevant}")

        except Exception as e:
            logger.error(f"加载统一统计数据失败: {e}")

    def refresh_stats_from_unified_system(self):
        """从统一统计系统刷新统计数据"""
        try:
            # 获取统一统计系统
            unified_stats = get_unified_statistics()
            stats = unified_stats.get_statistics()

            # 更新本地统计数据
            self.stats['total_processed'] = stats.total_processed
            self.stats['successful_accounting'] = stats.accounting_success
            self.stats['failed_accounting'] = stats.accounting_failed
            self.stats['irrelevant_messages'] = stats.accounting_irrelevant

            # 更新UI显示
            self.update_stats_display()

            logger.debug(f"刷新统计数据: 处理={stats.total_processed}, 成功={stats.accounting_success}, 失败={stats.accounting_failed}, 无关={stats.accounting_irrelevant}")

        except Exception as e:
            logger.error(f"刷新统计数据失败: {e}")

    def init_modules(self):
        """初始化所有模块"""
        try:
            # 1. 配置管理器（最先初始化）
            self.config_manager = ConfigManager(parent=self)
            
            # 2. 日志管理器
            self.log_manager = LogManager(parent=self)
            
            # 3. wxauto管理器
            self.wxauto_manager = WxautoManager(parent=self)
            
            # 4. 记账管理器
            self.accounting_manager = AccountingManager(config_manager=self.config_manager, parent=self)
            
            # 5. 微信服务管理器
            self.wechat_service_manager = WechatServiceManager(
                wxauto_manager=self.wxauto_manager,
                parent=self
            )
            
            # 6. 消息监听器
            self.message_listener = MessageListener(
                wxauto_manager=self.wxauto_manager,
                parent=self
            )
            
            # 7. 消息投递服务
            self.message_delivery = MessageDelivery(
                accounting_manager=self.accounting_manager,
                wxauto_manager=self.wxauto_manager,
                parent=self
            )
            
            # 8. 服务监控器
            self.service_monitor = ServiceMonitor(parent=self)
            
            logger.info("所有模块初始化完成")
            
        except Exception as e:
            logger.error(f"模块初始化失败: {e}")
            QMessageBox.critical(self, "错误", f"模块初始化失败: {str(e)}")
    
    def init_ui(self):
        """初始化UI - 使用增强版美化组件"""
        self.setWindowTitle("只为记账--微信助手")
        self.setFixedSize(520, 680)  # 稍微增大以容纳阴影效果

        # 创建纹理背景
        self.textured_background = TexturedBackground()
        self.setCentralWidget(self.textured_background)

        # 主布局
        main_layout = QVBoxLayout(self.textured_background)
        main_layout.setSpacing(35)
        main_layout.setContentsMargins(45, 45, 45, 45)

        # 标题
        title_label = QLabel("只为记账--微信助手")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 28px;
                font-weight: bold;
                margin: 20px 0;
            }
        """)
        main_layout.addWidget(title_label)

        # 状态指示器区域
        status_layout = QHBoxLayout()
        status_layout.setSpacing(20)

        # 只为记账服务状态
        self.accounting_indicator = EnhancedStatusIndicator(
            "只为记账服务",
            "账号: zhangjie@jacksonz.cn\n联系: 我们的家庭账本"
        )
        self.accounting_indicator.clicked.connect(lambda: self.open_config_dialog('只为记账服务'))
        status_layout.addWidget(self.accounting_indicator)

        # 微信状态
        self.wechat_indicator = EnhancedStatusIndicator(
            "微信监控服务",
            "wxauto: 已加载\n微信: 助手"
        )
        self.wechat_indicator.clicked.connect(lambda: self.open_config_dialog('微信监控服务'))
        status_layout.addWidget(self.wechat_indicator)

        main_layout.addLayout(status_layout)

        # 主控按钮
        button_layout = QVBoxLayout()

        # 按钮容器
        btn_container = QHBoxLayout()
        btn_container.addStretch()

        self.main_button = EnhancedCircularButton("开始监听")
        self.main_button.clicked.connect(self.toggle_monitoring)
        btn_container.addWidget(self.main_button)

        btn_container.addStretch()
        button_layout.addLayout(btn_container)

        # 进度显示标签
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("""
            QLabel {
                color: #f59e0b;
                font-size: 14px;
                font-weight: bold;
                margin: 10px 0;
                padding: 5px;
                background: rgba(245, 158, 11, 0.1);
                border-radius: 5px;
                min-height: 20px;
            }
        """)
        self.progress_label.hide()  # 初始隐藏
        button_layout.addWidget(self.progress_label)

        main_layout.addLayout(button_layout)

        # 统计卡片区域
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)

        self.processed_card = EnhancedStatCard("处理消息数", 0)
        self.success_card = EnhancedStatCard("成功记账数", 0)
        self.failed_card = EnhancedStatCard("失败记账数", 0)

        stats_layout.addWidget(self.processed_card)
        stats_layout.addWidget(self.success_card)
        stats_layout.addWidget(self.failed_card)

        main_layout.addLayout(stats_layout)

        # 底部按钮 - 查看日志按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        # 查看日志按钮 - 使用增强版按钮
        log_btn = EnhancedButton("查看日志")
        log_btn.clicked.connect(self.show_logs)
        bottom_layout.addWidget(log_btn)

        main_layout.addLayout(bottom_layout)

        # 启动纹理动画（可选）
        # self.textured_background.start_texture_animation()

    def open_config_dialog(self, config_type):
        """打开配置对话框"""
        try:
            dialog = ConfigDialog(config_type, self.config_manager, self.accounting_manager, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # 配置已保存，更新UI状态
                self.update_ui_from_config()
                logger.info(f"{config_type}配置已更新")
        except Exception as e:
            logger.error(f"打开配置对话框失败: {e}")
            QMessageBox.warning(self, "错误", f"打开配置失败: {str(e)}")

    def show_logs(self):
        """显示日志窗口"""
        try:
            if not hasattr(self, 'log_window') or self.log_window is None:
                from app.qt_ui.enhanced_log_window import EnhancedLogWindow
                self.log_window = EnhancedLogWindow(self.log_manager, self)

            self.log_window.show()
            self.log_window.raise_()
            self.log_window.activateWindow()

        except Exception as e:
            logger.error(f"显示日志窗口失败: {e}")
            QMessageBox.warning(self, "错误", f"显示日志窗口失败: {str(e)}")

    def update_stats_display(self):
        """更新统计显示"""
        try:
            self.total_card.set_value(self.stats['total_processed'])
            self.success_card.set_value(self.stats['successful_accounting'])
            self.failed_card.set_value(self.stats['failed_accounting'])
            self.irrelevant_card.set_value(self.stats['irrelevant_messages'])
        except Exception as e:
            logger.error(f"更新统计显示失败: {e}")







    def setup_connections(self):
        """设置信号连接"""
        try:
            # 配置管理器信号
            if self.config_manager:
                self.config_manager.config_loaded.connect(self.on_config_loaded)
                self.config_manager.config_changed.connect(self.on_config_changed)

            # 记账管理器信号
            if self.accounting_manager:
                self.accounting_manager.login_completed.connect(self.on_accounting_login)
                self.accounting_manager.accounting_completed.connect(self.on_accounting_completed)

            # 微信服务管理器信号
            if self.wechat_service_manager:
                self.wechat_service_manager.monitoring_started.connect(self.on_monitoring_started)
                self.wechat_service_manager.monitoring_stopped.connect(self.on_monitoring_stopped)
                self.wechat_service_manager.stats_updated.connect(self.on_stats_updated)

            # wxauto管理器信号
            if self.wxauto_manager:
                self.wxauto_manager.instance_initialized.connect(self.on_wxauto_initialized)
                self.wxauto_manager.connection_status_changed.connect(self.on_wxauto_connection_changed)

            # 消息监听器信号
            if self.message_listener:
                self.message_listener.new_message_received.connect(self.on_new_message)
                self.message_listener.listening_started.connect(self.on_listening_started)
                self.message_listener.listening_stopped.connect(self.on_listening_stopped)

            # 消息投递服务信号
            if self.message_delivery:
                self.message_delivery.accounting_completed.connect(self.on_delivery_accounting_completed)
                self.message_delivery.wechat_reply_sent.connect(self.on_wechat_reply_sent)

            # 服务监控器信号
            if self.service_monitor:
                self.service_monitor.service_status_changed.connect(self.on_service_status_changed)
                self.service_monitor.service_failed.connect(self.on_service_failed)
                self.service_monitor.service_recovered.connect(self.on_service_recovered)

            logger.info("信号连接设置完成")

        except Exception as e:
            logger.error(f"设置信号连接失败: {e}")

    def start_modules(self):
        """启动所有模块"""
        try:
            # 按依赖顺序启动模块
            modules_to_start = [
                ("配置管理器", self.config_manager),
                ("日志管理器", self.log_manager),
                ("wxauto管理器", self.wxauto_manager),
                ("记账管理器", self.accounting_manager),
                ("微信服务管理器", self.wechat_service_manager),
                ("消息监听器", self.message_listener),
                ("消息投递服务", self.message_delivery),
                ("服务监控器", self.service_monitor)
            ]

            for name, module in modules_to_start:
                if module:
                    if module.start():
                        logger.info(f"{name}启动成功")
                    else:
                        logger.error(f"{name}启动失败")
                        QMessageBox.warning(self, "警告", f"{name}启动失败")

            # 注册服务到监控器
            self.register_services_to_monitor()

            # 启动服务监控
            if self.service_monitor:
                self.service_monitor.start_monitoring()

            logger.info("所有模块启动完成")

        except Exception as e:
            logger.error(f"启动模块失败: {e}")
            QMessageBox.critical(self, "错误", f"启动模块失败: {str(e)}")

    def register_services_to_monitor(self):
        """注册服务到监控器"""
        try:
            if not self.service_monitor:
                return

            # 注册各个服务
            services = [
                ("accounting_manager", self.accounting_manager),
                ("wxauto_manager", self.wxauto_manager),
                ("wechat_service_manager", self.wechat_service_manager),
                ("message_listener", self.message_listener),
                ("message_delivery", self.message_delivery),
                ("log_manager", self.log_manager)
            ]

            for service_name, service in services:
                if service:
                    self.service_monitor.register_service(
                        service_name,
                        service.check_health,
                        getattr(service, 'restart', None)
                    )

            logger.info("服务注册到监控器完成")

        except Exception as e:
            logger.error(f"注册服务到监控器失败: {e}")

    # 信号处理方法

    def on_config_loaded(self, config_data):
        """配置加载完成"""
        logger.info("配置加载完成")
        self.update_ui_from_config()

    def on_config_changed(self, section, config_data):
        """配置变更"""
        logger.info(f"配置变更: {section}")
        self.update_ui_from_config()

    def on_accounting_login(self, success, message, user_info):
        """记账服务登录结果"""
        if success:
            self.accounting_indicator.set_active(True)
            self.accounting_indicator.set_subtitle("已连接")
            logger.info("记账服务登录成功")
        else:
            self.accounting_indicator.set_active(False)
            self.accounting_indicator.set_subtitle("登录失败")
            logger.error(f"记账服务登录失败: {message}")

    def on_accounting_completed(self, success, message, data):
        """记账完成"""
        # 不再使用本地计数器，直接从统一统计系统获取最新数据
        self.refresh_stats_from_unified_system()
        logger.info(f"记账完成，统计已更新: 成功={success}")

    def on_monitoring_started(self, chat_names):
        """监控开始"""
        self.monitored_chats = chat_names
        logger.info(f"监控开始: {chat_names}")

    def on_monitoring_stopped(self):
        """监控停止"""
        self.monitored_chats = []
        logger.info("监控停止")

    def on_stats_updated(self, chat_name, stats):
        """统计更新"""
        # 不再使用外部传入的统计数据，直接从统一统计系统获取最新数据
        self.refresh_stats_from_unified_system()
        logger.info(f"收到统计更新信号: {chat_name}, 已刷新统计数据")

    def on_wxauto_initialized(self, success, message, info):
        """wxauto初始化结果"""
        if success:
            self.wechat_indicator.set_active(True)
            self.wechat_indicator.set_subtitle(info.get('window_name', '已连接'))
            logger.info("wxauto初始化成功")
        else:
            self.wechat_indicator.set_active(False)
            self.wechat_indicator.set_subtitle("初始化失败")
            logger.error(f"wxauto初始化失败: {message}")

    def on_wxauto_connection_changed(self, connected, message):
        """wxauto连接状态变化"""
        self.wechat_indicator.set_active(connected)
        self.wechat_indicator.set_subtitle("已连接" if connected else "连接断开")

    def on_new_message(self, chat_name, message_data):
        """收到新消息"""
        logger.info(f"收到新消息: {chat_name} - {message_data.get('sender', '')} - {message_data.get('content', '')[:50]}...")

        # 发送到消息投递服务处理
        if self.message_delivery:
            success, message = self.message_delivery.process_message(
                chat_name,
                message_data.get('content', ''),
                message_data.get('sender_remark', message_data.get('sender', ''))
            )
            if success:
                logger.info(f"消息已加入处理队列: {message}")
            else:
                logger.error(f"消息处理失败: {message}")
        else:
            logger.error("消息投递服务未初始化")

    def on_listening_started(self, chat_names):
        """消息监听开始"""
        logger.info(f"消息监听开始: {chat_names}")

    def on_listening_stopped(self):
        """消息监听停止"""
        logger.info("消息监听停止")

    def on_delivery_accounting_completed(self, chat_name, success, message, data):
        """投递记账完成"""
        # 不再使用本地计数器，直接从统一统计系统获取最新数据
        self.refresh_stats_from_unified_system()
        logger.info(f"投递记账完成: {chat_name}, 成功={success}, 统计已更新")

    def on_wechat_reply_sent(self, chat_name, success, message):
        """微信回复发送结果"""
        if success:
            logger.info(f"回复发送成功: {chat_name}")
        else:
            logger.error(f"回复发送失败: {chat_name} - {message}")

    def on_service_status_changed(self, service_name, old_status, new_status):
        """服务状态变化"""
        logger.info(f"服务状态变化: {service_name} {old_status} -> {new_status}")

    def on_service_failed(self, service_name, error_message):
        """服务失败"""
        logger.error(f"服务失败: {service_name} - {error_message}")

    def on_service_recovered(self, service_name):
        """服务恢复"""
        logger.info(f"服务恢复: {service_name}")

    # UI更新方法

    def update_ui_from_config(self):
        """根据配置更新UI"""
        try:
            if not self.config_manager:
                return

            config = self.config_manager.get_config()

            # 更新监控聊天列表
            monitored_chats = config.wechat_monitor.monitored_chats
            if monitored_chats != self.monitored_chats:
                self.monitored_chats = monitored_chats

                # 更新微信服务管理器
                if self.wechat_service_manager:
                    for chat in monitored_chats:
                        self.wechat_service_manager.add_chat(chat)

            logger.debug("UI已根据配置更新")

        except Exception as e:
            logger.error(f"根据配置更新UI失败: {e}")

    def update_stats_display(self):
        """更新统计显示"""
        self.processed_card.set_value(self.stats['total_processed'])
        self.success_card.set_value(self.stats['successful_accounting'])
        self.failed_card.set_value(self.stats['failed_accounting'])

    def update_progress(self, message: str):
        """更新进度显示"""
        try:
            if hasattr(self, 'progress_label'):
                self.progress_label.setText(message)
                self.progress_label.show()
        except Exception as e:
            logger.error(f"更新进度显示失败: {e}")

    # 用户交互方法

    def toggle_monitoring(self):
        """切换监控状态"""
        try:
            if not self.is_monitoring:
                # 开始监控
                self.update_progress("正在启动监控...")
                if self.start_monitoring():
                    self.is_monitoring = True
                    self.main_button.set_listening_state(True)
                    self.update_progress("监控已启动")
                    # 3秒后隐藏进度标签
                    QTimer.singleShot(3000, lambda: self.progress_label.hide() if hasattr(self, 'progress_label') else None)
                else:
                    self.update_progress("监控启动失败")
                    QTimer.singleShot(3000, lambda: self.progress_label.hide() if hasattr(self, 'progress_label') else None)
            else:
                # 停止监控
                self.update_progress("正在停止监控...")
                if self.stop_monitoring():
                    self.is_monitoring = False
                    self.main_button.set_listening_state(False)
                    self.update_progress("监控已停止")
                    QTimer.singleShot(3000, lambda: self.progress_label.hide() if hasattr(self, 'progress_label') else None)
                else:
                    self.update_progress("监控停止失败")
                    QTimer.singleShot(3000, lambda: self.progress_label.hide() if hasattr(self, 'progress_label') else None)

        except Exception as e:
            logger.error(f"切换监控状态失败: {e}")
            self.update_progress(f"操作失败: {str(e)}")
            QTimer.singleShot(3000, lambda: self.progress_label.hide() if hasattr(self, 'progress_label') else None)
            QMessageBox.warning(self, "错误", f"切换监控状态失败: {str(e)}")

    def start_monitoring(self) -> bool:
        """开始监控"""
        try:
            # 检查前置条件
            if not self.monitored_chats:
                QMessageBox.warning(self, "警告", "请先配置监控聊天")
                return False

            if not self.wxauto_manager or not self.wxauto_manager.is_connected():
                QMessageBox.warning(self, "警告", "微信服务未连接")
                return False

            # 启动消息监听
            if self.message_listener:
                if not self.message_listener.start_listening(self.monitored_chats):
                    QMessageBox.warning(self, "错误", "启动消息监听失败")
                    return False

            # 启动微信服务监控
            if self.wechat_service_manager:
                if not self.wechat_service_manager.start_monitoring():
                    QMessageBox.warning(self, "错误", "启动微信服务监控失败")
                    return False

            logger.info("监控启动成功")
            return True

        except Exception as e:
            logger.error(f"启动监控失败: {e}")
            return False

    def stop_monitoring(self) -> bool:
        """停止监控"""
        try:
            # 停止消息监听
            if self.message_listener:
                self.message_listener.stop_listening()

            # 停止微信服务监控
            if self.wechat_service_manager:
                self.wechat_service_manager.stop_monitoring()

            logger.info("监控停止成功")
            return True

        except Exception as e:
            logger.error(f"停止监控失败: {e}")
            return False

    def open_config_dialog(self, config_type):
        """打开配置对话框"""
        try:
            dialog = ConfigDialog(
                config_type,
                config_manager=self.config_manager,
                accounting_manager=self.accounting_manager,
                wechat_service_manager=self.wechat_service_manager,
                parent=self
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                logger.info(f"{config_type}配置已更新")

        except Exception as e:
            logger.error(f"打开配置对话框失败: {e}")
            QMessageBox.warning(self, "错误", f"打开配置对话框失败: {str(e)}")

    def show_logs(self):
        """显示日志窗口"""
        try:
            # 检查是否已经有日志窗口打开
            if hasattr(self, 'log_window') and self.log_window and self.log_window.isVisible():
                # 如果已经打开，就将其置于前台
                self.log_window.raise_()
                self.log_window.activateWindow()
                return

            # 创建新的日志窗口（不设置父窗口，确保独立显示）
            self.log_window = EnhancedLogWindow(parent=None)

            # 设置窗口位置（相对于主窗口偏移）
            try:
                main_geometry = self.geometry()
                log_x = main_geometry.x() + 50
                log_y = main_geometry.y() + 50
                self.log_window.setGeometry(log_x, log_y, 1000, 600)
            except:
                # 如果获取主窗口位置失败，使用默认位置
                self.log_window.setGeometry(200, 200, 1000, 600)

            # 显示窗口
            self.log_window.show()
            self.log_window.raise_()
            self.log_window.activateWindow()

            logger.info("日志窗口已打开")

        except Exception as e:
            logger.error(f"显示日志窗口失败: {e}")
            QMessageBox.warning(self, "错误", f"显示日志窗口失败: {str(e)}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            logger.info("旧版UI主窗口正在关闭...")

            # 停止监控
            if self.is_monitoring:
                self.stop_monitoring()

            # 停止所有模块
            modules_to_stop = [
                ("服务监控器", self.service_monitor),
                ("消息投递服务", self.message_delivery),
                ("消息监听器", self.message_listener),
                ("微信服务管理器", self.wechat_service_manager),
                ("记账管理器", self.accounting_manager),
                ("wxauto管理器", self.wxauto_manager),
                ("日志管理器", self.log_manager),
                ("配置管理器", self.config_manager)
            ]

            for name, module in modules_to_stop:
                if module:
                    try:
                        module.stop()
                        logger.info(f"{name}已停止")
                    except Exception as e:
                        logger.error(f"停止{name}失败: {e}")

            event.accept()
            logger.info("旧版UI主窗口关闭完成")

        except Exception as e:
            logger.error(f"关闭窗口时出错: {e}")
            event.accept()  # 确保窗口能够关闭


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用程序属性
    app.setApplicationName("只为记账-微信助手")
    app.setApplicationVersion("2.0.0")

    # 创建并显示主窗口
    window = LegacyMainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
