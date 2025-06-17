import sys
import logging
import re
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                             QPushButton, QCheckBox, QLabel, QFrame, QSplitter,
                             QGroupBox, QScrollArea, QApplication)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QColor, QPalette

from app.logs import log_memory_handler, logger, log_signal_emitter


class LogDisplayWidget(QTextEdit):
    """日志显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        
        # 字体设置
        self.base_font_size = 11  # 增加基础字体大小
        self.current_font_size = self.base_font_size
        self.font_family = "Consolas"
        self.update_font()
        
        # 设置样式
        self.update_style()
        
        # 自动滚动到底部
        self.auto_scroll = True
        # 记录当前显示的日志数量，用于性能优化
        self.displayed_log_count = 0
    
    def update_font(self):
        """更新字体"""
        font = QFont(self.font_family, self.current_font_size)
        self.setFont(font)
    
    def update_style(self):
        """更新样式"""
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                padding: 8px;
                font-family: '{self.font_family}', 'Monaco', monospace;
                font-size: {self.current_font_size}px;
                line-height: 1.4;
            }}
            QScrollBar:vertical {{
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #666666;
            }}
        """)
    
    def zoom_in(self):
        """放大字体"""
        if self.current_font_size < 24:  # 最大字体大小限制
            self.current_font_size += 1
            self.update_font()
            self.update_style()
    
    def zoom_out(self):
        """缩小字体"""
        if self.current_font_size > 8:  # 最小字体大小限制
            self.current_font_size -= 1
            self.update_font()
            self.update_style()
    
    def reset_zoom(self):
        """重置字体大小"""
        self.current_font_size = self.base_font_size
        self.update_font()
        self.update_style()
        
    def append_log(self, log_text, log_level):
        """添加日志文本"""
        # 根据日志级别设置颜色
        color = self.get_log_color(log_level)
        
        # 移动到文档末尾
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # 转义HTML特殊字符
        escaped_text = log_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # 插入带颜色的文本
        cursor.insertHtml(f'<span style="color: {color};">{escaped_text}</span><br>')
        
        # 增加显示计数
        self.displayed_log_count += 1
        
        # 如果日志太多，清理旧的日志以保持性能
        if self.displayed_log_count > 1000:
            self.trim_logs()
        
        # 自动滚动到底部
        if self.auto_scroll:
            self.ensureCursorVisible()
    
    def trim_logs(self):
        """清理旧的日志以保持性能"""
        try:
            # 获取当前文档
            document = self.document()
            cursor = QTextCursor(document)
            
            # 移动到文档开始
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            
            # 删除前面的一半日志
            lines_to_delete = self.displayed_log_count // 2
            for _ in range(lines_to_delete):
                cursor.select(QTextCursor.SelectionType.LineUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # 删除换行符
            
            # 更新计数
            self.displayed_log_count = self.displayed_log_count - lines_to_delete
            
        except Exception as e:
            print(f"清理日志失败: {e}")
    
    def get_log_color(self, log_level):
        """根据日志级别获取颜色"""
        colors = {
            'DEBUG': '#9cdcfe',    # 浅蓝色
            'INFO': '#d4d4d4',     # 白色
            'WARNING': '#dcdcaa',  # 黄色
            'ERROR': '#f44747',    # 红色
            'CRITICAL': '#ff6b6b'  # 亮红色
        }
        return colors.get(log_level, '#d4d4d4')
    
    def clear_logs(self):
        """清空日志"""
        self.clear()
        self.displayed_log_count = 0


class LogFilterWindow(QWidget):
    """日志过滤器独立窗口"""
    
    filter_changed = pyqtSignal()
    clear_logs = pyqtSignal()
    refresh_logs = pyqtSignal()
    zoom_in = pyqtSignal()
    zoom_out = pyqtSignal()
    reset_zoom = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("日志过滤器")
        
        # 设置窗口位置和大小
        self.setGeometry(50, 50, 300, 550)
        
        # 设置为独立的浮动窗口，始终置顶
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        # 设置最小窗口大小
        self.setMinimumSize(280, 500)
        
        # 设置窗口样式
        self.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                color: #ffffff;
            }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("日志过滤器")
        title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                margin-bottom: 10px;
                padding: 10px;
                background-color: #374151;
                border-radius: 8px;
                text-align: center;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 日志级别过滤
        level_group = QGroupBox("日志级别")
        level_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3e3e3e;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                color: #ffffff;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background-color: #2d2d2d;
            }
        """)
        level_layout = QVBoxLayout(level_group)
        level_layout.setSpacing(10)
        
        # 创建复选框
        self.debug_cb = QCheckBox("DEBUG")
        self.info_cb = QCheckBox("INFO")
        self.warning_cb = QCheckBox("WARNING")
        self.error_cb = QCheckBox("ERROR")
        
        # 默认选中INFO和以上级别
        self.info_cb.setChecked(True)
        self.warning_cb.setChecked(True)
        self.error_cb.setChecked(True)
        
        # 设置复选框样式
        checkbox_style = """
            QCheckBox {
                color: #ffffff;
                font-size: 13px;
                spacing: 10px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #555555;
                background-color: #2d2d2d;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #0078d4;
                background-color: #0078d4;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #106ebe;
            }
            QCheckBox:hover {
                background-color: #3e3e3e;
                border-radius: 4px;
            }
        """
        
        for cb in [self.debug_cb, self.info_cb, self.warning_cb, self.error_cb]:
            cb.setStyleSheet(checkbox_style)
            cb.stateChanged.connect(self.filter_changed.emit)
            level_layout.addWidget(cb)
        
        layout.addWidget(level_group)
        
        # 实时更新选项
        realtime_group = QGroupBox("更新选项")
        realtime_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3e3e3e;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                color: #ffffff;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background-color: #2d2d2d;
            }
        """)
        realtime_layout = QVBoxLayout(realtime_group)
        realtime_layout.setSpacing(10)
        
        self.realtime_cb = QCheckBox("实时更新")
        self.realtime_cb.setChecked(True)
        self.realtime_cb.setStyleSheet(checkbox_style)
        realtime_layout.addWidget(self.realtime_cb)
        
        self.autoscroll_cb = QCheckBox("自动滚动")
        self.autoscroll_cb.setChecked(True)
        self.autoscroll_cb.setStyleSheet(checkbox_style)
        realtime_layout.addWidget(self.autoscroll_cb)
        
        layout.addWidget(realtime_group)
        
        # 字体大小控制
        font_group = QGroupBox("字体大小")
        font_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3e3e3e;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                color: #ffffff;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background-color: #2d2d2d;
            }
        """)
        font_layout = QVBoxLayout(font_group)
        font_layout.setSpacing(10)
        
        # 字体大小按钮
        font_button_layout = QHBoxLayout()
        font_button_layout.setSpacing(8)
        
        self.zoom_out_btn = QPushButton("A-")
        self.zoom_out_btn.setToolTip("缩小字体")
        self.zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: bold;
                min-width: 35px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        
        self.zoom_reset_btn = QPushButton("A")
        self.zoom_reset_btn.setToolTip("重置字体大小")
        self.zoom_reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: bold;
                min-width: 35px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:pressed {
                background-color: #117a8b;
            }
        """)
        
        self.zoom_in_btn = QPushButton("A+")
        self.zoom_in_btn.setToolTip("放大字体")
        self.zoom_in_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: bold;
                min-width: 35px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        
        # 连接信号
        self.zoom_out_btn.clicked.connect(self.zoom_out.emit)
        self.zoom_reset_btn.clicked.connect(self.reset_zoom.emit)
        self.zoom_in_btn.clicked.connect(self.zoom_in.emit)
        
        font_button_layout.addWidget(self.zoom_out_btn)
        font_button_layout.addWidget(self.zoom_reset_btn)
        font_button_layout.addWidget(self.zoom_in_btn)
        
        font_layout.addLayout(font_button_layout)
        
        # 字体大小显示标签
        self.font_size_label = QLabel("字体: 11px")
        self.font_size_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 11px;
                text-align: center;
                margin-top: 8px;
                padding: 5px;
                background-color: #374151;
                border-radius: 4px;
            }
        """)
        self.font_size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font_layout.addWidget(self.font_size_label)
        
        layout.addWidget(font_group)
        
        # 控制按钮
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 20px;
                font-size: 13px;
                font-weight: bold;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
        """)
        
        self.refresh_btn = QPushButton("刷新日志")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 20px;
                font-size: 13px;
                font-weight: bold;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        
        # 连接信号
        self.clear_btn.clicked.connect(self.clear_logs.emit)
        self.refresh_btn.clicked.connect(self.refresh_logs.emit)
        
        button_layout.addWidget(self.clear_btn)
        button_layout.addWidget(self.refresh_btn)
        layout.addLayout(button_layout)
        
        layout.addStretch()
    
    def get_enabled_levels(self):
        """获取启用的日志级别"""
        levels = []
        if self.debug_cb.isChecked():
            levels.append('DEBUG')
        if self.info_cb.isChecked():
            levels.append('INFO')
        if self.warning_cb.isChecked():
            levels.append('WARNING')
        if self.error_cb.isChecked():
            levels.append('ERROR')
        return levels
    
    def is_realtime_enabled(self):
        """是否启用实时更新"""
        return self.realtime_cb.isChecked()
    
    def is_autoscroll_enabled(self):
        """是否启用自动滚动"""
        return self.autoscroll_cb.isChecked()
    
    def update_font_size_label(self, font_size):
        """更新字体大小标签"""
        self.font_size_label.setText(f"字体: {font_size}px")
    
    def closeEvent(self, event):
        """窗口关闭事件 - 隐藏而不是关闭"""
        self.hide()
        event.ignore()


class LogFilterWidget(QWidget):
    """日志过滤器组件（保留用于兼容性）"""
    
    filter_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # 这个类现在只是一个占位符，实际功能由LogFilterWindow提供
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 显示提示信息
        info_label = QLabel("日志过滤器已移至\n独立窗口")
        info_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #ffffff;
                text-align: center;
                padding: 20px;
                background-color: #374151;
                border-radius: 8px;
            }
        """)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)
        
        layout.addStretch()
    
    def get_enabled_levels(self):
        """获取启用的日志级别（兼容性方法）"""
        return ['INFO', 'WARNING', 'ERROR']
    
    def is_realtime_enabled(self):
        """是否启用实时更新（兼容性方法）"""
        return True
    
    def is_autoscroll_enabled(self):
        """是否启用自动滚动（兼容性方法）"""
        return True
    
    def update_font_size_label(self, font_size):
        """更新字体大小标签（兼容性方法）"""
        pass


class LogWindow(QWidget):
    """日志窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("日志窗口 - 只为记账微信助手")
        
        # 设置为独立窗口
        self.setWindowFlags(Qt.WindowType.Window)
        
        # 设置窗口大小和位置
        self.setGeometry(200, 100, 1200, 700)
        
        # 设置最小窗口大小
        self.setMinimumSize(800, 500)
        
        # 设置窗口图标和样式
        self.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                color: #ffffff;
            }
        """)
        
        self.setup_ui()
        self.setup_connections()
        
        # 初始加载日志
        self.refresh_logs()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 创建工具栏
        toolbar_layout = QVBoxLayout()
        toolbar_layout.setSpacing(8)
        
        # 第一行：标题和基本控制按钮
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("日志窗口")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                padding: 8px;
            }
        """)
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
        """)
        clear_btn.clicked.connect(self.clear_logs)
        title_layout.addWidget(clear_btn)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_logs)
        title_layout.addWidget(refresh_btn)
        
        toolbar_layout.addLayout(title_layout)
        
        # 第二行：过滤器控件
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(15)
        
        # 日志级别过滤
        level_label = QLabel("日志级别:")
        level_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: bold;")
        filter_layout.addWidget(level_label)
        
        self.debug_cb = QCheckBox("DEBUG")
        self.info_cb = QCheckBox("INFO")
        self.warning_cb = QCheckBox("WARNING")
        self.error_cb = QCheckBox("ERROR")
        
        # 默认选中INFO和以上级别
        self.info_cb.setChecked(True)
        self.warning_cb.setChecked(True)
        self.error_cb.setChecked(True)
        
        # 设置复选框样式
        checkbox_style = """
            QCheckBox {
                color: #ffffff;
                font-size: 11px;
                spacing: 5px;
                padding: 2px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555555;
                background-color: #2d2d2d;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #0078d4;
                background-color: #0078d4;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #106ebe;
            }
            QCheckBox:hover {
                background-color: #3e3e3e;
                border-radius: 3px;
            }
        """
        
        for cb in [self.debug_cb, self.info_cb, self.warning_cb, self.error_cb]:
            cb.setStyleSheet(checkbox_style)
            cb.stateChanged.connect(self.refresh_logs)
            filter_layout.addWidget(cb)
        
        # 分隔线
        separator1 = QLabel("|")
        separator1.setStyleSheet("color: #555555; font-size: 14px;")
        filter_layout.addWidget(separator1)
        
        # 实时更新选项
        self.realtime_cb = QCheckBox("实时更新")
        self.realtime_cb.setChecked(True)
        self.realtime_cb.setStyleSheet(checkbox_style)
        filter_layout.addWidget(self.realtime_cb)
        
        self.autoscroll_cb = QCheckBox("自动滚动")
        self.autoscroll_cb.setChecked(True)
        self.autoscroll_cb.setStyleSheet(checkbox_style)
        self.autoscroll_cb.stateChanged.connect(self.on_autoscroll_changed)
        filter_layout.addWidget(self.autoscroll_cb)
        
        # 分隔线
        separator2 = QLabel("|")
        separator2.setStyleSheet("color: #555555; font-size: 14px;")
        filter_layout.addWidget(separator2)
        
        # 字体大小控制
        font_label = QLabel("字体:")
        font_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: bold;")
        filter_layout.addWidget(font_label)
        
        self.zoom_out_btn = QPushButton("A-")
        self.zoom_out_btn.setToolTip("缩小字体")
        self.zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: bold;
                min-width: 25px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        
        self.zoom_reset_btn = QPushButton("A")
        self.zoom_reset_btn.setToolTip("重置字体大小")
        self.zoom_reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: bold;
                min-width: 25px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:pressed {
                background-color: #117a8b;
            }
        """)
        
        self.zoom_in_btn = QPushButton("A+")
        self.zoom_in_btn.setToolTip("放大字体")
        self.zoom_in_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: bold;
                min-width: 25px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        
        # 连接信号
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_reset_btn.clicked.connect(self.reset_zoom)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        
        filter_layout.addWidget(self.zoom_out_btn)
        filter_layout.addWidget(self.zoom_reset_btn)
        filter_layout.addWidget(self.zoom_in_btn)
        
        # 字体大小显示标签
        self.font_size_label = QLabel("11px")
        self.font_size_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 10px;
                text-align: center;
                padding: 2px 4px;
                background-color: #374151;
                border-radius: 3px;
                min-width: 30px;
            }
        """)
        self.font_size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filter_layout.addWidget(self.font_size_label)
        
        filter_layout.addStretch()
        
        toolbar_layout.addLayout(filter_layout)
        
        # 添加分隔线
        separator_line = QFrame()
        separator_line.setFrameShape(QFrame.Shape.HLine)
        separator_line.setFrameShadow(QFrame.Shadow.Sunken)
        separator_line.setStyleSheet("QFrame { color: #3e3e3e; }")
        toolbar_layout.addWidget(separator_line)
        
        layout.addLayout(toolbar_layout)
        
        # 日志显示区域（占据整个剩余空间）
        self.log_display = LogDisplayWidget()
        layout.addWidget(self.log_display)
    
    def setup_connections(self):
        """设置连接"""
        # 连接实时日志信号
        if hasattr(log_signal_emitter, 'new_log') and log_signal_emitter.new_log:
            log_signal_emitter.new_log.connect(self.on_new_log)
        
        # 设置定时器，定期刷新日志（作为备用）
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_logs_if_needed)
        self.timer.start(5000)  # 每5秒检查一次
    
    def on_new_log(self, log_text, log_level):
        """处理新日志信号"""
        try:
            # 检查是否启用实时更新
            if not self.realtime_cb.isChecked():
                return
            
            # 检查日志级别是否在过滤范围内
            if not self.is_level_enabled(log_level):
                return
            
            # 添加到显示
            self.log_display.append_log(log_text, log_level)
            
        except Exception as e:
            print(f"处理新日志失败: {e}")
    
    def is_level_enabled(self, log_level):
        """检查日志级别是否启用"""
        if log_level == 'DEBUG' and self.debug_cb.isChecked():
            return True
        elif log_level == 'INFO' and self.info_cb.isChecked():
            return True
        elif log_level == 'WARNING' and self.warning_cb.isChecked():
            return True
        elif log_level == 'ERROR' and self.error_cb.isChecked():
            return True
        return False
    
    def on_autoscroll_changed(self, state):
        """自动滚动选项变化"""
        self.log_display.auto_scroll = (state == Qt.CheckState.Checked.value)
    
    def zoom_in(self):
        """放大字体"""
        self.log_display.zoom_in()
        self.font_size_label.setText(f"{self.log_display.current_font_size}px")
    
    def zoom_out(self):
        """缩小字体"""
        self.log_display.zoom_out()
        self.font_size_label.setText(f"{self.log_display.current_font_size}px")
    
    def reset_zoom(self):
        """重置字体大小"""
        self.log_display.reset_zoom()
        self.font_size_label.setText(f"{self.log_display.current_font_size}px")
    
    def refresh_logs_if_needed(self):
        """如果需要则刷新日志"""
        # 只有在非实时模式下才定期刷新
        if not self.realtime_cb.isChecked():
            self.refresh_logs()
    
    def refresh_logs(self):
        """刷新日志显示"""
        try:
            # 获取所有日志
            all_logs = log_memory_handler.get_logs()
            
            # 清空当前显示
            self.log_display.clear_logs()
            
            # 过滤并显示日志
            for log_line in all_logs:
                log_level = self.extract_log_level(log_line)
                if self.is_level_enabled(log_level):
                    self.log_display.append_log(log_line, log_level)
                    
        except Exception as e:
            print(f"刷新日志失败: {e}")
    
    def extract_log_level(self, log_line):
        """从日志行中提取日志级别"""
        # 匹配日志级别的正则表达式
        level_patterns = [
            r'\[DEBUG\]',
            r'\[INFO\]', 
            r'\[WARNING\]',
            r'\[ERROR\]',
            r'\[CRITICAL\]'
        ]
        
        for pattern in level_patterns:
            if re.search(pattern, log_line):
                return pattern.strip('[]')
        
        # 如果没有找到明确的级别标识，根据关键词判断
        if any(keyword in log_line.lower() for keyword in ['error', '错误', 'failed', '失败']):
            return 'ERROR'
        elif any(keyword in log_line.lower() for keyword in ['warning', '警告', 'warn']):
            return 'WARNING'
        elif any(keyword in log_line.lower() for keyword in ['debug', '调试']):
            return 'DEBUG'
        else:
            return 'INFO'
    
    def clear_logs(self):
        """清空日志"""
        try:
            # 清空内存中的日志
            log_memory_handler.clear()
            # 清空显示
            self.log_display.clear_logs()
            print("日志已清空")
        except Exception as e:
            print(f"清空日志失败: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止定时器
        if hasattr(self, 'timer'):
            self.timer.stop()
        
        event.accept()


def main():
    """测试函数"""
    app = QApplication(sys.argv)
    
    # 创建一些测试日志
    logger.info("这是一条INFO日志")
    logger.debug("这是一条DEBUG日志")
    logger.warning("这是一条WARNING日志")
    logger.error("这是一条ERROR日志")
    
    window = LogWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main()) 