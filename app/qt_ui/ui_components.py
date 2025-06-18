"""
UI组件模块
包含可复用的UI组件
"""

from PyQt6.QtWidgets import (QPushButton, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QDialog, QLineEdit, QComboBox, QCheckBox,
                             QSpinBox, QTextEdit, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QPen, QBrush, QLinearGradient


class CircularButton(QPushButton):
    """圆形主控按钮"""
    
    def __init__(self, text="开始监听", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(120, 120)  # 60px半径
        self.is_listening = False
        
        # 设置样式
        self.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 60px;
                background-color: #3b82f6;
                color: white;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Microsoft YaHei';
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)
        
        # 动画效果
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 闪烁动画
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self._toggle_blink)
        self.blink_state = False
    
    def paintEvent(self, event):
        """自定义绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # 绘制背景圆形
        if self.is_listening:
            # 监听状态：红色
            if self.blink_state:
                color = QColor(239, 68, 68)  # 亮红色
            else:
                color = QColor(220, 38, 38)  # 暗红色
        else:
            # 非监听状态：蓝色
            color = QColor(59, 130, 246)
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawEllipse(rect)
        
        # 绘制文本
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        
        text = "停止监听" if self.is_listening else "开始监听"
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    
    def set_listening_state(self, is_listening: bool):
        """设置监听状态"""
        self.is_listening = is_listening
        
        if is_listening:
            # 开始闪烁
            self.blink_timer.start(500)  # 每500ms闪烁一次
        else:
            # 停止闪烁
            self.blink_timer.stop()
            self.blink_state = False
        
        self.update()
    
    def _toggle_blink(self):
        """切换闪烁状态"""
        self.blink_state = not self.blink_state
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
        
        self.setFixedSize(150, 80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # 闪烁动画
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self._toggle_blink)
        self.blink_state = False
    
    def paintEvent(self, event):
        """自定义绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # 绘制背景
        background_color = QColor(30, 41, 59)  # slate-800
        painter.setBrush(QBrush(background_color))
        painter.setPen(QPen(QColor(51, 65, 85), 1))  # slate-600
        painter.drawRoundedRect(rect, 8, 8)
        
        # 绘制状态指示点
        indicator_rect = QRect(10, 10, 12, 12)
        
        if self.is_active:
            if self.is_blinking and self.blink_state:
                indicator_color = QColor(34, 197, 94)  # 亮绿色
            else:
                indicator_color = QColor(22, 163, 74)  # 绿色
        else:
            indicator_color = QColor(156, 163, 175)  # 灰色
        
        painter.setBrush(QBrush(indicator_color))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawEllipse(indicator_rect)
        
        # 绘制标题
        painter.setPen(QColor(241, 245, 249))  # slate-100
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title_rect = QRect(30, 8, rect.width() - 40, 20)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)
        
        # 绘制副标题
        painter.setPen(QColor(148, 163, 184))  # slate-400
        painter.setFont(QFont("Microsoft YaHei", 8))
        subtitle_rect = QRect(30, 28, rect.width() - 40, 40)
        painter.drawText(subtitle_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.subtitle)
    
    def set_active(self, active: bool, blinking: bool = False):
        """设置活跃状态"""
        self.is_active = active
        self.is_blinking = blinking
        
        if blinking and active:
            self.blink_timer.start(500)
        else:
            self.blink_timer.stop()
            self.blink_state = False
        
        self.update()
    
    def set_subtitle(self, subtitle: str):
        """设置副标题"""
        self.subtitle = subtitle
        self.update()
    
    def _toggle_blink(self):
        """切换闪烁状态"""
        self.blink_state = not self.blink_state
        self.update()
    
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
        
        self.setFixedSize(80, 60)
    
    def paintEvent(self, event):
        """自定义绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # 绘制背景
        painter.setBrush(QBrush(QColor(51, 65, 85)))  # slate-600
        painter.setPen(QPen(QColor(71, 85, 105), 1))  # slate-500
        painter.drawRoundedRect(rect, 6, 6)
        
        # 绘制数值
        painter.setPen(QColor(241, 245, 249))  # slate-100
        painter.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        value_rect = QRect(0, 8, rect.width(), 25)
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignCenter, str(self.value))
        
        # 绘制标题
        painter.setPen(QColor(156, 163, 175))  # slate-400
        painter.setFont(QFont("Microsoft YaHei", 8))
        title_rect = QRect(0, 35, rect.width(), 20)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.title)
    
    def set_value(self, value):
        """设置数值"""
        self.value = value
        self.update()


class ConfigDialog(QDialog):
    """配置对话框"""
    
    def __init__(self, config_type, parent=None):
        super().__init__(parent)
        self.config_type = config_type
        self.setWindowTitle(f"{config_type}配置")
        self.setModal(True)
        self.resize(400, 300)
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: white;
            }
            QLabel {
                color: white;
                font-family: 'Microsoft YaHei';
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 8px;
                color: white;
                font-family: 'Microsoft YaHei';
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #3b82f6;
            }
            QPushButton {
                background-color: #475569;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
                font-size: 12px;
                font-family: 'Microsoft YaHei';
            }
            QPushButton:hover {
                background-color: #64748b;
            }
            QPushButton:pressed {
                background-color: #334155;
            }
            QCheckBox {
                color: white;
                font-family: 'Microsoft YaHei';
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #334155;
                border-radius: 3px;
                background-color: #1e293b;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
        """)
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 根据配置类型创建不同的界面
        if self.config_type == "记账服务":
            self.create_accounting_config_ui(layout)
        elif self.config_type == "微信服务":
            self.create_wechat_config_ui(layout)
        else:
            # 通用配置界面
            label = QLabel(f"{self.config_type}配置功能开发中...")
            layout.addWidget(label)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def create_accounting_config_ui(self, layout):
        """创建记账配置UI"""
        # 服务器地址
        layout.addWidget(QLabel("服务器地址:"))
        self.server_edit = QLineEdit()
        layout.addWidget(self.server_edit)
        
        # 用户名
        layout.addWidget(QLabel("用户名:"))
        self.username_edit = QLineEdit()
        layout.addWidget(self.username_edit)
        
        # 密码
        layout.addWidget(QLabel("密码:"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_edit)
    
    def create_wechat_config_ui(self, layout):
        """创建微信配置UI"""
        # 启用监控
        self.enabled_check = QCheckBox("启用微信监控")
        layout.addWidget(self.enabled_check)
        
        # 监控聊天列表
        layout.addWidget(QLabel("监控聊天列表 (每行一个):"))
        self.chats_edit = QTextEdit()
        self.chats_edit.setMaximumHeight(100)
        layout.addWidget(self.chats_edit)
        
        # 自动回复
        self.auto_reply_check = QCheckBox("启用自动回复")
        layout.addWidget(self.auto_reply_check)
        
        # 回复模板
        layout.addWidget(QLabel("回复模板:"))
        self.template_edit = QLineEdit()
        layout.addWidget(self.template_edit)
