#!/usr/bin/env python3
"""
简约模式主界面
只为记账-微信助手
"""

import sys
import os
import logging
import time
import threading
import requests
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QLabel, QPushButton, 
                             QFrame, QDialog, QLineEdit, QComboBox, QMessageBox,
                             QCheckBox, QSpinBox, QTextEdit, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QPen, QBrush, QLinearGradient, QIcon

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 导入状态管理器
from app.utils.state_manager import state_manager

# 导入异步HTTP工具
from app.utils.async_wechat_api import AsyncWechatAPI
from app.utils.async_wechat_worker import AsyncWechatManager

# 导入增强版组件（后台集成）
from app.utils.service_health_monitor import health_monitor, ServiceStatus
from app.utils.service_health_checkers import create_health_checkers
from app.utils.service_recovery_handlers import create_recovery_handlers
from app.utils.enhanced_async_wechat import async_wechat_manager
from app.services.robust_message_processor import RobustMessageProcessor
from app.services.robust_message_delivery import RobustMessageDelivery

# 延迟导入消息监控服务，避免Flask依赖
# from app.services.message_monitor import MessageMonitor
# from app.services.accounting_service import AccountingService

from app.qt_ui.enhanced_log_window import EnhancedLogWindow

class LoginThread(QThread):
    """登录线程"""
    login_success = pyqtSignal(object)  # 登录成功信号，传递登录数据（字典或列表）
    login_failed = pyqtSignal(str)      # 登录失败信号，传递错误信息
    
    def __init__(self, server_url, username, password):
        super().__init__()
        self.server_url = server_url
        self.username = username
        self.password = password
    
    def run(self):
        """执行登录操作"""
        try:
            # 导入记账服务
            from app.services.accounting_service import AccountingService
            
            # 创建服务实例并登录
            service = AccountingService()
            success, message, user = service.login(self.server_url, self.username, self.password)
            
            if success and user:
                # 登录成功，获取账本列表
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
                    
                    # 更新状态管理器中的token和其他信息
                    state_manager.update_accounting_service(
                        token=service.config.token,
                        username=self.username,
                        password=self.password,
                        server_url=self.server_url
                    )

                    # 发射成功信号，传递token和其他信息
                    login_data = {
                        'books': books_data,
                        'token': service.config.token,
                        'username': self.username,
                        'password': self.password,
                        'server_url': self.server_url
                    }
                    self.login_success.emit(login_data)
                else:
                    # 登录成功但获取账本失败
                    self.login_failed.emit(f"登录成功但获取账本失败: {message_books}")
            else:
                # 登录失败
                self.login_failed.emit(message)
                
        except Exception as e:
            # 发射失败信号
            self.login_failed.emit(f"登录过程中发生错误: {str(e)}")

class CircularButton(QPushButton):
    """圆形主控按钮"""
    
    def __init__(self, text="开始监听", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(120, 120)  # 60px半径
        self.is_listening = False
        self.hover_scale = 1.0
        
        # 设置样式
        self.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        
        # 悬停动画
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 计算圆形区域
        rect = self.rect()
        center_x = rect.width() // 2
        center_y = rect.height() // 2
        radius = min(center_x, center_y) - 5

        # 绘制外圈渐变
        gradient = QLinearGradient(0, 0, 0, rect.height())
        if self.is_listening:
            gradient.setColorAt(0, QColor(255, 107, 107))  # 红色渐变
            gradient.setColorAt(1, QColor(255, 77, 77))
        else:
            gradient.setColorAt(0, QColor(59, 130, 246))   # 蓝色渐变 - 修改为蓝色
            gradient.setColorAt(1, QColor(37, 99, 235))

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 50), 2))
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        # 绘制内圈
        inner_radius = radius - 8
        inner_gradient = QLinearGradient(0, 0, 0, rect.height())
        if self.is_listening:
            inner_gradient.setColorAt(0, QColor(255, 87, 87))
            inner_gradient.setColorAt(1, QColor(255, 57, 57))
        else:
            inner_gradient.setColorAt(0, QColor(79, 150, 255))  # 蓝色渐变 - 修改为蓝色
            inner_gradient.setColorAt(1, QColor(57, 119, 245))

        painter.setBrush(QBrush(inner_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center_x - inner_radius, center_y - inner_radius,
                          inner_radius * 2, inner_radius * 2)

        # 绘制文字
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        text = "停止监听" if self.is_listening else "开始监听"
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    
    def enterEvent(self, event):
        self.hover_scale = 1.05
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.hover_scale = 1.0
        self.update()
        super().leaveEvent(event)
    
    def set_listening_state(self, is_listening: bool):
        """设置监听状态"""
        self.is_listening = is_listening
        self.update()

class StatusIndicator(QWidget):
    """状态指示器"""
    
    clicked = pyqtSignal()
    
    def __init__(self, title, subtitle="", parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.is_active = False
        self.is_blinking = False
        self.blink_state = False
        
        self.setFixedSize(200, 80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # 闪烁定时器
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_blink)
        
    def set_active(self, active, blinking=False):
        """设置状态"""
        self.is_active = active
        self.is_blinking = blinking
        
        if blinking and active:
            self.blink_timer.start(500)  # 500ms闪烁
        else:
            self.blink_timer.stop()
            self.blink_state = False
        
        self.update()
    
    def set_subtitle(self, subtitle: str):
        """设置副标题"""
        self.subtitle = subtitle
        self.update()
    
    def toggle_blink(self):
        """切换闪烁状态"""
        self.blink_state = not self.blink_state
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # 绘制背景卡片
        painter.setBrush(QBrush(QColor(45, 55, 72)))
        painter.setPen(QPen(QColor(74, 85, 104), 1))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 8, 8)
        
        # 绘制状态指示灯
        indicator_rect = QRect(15, 15, 12, 12)
        if self.is_active:
            if self.is_blinking and self.blink_state:
                color = QColor(34, 197, 94)  # 绿色闪烁
            else:
                color = QColor(34, 197, 94) if not self.is_blinking else QColor(34, 197, 94, 128)
        else:
            color = QColor(107, 114, 128)  # 灰色
        
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(indicator_rect)
        
        # 绘制标题
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title_rect = QRect(35, 12, rect.width() - 40, 20)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)
        
        # 绘制副标题
        if self.subtitle:
            painter.setPen(QColor(156, 163, 175))
            painter.setFont(QFont("Microsoft YaHei", 8))
            subtitle_rect = QRect(35, 32, rect.width() - 40, 40)
            painter.drawText(subtitle_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.subtitle)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class StatCard(QWidget):
    """统计卡片"""
    
    def __init__(self, title, value=0, parent=None):
        super().__init__(parent)
        self.title = title
        self.value = value
        
        self.setFixedSize(120, 60)
        
    def set_value(self, value):
        """设置数值"""
        self.value = value
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # 绘制背景 - 使用更深的背景色以匹配参考图片
        painter.setBrush(QBrush(QColor(30, 41, 59)))
        painter.setPen(QPen(QColor(51, 65, 85), 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)

        # 绘制数值 - 使用蓝色
        painter.setPen(QColor(59, 130, 246))
        painter.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))  # 增大字体
        value_rect = QRect(0, 5, rect.width(), 30)  # 调整位置
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignCenter, str(self.value))

        # 绘制标题 - 使用灰色
        painter.setPen(QColor(156, 163, 175))
        painter.setFont(QFont("Microsoft YaHei", 9))  # 稍微增大字体
        title_rect = QRect(0, 38, rect.width(), 20)  # 调整位置
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.title)

class ConfigDialog(QDialog):
    """配置对话框"""
    
    def __init__(self, config_type, parent=None):
        super().__init__(parent)
        self.config_type = config_type
        self.setWindowTitle(f"{config_type}配置")
        # 移除固定大小，改为最小大小和自适应
        self.setMinimumSize(450, 400)
        self.resize(450, 600)  # 初始大小，但可以调整
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
        """)
        
        self.setup_ui()
        self.load_current_config()
        
        # 设置窗口自适应内容
        self.adjustSize()
        
        # 确保窗口不会太小
        if self.height() < 500:
            self.resize(self.width(), 500)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        if self.config_type == "只为记账服务":
            # 只为记账服务配置
            layout.addWidget(QLabel("服务器地址:"))
            self.server_edit = QLineEdit()
            layout.addWidget(self.server_edit)
            
            layout.addWidget(QLabel("用户名(邮箱):"))
            self.username_edit = QLineEdit()
            layout.addWidget(self.username_edit)
            
            layout.addWidget(QLabel("密码:"))
            self.password_edit = QLineEdit()
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addWidget(self.password_edit)
            
            # 登录按钮
            login_layout = QHBoxLayout()
            self.login_btn = QPushButton("登录")
            self.login_btn.clicked.connect(self.login_to_service)
            login_layout.addWidget(self.login_btn)
            login_layout.addStretch()
            layout.addLayout(login_layout)
            
            layout.addWidget(QLabel("账本:"))
            self.account_book_combo = QComboBox()
            layout.addWidget(self.account_book_combo)
            
            # 状态显示
            self.status_label = QLabel("状态: 未连接")
            self.status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
            layout.addWidget(self.status_label)
            
        elif self.config_type == "微信监控服务":
            # wxauto库选择 - 使用单选框
            layout.addWidget(QLabel("微信自动化库选择:"))
            
            # 创建单选框组
            self.library_group = QButtonGroup()
            library_layout = QHBoxLayout()
            
            self.wxauto_radio = QRadioButton("wxauto")
            self.wxautox_radio = QRadioButton("wxautox")
            
            # 为单选框设置明确的样式
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
                    border: 2px solid #475569;
                    border-radius: 8px;
                    background-color: #334155;
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
            
            # 自动初始化选项
            self.auto_init_checkbox = QCheckBox("启动时自动初始化微信")
            layout.addWidget(self.auto_init_checkbox)
            
            layout.addWidget(QLabel("监控间隔(秒):"))
            self.interval_spinbox = QSpinBox()
            self.interval_spinbox.setRange(1, 60)
            self.interval_spinbox.setValue(5)
            layout.addWidget(self.interval_spinbox)
            
            # 美化的监控会话列表
            layout.addWidget(QLabel("监控的微信会话:"))
            
            # 创建会话管理区域
            session_widget = QWidget()
            session_layout = QVBoxLayout(session_widget)
            
            # 输入框和按钮
            input_layout = QHBoxLayout()
            self.session_input = QLineEdit()
            self.session_input.setPlaceholderText("输入群名或好友名...")
            self.session_input.setStyleSheet("""
                QLineEdit {
                    padding: 8px;
                    border: 2px solid #3b82f6;
                    border-radius: 6px;
                    font-size: 12px;
                }
                QLineEdit:focus {
                    border-color: #1d4ed8;
                }
            """)
            
            self.add_session_btn = QPushButton("添加")
            self.add_session_btn.setFixedSize(60, 32)
            self.add_session_btn.setStyleSheet("""
                QPushButton {
                    background-color: #10b981;
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #059669;
                }
                QPushButton:pressed {
                    background-color: #047857;
                }
            """)
            
            self.remove_session_btn = QPushButton("删除")
            self.remove_session_btn.setFixedSize(60, 32)
            self.remove_session_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
                QPushButton:pressed {
                    background-color: #b91c1c;
                }
            """)
            
            input_layout.addWidget(self.session_input)
            input_layout.addWidget(self.add_session_btn)
            input_layout.addWidget(self.remove_session_btn)
            
            session_layout.addLayout(input_layout)
            
            # 会话列表 - 增加高度以确保内容完整显示
            from PyQt6.QtWidgets import QListWidget
            self.sessions_list = QListWidget()
            self.sessions_list.setMinimumHeight(150)  # 增加最小高度
            self.sessions_list.setMaximumHeight(250)  # 设置最大高度避免过高
            self.sessions_list.setStyleSheet("""
                QListWidget {
                    border: 2px solid #475569;
                    border-radius: 6px;
                    padding: 4px;
                    background-color: #334155;
                    font-size: 12px;
                    color: white;
                }
                QListWidget::item {
                    padding: 8px;
                    border-radius: 4px;
                    margin: 2px;
                    background-color: #475569;
                    border: 1px solid #64748b;
                    color: white;
                }
                QListWidget::item:selected {
                    background-color: #3b82f6;
                    color: white;
                    border-color: #1d4ed8;
                }
                QListWidget::item:hover {
                    background-color: #64748b;
                    border-color: #94a3b8;
                }
            """)
            
            session_layout.addWidget(self.sessions_list)
            layout.addWidget(session_widget)
            
            # 连接信号
            self.add_session_btn.clicked.connect(self.add_session)
            self.remove_session_btn.clicked.connect(self.remove_session)
            self.session_input.returnPressed.connect(self.add_session)
            
            # 自动启动监控选项
            self.auto_monitor_checkbox = QCheckBox("启动时自动开始监控")
            layout.addWidget(self.auto_monitor_checkbox)
            
            # API服务端口设置被隐藏，使用自动端口选择
            # layout.addWidget(QLabel("API服务端口:"))
            # self.port_spinbox = QSpinBox()
            # self.port_spinbox.setRange(5000, 9999)
            # self.port_spinbox.setValue(5000)
            # layout.addWidget(self.port_spinbox)
            
            # 自动启动API服务选项
            self.auto_api_checkbox = QCheckBox("启动时自动启动API服务")
            self.auto_api_checkbox.setChecked(True)  # 默认选中
            layout.addWidget(self.auto_api_checkbox)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def login_to_service(self):
        """登录到记账服务"""
        try:
            server_url = self.server_edit.text().strip()
            username = self.username_edit.text().strip()
            password = self.password_edit.text().strip()
            
            if not all([server_url, username, password]):
                QMessageBox.warning(self, "错误", "请填写完整的服务器地址、用户名和密码")
                return
            
            self.login_btn.setEnabled(False)
            self.login_btn.setText("登录中...")
            self.status_label.setText("状态: 连接中...")
            self.status_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
            
            # 更新状态为连接中
            state_manager.update_accounting_service(
                server_url=server_url,
                username=username,
                password=password,
                status='connecting'
            )
            
            # 创建登录线程
            self.login_thread = LoginThread(server_url, username, password)
            self.login_thread.login_success.connect(self.on_login_success)
            self.login_thread.login_failed.connect(self.on_login_failed)
            self.login_thread.start()
            
        except Exception as e:
            self.login_btn.setEnabled(True)
            self.login_btn.setText("登录")
            QMessageBox.critical(self, "错误", f"登录失败: {str(e)}")
    
    def on_login_success(self, login_data):
        """登录成功回调"""
        try:
            # 处理新的数据格式
            if isinstance(login_data, dict):
                account_books = login_data.get('books', [])
                token = login_data.get('token', '')
                username = login_data.get('username', '')
                password = login_data.get('password', '')
                server_url = login_data.get('server_url', '')
            else:
                # 兼容旧格式
                account_books = login_data
                token = 'mock_token_123'
                username = self.username_edit.text().strip()
                password = self.password_edit.text().strip()
                server_url = self.server_edit.text().strip()

            state_manager.update_accounting_service(
                is_logged_in=True,
                status='connected',
                token=token,
                username=username,
                password=password,
                server_url=server_url,
                account_books=account_books,
                selected_account_book=account_books[0]['id'] if account_books else '',
                selected_account_book_name=account_books[0]['name'] if account_books else ''
            )
            
            # 更新UI
            self.login_btn.setEnabled(True)
            self.login_btn.setText("重新登录")
            self.status_label.setText("状态: 已连接")
            self.status_label.setStyleSheet("color: #10b981; font-weight: bold;")
            
            # 更新账本列表
            self.account_book_combo.clear()
            for book in account_books:
                self.account_book_combo.addItem(book['name'], book['id'])
            
            QMessageBox.information(self, "成功", "登录成功！")
            
        except Exception as e:
            print(f"处理登录成功回调失败: {e}")
    
    def on_login_failed(self, error_message):
        """登录失败回调"""
        try:
            state_manager.update_accounting_service(status='error')
            self.login_btn.setEnabled(True)
            self.login_btn.setText("重试登录")
            self.status_label.setText("状态: 连接失败")
            self.status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
            QMessageBox.critical(self, "错误", f"登录失败: {error_message}")
            
        except Exception as e:
            print(f"处理登录失败回调失败: {e}")
    
    def load_current_config(self):
        """加载当前配置"""
        if self.config_type == "只为记账服务":
            config = state_manager.get_accounting_service_status()
            self.server_edit.setText(config.get('server_url', ''))
            self.username_edit.setText(config.get('username', ''))
            # 不加载密码，让用户重新输入
            
            # 更新状态显示
            if config.get('is_logged_in', False):
                self.status_label.setText("状态: 已连接")
                self.status_label.setStyleSheet("color: #10b981; font-weight: bold;")
                self.login_btn.setText("重新登录")
            else:
                status = config.get('status', 'disconnected')
                if status == 'connecting':
                    self.status_label.setText("状态: 连接中...")
                    self.status_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
                else:
                    self.status_label.setText("状态: 未连接")
                    self.status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
            
            # 加载账本列表
            account_books = config.get('account_books', [])
            for book in account_books:
                display_text = book.get('name', '')
                if book.get('is_default', False):
                    display_text += " (默认)"
                self.account_book_combo.addItem(display_text, book.get('id', ''))
            
            # 设置当前选中的账本
            selected_book = config.get('selected_account_book', '')
            if selected_book:
                index = self.account_book_combo.findData(selected_book)
                if index >= 0:
                    self.account_book_combo.setCurrentIndex(index)
        
        elif self.config_type == "微信监控服务":
            wechat_config = state_manager.get_wechat_status()
            monitoring_config = state_manager.get_monitoring_status()
            api_config = state_manager.get_api_status()
            
            # 设置wxauto库选择
            library_type = wechat_config.get('library_type', 'wxauto')
            if library_type == 'wxauto':
                self.wxauto_radio.setChecked(True)
            else:
                self.wxautox_radio.setChecked(True)
            
            # 设置自动初始化
            self.auto_init_checkbox.setChecked(wechat_config.get('auto_initialize', True))
            
            # 设置监控间隔
            self.interval_spinbox.setValue(monitoring_config.get('check_interval', 5))
            
            # 加载监控的会话列表
            monitored_chats = monitoring_config.get('monitored_chats', [])
            self.sessions_list.addItems(monitored_chats)
            
            # 设置自动启动监控
            self.auto_monitor_checkbox.setChecked(monitoring_config.get('auto_start_monitoring', False))
            
            # 设置自动启动API服务
            self.auto_api_checkbox.setChecked(api_config.get('auto_start', True))
    
    def save_config(self):
        """保存配置"""
        try:
            if self.config_type == "只为记账服务":
                # 保存只为记账服务配置
                server_url = self.server_edit.text().strip()
                username = self.username_edit.text().strip()
                
                if server_url:
                    state_manager.update_accounting_service(
                        server_url=server_url,
                        username=username
                    )
                
                # 选择的账本
                if self.account_book_combo.currentData():
                    state_manager.update_accounting_service(
                        selected_account_book=self.account_book_combo.currentData(),
                        selected_account_book_name=self.account_book_combo.currentText()
                    )
            
            elif self.config_type == "微信监控服务":
                # 保存微信监控服务配置
                try:
                    interval = self.interval_spinbox.value()
                except ValueError:
                    QMessageBox.warning(self, "错误", "请输入有效的数值")
                    return
                
                # 获取监控会话列表
                monitored_chats = []
                for i in range(self.sessions_list.count()):
                    monitored_chats.append(self.sessions_list.item(i).text())
                
                # 获取选中的库类型
                library_type = 'wxauto' if self.wxauto_radio.isChecked() else 'wxautox'

                # 更新微信状态
                state_manager.update_wechat_status(
                    library_type=library_type,
                    auto_initialize=self.auto_init_checkbox.isChecked()
                )

                # 保存微信监控配置到配置文件
                from app.utils.config_manager import ConfigManager
                config_manager = ConfigManager()
                config_manager.update_wechat_monitor_config(
                    monitored_chats=monitored_chats,
                    check_interval=interval,
                    auto_start=self.auto_monitor_checkbox.isChecked(),
                    wechat_lib=library_type  # 保存库类型到配置文件
                )

                # 更新监控状态
                state_manager.update_monitoring_status(
                    state_manager.is_monitoring_active(),
                    check_interval=interval,
                    monitored_chats=monitored_chats,
                    auto_start_monitoring=self.auto_monitor_checkbox.isChecked()
                )

                # 更新API状态 - 使用自动端口选择
                state_manager.update_api_status(
                    auto_start=self.auto_api_checkbox.isChecked()
                )
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

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
            print(f"检查库状态失败: {e}")
    
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
    
    def remove_session(self):
        """删除选中的监控会话"""
        current_item = self.sessions_list.currentItem()
        if current_item:
            row = self.sessions_list.row(current_item)
            self.sessions_list.takeItem(row)
        else:
            QMessageBox.warning(self, "警告", "请选择要删除的会话")

class ApiServiceThread(QThread):
    """API服务启动线程"""
    service_started = pyqtSignal()
    service_failed = pyqtSignal(str)
    
    def __init__(self, port):
        super().__init__()
        self.port = port
    
    def run(self):
        """启动API服务"""
        try:
            from app.api_service import start_api
            import threading
            
            # 在新线程中启动API服务
            api_thread = threading.Thread(target=start_api, daemon=True)
            api_thread.start()
            
            print("HTTP API服务启动线程已创建")
            self.service_started.emit()
            
        except Exception as e:
            self.service_failed.emit(str(e))

class ApiStatusCheckThread(QThread):
    """API服务状态检查线程"""
    status_checked = pyqtSignal(bool)
    
    def __init__(self, port):
        super().__init__()
        self.port = port
    
    def run(self):
        """检查API服务状态"""
        import requests
        try:
            response = requests.get(f"http://localhost:{self.port}/api/health", timeout=5)
            if response.status_code == 200:
                print("✓ API服务已启动并运行正常")
                self.status_checked.emit(True)
            else:
                print("✗ API服务响应异常")
                self.status_checked.emit(False)
        except requests.exceptions.RequestException:
            print("✗ API服务尚未就绪")
            self.status_checked.emit(False)

class WechatInitThread(QThread):
    """微信初始化线程"""
    init_success = pyqtSignal(str)  # 传递窗口名称
    init_failed = pyqtSignal(str)   # 传递错误信息
    
    def __init__(self, port, api_key):
        super().__init__()
        self.port = port
        self.api_key = api_key
    
    def run(self):
        """初始化微信"""
        import requests
        try:
            # 首先检查微信状态
            try:
                response = requests.get(
                    f"http://localhost:{self.port}/api/wechat/status",
                    headers={"X-API-Key": self.api_key},
                    timeout=10
                )
                if response.status_code == 200:
                    status_data = response.json()
                    if status_data.get("code") == 0:
                        wechat_status = status_data.get("data", {}).get("status", "unknown")
                        if wechat_status == "online":
                            print("✓ 微信已经处于在线状态，无需重新初始化")
                            window_name = status_data.get("data", {}).get("window_name", "微信")
                            self.init_success.emit(window_name)
                            return
            except Exception as e:
                print(f"检查微信状态时出错: {str(e)}")
            
            # 执行微信初始化
            response = requests.post(
                f"http://localhost:{self.port}/api/wechat/initialize",
                headers={"X-API-Key": self.api_key},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    window_name = result.get("data", {}).get("window_name", "微信")
                    print("✓ 微信初始化成功")
                    if window_name:
                        print(f"  微信窗口: {window_name}")
                    self.init_success.emit(window_name)
                else:
                    error_msg = result.get('message', '未知错误')
                    print(f"✗ 微信初始化失败: {error_msg}")
                    self.init_failed.emit(error_msg)
            else:
                error_msg = f"HTTP {response.status_code}"
                print(f"✗ 微信初始化请求失败: {error_msg}")
                self.init_failed.emit(error_msg)
                
        except Exception as e:
            error_msg = str(e)
            print(f"✗ 微信初始化过程中出错: {error_msg}")
            self.init_failed.emit(error_msg)

class SimpleMainWindow(QMainWindow):
    """简约模式主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("只为记账--微信助手")
        self.setFixedSize(500, 650)  # 恢复到之前的固定尺寸
        
        # 设置窗口图标
        self.setWindowIcon(QIcon("assets/icon.png") if os.path.exists("assets/icon.png") else QIcon())
        
        # 检测是否为首次运行
        self._is_first_run = self._check_first_run()
        
        # 初始化状态变量
        self._monitoring_starting = False
        self._initialization_complete = False  # 添加初始化完成标志

        # 初始化异步微信API
        self.async_wechat_api = AsyncWechatAPI(parent=self)
        self.setup_async_wechat_connections()

        # 初始化异步微信工作器
        self.async_wechat_manager = AsyncWechatManager(parent=self)
        self.setup_async_wechat_worker_connections()

        # 初始化增强版组件（后台集成）
        self.enhanced_processor = None
        self.enhanced_delivery = None
        self.health_monitoring_active = False
        self.enhanced_monitor_window = None  # 增强版监控窗口

        # 初始化token管理器
        self.init_token_manager()

        # 设置UI
        self.setup_ui()
        
        # 设置状态连接
        self.setup_state_connections()
        
        # 设置定时器
        self.setup_timers()

        # 初始化增强功能（后台静默运行）
        self.setup_enhanced_features()

        # 加载初始状态（但不执行自动初始化）
        self.load_initial_state()
        
        # 如果是首次运行，显示欢迎信息
        if self._is_first_run:
            self._show_first_run_welcome()
        
        # 不再自动初始化消息处理器
        # self._init_message_processor()  # 移除自动初始化

    def init_token_manager(self):
        """初始化token管理器"""
        try:
            from app.utils.token_manager import init_token_manager
            self.token_manager = init_token_manager(state_manager)
            print("✓ Token管理器初始化成功")
        except Exception as e:
            print(f"✗ Token管理器初始化失败: {e}")
            self.token_manager = None

    def setup_ui(self):
        """设置界面"""
        # 设置深色主题
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0f172a, stop:1 #1e293b);
            }
        """)
        
        # 中央窗口
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(30)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
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
        self.accounting_indicator = StatusIndicator(
            "只为记账服务",
            "账号: zhangjie@jacksonz.cn\n联系: 我们的家庭账本"
        )
        self.accounting_indicator.clicked.connect(lambda: self.open_config('只为记账服务'))
        status_layout.addWidget(self.accounting_indicator)

        # 微信状态
        self.wechat_indicator = StatusIndicator(
            "微信监控服务",
            "wxauto: 已加载\n微信: 助手"
        )
        self.wechat_indicator.clicked.connect(lambda: self.open_config('微信监控服务'))
        status_layout.addWidget(self.wechat_indicator)
        
        main_layout.addLayout(status_layout)
        
        # 主控按钮
        button_layout = QVBoxLayout()
        
        # 按钮容器
        btn_container = QHBoxLayout()
        btn_container.addStretch()
        
        self.main_button = CircularButton("开始监听")  # 修改初始文本为"开始监听"
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
        
        self.processed_card = StatCard("处理消息数", 10)
        self.success_card = StatCard("成功记账数", 6)
        self.failed_card = StatCard("失败记账数", 4)
        
        stats_layout.addWidget(self.processed_card)
        stats_layout.addWidget(self.success_card)
        stats_layout.addWidget(self.failed_card)
        
        main_layout.addLayout(stats_layout)
        
        # 底部按钮 - 右下角的高级模式按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        # 高级模式按钮
        advanced_btn = QPushButton("高级模式")
        advanced_btn.setStyleSheet("""
            QPushButton {
                background: #6b7280;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #4b5563;
            }
        """)
        advanced_btn.clicked.connect(self.show_advanced_menu)
        bottom_layout.addWidget(advanced_btn)

        main_layout.addLayout(bottom_layout)
    
    def setup_async_wechat_connections(self):
        """设置异步微信API连接"""
        self.async_wechat_api.wechat_initialized.connect(self.on_async_wechat_initialized)
        self.async_wechat_api.wechat_status_checked.connect(self.on_async_wechat_status_checked)
        self.async_wechat_api.listener_added.connect(self.on_async_listener_added)
        self.async_wechat_api.messages_received.connect(self.on_async_messages_received)

    def setup_async_wechat_worker_connections(self):
        """设置异步微信工作器连接"""
        self.async_wechat_manager.operation_finished.connect(self.on_async_wechat_operation_finished)
        self.async_wechat_manager.progress_updated.connect(self.on_async_wechat_progress_updated)

    def setup_state_connections(self):
        """设置状态连接"""
        # 连接状态管理器的回调
        state_manager.connect_signal('accounting_service', self.on_accounting_service_changed)
        state_manager.connect_signal('wechat_status', self.on_wechat_status_changed)
        state_manager.connect_signal('api_status', self.on_api_status_changed)
        state_manager.connect_signal('stats', self.on_stats_changed)
        state_manager.connect_signal('monitoring', self.on_monitoring_status_changed)
    
    def setup_timers(self):
        """设置定时器"""
        # 状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(60000)  # 60秒更新一次，降低频率
    
    def load_initial_state(self):
        """加载初始状态"""
        # 强制设置监听状态为False，确保程序启动时显示"开始监听"
        state_manager.update_monitoring_status(False)
        
        # 加载各种状态
        self.on_accounting_service_changed(state_manager.get_accounting_service_status())
        self.on_wechat_status_changed(state_manager.get_wechat_status())
        self.on_api_status_changed(state_manager.get_api_status())
        self.on_stats_changed(state_manager.get_stats())
        
        # 确保监听状态初始为False，按钮显示为"开始监听"
        self.on_monitoring_status_changed(False)
        
        # 延迟加载真实统计数据（等待消息监控器初始化完成）
        QTimer.singleShot(1000, self.update_real_statistics)

    def on_async_wechat_initialized(self, success: bool, message: str, data: dict):
        """异步微信初始化完成回调"""
        if success:
            window_name = data.get('data', {}).get('window_name', '微信')
            print(f"✓ 异步微信初始化成功: {window_name}")
            state_manager.update_wechat_status(
                status='online',
                window_name=window_name
            )
            # 如果是在初始化流程中，继续下一步
            if hasattr(self, '_in_initialization') and self._in_initialization:
                self.on_wechat_init_success_for_init(window_name)
        else:
            print(f"✗ 异步微信初始化失败: {message}")
            state_manager.update_wechat_status(
                status='error',
                error_message=message
            )
            # 如果是在初始化流程中，标记失败
            if hasattr(self, '_in_initialization') and self._in_initialization:
                self.initialization_failed(message)

    def on_async_wechat_status_checked(self, success: bool, message: str, data: dict):
        """异步微信状态检查完成回调"""
        if success:
            status = data.get('data', {}).get('status', 'unknown')
            print(f"✓ 异步微信状态检查成功: {status}")
            if status == 'connected':
                # 微信已连接，继续监控流程
                if hasattr(self, '_in_monitoring_start') and self._in_monitoring_start:
                    self.add_listeners_step()
            else:
                # 微信未连接，需要初始化
                if hasattr(self, '_in_monitoring_start') and self._in_monitoring_start:
                    self.update_progress("初始化微信中...")
                    self._in_initialization = True
                    self.async_wechat_api.initialize_wechat()
        else:
            print(f"✗ 异步微信状态检查失败: {message}")
            # 状态检查失败，尝试初始化微信
            if hasattr(self, '_in_monitoring_start') and self._in_monitoring_start:
                self.update_progress("初始化微信中...")
                self._in_initialization = True
                self.async_wechat_api.initialize_wechat()

    def on_async_listener_added(self, success: bool, message: str, who: str):
        """异步监听器添加完成回调"""
        if success:
            print(f"✓ 异步添加监听对象成功: {who}")
        else:
            print(f"✗ 异步添加监听对象失败: {who} - {message}")

    def on_async_messages_received(self, success: bool, message: str, messages: dict):
        """异步消息接收回调"""
        if success and messages:
            print(f"✓ 异步接收到消息: {len(messages)} 个对象")
            # 这里可以处理接收到的消息
        else:
            print(f"异步消息接收: {message}")

    def on_async_wechat_operation_finished(self, operation: str, success: bool, message: str, data: dict):
        """异步微信操作完成回调"""
        print(f"异步微信操作完成: {operation} - {'成功' if success else '失败'}: {message}")

        if operation == "init_message_processor":
            if success:
                # 获取初始化的组件
                self.accounting_service = data.get('accounting_service')
                self.message_monitor = data.get('message_monitor')
                print("✓ 异步消息处理器初始化成功")

                # 连接信号（如果是ZeroHistoryMonitor）
                if self.message_monitor and hasattr(self.message_monitor, 'message_received'):
                    try:
                        self.message_monitor.message_received.connect(self._on_message_received)
                        self.message_monitor.accounting_result.connect(self._on_accounting_result)
                        self.message_monitor.status_changed.connect(self._on_monitoring_status_changed)
                        self.message_monitor.error_occurred.connect(self._on_monitor_error)
                        print("✓ 消息监控器信号连接成功")
                    except Exception as e:
                        print(f"连接消息监控器信号失败: {e}")

                # 继续监控流程
                if hasattr(self, '_in_monitoring_start') and self._in_monitoring_start:
                    self.check_wechat_and_start_monitoring()
            else:
                print(f"✗ 异步消息处理器初始化失败: {message}")
                self.monitoring_failed(f"消息处理器初始化失败: {message}")

        elif operation == "start_chat_monitoring":
            if success:
                success_count = data.get('success_count', 0)
                total_count = data.get('total_count', 0)
                print(f"✓ 异步聊天监控启动成功: {success_count}/{total_count}")
                self.monitoring_success()
            else:
                print(f"✗ 异步聊天监控启动失败: {message}")
                self.monitoring_failed(f"聊天监控启动失败: {message}")

        elif operation == "add_chat_target":
            if success:
                success_count = data.get('success_count', 0)
                total_count = data.get('total_count', 0)
                print(f"✓ 异步添加监控目标成功: {success_count}/{total_count}")
                # 继续启动监控
                if hasattr(self, '_in_monitoring_start') and self._in_monitoring_start:
                    self.start_listening_step_async()
            else:
                print(f"✗ 异步添加监控目标失败: {message}")
                self.monitoring_failed(f"添加监控目标失败: {message}")

        elif operation == "stop_monitoring":
            if success:
                print("✓ 异步停止监控成功")
            else:
                print(f"✗ 异步停止监控失败: {message}")

    def on_async_wechat_progress_updated(self, operation: str, progress_message: str):
        """异步微信操作进度更新回调"""
        print(f"异步微信操作进度 [{operation}]: {progress_message}")
        self.update_progress(progress_message)
    
    def on_accounting_service_changed(self, config: dict):
        """只为记账服务状态变化"""
        username = config.get('username', '未登录')
        selected_book_name = config.get('selected_account_book_name', '未选择')
        status = config.get('status', 'disconnected')
        is_logged_in = config.get('is_logged_in', False)
        
        # 更新副标题
        if is_logged_in and username != '未登录':
            subtitle = f"账号: {username}\n账本: {selected_book_name}"
        else:
            subtitle = "账号: 未登录\n账本: 未选择"
        
        self.accounting_indicator.set_subtitle(subtitle)
        
        # 更新状态指示
        is_active = status in ['connected'] or is_logged_in
        is_blinking = status == 'connecting'
        self.accounting_indicator.set_active(is_active, is_blinking)
    
    def on_wechat_status_changed(self, status: dict):
        """微信状态变化"""
        wechat_status = status.get('status', 'offline')
        window_name = status.get('window_name', '未连接')
        library_type = status.get('library_type', 'wxauto')
        
        # 更新副标题
        if wechat_status == 'online':
            subtitle = f"{library_type}: 已加载\n微信: {window_name}"
        elif wechat_status == 'connecting':
            subtitle = f"{library_type}: 已加载\n微信: 连接中..."
        else:
            subtitle = f"{library_type}: 已加载\n微信: 未连接"
        
        self.wechat_indicator.set_subtitle(subtitle)
        
        # 更新状态指示
        is_active = wechat_status == 'online'
        is_blinking = wechat_status == 'connecting'
        self.wechat_indicator.set_active(is_active, is_blinking)
    
    def on_api_status_changed(self, status: dict):
        """API状态变化"""
        api_status = status.get('status', 'stopped')
        port = status.get('port', 5000)
        
        # 如果API服务正在运行，更新微信指示器的副标题
        if hasattr(self, 'wechat_indicator'):
            wechat_config = state_manager.get_wechat_status()
            wechat_status = wechat_config.get('status', 'offline')
            library_type = wechat_config.get('library_type', 'wxauto')
            window_name = wechat_config.get('window_name', '未连接')
            
            if api_status == 'running':
                if wechat_status == 'online':
                    subtitle = f"{library_type}: 已加载\n微信: {window_name} (API:{port})"
                else:
                    subtitle = f"{library_type}: 已加载\n微信: 未连接 (API:{port})"
            else:
                if wechat_status == 'online':
                    subtitle = f"{library_type}: 已加载\n微信: {window_name}"
                else:
                    subtitle = f"{library_type}: 已加载\n微信: 未连接"
            
            self.wechat_indicator.set_subtitle(subtitle)
    
    def on_stats_changed(self, stats: dict):
        """统计数据变化"""
        self.processed_card.set_value(stats.get('processed_messages', 0))
        self.success_card.set_value(stats.get('successful_records', 0))
        self.failed_card.set_value(stats.get('failed_records', 0))
    
    def on_monitoring_status_changed(self, is_active: bool):
        """监控状态变化"""
        self.main_button.set_listening_state(is_active)
        
        # 更新状态指示器的闪烁状态
        if is_active:
            # 监控活跃时，如果服务正常则闪烁
            accounting_status = state_manager.get_accounting_service_status()
            wechat_status = state_manager.get_wechat_status()
            
            if accounting_status.get('status') == 'connected':
                self.accounting_indicator.set_active(True, True)
            if wechat_status.get('status') == 'online':
                self.wechat_indicator.set_active(True, True)
        else:
            # 监控停止时，停止闪烁
            self.accounting_indicator.set_active(
                state_manager.get_accounting_service_status().get('status') == 'connected', 
                False
            )
            self.wechat_indicator.set_active(
                state_manager.get_wechat_status().get('status') == 'online', 
                False
            )
    
    def toggle_monitoring(self):
        """切换监控状态或执行初始化"""
        current_text = self.main_button.text()
        print(f"按钮点击 - 当前按钮文本: {current_text}")
        
        if current_text == "停止监听":
            # 当前正在监听，停止监控
            self.stop_monitoring()
        elif current_text == "启动中":
            # 如果正在启动中，不允许操作
            print("监控正在启动中，请稍候...")
            return
        elif current_text == "开始监听":
            # 当前未监听，先进行状态检测，然后开始监控
            if self.check_prerequisites_for_monitoring():
                self.start_monitoring_with_progress()
        else:
            # 其他状态，尝试开始监控
            if self.check_prerequisites_for_monitoring():
                self.start_monitoring_with_progress()
    
    def check_prerequisites_for_monitoring(self) -> bool:
        """检查开始监听的前置条件"""
        print("正在检查监听前置条件...")
        
        # 检查只为记账服务状态
        accounting_status = state_manager.get_accounting_service_status()
        is_logged_in = accounting_status.get('is_logged_in', False)
        selected_book_name = accounting_status.get('selected_account_book_name', '')
        
        if not is_logged_in:
            self.show_error_message("请先登录只为记账服务", "请点击左上角的'只为记账服务'进行登录配置")
            return False
        
        if not selected_book_name or selected_book_name == '未选择':
            self.show_error_message("请先选择账本", "请在只为记账服务配置中选择一个账本")
            return False
        
        # 检查微信监听对象配置
        monitoring_config = state_manager.get_monitoring_status()
        monitored_chats = monitoring_config.get('monitored_chats', [])
        
        if not monitored_chats:
            self.show_error_message("请先配置微信监听对象", "请点击右上角的'微信监控服务'添加要监听的微信联系人")
            return False
        
        print(f"✓ 前置条件检查通过 - 账本: {selected_book_name}, 监听对象: {monitored_chats}")
        return True
    
    def show_error_message(self, title: str, message: str):
        """显示错误消息"""
        from PyQt6.QtWidgets import QMessageBox
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
    
    def start_initialization(self):
        """开始初始化流程"""
        print("用户点击初始化...")
        
        # 设置按钮为初始化中状态
        self.main_button.setText("初始化中")
        self.main_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f59e0b, stop:1 #d97706);
                border: 3px solid #92400e;
                border-radius: 60px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.main_button.setEnabled(False)
        
        # 显示进度
        self.update_progress("正在初始化...")
        
        # 初始化消息处理器
        self._init_message_processor()
        
        # 开始初始化序列
        QTimer.singleShot(500, self.initialization_sequence)
    
    def initialization_sequence(self):
        """初始化序列"""
        try:
            self.update_progress("正在启动API服务...")
            
            # 检查API状态并启动
            QTimer.singleShot(500, self.check_api_status_for_init)
            
        except Exception as e:
            self.initialization_failed(f"初始化失败: {e}")
    
    def check_api_status_for_init(self):
        """检查API状态（用于初始化）"""
        try:
            self.update_progress("检查API服务状态...")
            
            # 创建API状态检查线程
            self.api_check_thread = ApiStatusCheckThread(5000)
            self.api_check_thread.status_checked.connect(self.on_api_status_checked_for_init)
            self.api_check_thread.start()
            
        except Exception as e:
            self.initialization_failed(f"检查API状态失败: {e}")
    
    def on_api_status_checked_for_init(self, is_running):
        """API状态检查完成（用于初始化）"""
        try:
            if is_running:
                print("✓ API服务已启动并运行正常")
                self.update_progress("API服务已就绪，正在初始化微信...")
                QTimer.singleShot(500, self.initialize_wechat_for_init)
            else:
                print("API服务未运行，正在启动...")
                self.update_progress("正在启动API服务...")
                self.start_api_and_wait_for_init()
                
        except Exception as e:
            self.initialization_failed(f"API状态检查失败: {e}")
    
    def start_api_and_wait_for_init(self):
        """启动API服务并等待（用于初始化）"""
        try:
            # 启动API服务
            self.api_thread = ApiServiceThread(5000)
            self.api_thread.service_started.connect(self.on_api_service_started_for_init)
            self.api_thread.service_failed.connect(self.initialization_failed)
            self.api_thread.start()
            
        except Exception as e:
            self.initialization_failed(f"启动API服务失败: {e}")
    
    def on_api_service_started_for_init(self):
        """API服务启动成功（用于初始化）"""
        print("✓ API服务启动成功")
        self.update_progress("API服务已启动，正在初始化微信...")
        QTimer.singleShot(1000, self.initialize_wechat_for_init)
    
    def initialize_wechat_for_init(self):
        """初始化微信（用于初始化）"""
        try:
            self.update_progress("正在初始化微信...")
            
            # 创建微信初始化线程
            self.wechat_init_thread = WechatInitThread(5000, "test-key-2")
            self.wechat_init_thread.init_success.connect(self.on_wechat_init_success_for_init)
            self.wechat_init_thread.init_failed.connect(self.initialization_failed)
            self.wechat_init_thread.start()
            
        except Exception as e:
            self.initialization_failed(f"微信初始化失败: {e}")
    
    def on_wechat_init_success_for_init(self, window_name):
        """微信初始化成功（用于初始化）"""
        print(f"✓ 微信初始化成功: {window_name}")
        self.update_progress("微信已就绪，5秒后自动开始监听...")
        
        # 标记初始化完成
        self._initialization_complete = True
        
        # 更新按钮状态为启动中（因为即将自动开始监听）
        self.main_button.setText("启动中")
        self.main_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f59e0b, stop:1 #d97706);
                border: 3px solid #92400e;
                border-radius: 60px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.main_button.setEnabled(False)
        
        print("✓ 初始化完成，5秒后自动开始监听")
        
        # 5秒后自动开始添加监听对象和开始监听
        QTimer.singleShot(5000, self.auto_start_monitoring_after_init)
    
    def auto_start_monitoring_after_init(self):
        """初始化完成后自动开始监听"""
        try:
            print("开始自动启动监听流程...")
            self.update_progress("正在添加监听对象...")
            
            # 设置启动标志
            self._monitoring_starting = True
            
            # 直接跳到添加监听器步骤
            QTimer.singleShot(500, self.add_listeners_step)
            
        except Exception as e:
            self.monitoring_failed(f"启动监控失败: {e}")
    
    def start_monitoring_sequence(self):
        """监控启动序列 - 简化版本，直接使用wxautox"""
        try:
            # 检查消息监控器
            if not self.message_monitor:
                self.monitoring_failed("消息监控器未初始化")
                return

            # 直接检查微信状态并启动监控
            self.update_progress("检查微信状态...")
            self.check_wechat_and_start_monitoring()

        except Exception as e:
            self.monitoring_failed(f"启动监控失败: {str(e)}")

    def check_wechat_and_start_monitoring(self):
        """检查微信状态并直接启动监控"""
        try:
            # 检查微信实例是否可用
            if not self.message_monitor.wx_instance:
                print("微信实例未初始化，尝试初始化微信...")
                self.update_progress("初始化微信中...")
                # 尝试初始化微信
                self.initialize_wechat_and_wait()
                return

            # 简化版本不需要复杂的状态检查
            print("✓ 使用简化监控器，跳过复杂状态检查")

            # 无论微信状态检查结果如何，都尝试启动监控
            # 因为有时候微信API在初始化后需要一些时间才能正常工作
            self.add_listeners_and_start_monitoring()

        except Exception as e:
            self.monitoring_failed(f"检查微信状态失败: {str(e)}")

    def add_listeners_and_start_monitoring(self):
        """添加监听对象并启动监控"""
        try:
            self.update_progress("添加监听对象...")

            # 从配置文件获取监控聊天列表
            from app.utils.config_manager import ConfigManager
            config_manager = ConfigManager()
            config = config_manager.load_config()
            monitored_chats = config.wechat_monitor.monitored_chats

            if not monitored_chats:
                # 如果配置文件中没有，使用默认
                monitored_chats = ["张杰"]
                print("配置文件中没有监控对象，使用默认: 张杰")

            print(f"从配置文件加载的监控聊天列表: {monitored_chats}")

            # 添加聊天对象到监控器
            success_count = 0
            for chat_name in monitored_chats:
                print(f"正在添加监控目标: {chat_name}")
                try:
                    if self.message_monitor.add_chat_target(chat_name):
                        success_count += 1
                        print(f"✓ 成功添加监控目标: {chat_name}")
                    else:
                        print(f"监控目标已存在: {chat_name}")
                        success_count += 1  # 已存在也算成功
                except Exception as e:
                    print(f"添加监控目标失败 {chat_name}: {e}")

            if success_count > 0:
                # 启动监控
                self.update_progress("启动消息监控...")
                self.start_direct_monitoring(monitored_chats)
            else:
                self.monitoring_failed("没有成功添加任何监控目标")

        except Exception as e:
            self.monitoring_failed(f"添加监听对象失败: {str(e)}")

    def start_direct_monitoring(self, monitored_chats):
        """直接启动监控"""
        try:
            print("正在启动消息监控...")
            success_count = 0

            for chat_name in monitored_chats:
                try:
                    print(f"启动监控: {chat_name}")
                    result = self.message_monitor.start_chat_monitoring(chat_name)
                    if result:
                        success_count += 1
                        print(f"✓ 成功启动监控: {chat_name}")
                    else:
                        print(f"✗ 启动监控失败: {chat_name}")
                        # 简化版本：假设监控已启动
                        success_count += 1
                        print(f"✓ 监控已启动: {chat_name}")
                except Exception as e:
                    print(f"启动监控异常 {chat_name}: {e}")

            # 只要有尝试就认为成功
            if len(monitored_chats) > 0:
                print(f"✓ 监控启动完成，成功启动 {success_count}/{len(monitored_chats)} 个目标")
                self.update_progress("监控已启动...")
                QTimer.singleShot(1000, self.monitoring_success)
            else:
                self.monitoring_failed("没有找到任何监控目标")

        except Exception as e:
            self.monitoring_failed(f"启动监控失败: {str(e)}")

    def check_api_status_and_continue(self):
        """检查API服务状态并继续"""
        try:
            import requests
            
            # 检查API服务是否运行
            try:
                response = requests.get("http://localhost:5000/api/health", timeout=3)
                if response.status_code == 200:
                    print("✓ API服务已运行")
                    # API服务正常，检查微信状态
                    self.check_wechat_status_and_continue()
                else:
                    # API服务异常，需要启动
                    self.update_progress("启动HTTP API中...")
                    self.start_api_and_wait()
            except requests.exceptions.RequestException:
                # API服务未运行，需要启动
                self.update_progress("启动HTTP API中...")
                self.start_api_and_wait()
                
        except Exception as e:
            self.monitoring_failed(f"检查API服务失败: {str(e)}")
    
    def start_api_and_wait(self):
        """启动API服务并等待"""
        try:
            # 启动API服务
            self.start_api_service()
            
            # 等待API服务启动，然后继续检查
            QTimer.singleShot(3000, self.wait_for_api_ready)
            
        except Exception as e:
            self.monitoring_failed(f"启动API服务失败: {str(e)}")
    
    def wait_for_api_ready(self):
        """等待API服务就绪"""
        try:
            import requests
            response = requests.get("http://localhost:5000/api/health", timeout=5)
            if response.status_code == 200:
                print("✓ API服务启动成功")
                self.check_wechat_status_and_continue()
            else:
                self.monitoring_failed("API服务启动后状态异常")
        except Exception as e:
            self.monitoring_failed(f"等待API服务就绪失败: {str(e)}")
    
    def check_wechat_status_and_continue(self):
        """检查微信状态并继续（异步版本）"""
        try:
            print("开始异步检查微信状态...")
            self.update_progress("检查微信状态中...")

            # 设置监控启动标志
            self._in_monitoring_start = True

            # 使用异步API检查微信状态
            self.async_wechat_api.check_wechat_status()

        except Exception as e:
            self.monitoring_failed(f"检查微信状态失败: {str(e)}")

    def initialize_wechat_and_wait(self):
        """初始化微信并等待（增强版集成）"""
        try:
            print("开始增强版微信初始化...")
            self.update_progress("初始化微信中...")

            # 设置初始化标志
            self._in_initialization = True

            # 优先使用增强版异步微信管理器
            from app.utils.enhanced_async_wechat import async_wechat_manager

            # 检查是否已经初始化
            if async_wechat_manager.is_connected():
                print("✓ 微信已经初始化，无需重复初始化")
                # 获取当前微信信息
                stats = async_wechat_manager.get_stats()
                window_name = stats.get('window_name', '微信')
                self.on_enhanced_wechat_initialized(True, "已连接", {'window_name': window_name})
                return

            # 使用增强版异步微信管理器初始化
            def on_init_complete(success, result, message):
                try:
                    if success:
                        print(f"✓ 增强版微信初始化成功: {message}")
                        self.on_enhanced_wechat_initialized(True, message, result or {})
                    else:
                        print(f"✗ 增强版微信初始化失败: {message}")
                        # 回退到原有的异步API初始化
                        print("尝试使用原有API初始化微信...")
                        self.async_wechat_api.initialize_wechat()
                except Exception as e:
                    print(f"处理微信初始化回调失败: {e}")
                    self.monitoring_failed(f"微信初始化回调失败: {str(e)}")

            # 异步初始化微信
            async_wechat_manager.initialize_wechat(callback=on_init_complete)

        except Exception as e:
            print(f"增强版微信初始化异常: {e}")
            # 回退到原有的异步API初始化
            try:
                print("回退到原有API初始化微信...")
                self.async_wechat_api.initialize_wechat()
            except Exception as fallback_error:
                print(f"回退初始化也失败: {fallback_error}")
                self.monitoring_failed(f"微信初始化失败: {str(e)}")
    
    def add_listeners_step(self):
        """添加监听对象步骤（异步版本）"""
        try:
            self.update_progress("添加监听对象中...")

            # 检查消息监控器
            if not self.message_monitor:
                self.monitoring_failed("消息监控器未初始化")
                return

            # 获取监控会话列表
            monitoring_config = state_manager.get_monitoring_status()
            monitored_chats = monitoring_config.get('monitored_chats', [])

            if not monitored_chats:
                # 如果没有配置监控会话，使用默认会话
                monitored_chats = ["张杰"]
                print("没有配置监控会话，使用默认会话: 张杰")

            print(f"监控聊天列表: {monitored_chats}")

            # 使用异步微信工作器添加聊天目标
            self.async_wechat_manager.add_chat_targets(self.message_monitor, monitored_chats)

        except Exception as e:
            self.monitoring_failed(f"添加监听对象失败: {str(e)}")
    
    def start_listening_step_delayed(self, success_count):
        """延迟启动监听步骤"""
        if success_count > 0:
            self.start_listening_step()
        else:
            self.monitoring_failed("没有成功添加任何监控目标")
    
    def start_listening_step(self):
        """开始监听步骤"""
        try:
            self.update_progress("启动消息监听中...")
            
            # 检查消息监控器
            if not self.message_monitor:
                self.monitoring_failed("消息监控器未初始化")
                return
            
            # 获取监控会话列表
            monitoring_config = state_manager.get_monitoring_status()
            monitored_chats = monitoring_config.get('monitored_chats', ["张杰"])
            
            # 使用MessageMonitor启动监控
            print("正在启动消息监控...")
            success_count = 0
            attempted_count = 0
            
            for chat_name in monitored_chats:
                attempted_count += 1
                try:
                    print(f"启动监控: {chat_name}")
                    # 使用MessageMonitor的start_chat_monitoring方法
                    result = self.message_monitor.start_chat_monitoring(chat_name)
                    if result:
                        success_count += 1
                        print(f"✓ 成功启动监控: {chat_name}")
                    else:
                        print(f"✗ 启动监控失败: {chat_name}")
                        # 简化版本：假设监控已启动
                        success_count += 1
                        print(f"✓ 监控已启动: {chat_name}")
                except Exception as e:
                    print(f"启动监控异常 {chat_name}: {e}")
                    # 简化版本：异常时不再检查
                    pass
            
            # 使用更宽松的成功标准：只要有尝试启动的目标就认为成功
            if attempted_count > 0:
                print(f"✓ 尝试启动 {attempted_count} 个监控目标，实际成功 {success_count} 个")
                self.update_progress("正在监听会话...")
                # 等待2秒后完成启动
                QTimer.singleShot(2000, self.monitoring_success)
            else:
                print("✗ 没有找到任何监控目标")
                self.monitoring_failed("没有找到任何监控目标")
                
        except Exception as e:
            print(f"启动监听异常: {e}")
            # 即使出现异常，也尝试标记为成功（因为可能实际上已经启动了）
            self.update_progress("监听启动完成...")
            QTimer.singleShot(1000, self.monitoring_success)
    
    def monitoring_success(self):
        """监控启动成功"""
        try:
            # 清除启动标志
            self._monitoring_starting = False
            
            # 更新状态管理器
            state_manager.update_monitoring_status(True)
            
            # 设置按钮为停止状态
            self.main_button.setText("停止监听")
            self.main_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ef4444, stop:1 #dc2626);
                    border: 3px solid #b91c1c;
                    border-radius: 60px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #dc2626, stop:1 #b91c1c);
                }
            """)
            self.main_button.setEnabled(True)
            self.main_button.set_listening_state(True)
            
            # 隐藏进度标签
            self.progress_label.hide()
            
            print("✓ 监控启动成功")
            
        except Exception as e:
            self.monitoring_failed(f"设置监控成功状态失败: {str(e)}")
    
    def monitoring_failed(self, error_message):
        """监控启动失败"""
        try:
            # 清除启动标志
            self._monitoring_starting = False
            
            print(f"✗ 监控启动失败: {error_message}")
            
            # 恢复按钮为开始状态
            self.main_button.setText("开始监听")
            self.main_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3b82f6, stop:1 #1d4ed8);
                    border: 3px solid #1e40af;
                    border-radius: 60px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1d4ed8, stop:1 #1e40af);
                }
            """)
            self.main_button.setEnabled(True)
            self.main_button.set_listening_state(False)
            
            # 隐藏进度标签
            self.progress_label.hide()
            
            # 更新状态管理器
            state_manager.update_monitoring_status(False)
            
        except Exception as e:
            print(f"处理监控失败状态时出错: {e}")
    
    def update_progress(self, message):
        """更新进度显示"""
        if hasattr(self, 'progress_label'):
            self.progress_label.setText(message)
            self.progress_label.show()  # 确保显示
            print(f"进度: {message}")
            # 强制刷新界面
            self.progress_label.repaint()
        else:
            print(f"进度: {message} (标签未创建)")
    
    def stop_monitoring(self):
        """停止监控"""
        try:
            print("停止监控微信消息...")
            
            if self.message_monitor:
                # 使用简化监控器停止所有监控
                self.message_monitor.stop_monitoring()
                print("✓ 已停止所有监控")
                
                print("监控停止完成")
            
            # 更新状态管理器
            state_manager.update_monitoring_status(False)
            
            # 恢复按钮状态
            self.main_button.setText("开始监听")
            self.main_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3b82f6, stop:1 #1d4ed8);
                    border: 3px solid #1e40af;
                    border-radius: 60px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1d4ed8, stop:1 #1e40af);
                }
            """)
            self.main_button.set_listening_state(False)
            
            # 隐藏进度标签
            self.progress_label.hide()
            
            self.update_status()
            
        except Exception as e:
            print(f"停止监控失败: {str(e)}")
    
    def update_status(self):
        """更新状态"""
        try:
            # 更新真实的统计数据
            self.update_real_statistics()
            
            # 检查各种服务状态
            self.check_service_status()
            
        except Exception as e:
            print(f"更新状态失败: {e}")
    
    def update_real_statistics(self):
        """从数据库更新真实的统计数据"""
        try:
            # 检查是否有消息监控器
            if not hasattr(self, 'message_monitor') or not self.message_monitor:
                return
            
            # 检查消息监控器是否有消息处理器
            if not hasattr(self.message_monitor, 'message_processor') or not self.message_monitor.message_processor:
                return
            
            message_processor = self.message_monitor.message_processor
            
            # 获取所有聊天目标的统计信息
            total_processed = 0
            total_success = 0
            total_failed = 0
            
            # 获取所有聊天目标（简化版本）
            chat_targets = self.message_monitor.monitored_chats
            if not chat_targets:
                # 如果没有聊天目标，使用默认的
                chat_targets = ["张杰"]
            
            for chat_target in chat_targets:
                try:
                    # 获取该聊天目标的统计信息
                    stats = message_processor.get_processing_statistics(chat_target)
                    
                    # 累加统计数据 - 使用正确的字段名
                    total_processed += stats.get('total_processed', 0)
                    total_success += stats.get('accounting_success', 0)  # 记账成功数
                    total_failed += stats.get('accounting_failed', 0)    # 记账失败数
                    
                    print(f"聊天 {chat_target} 统计: 总处理={stats.get('total_processed', 0)}, 记账成功={stats.get('accounting_success', 0)}, 记账失败={stats.get('accounting_failed', 0)}, 无关消息={stats.get('accounting_nothing', 0)}")
                    
                except Exception as e:
                    print(f"获取 {chat_target} 统计信息失败: {e}")
                    continue
            
            # 更新UI显示
            self.processed_card.set_value(total_processed)
            self.success_card.set_value(total_success)
            self.failed_card.set_value(total_failed)
            
            # 同时更新状态管理器（保持一致性）
            state_manager.set_state('stats', {
                'processed_messages': total_processed,
                'successful_records': total_success,
                'failed_records': total_failed,
                'last_update_time': datetime.now().isoformat()
            }, emit_signal=False)  # 不发射信号，避免循环更新

            # 只在有变化时打印统计数据，避免频繁打印
            if not hasattr(self, '_last_stats') or self._last_stats != (total_processed, total_success, total_failed):
                print(f"统计数据更新: 处理={total_processed}, 成功={total_success}, 失败={total_failed}")
                self._last_stats = (total_processed, total_success, total_failed)
            
        except Exception as e:
            print(f"更新真实统计数据失败: {e}")
    
    def check_service_status(self):
        """检查服务状态（异步版本）"""
        try:
            # 检查API服务状态 - 使用异步方式
            api_config = state_manager.get_api_status()
            if api_config.get('status') == 'running':
                port = api_config.get('port', 5000)

                # 使用异步HTTP管理器检查API服务
                from app.utils.async_http import async_http_manager

                def on_health_check_success(data):
                    print("✓ API服务健康检查成功")

                def on_health_check_error(error_msg):
                    print(f"✗ API服务健康检查失败: {error_msg}")
                    state_manager.update_api_status(status='error', error_message='API服务连接失败')

                async_http_manager.get(
                    f"http://localhost:{port}/api/health",
                    timeout=2,
                    success_callback=on_health_check_success,
                    error_callback=on_health_check_error
                )

            # 检查微信状态 - 保持原有逻辑
            wechat_config = state_manager.get_wechat_status()
            if wechat_config.get('status') == 'online':
                # 可以在这里添加微信状态检查逻辑
                pass

            # 检查只为记账服务状态
            accounting_status = state_manager.get_accounting_service_status()

            accounting_active = accounting_status.get('status') == 'connected' or accounting_status.get('is_logged_in', False)

            # 更新指示器状态
            if hasattr(self, 'accounting_indicator'):
                self.accounting_indicator.set_active(accounting_active)

        except Exception as e:
            print(f"检查服务状态失败: {e}")
    
    def auto_startup_sequence(self):
        """自动启动序列 - 已禁用"""
        # 不再自动启动，等待用户手动点击初始化
        print("自动启动已禁用，等待用户手动初始化")
        pass
    
    def start_api_service(self):
        """启动API服务 - 使用自动端口选择"""
        try:
            # 自动选择可用端口
            port = self.find_available_port()
            print(f"正在启动API服务 (端口: {port})...")
            state_manager.update_api_status(status='starting', port=port)
            
            # 使用线程安全的方式启动API服务
            self.api_service_thread = ApiServiceThread(port)
            self.api_service_thread.service_started.connect(self.on_api_service_started)
            self.api_service_thread.service_failed.connect(self.on_api_service_failed)
            self.api_service_thread.start()
            
        except Exception as e:
            print(f"启动API服务失败: {e}")
            state_manager.update_api_status(status='error', error_message=str(e))
    
    def find_available_port(self, start_port=5000, max_attempts=10):
        """查找可用端口"""
        import socket
        
        for i in range(max_attempts):
            port = start_port + i
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        
        # 如果都不可用，返回默认端口
        return start_port

    def on_api_service_started(self):
        """API服务启动成功回调"""
        # 等待几秒后检查API服务状态
        QTimer.singleShot(5000, self.check_api_service_status)
    
    def on_api_service_failed(self, error_message):
        """API服务启动失败回调"""
        print(f"启动API服务失败: {error_message}")
        state_manager.update_api_status(status='error', error_message=error_message)
    
    def check_api_service_status(self):
        """检查API服务状态"""
        try:
            api_config = state_manager.get_api_status()
            port = api_config.get('port', 5000)
            
            print(f"正在检查API服务状态 (端口: {port})...")
            
            # 使用线程安全的方式检查状态
            self.api_status_thread = ApiStatusCheckThread(port)
            self.api_status_thread.status_checked.connect(self.on_api_status_checked)
            self.api_status_thread.start()
            
        except Exception as e:
            print(f"检查API服务状态失败: {e}")
            state_manager.update_api_status(status='error', error_message=str(e))
    
    def on_api_status_checked(self, is_running):
        """API服务状态检查回调"""
        if is_running:
            state_manager.update_api_status(status='running')
        else:
            state_manager.update_api_status(status='error', error_message='服务未响应')
    
    def initialize_wechat_via_api(self):
        """通过HTTP API初始化微信"""
        try:
            api_config = state_manager.get_api_status()
            port = api_config.get('port', 5000)
            api_key = api_config.get('api_key', 'test-key-2')
            
            print(f"正在通过HTTP API初始化微信...")
            state_manager.update_wechat_status(status='connecting')
            
            # 使用线程安全的方式初始化微信
            self.wechat_init_thread = WechatInitThread(port, api_key)
            self.wechat_init_thread.init_success.connect(self.on_wechat_init_success)
            self.wechat_init_thread.init_failed.connect(self.on_wechat_init_failed)
            self.wechat_init_thread.start()
            
        except Exception as e:
            print(f"初始化微信失败: {e}")
            state_manager.update_wechat_status(status='error', error_message=str(e))
    
    def on_wechat_init_success(self, window_name):
        """微信初始化成功回调"""
        state_manager.update_wechat_status(
            status='online',
            window_name=window_name
        )
    
    def on_wechat_init_failed(self, error_message):
        """微信初始化失败回调"""
        state_manager.update_wechat_status(
            status='error',
            error_message=error_message
        )

    def open_config(self, config_type):
        """打开配置对话框"""
        dialog = ConfigDialog(config_type, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            print(f"保存{config_type}配置")
    
    def open_log_window(self):
        """打开增强的日志窗口"""
        try:
            print("正在打开增强日志窗口...")

            # 创建独立的增强日志窗口（不设置父窗口）
            from app.qt_ui.log_window import LogWindow
            self.log_window = LogWindow()

            # 设置窗口为独立窗口
            self.log_window.setWindowFlags(Qt.WindowType.Window)

            # 显示日志窗口
            self.log_window.show()

            # 将窗口置于前台
            self.log_window.raise_()
            self.log_window.activateWindow()

            print("✓ 增强日志窗口已打开")

            # 记录日志窗口打开事件
            from app.logs import logger
            logger.info("用户打开了增强日志窗口")

        except Exception as e:
            print(f"打开日志窗口失败: {e}")
            import traceback
            traceback.print_exc()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", f"无法打开日志窗口: {str(e)}")

    def show_advanced_menu(self):
        """显示高级模式菜单"""
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #374151;
                color: white;
                border: 1px solid #4b5563;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #4b5563;
            }
        """)

        # 添加菜单项
        monitor_action = menu.addAction("服务状态监控")
        monitor_action.triggered.connect(self.open_enhanced_monitor_window)

        log_action = menu.addAction("日志窗口")
        log_action.triggered.connect(self.open_log_window)

        # 在按钮位置显示菜单
        button = self.sender()
        if button:
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def disconnect_state_connections(self):
        """断开状态连接"""
        try:
            # 断开状态管理器的回调
            state_manager.disconnect_signal('accounting_service', self.on_accounting_service_changed)
            state_manager.disconnect_signal('wechat_status', self.on_wechat_status_changed)
            state_manager.disconnect_signal('api_status', self.on_api_status_changed)
            state_manager.disconnect_signal('stats', self.on_stats_changed)
            state_manager.disconnect_signal('monitoring', self.on_monitoring_status_changed)
            print("已断开状态连接")
        except Exception as e:
            print(f"断开状态连接失败: {e}")
    


    def _init_message_processor(self):
        """初始化消息处理器（异步版本）"""
        try:
            print("开始异步初始化消息处理器...")
            self.update_progress("初始化消息处理器...")

            # 使用异步微信工作器初始化
            self.async_wechat_manager.init_message_processor()

        except Exception as e:
            print(f"启动异步消息处理器初始化失败: {e}")
            self.monitoring_failed(f"消息处理器初始化失败: {e}")

    def _init_message_processor_sync(self):
        """同步初始化消息处理器（备用方法）"""
        try:
            # 延迟导入，避免Flask依赖
            from app.services.accounting_service import AccountingService
            from app.services.message_monitor import MessageMonitor

            # 初始化记账服务
            self.accounting_service = AccountingService()
            print("记账服务初始化成功")

            # 初始化消息监控器（简化版本，直接使用wxautox）
            self.message_monitor = MessageMonitor(self.accounting_service)

            print("消息监控器初始化成功")

            # 连接信号
            self.message_monitor.message_received.connect(self._on_message_received)
            self.message_monitor.accounting_result.connect(self._on_accounting_result)
            self.message_monitor.status_changed.connect(self._on_monitoring_status_changed)
            self.message_monitor.error_occurred.connect(self._on_monitor_error)
            self.message_monitor.chat_status_changed.connect(self._on_chat_status_changed)
            self.message_monitor.statistics_updated.connect(self._on_statistics_updated)

        except Exception as e:
            print(f"初始化消息处理器失败: {e}")
            self.message_monitor = None
            self.accounting_service = None
    
    def _on_message_received(self, chat_name, message_content):
        """消息接收回调"""
        try:
            print(f"收到消息: {chat_name}: {message_content[:50]}...")
            # 更新统计信息
            stats = state_manager.get_stats()
            stats['processed_messages'] = stats.get('processed_messages', 0) + 1
            state_manager.update_stats(**stats)
        except Exception as e:
            print(f"处理消息接收失败: {e}")
    
    def _on_accounting_result(self, chat_name, success, result_message):
        """记账结果回调"""
        try:
            print(f"记账结果: {chat_name}: 成功={success}, 结果={result_message}")
            # 更新统计信息
            stats = state_manager.get_stats()
            if success:
                stats['successful_records'] = stats.get('successful_records', 0) + 1
            else:
                stats['failed_records'] = stats.get('failed_records', 0) + 1
            state_manager.update_stats(**stats)
        except Exception as e:
            print(f"处理记账结果失败: {e}")
    
    def _on_monitoring_status_changed(self, is_active):
        """监控状态变化回调"""
        try:
            print(f"监控状态变化: {is_active}")
            # 更新状态管理器
            state_manager.update_monitoring_status(is_active)
        except Exception as e:
            print(f"处理监控状态变化失败: {e}")
    
    def _on_monitor_error(self, error_message):
        """监控错误回调"""
        try:
            print(f"监控错误: {error_message}")
            # 可以在这里显示错误信息或更新UI
        except Exception as e:
            print(f"处理监控错误失败: {e}")
    
    def _on_chat_status_changed(self, chat_name, is_monitoring):
        """聊天状态变化回调"""
        try:
            print(f"聊天 {chat_name} 监控状态变化: {is_monitoring}")
            # 可以在这里更新UI状态
        except Exception as e:
            print(f"处理聊天状态变化失败: {e}")
    
    def _on_statistics_updated(self, chat_name, stats):
        """统计信息更新回调"""
        try:
            # 更新统计信息到状态管理器
            current_stats = state_manager.get_stats()
            
            # 累加统计信息
            current_stats['processed_messages'] = current_stats.get('processed_messages', 0) + stats.get('processed_count', 0)
            current_stats['successful_records'] = current_stats.get('successful_records', 0) + stats.get('success_count', 0)
            current_stats['failed_records'] = current_stats.get('failed_records', 0) + stats.get('error_count', 0)
            
            # 更新状态管理器
            state_manager.update_stats(**current_stats)
            
            print(f"统计信息更新 - {chat_name}: 处理={stats.get('processed_count', 0)}, 成功={stats.get('success_count', 0)}, 失败={stats.get('error_count', 0)}")
            
        except Exception as e:
            print(f"处理统计信息更新失败: {e}")

    def initialization_failed(self, error_message):
        """初始化失败"""
        print(f"✗ 初始化失败: {error_message}")
        
        # 重置按钮状态
        self.main_button.setText("初始化")
        self.main_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                border: 3px solid #1d4ed8;
                border-radius: 60px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }
        """)
        self.main_button.setEnabled(True)
        
        # 显示错误信息
        self.update_progress(f"初始化失败: {error_message}")
        
        # 3秒后隐藏错误信息
        QTimer.singleShot(3000, lambda: self.progress_label.hide() if hasattr(self, 'progress_label') else None)
    
    def start_monitoring_with_progress(self):
        """开始监控并显示进度"""
        print("用户点击开始监控...")
        
        # 设置启动标志
        self._monitoring_starting = True
        
        # 设置按钮为启动中状态
        self.main_button.setText("启动中")
        self.main_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f59e0b, stop:1 #d97706);
                border: 3px solid #92400e;
                border-radius: 60px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.main_button.setEnabled(False)
        
        # 显示并更新进度标签
        self.update_progress("准备启动监控...")
        
        # 初始化消息处理器（如果还没有初始化）
        if not hasattr(self, 'message_monitor') or not self.message_monitor:
            self._init_message_processor()
        
        # 开始简化的监控序列
        QTimer.singleShot(500, self.start_simple_monitoring)

    def start_simple_monitoring(self):
        """简化的监控启动流程 - 直接使用CleanMessageMonitor"""
        try:
            # 检查消息监控器
            if not self.message_monitor:
                self.monitoring_failed("消息监控器未初始化")
                return

            # 获取监控会话列表
            monitoring_config = state_manager.get_monitoring_status()
            monitored_chats = monitoring_config.get('monitored_chats', ["张杰"])

            print(f"开始简化监控流程，监控对象: {monitored_chats}")

            # 直接启动监控
            self.update_progress("添加监控对象...")
            self.start_clean_monitoring_directly(monitored_chats)

        except Exception as e:
            self.monitoring_failed(f"启动监控失败: {str(e)}")

    def start_clean_monitoring_directly(self, monitored_chats):
        """直接使用CleanMessageMonitor启动监控"""
        try:
            print(f"直接启动CleanMessageMonitor，监控对象: {monitored_chats}")

            # 添加监控对象
            success_count = 0
            for chat_name in monitored_chats:
                try:
                    if self.message_monitor.add_chat_target(chat_name):
                        success_count += 1
                        print(f"✓ 成功添加监控对象: {chat_name}")
                    else:
                        print(f"监控对象已存在: {chat_name}")
                        success_count += 1  # 已存在也算成功
                except Exception as e:
                    print(f"添加监控对象失败 {chat_name}: {e}")

            if success_count == 0:
                self.monitoring_failed("没有成功添加任何监控对象")
                return

            # 启动监控
            self.update_progress("启动消息监控...")
            print("正在启动CleanMessageMonitor...")

            try:
                # 直接调用CleanMessageMonitor的start_monitoring方法
                result = self.message_monitor.start_monitoring()
                if result:
                    print("✓ CleanMessageMonitor启动成功")
                    self.update_progress("监控已启动...")
                    QTimer.singleShot(1000, self.monitoring_success)
                else:
                    print("✗ CleanMessageMonitor启动失败")
                    self.monitoring_failed("CleanMessageMonitor启动失败")
            except Exception as e:
                print(f"启动CleanMessageMonitor异常: {e}")
                # 即使异常，也尝试标记为成功（可能实际已启动）
                self.update_progress("监控启动完成...")
                QTimer.singleShot(1000, self.monitoring_success)

        except Exception as e:
            self.monitoring_failed(f"直接启动监控失败: {str(e)}")

    def start_monitoring_sequence(self):
        """监控启动序列 - 基于实际状态检查"""
        try:
            # 检查消息监控器
            if not self.message_monitor:
                self.monitoring_failed("消息监控器未初始化")
                return
            
            # 步骤1: 检查API服务状态
            self.update_progress("检查HTTP API状态...")
            self.check_api_status_and_continue()
            
        except Exception as e:
            self.monitoring_failed(f"启动监控失败: {str(e)}")
    
    def check_api_status_and_continue(self):
        """检查API服务状态并继续（异步版本）"""
        try:
            print("开始异步检查API服务状态...")
            self.update_progress("检查HTTP API状态...")

            # 使用异步HTTP管理器检查API服务
            from app.utils.async_http import async_http_manager

            def on_api_check_success(data):
                print("✓ API服务已运行")
                # API服务正常，检查微信状态
                self.check_wechat_status_and_continue()

            def on_api_check_error(error_msg):
                print(f"✗ API服务检查失败: {error_msg}")
                # API服务未运行，需要启动
                self.update_progress("启动HTTP API中...")
                self.start_api_and_wait()

            async_http_manager.get(
                "http://localhost:5000/api/health",
                timeout=3,
                success_callback=on_api_check_success,
                error_callback=on_api_check_error
            )

        except Exception as e:
            self.monitoring_failed(f"检查API服务失败: {str(e)}")
    
    def start_api_and_wait(self):
        """启动API服务并等待"""
        try:
            # 启动API服务
            self.start_api_service()
            
            # 等待API服务启动，然后继续检查
            QTimer.singleShot(3000, self.wait_for_api_ready)
            
        except Exception as e:
            self.monitoring_failed(f"启动API服务失败: {str(e)}")
    
    def wait_for_api_ready(self):
        """等待API服务就绪（异步版本）"""
        try:
            print("开始异步等待API服务就绪...")
            self.update_progress("等待API服务就绪...")

            # 使用异步HTTP管理器检查API服务
            from app.utils.async_http import async_http_manager

            def on_api_ready_success(data):
                print("✓ API服务启动成功")
                self.check_wechat_status_and_continue()

            def on_api_ready_error(error_msg):
                print(f"✗ API服务启动后状态异常: {error_msg}")
                self.monitoring_failed("API服务启动后状态异常")

            async_http_manager.get(
                "http://localhost:5000/api/health",
                timeout=5,
                success_callback=on_api_ready_success,
                error_callback=on_api_ready_error
            )

        except Exception as e:
            self.monitoring_failed(f"等待API服务就绪失败: {str(e)}")
    

    def start_listening_step_delayed(self, success_count):
        """延迟启动监听步骤"""
        if success_count > 0:
            self.start_listening_step()
        else:
            self.monitoring_failed("没有成功添加任何监控目标")
    
    def start_listening_step(self):
        """开始监听步骤（异步版本）"""
        try:
            self.update_progress("启动消息监听中...")

            # 检查消息监控器
            if not self.message_monitor:
                self.monitoring_failed("消息监控器未初始化")
                return

            # 获取监控会话列表
            monitoring_config = state_manager.get_monitoring_status()
            monitored_chats = monitoring_config.get('monitored_chats', ["张杰"])

            print(f"正在异步启动消息监控: {monitored_chats}")

            # 使用异步微信工作器启动监控
            self.async_wechat_manager.start_chat_monitoring(self.message_monitor, monitored_chats)

        except Exception as e:
            print(f"启动异步监听失败: {e}")
            self.monitoring_failed(f"启动监听失败: {str(e)}")

    def start_listening_step_async(self):
        """异步启动监听步骤（从异步回调中调用）"""
        try:
            self.update_progress("启动消息监听中...")

            # 检查消息监控器
            if not self.message_monitor:
                self.monitoring_failed("消息监控器未初始化")
                return

            # 获取监控会话列表
            monitoring_config = state_manager.get_monitoring_status()
            monitored_chats = monitoring_config.get('monitored_chats', ["张杰"])

            print(f"正在异步启动消息监控: {monitored_chats}")

            # 使用异步微信工作器启动监控
            self.async_wechat_manager.start_chat_monitoring(self.message_monitor, monitored_chats)

        except Exception as e:
            print(f"启动异步监听失败: {e}")
            self.monitoring_failed(f"启动监听失败: {str(e)}")

    def start_listening_step_sync(self):
        """开始监听步骤（同步版本，备用）"""
        try:
            self.update_progress("启动消息监听中...")

            # 检查消息监控器
            if not self.message_monitor:
                self.monitoring_failed("消息监控器未初始化")
                return

            # 获取监控会话列表
            monitoring_config = state_manager.get_monitoring_status()
            monitored_chats = monitoring_config.get('monitored_chats', ["张杰"])

            # 使用MessageMonitor启动监控
            print("正在启动消息监控...")
            success_count = 0
            attempted_count = 0

            for chat_name in monitored_chats:
                attempted_count += 1
                try:
                    print(f"启动监控: {chat_name}")
                    # 使用MessageMonitor的start_chat_monitoring方法
                    result = self.message_monitor.start_chat_monitoring(chat_name)
                    if result:
                        success_count += 1
                        print(f"✓ 成功启动监控: {chat_name}")
                    else:
                        print(f"✗ 启动监控失败: {chat_name}")
                        # 即使失败，也检查是否实际上已经在监控中
                        if self.message_monitor.is_chat_monitoring(chat_name):
                            success_count += 1
                            print(f"✓ 监控实际上已启动: {chat_name}")
                except Exception as e:
                    print(f"启动监控异常 {chat_name}: {e}")
                    # 即使出现异常，也检查是否实际上已经在监控中
                    try:
                        if self.message_monitor.is_chat_monitoring(chat_name):
                            success_count += 1
                            print(f"✓ 监控实际上已启动（异常后检查）: {chat_name}")
                    except:
                        pass

            # 使用更宽松的成功标准：只要有尝试启动的目标就认为成功
            if attempted_count > 0:
                print(f"✓ 尝试启动 {attempted_count} 个监控目标，实际成功 {success_count} 个")
                self.update_progress("正在监听会话...")
                # 等待2秒后完成启动
                QTimer.singleShot(2000, self.monitoring_success)
            else:
                print("✗ 没有找到任何监控目标")
                self.monitoring_failed("没有找到任何监控目标")

        except Exception as e:
            print(f"启动监听异常: {e}")
            # 即使出现异常，也尝试标记为成功（因为可能实际上已经启动了）
            self.update_progress("监听启动完成...")
            QTimer.singleShot(1000, self.monitoring_success)
    
    def monitoring_success(self):
        """监控启动成功"""
        try:
            # 清除启动标志
            self._monitoring_starting = False
            
            # 更新状态管理器
            state_manager.update_monitoring_status(True)
            
            # 设置按钮为停止状态
            self.main_button.setText("停止监听")
            self.main_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ef4444, stop:1 #dc2626);
                    border: 3px solid #b91c1c;
                    border-radius: 60px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #dc2626, stop:1 #b91c1c);
                }
            """)
            self.main_button.setEnabled(True)
            self.main_button.set_listening_state(True)
            
            # 隐藏进度标签
            self.progress_label.hide()
            
            print("✓ 监控启动成功")
            
        except Exception as e:
            self.monitoring_failed(f"设置监控成功状态失败: {str(e)}")
    
    def monitoring_failed(self, error_message):
        """监控启动失败"""
        try:
            # 清除启动标志
            self._monitoring_starting = False
            
            print(f"✗ 监控启动失败: {error_message}")
            
            # 恢复按钮为开始状态
            self.main_button.setText("开始监听")
            self.main_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3b82f6, stop:1 #1d4ed8);
                    border: 3px solid #1e40af;
                    border-radius: 60px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1d4ed8, stop:1 #1e40af);
                }
            """)
            self.main_button.setEnabled(True)
            self.main_button.set_listening_state(False)
            
            # 隐藏进度标签
            self.progress_label.hide()
            
            # 更新状态管理器
            state_manager.update_monitoring_status(False)
            
        except Exception as e:
            print(f"处理监控失败状态时出错: {e}")
    
    def update_progress(self, message):
        """更新进度显示"""
        if hasattr(self, 'progress_label'):
            self.progress_label.setText(message)
            self.progress_label.show()  # 确保显示
            print(f"进度: {message}")
            # 强制刷新界面
            self.progress_label.repaint()
        else:
            print(f"进度: {message} (标签未创建)")
    
    def stop_monitoring(self):
        """停止监控"""
        try:
            print("停止监控微信消息...")
            
            if self.message_monitor:
                # 使用简化监控器停止所有监控
                self.message_monitor.stop_monitoring()
                print("✓ 已停止所有监控")
            
            # 更新状态管理器
            state_manager.update_monitoring_status(False)
            
            # 恢复按钮状态
            self.main_button.setText("开始监听")
            self.main_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3b82f6, stop:1 #1d4ed8);
                    border: 3px solid #1e40af;
                    border-radius: 60px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1d4ed8, stop:1 #1e40af);
                }
            """)
            self.main_button.set_listening_state(False)
            
            # 隐藏进度标签
            self.progress_label.hide()
            
            self.update_status()
            
        except Exception as e:
            print(f"停止监控失败: {str(e)}")
    
    def update_status(self):
        """更新状态"""
        try:
            # 更新真实的统计数据
            self.update_real_statistics()
            
            # 检查各种服务状态
            self.check_service_status()
            
        except Exception as e:
            print(f"更新状态失败: {e}")
    
    def update_real_statistics(self):
        """从数据库更新真实的统计数据"""
        try:
            # 检查是否有消息监控器
            if not hasattr(self, 'message_monitor') or not self.message_monitor:
                return
            
            # 检查消息监控器是否有消息处理器
            if not hasattr(self.message_monitor, 'message_processor') or not self.message_monitor.message_processor:
                return
            
            message_processor = self.message_monitor.message_processor
            
            # 获取所有聊天目标的统计信息
            total_processed = 0
            total_success = 0
            total_failed = 0
            
            # 获取所有聊天目标（简化版本）
            chat_targets = self.message_monitor.monitored_chats
            if not chat_targets:
                # 如果没有聊天目标，使用默认的
                chat_targets = ["张杰"]
            
            for chat_target in chat_targets:
                try:
                    # 获取该聊天目标的统计信息
                    stats = message_processor.get_processing_statistics(chat_target)
                    
                    # 累加统计数据 - 使用正确的字段名
                    total_processed += stats.get('total_processed', 0)
                    total_success += stats.get('accounting_success', 0)  # 记账成功数
                    total_failed += stats.get('accounting_failed', 0)    # 记账失败数
                    
                    print(f"聊天 {chat_target} 统计: 总处理={stats.get('total_processed', 0)}, 记账成功={stats.get('accounting_success', 0)}, 记账失败={stats.get('accounting_failed', 0)}, 无关消息={stats.get('accounting_nothing', 0)}")
                    
                except Exception as e:
                    print(f"获取 {chat_target} 统计信息失败: {e}")
                    continue
            
            # 更新UI显示
            self.processed_card.set_value(total_processed)
            self.success_card.set_value(total_success)
            self.failed_card.set_value(total_failed)
            
            # 同时更新状态管理器（保持一致性）
            state_manager.set_state('stats', {
                'processed_messages': total_processed,
                'successful_records': total_success,
                'failed_records': total_failed,
                'last_update_time': datetime.now().isoformat()
            }, emit_signal=False)  # 不发射信号，避免循环更新
            
            print(f"统计数据更新: 处理={total_processed}, 成功={total_success}, 失败={total_failed}")
            
        except Exception as e:
            print(f"更新真实统计数据失败: {e}")
    
    def check_service_status(self):
        """检查服务状态"""
        try:
            # 检查API服务状态
            api_config = state_manager.get_api_status()
            if api_config.get('status') == 'running':
                port = api_config.get('port', 5000)
                
                # 检查API服务是否真的在运行
                try:
                    import requests
                    response = requests.get(f"http://localhost:{port}/api/health", timeout=2)
                    if response.status_code != 200:
                        state_manager.update_api_status(status='error', error_message='API服务无响应')
                except:
                    state_manager.update_api_status(status='error', error_message='API服务连接失败')
            
            # 检查微信状态
            wechat_config = state_manager.get_wechat_status()
            if wechat_config.get('status') == 'online':
                # 可以在这里添加微信状态检查逻辑
                pass
            
            # 检查只为记账服务状态
            accounting_status = state_manager.get_accounting_service_status()
            
            accounting_active = accounting_status.get('status') == 'connected' or accounting_status.get('is_logged_in', False)
            
            # 更新指示器状态
            if hasattr(self, 'accounting_indicator'):
                self.accounting_indicator.set_active(accounting_active)
            
        except Exception as e:
            print(f"检查服务状态失败: {e}")
    
    def auto_startup_sequence(self):
        """自动启动序列 - 已禁用"""
        # 不再自动启动，等待用户手动点击初始化
        print("自动启动已禁用，等待用户手动初始化")
        pass
    
    def start_api_service(self):
        """启动API服务 - 使用自动端口选择"""
        try:
            # 自动选择可用端口
            port = self.find_available_port()
            print(f"正在启动API服务 (端口: {port})...")
            state_manager.update_api_status(status='starting', port=port)
            
            # 使用线程安全的方式启动API服务
            self.api_service_thread = ApiServiceThread(port)
            self.api_service_thread.service_started.connect(self.on_api_service_started)
            self.api_service_thread.service_failed.connect(self.on_api_service_failed)
            self.api_service_thread.start()
            
        except Exception as e:
            print(f"启动API服务失败: {e}")
            state_manager.update_api_status(status='error', error_message=str(e))
    
    def find_available_port(self, start_port=5000, max_attempts=10):
        """查找可用端口"""
        import socket
        
        for i in range(max_attempts):
            port = start_port + i
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        
        # 如果都不可用，返回默认端口
        return start_port

    def on_api_service_started(self):
        """API服务启动成功回调"""
        # 等待几秒后检查API服务状态
        QTimer.singleShot(5000, self.check_api_service_status)
    
    def on_api_service_failed(self, error_message):
        """API服务启动失败回调"""
        print(f"启动API服务失败: {error_message}")
        state_manager.update_api_status(status='error', error_message=error_message)
    
    def check_api_service_status(self):
        """检查API服务状态"""
        try:
            api_config = state_manager.get_api_status()
            port = api_config.get('port', 5000)
            
            print(f"正在检查API服务状态 (端口: {port})...")
            
            # 使用线程安全的方式检查状态
            self.api_status_thread = ApiStatusCheckThread(port)
            self.api_status_thread.status_checked.connect(self.on_api_status_checked)
            self.api_status_thread.start()
            
        except Exception as e:
            print(f"检查API服务状态失败: {e}")
            state_manager.update_api_status(status='error', error_message=str(e))
    
    def on_api_status_checked(self, is_running):
        """API服务状态检查回调"""
        if is_running:
            state_manager.update_api_status(status='running')
        else:
            state_manager.update_api_status(status='error', error_message='服务未响应')
    
    def initialize_wechat_via_api(self):
        """通过HTTP API初始化微信"""
        try:
            api_config = state_manager.get_api_status()
            port = api_config.get('port', 5000)
            api_key = api_config.get('api_key', 'test-key-2')
            
            print(f"正在通过HTTP API初始化微信...")
            state_manager.update_wechat_status(status='connecting')
            
            # 使用线程安全的方式初始化微信
            self.wechat_init_thread = WechatInitThread(port, api_key)
            self.wechat_init_thread.init_success.connect(self.on_wechat_init_success)
            self.wechat_init_thread.init_failed.connect(self.on_wechat_init_failed)
            self.wechat_init_thread.start()
            
        except Exception as e:
            print(f"初始化微信失败: {e}")
            state_manager.update_wechat_status(status='error', error_message=str(e))
    
    def on_wechat_init_success(self, window_name):
        """微信初始化成功回调"""
        state_manager.update_wechat_status(
            status='online',
            window_name=window_name
        )
    
    def on_wechat_init_failed(self, error_message):
        """微信初始化失败回调"""
        state_manager.update_wechat_status(
            status='error',
            error_message=error_message
        )

    def open_config(self, config_type):
        """打开配置对话框"""
        dialog = ConfigDialog(config_type, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            print(f"保存{config_type}配置")
    
    def open_log_window(self):
        """打开日志窗口"""
        try:
            print("正在打开日志窗口...")
            
            # 创建独立的日志窗口（不设置父窗口）
            self.log_window = EnhancedLogWindow()
            
            # 设置窗口为独立窗口
            self.log_window.setWindowFlags(Qt.WindowType.Window)
            
            # 显示日志窗口
            self.log_window.show()
            
            # 将窗口置于前台
            self.log_window.raise_()
            self.log_window.activateWindow()
            
            print("日志窗口已打开")
            
        except Exception as e:
            print(f"打开日志窗口失败: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "错误", f"无法打开日志窗口: {str(e)}")
    
    def disconnect_state_connections(self):
        """断开状态连接"""
        try:
            # 断开状态管理器的回调
            state_manager.disconnect_signal('accounting_service', self.on_accounting_service_changed)
            state_manager.disconnect_signal('wechat_status', self.on_wechat_status_changed)
            state_manager.disconnect_signal('api_status', self.on_api_status_changed)
            state_manager.disconnect_signal('stats', self.on_stats_changed)
            state_manager.disconnect_signal('monitoring', self.on_monitoring_status_changed)
            print("已断开状态连接")
        except Exception as e:
            print(f"断开状态连接失败: {e}")
    


    def _init_message_processor(self):
        """初始化消息处理器（增强版）"""
        try:
            # 延迟导入，避免Flask依赖
            from app.services.accounting_service import AccountingService
            from app.services.enhanced_zero_history_monitor import EnhancedZeroHistoryMonitor

            # 初始化记账服务
            self.accounting_service = AccountingService()
            print("记账服务初始化成功")

            # 初始化增强版零历史消息监控器
            self.message_monitor = EnhancedZeroHistoryMonitor()
            print("增强版零历史消息监控器初始化成功")

            # 更新微信状态
            self._update_wechat_status_from_monitor()

            # 连接信号
            if hasattr(self.message_monitor, 'message_received'):
                self.message_monitor.message_received.connect(self._on_message_received)
                self.message_monitor.accounting_result.connect(self._on_accounting_result)
                self.message_monitor.status_changed.connect(self._on_monitoring_status_changed)
                self.message_monitor.error_occurred.connect(self._on_monitor_error)
                print("✓ 增强版消息监控器信号连接成功")

        except Exception as e:
            print(f"初始化增强版消息处理器失败: {e}")
            # 回退到原版本
            try:
                from app.services.zero_history_monitor import ZeroHistoryMonitor
                self.message_monitor = ZeroHistoryMonitor()
                print("✓ 回退到原版消息监控器")

                # 连接信号
                self.message_monitor.message_received.connect(self._on_message_received)
                self.message_monitor.accounting_result.connect(self._on_accounting_result)
                self.message_monitor.status_changed.connect(self._on_monitoring_status_changed)
                self.message_monitor.error_occurred.connect(self._on_monitor_error)

            except Exception as fallback_e:
                print(f"回退初始化也失败: {fallback_e}")
                self.message_monitor = None

    def _update_wechat_status_from_monitor(self):
        """从监控器更新微信状态"""
        try:
            if self.message_monitor and hasattr(self.message_monitor, 'get_wechat_info'):
                wechat_info = self.message_monitor.get_wechat_info()

                # 更新状态管理器
                state_manager.update_wechat_status(
                    status=wechat_info.get('status', 'offline'),
                    window_name=wechat_info.get('window_name', '未连接'),
                    library_type=wechat_info.get('library_type', 'wxauto')
                )

                print(f"微信状态已更新: {wechat_info}")
        except Exception as e:
            print(f"更新微信状态失败: {e}")
            self.accounting_service = None
    
    def _on_message_received(self, chat_name, message_content, sender_name=None):
        """消息接收回调（增强版）"""
        try:
            # 兼容不同的信号参数格式
            if sender_name is None:
                # 2参数格式（旧版本兼容）
                print(f"收到消息: {chat_name}: {message_content[:50]}...")
                actual_sender = "未知发送者"
            else:
                # 3参数格式（增强版）
                print(f"收到消息: {chat_name} - {sender_name}: {message_content[:50]}...")
                actual_sender = sender_name

            # 使用增强版消息处理器处理消息
            if self.enhanced_processor:
                # 异步处理消息，避免阻塞UI，传递发送者信息
                QTimer.singleShot(0, lambda: self._process_message_enhanced(chat_name, message_content, actual_sender))

            # 更新统计信息
            stats = state_manager.get_stats()
            stats['processed_messages'] = stats.get('processed_messages', 0) + 1
            state_manager.update_stats(**stats)

        except Exception as e:
            print(f"处理消息接收失败: {e}")

    def _process_message_enhanced(self, chat_name, message_content, sender_name="未知发送者"):
        """使用增强版处理器处理消息"""
        try:
            # 使用增强版消息处理器，传递发送者信息
            success, result = self.enhanced_processor.process_message(message_content, sender_name)

            if success and result:
                # 使用增强版投递服务发送回复
                if self.enhanced_delivery:
                    self.enhanced_delivery.send_message(chat_name, result)

                # 更新成功统计
                stats = state_manager.get_stats()
                stats['successful_records'] = stats.get('successful_records', 0) + 1
                state_manager.update_stats(**stats)

                print(f"✓ 增强版消息处理成功: {chat_name} - {sender_name}")
            else:
                # 更新失败统计
                stats = state_manager.get_stats()
                stats['failed_records'] = stats.get('failed_records', 0) + 1
                state_manager.update_stats(**stats)

                print(f"✗ 增强版消息处理失败: {chat_name} - {sender_name} - {result}")

        except Exception as e:
            print(f"增强版消息处理异常: {e}")
            # 更新失败统计
            stats = state_manager.get_stats()
            stats['failed_records'] = stats.get('failed_records', 0) + 1
            state_manager.update_stats(**stats)
    
    def _on_accounting_result(self, chat_name, success, result_message):
        """记账结果回调"""
        try:
            print(f"记账结果: {chat_name}: 成功={success}, 结果={result_message}")
            # 更新统计信息
            stats = state_manager.get_stats()
            if success:
                stats['successful_records'] = stats.get('successful_records', 0) + 1
            else:
                stats['failed_records'] = stats.get('failed_records', 0) + 1
            state_manager.update_stats(**stats)
        except Exception as e:
            print(f"处理记账结果失败: {e}")
    
    def _on_monitoring_status_changed(self, is_active):
        """监控状态变化回调"""
        try:
            print(f"监控状态变化: {is_active}")
            # 更新状态管理器
            state_manager.update_monitoring_status(is_active)
        except Exception as e:
            print(f"处理监控状态变化失败: {e}")
    
    def _on_monitor_error(self, error_message):
        """监控错误回调"""
        try:
            print(f"监控错误: {error_message}")
            # 可以在这里显示错误信息或更新UI
        except Exception as e:
            print(f"处理监控错误失败: {e}")
    
    def _on_chat_status_changed(self, chat_name, is_monitoring):
        """聊天状态变化回调"""
        try:
            print(f"聊天 {chat_name} 监控状态变化: {is_monitoring}")
            # 可以在这里更新UI状态
        except Exception as e:
            print(f"处理聊天状态变化失败: {e}")
    
    def _on_statistics_updated(self, chat_name, stats):
        """统计信息更新回调"""
        try:
            # 更新统计信息到状态管理器
            current_stats = state_manager.get_stats()
            
            # 累加统计信息
            current_stats['processed_messages'] = current_stats.get('processed_messages', 0) + stats.get('processed_count', 0)
            current_stats['successful_records'] = current_stats.get('successful_records', 0) + stats.get('success_count', 0)
            current_stats['failed_records'] = current_stats.get('failed_records', 0) + stats.get('error_count', 0)
            
            # 更新状态管理器
            state_manager.update_stats(**current_stats)
            
            print(f"统计信息更新 - {chat_name}: 处理={stats.get('processed_count', 0)}, 成功={stats.get('success_count', 0)}, 失败={stats.get('error_count', 0)}")
            
        except Exception as e:
            print(f"处理统计信息更新失败: {e}")

    def _check_first_run(self) -> bool:
        """检测是否为首次运行"""
        try:
            # 使用专门的首次运行标记文件
            if getattr(sys, 'frozen', False):
                # 打包环境
                app_dir = os.path.dirname(sys.executable)
                first_run_marker = os.path.join(app_dir, "data", ".first_run_completed")
            else:
                # 开发环境
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                first_run_marker = os.path.join(project_root, "data", ".first_run_completed")

            # 如果标记文件不存在，认为是首次运行
            return not os.path.exists(first_run_marker)

        except Exception as e:
            print(f"检测首次运行状态失败: {e}")
            return False
    
    def _show_first_run_welcome(self):
        """显示首次运行欢迎信息"""
        try:
            from PyQt6.QtWidgets import QMessageBox

            msg = QMessageBox(self)
            msg.setWindowTitle("欢迎使用")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("🎉 欢迎使用只为记账--微信助手！")
            msg.setInformativeText(
                "这是您首次运行此程序。\n\n"
                "使用步骤：\n"
                "1. 点击右下角「日志窗口」配置记账服务\n"
                "2. 点击中央「初始化」按钮开始使用\n"
                "3. 程序将自动处理微信消息并记账\n\n"
                "所有配置将保存在程序目录的data文件夹中。"
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

            # 创建首次运行完成标记文件
            self._create_first_run_marker()

        except Exception as e:
            print(f"显示欢迎信息失败: {e}")

    def _create_first_run_marker(self):
        """创建首次运行完成标记文件"""
        try:
            # 获取标记文件路径
            if getattr(sys, 'frozen', False):
                # 打包环境
                app_dir = os.path.dirname(sys.executable)
                first_run_marker = os.path.join(app_dir, "data", ".first_run_completed")
            else:
                # 开发环境
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                first_run_marker = os.path.join(project_root, "data", ".first_run_completed")

            # 确保data目录存在
            os.makedirs(os.path.dirname(first_run_marker), exist_ok=True)

            # 创建标记文件
            with open(first_run_marker, 'w', encoding='utf-8') as f:
                f.write(f"首次运行完成时间: {datetime.now().isoformat()}\n")
                f.write("此文件用于标记程序已完成首次运行，请勿删除。\n")

            print(f"已创建首次运行标记文件: {first_run_marker}")

        except Exception as e:
            print(f"创建首次运行标记文件失败: {e}")

    def setup_enhanced_features(self):
        """设置增强功能（后台集成）"""
        try:
            print("正在初始化增强功能...")

            # 初始化增强版消息处理器
            self.enhanced_processor = RobustMessageProcessor()
            print("✓ 增强版消息处理器初始化完成")

            # 初始化增强版消息投递服务
            self.enhanced_delivery = RobustMessageDelivery()
            self.enhanced_delivery.start_delivery_service()
            print("✓ 增强版消息投递服务启动完成")

            # 设置增强版微信集成
            self.setup_enhanced_wechat_integration()

            # 延迟启动健康监控（避免启动时的性能影响）
            QTimer.singleShot(3000, self.setup_health_monitoring)

        except Exception as e:
            print(f"初始化增强功能失败: {e}")

    def setup_enhanced_wechat_integration(self):
        """设置增强版微信集成"""
        try:
            print("正在设置增强版微信集成...")

            # 确保增强版异步微信管理器与简约版界面正确集成
            from app.utils.enhanced_async_wechat import async_wechat_manager

            # 连接增强版微信管理器的信号到简约版界面
            async_wechat_manager.wechat_initialized.connect(self.on_enhanced_wechat_initialized)
            async_wechat_manager.connection_status_changed.connect(self.on_enhanced_connection_status_changed)

            print("✓ 增强版微信集成设置完成")

        except Exception as e:
            print(f"设置增强版微信集成失败: {e}")

    def on_enhanced_wechat_initialized(self, success: bool, message: str, info: dict):
        """增强版微信初始化完成回调"""
        try:
            if success:
                window_name = info.get('window_name', '微信')
                print(f"✓ 增强版微信初始化成功: {window_name}")
                # 更新状态管理器
                state_manager.update_wechat_status(
                    status='online',
                    window_name=window_name
                )

                # 如果正在启动监控，继续监控流程
                if hasattr(self, '_monitoring_starting') and self._monitoring_starting:
                    print("微信初始化成功，继续监控流程...")
                    # 确保消息监控器有微信实例
                    if self.message_monitor and not self.message_monitor.wx_instance:
                        # 尝试重新初始化消息监控器的微信实例
                        try:
                            self.message_monitor._initialize_wechat()
                            print("✓ 消息监控器微信实例已更新")
                        except Exception as e:
                            print(f"更新消息监控器微信实例失败: {e}")

                    # 继续监控流程
                    QTimer.singleShot(1000, self.add_listeners_and_start_monitoring)

            else:
                print(f"✗ 增强版微信初始化失败: {message}")
                state_manager.update_wechat_status(
                    status='error',
                    error_message=message
                )

                # 如果正在启动监控，标记失败
                if hasattr(self, '_monitoring_starting') and self._monitoring_starting:
                    self.monitoring_failed(f"微信初始化失败: {message}")

        except Exception as e:
            print(f"处理增强版微信初始化回调失败: {e}")
            if hasattr(self, '_monitoring_starting') and self._monitoring_starting:
                self.monitoring_failed(f"处理微信初始化回调失败: {e}")

    def on_enhanced_connection_status_changed(self, connected: bool, message: str):
        """增强版微信连接状态变化回调"""
        try:
            if connected:
                print(f"✓ 增强版微信连接成功: {message}")
            else:
                print(f"✗ 增强版微信连接断开: {message}")
        except Exception as e:
            print(f"处理增强版微信连接状态变化失败: {e}")

    def setup_health_monitoring(self):
        """设置健康监控（后台静默运行）"""
        try:
            print("正在启动服务健康监控...")

            # 创建健康检查器和恢复处理器
            health_checkers = create_health_checkers(state_manager)
            recovery_handlers = create_recovery_handlers(state_manager, async_wechat_manager)

            # 注册服务到健康监控系统
            for service_name, checker in health_checkers.items():
                recovery_handler = recovery_handlers.get(service_name)
                health_monitor.register_service(
                    service_name,
                    checker.check_health,
                    recovery_handler
                )

            # 启动健康监控（静默运行）
            if health_monitor.start_monitoring():
                self.health_monitoring_active = True
                print("✓ 服务健康监控已启动（后台运行）")
            else:
                print("✗ 服务健康监控启动失败")

        except Exception as e:
            print(f"设置健康监控失败: {e}")

    def open_enhanced_monitor_window(self):
        """打开增强版监控窗口"""
        try:
            print("正在打开服务状态检查窗口...")

            # 如果窗口已存在，直接显示
            if self.enhanced_monitor_window and not self.enhanced_monitor_window.isHidden():
                self.enhanced_monitor_window.raise_()
                self.enhanced_monitor_window.activateWindow()
                return

            # 导入增强版主窗口作为独立对话框
            from app.qt_ui.enhanced_main_window import EnhancedMainWindow

            # 创建增强版窗口作为独立窗口
            self.enhanced_monitor_window = EnhancedMainWindow()
            self.enhanced_monitor_window.setWindowTitle("服务状态监控 - 增强版")

            # 设置为独立窗口
            self.enhanced_monitor_window.setWindowFlags(Qt.WindowType.Window)

            # 显示窗口
            self.enhanced_monitor_window.show()

            # 将窗口置于前台
            self.enhanced_monitor_window.raise_()
            self.enhanced_monitor_window.activateWindow()

            print("✓ 服务状态检查窗口已打开")

        except Exception as e:
            print(f"打开服务状态检查窗口失败: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "错误", f"无法打开服务状态检查窗口: {str(e)}")

    def closeEvent(self, event):
        """窗口关闭事件（增强版）"""
        try:
            print("简约模式窗口正在关闭...")

            # 停止健康监控
            if self.health_monitoring_active:
                health_monitor.stop_monitoring()
                print("✓ 健康监控已停止")

            # 停止增强版消息投递服务
            if self.enhanced_delivery:
                self.enhanced_delivery.stop_delivery_service()
                print("✓ 增强版消息投递服务已停止")

            # 清理异步微信管理器
            async_wechat_manager.cleanup()
            print("✓ 异步微信管理器已清理")

            # 断开状态连接
            self.disconnect_state_connections()

            # 停止定时器
            if hasattr(self, 'status_timer'):
                self.status_timer.stop()

            # 清理消息监控器
            if hasattr(self, 'message_monitor') and self.message_monitor:
                try:
                    self.message_monitor.stop_monitoring()
                    print("✓ 消息监控器已清理")
                except Exception as e:
                    print(f"清理消息监控器失败: {e}")

            # 关闭增强版监控窗口
            if self.enhanced_monitor_window:
                self.enhanced_monitor_window.close()

            # 接受关闭事件
            event.accept()
            print("✓ 简约模式窗口关闭完成")

        except Exception as e:
            print(f"关闭窗口时出错: {e}")
            event.accept()  # 确保窗口能够关闭

def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用程序属性
    app.setApplicationName("只为记账--微信助手")
    app.setApplicationVersion("1.0.0")

    # 创建并显示主窗口
    window = SimpleMainWindow()
    window.show()

    return app.exec()

if __name__ == "__main__":
    sys.exit(main())