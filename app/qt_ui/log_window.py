import sys
import logging
import re
import json
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QPushButton, QCheckBox, QLabel, QFrame, QSplitter,
                             QGroupBox, QScrollArea, QApplication, QLineEdit,
                             QComboBox, QFileDialog, QMessageBox, QProgressBar,
                             QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread, QMutex, QMutexLocker
from PyQt6.QtGui import QFont, QTextCursor, QColor, QPalette, QTextCharFormat

from app.logs import log_memory_handler, logger, log_signal_emitter


class EnhancedLogDisplayWidget(QTextEdit):
    """增强的日志显示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

        # 字体设置
        self.base_font_size = 11
        self.current_font_size = self.base_font_size
        self.font_family = "Consolas"
        self.update_font()

        # 设置样式
        self.update_style()

        # 自动滚动到底部
        self.auto_scroll = True
        self.user_scrolled_up = False  # 用户是否手动向上滚动
        self.last_scroll_position = 0  # 上次滚动位置

        # 记录当前显示的日志数量，用于性能优化
        self.displayed_log_count = 0
        # 搜索相关
        self.search_query = ""
        self.search_results = []
        self.current_search_index = -1
        # 性能优化
        self.max_display_lines = 5000
        # 线程安全
        self.mutex = QMutex()

        # 连接滚动条信号，检测用户滚动行为
        self.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)
        self.verticalScrollBar().sliderPressed.connect(self.on_scroll_pressed)
        self.verticalScrollBar().sliderReleased.connect(self.on_scroll_released)

    def on_scroll_changed(self, value):
        """滚动位置改变时调用"""
        scrollbar = self.verticalScrollBar()
        max_value = scrollbar.maximum()

        # 如果用户滚动到接近底部（允许一些误差），认为用户想要自动滚动
        if max_value > 0 and value >= max_value - 10:
            self.user_scrolled_up = False
        elif value < self.last_scroll_position:
            # 用户向上滚动
            self.user_scrolled_up = True

        self.last_scroll_position = value

    def on_scroll_pressed(self):
        """用户按下滚动条时"""
        # 用户主动操作滚动条，暂时禁用自动滚动
        pass

    def on_scroll_released(self):
        """用户释放滚动条时"""
        # 检查是否在底部，如果是则重新启用自动滚动
        scrollbar = self.verticalScrollBar()
        if scrollbar.value() >= scrollbar.maximum() - 10:
            self.user_scrolled_up = False

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
        
    def append_log(self, log_text, log_level, timestamp=None):
        """添加日志文本（线程安全）"""
        with QMutexLocker(self.mutex):
            try:
                # 根据日志级别设置颜色
                color = self.get_log_color(log_level)

                # 移动到文档末尾
                cursor = self.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)

                # 转义HTML特殊字符
                escaped_text = log_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                # 添加时间戳（如果提供）
                if timestamp:
                    time_color = "#888888"
                    cursor.insertHtml(f'<span style="color: {time_color};">[{timestamp}]</span> ')

                # 插入带颜色的文本
                cursor.insertHtml(f'<span style="color: {color};">{escaped_text}</span><br>')

                # 增加显示计数
                self.displayed_log_count += 1

                # 如果日志太多，清理旧的日志以保持性能
                if self.displayed_log_count > self.max_display_lines:
                    self.trim_logs()

                # 智能自动滚动到底部
                if self.auto_scroll and not self.user_scrolled_up:
                    self.scroll_to_bottom()

            except Exception as e:
                print(f"添加日志失败: {e}")

    def append_log_batch(self, log_entries):
        """批量添加日志（提高性能）"""
        with QMutexLocker(self.mutex):
            try:
                cursor = self.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)

                html_content = ""
                for entry in log_entries:
                    if isinstance(entry, dict):
                        log_text = entry.get('message', '')
                        log_level = entry.get('level', 'INFO')
                        timestamp = entry.get('timestamp', '')
                    else:
                        log_text = str(entry)
                        log_level = 'INFO'
                        timestamp = ''

                    color = self.get_log_color(log_level)
                    escaped_text = log_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                    if timestamp:
                        time_color = "#888888"
                        html_content += f'<span style="color: {time_color};">[{timestamp}]</span> '

                    html_content += f'<span style="color: {color};">{escaped_text}</span><br>'
                    self.displayed_log_count += 1

                cursor.insertHtml(html_content)

                # 如果日志太多，清理旧的日志
                if self.displayed_log_count > self.max_display_lines:
                    self.trim_logs()

                # 智能自动滚动到底部
                if self.auto_scroll and not self.user_scrolled_up:
                    self.scroll_to_bottom()

            except Exception as e:
                print(f"批量添加日志失败: {e}")

    def scroll_to_bottom(self):
        """强制滚动到底部"""
        try:
            # 移动光标到文档末尾
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)

            # 确保光标可见
            self.ensureCursorVisible()

            # 强制滚动条到底部
            scrollbar = self.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

            # 更新滚动状态
            self.user_scrolled_up = False
            self.last_scroll_position = scrollbar.maximum()

        except Exception as e:
            print(f"滚动到底部失败: {e}")

    def search_text(self, query, case_sensitive=False):
        """搜索文本"""
        if not query:
            self.clear_search_highlights()
            return 0

        self.search_query = query
        self.search_results = []

        # 清除之前的高亮
        self.clear_search_highlights()

        # 搜索文本
        flags = QTextCursor.FindFlag(0)
        if case_sensitive:
            flags |= QTextCursor.FindFlag.FindCaseSensitively

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        while True:
            cursor = self.document().find(query, cursor, flags)
            if cursor.isNull():
                break
            self.search_results.append(cursor.position())

        # 高亮搜索结果
        self.highlight_search_results()

        if self.search_results:
            self.current_search_index = 0
            self.goto_search_result(0)

        return len(self.search_results)

    def goto_next_search_result(self):
        """跳转到下一个搜索结果"""
        if not self.search_results:
            return

        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        self.goto_search_result(self.current_search_index)

    def goto_previous_search_result(self):
        """跳转到上一个搜索结果"""
        if not self.search_results:
            return

        self.current_search_index = (self.current_search_index - 1) % len(self.search_results)
        self.goto_search_result(self.current_search_index)

    def goto_search_result(self, index):
        """跳转到指定的搜索结果"""
        if 0 <= index < len(self.search_results):
            cursor = self.textCursor()
            cursor.setPosition(self.search_results[index])
            cursor.movePosition(QTextCursor.MoveOperation.Right,
                              QTextCursor.MoveMode.KeepAnchor,
                              len(self.search_query))
            self.setTextCursor(cursor)
            self.ensureCursorVisible()

    def highlight_search_results(self):
        """高亮搜索结果"""
        if not self.search_query:
            return

        # 创建高亮格式
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor(255, 255, 0, 100))  # 黄色背景

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        while True:
            cursor = self.document().find(self.search_query, cursor)
            if cursor.isNull():
                break
            cursor.mergeCharFormat(highlight_format)

    def clear_search_highlights(self):
        """清除搜索高亮"""
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)

        # 重置格式
        format = QTextCharFormat()
        cursor.mergeCharFormat(format)

        # 重新设置光标位置
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
    
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
    
    def export_logs(self, filename, level_filter=None):
        """导出日志到文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # 从内存处理器获取日志
                if hasattr(log_memory_handler, 'get_logs'):
                    logs = log_memory_handler.get_logs(level_filter)
                    for log_entry in logs:
                        if isinstance(log_entry, dict):
                            timestamp = log_entry.get('timestamp', '')
                            level = log_entry.get('level', '')
                            message = log_entry.get('message', '')
                            f.write(f"[{timestamp}] {level}: {message}\n")
                        else:
                            f.write(f"{log_entry}\n")
                else:
                    # 备用方案：导出当前显示的文本
                    f.write(self.toPlainText())
            return True
        except Exception as e:
            print(f"导出日志失败: {e}")
            return False

    def get_log_statistics(self):
        """获取日志统计信息"""
        if hasattr(log_memory_handler, 'get_stats'):
            return log_memory_handler.get_stats()
        return {
            'total_logs': self.displayed_log_count,
            'debug_logs': 0,
            'info_logs': 0,
            'warning_logs': 0,
            'error_logs': 0,
            'critical_logs': 0
        }

    def clear_logs(self):
        """清空日志"""
        with QMutexLocker(self.mutex):
            self.clear()
            self.displayed_log_count = 0
            self.search_results = []
            self.current_search_index = -1


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
        
        # 创建标签页容器
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3e3e3e;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #3e3e3e;
                border-bottom: 2px solid #0078d4;
            }
            QTabBar::tab:hover {
                background-color: #404040;
            }
        """)

        # 主日志显示区域
        main_log_widget = QWidget()
        main_log_layout = QVBoxLayout(main_log_widget)
        main_log_layout.setContentsMargins(0, 0, 0, 0)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        search_label = QLabel("搜索:")
        search_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #334155;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 6px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        search_layout.addWidget(self.search_input)

        self.search_prev_btn = QPushButton("↑")
        self.search_prev_btn.setFixedSize(30, 30)
        self.search_prev_btn.setToolTip("上一个")
        self.search_prev_btn.clicked.connect(self.search_previous)

        self.search_next_btn = QPushButton("↓")
        self.search_next_btn.setFixedSize(30, 30)
        self.search_next_btn.setToolTip("下一个")
        self.search_next_btn.clicked.connect(self.search_next)

        self.search_result_label = QLabel("")
        self.search_result_label.setStyleSheet("color: #888888; font-size: 11px;")

        for btn in [self.search_prev_btn, self.search_next_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                }
                QPushButton:pressed {
                    background-color: #545b62;
                }
            """)

        search_layout.addWidget(self.search_prev_btn)
        search_layout.addWidget(self.search_next_btn)
        search_layout.addWidget(self.search_result_label)

        # 导出按钮
        export_btn = QPushButton("导出日志")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:pressed {
                background-color: #117a8b;
            }
        """)
        export_btn.clicked.connect(self.export_logs_dialog)
        search_layout.addWidget(export_btn)

        search_layout.addStretch()
        main_log_layout.addLayout(search_layout)

        # 日志显示区域
        self.log_display = EnhancedLogDisplayWidget()
        main_log_layout.addWidget(self.log_display)

        # 统计信息标签
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 10px;
                padding: 4px;
                background-color: #2d2d2d;
                border-top: 1px solid #3e3e3e;
            }
        """)
        main_log_layout.addWidget(self.stats_label)

        tab_widget.addTab(main_log_widget, "实时日志")

        # 统计信息标签页
        stats_widget = self.create_stats_widget()
        tab_widget.addTab(stats_widget, "统计信息")

        layout.addWidget(tab_widget)

    def create_stats_widget(self):
        """创建统计信息组件"""
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        stats_layout.setContentsMargins(15, 15, 15, 15)
        stats_layout.setSpacing(15)

        # 标题
        title_label = QLabel("日志统计信息")
        title_label.setStyleSheet("""
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
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_layout.addWidget(title_label)

        # 统计表格
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["项目", "数量"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                gridline-color: #3e3e3e;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3e3e3e;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px;
                border: 1px solid #3e3e3e;
                font-weight: bold;
            }
        """)
        stats_layout.addWidget(self.stats_table)

        # 刷新按钮
        refresh_stats_btn = QPushButton("刷新统计")
        refresh_stats_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        refresh_stats_btn.clicked.connect(self.update_statistics)
        stats_layout.addWidget(refresh_stats_btn)

        stats_layout.addStretch()
        return stats_widget

    def update_statistics(self):
        """更新统计信息"""
        try:
            stats = self.log_display.get_log_statistics()

            # 更新表格
            self.stats_table.setRowCount(len(stats))

            stat_items = [
                ("总日志数", stats.get('total_logs', 0)),
                ("DEBUG日志", stats.get('debug_logs', 0)),
                ("INFO日志", stats.get('info_logs', 0)),
                ("WARNING日志", stats.get('warning_logs', 0)),
                ("ERROR日志", stats.get('error_logs', 0)),
                ("CRITICAL日志", stats.get('critical_logs', 0)),
            ]

            for row, (name, value) in enumerate(stat_items):
                name_item = QTableWidgetItem(name)
                value_item = QTableWidgetItem(str(value))

                # 设置颜色
                if "ERROR" in name or "CRITICAL" in name:
                    value_item.setForeground(QColor(244, 71, 71))  # 红色
                elif "WARNING" in name:
                    value_item.setForeground(QColor(245, 158, 11))  # 黄色
                elif "INFO" in name:
                    value_item.setForeground(QColor(34, 197, 94))  # 绿色
                elif "DEBUG" in name:
                    value_item.setForeground(QColor(156, 163, 175))  # 灰色

                self.stats_table.setItem(row, 0, name_item)
                self.stats_table.setItem(row, 1, value_item)

            # 更新底部统计标签
            total = stats.get('total_logs', 0)
            errors = stats.get('error_logs', 0) + stats.get('critical_logs', 0)
            warnings = stats.get('warning_logs', 0)

            self.stats_label.setText(
                f"总计: {total} | 错误: {errors} | 警告: {warnings} | "
                f"显示: {self.log_display.displayed_log_count}"
            )

        except Exception as e:
            print(f"更新统计信息失败: {e}")

    def on_search_text_changed(self, text):
        """搜索文本变化"""
        if text:
            count = self.log_display.search_text(text, case_sensitive=False)
            if count > 0:
                self.search_result_label.setText(f"找到 {count} 个结果")
            else:
                self.search_result_label.setText("未找到结果")
        else:
            self.log_display.clear_search_highlights()
            self.search_result_label.setText("")

    def search_next(self):
        """搜索下一个"""
        self.log_display.goto_next_search_result()
        self.update_search_position()

    def search_previous(self):
        """搜索上一个"""
        self.log_display.goto_previous_search_result()
        self.update_search_position()

    def update_search_position(self):
        """更新搜索位置显示"""
        if self.log_display.search_results:
            current = self.log_display.current_search_index + 1
            total = len(self.log_display.search_results)
            self.search_result_label.setText(f"{current}/{total}")

    def export_logs_dialog(self):
        """显示导出日志对话框"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "导出日志",
                f"wxauto_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "文本文件 (*.txt);;所有文件 (*)"
            )

            if filename:
                # 获取当前选中的日志级别
                level_filter = []
                if self.debug_cb.isChecked():
                    level_filter.append('DEBUG')
                if self.info_cb.isChecked():
                    level_filter.append('INFO')
                if self.warning_cb.isChecked():
                    level_filter.append('WARNING')
                if self.error_cb.isChecked():
                    level_filter.append('ERROR')

                if self.log_display.export_logs(filename, level_filter):
                    QMessageBox.information(self, "成功", f"日志已导出到: {filename}")
                else:
                    QMessageBox.warning(self, "失败", "导出日志失败")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出日志时发生错误: {str(e)}")

    def setup_connections(self):
        """设置连接"""
        try:
            # 连接实时日志信号
            if hasattr(log_signal_emitter, 'new_log') and log_signal_emitter.new_log:
                log_signal_emitter.new_log.connect(self.on_new_log)
                print("✓ 日志信号连接成功")
            else:
                print("✗ 日志信号连接失败")

            # 设置定时器，定期刷新日志和统计信息
            self.timer = QTimer()
            self.timer.timeout.connect(self.refresh_logs_if_needed)
            self.timer.start(3000)  # 每3秒检查一次

            # 统计信息更新定时器
            self.stats_timer = QTimer()
            self.stats_timer.timeout.connect(self.update_statistics)
            self.stats_timer.start(10000)  # 每10秒更新统计信息

        except Exception as e:
            print(f"设置连接失败: {e}")
    
    def on_new_log(self, log_text, log_level):
        """处理新日志信号"""
        try:
            # 检查是否启用实时更新
            if not self.realtime_cb.isChecked():
                return

            # 检查日志级别是否在过滤范围内
            if not self.is_level_enabled(log_level):
                return

            # 获取时间戳
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

            # 添加到显示
            self.log_display.append_log(log_text, log_level, timestamp)

            # 定期更新统计信息（避免频繁更新）
            if self.log_display.displayed_log_count % 50 == 0:
                self.update_statistics()

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
        is_enabled = (state == Qt.CheckState.Checked.value)
        self.log_display.auto_scroll = is_enabled

        # 如果启用自动滚动，立即滚动到底部
        if is_enabled:
            self.log_display.user_scrolled_up = False
            self.log_display.scroll_to_bottom()
    
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
            # 获取启用的日志级别
            enabled_levels = []
            if self.debug_cb.isChecked():
                enabled_levels.append('DEBUG')
            if self.info_cb.isChecked():
                enabled_levels.append('INFO')
            if self.warning_cb.isChecked():
                enabled_levels.append('WARNING')
            if self.error_cb.isChecked():
                enabled_levels.append('ERROR')

            # 从增强的内存处理器获取日志
            if hasattr(log_memory_handler, 'get_logs'):
                all_logs = log_memory_handler.get_logs(enabled_levels)

                # 清空当前显示
                self.log_display.clear_logs()

                # 批量添加日志（提高性能）
                if all_logs:
                    self.log_display.append_log_batch(all_logs)
            else:
                # 备用方案：使用旧的方法
                all_logs = log_memory_handler.get_formatted_logs() if hasattr(log_memory_handler, 'get_formatted_logs') else []

                # 清空当前显示
                self.log_display.clear_logs()

                # 过滤并显示日志
                for log_line in all_logs:
                    log_level = self.extract_log_level(log_line)
                    if self.is_level_enabled(log_level):
                        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        self.log_display.append_log(log_line, log_level, timestamp)

            # 更新统计信息
            self.update_statistics()

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
            if hasattr(log_memory_handler, 'clear'):
                log_memory_handler.clear()

            # 清空显示
            self.log_display.clear_logs()

            # 更新统计信息
            self.update_statistics()

            print("日志已清空")
            logger.info("用户清空了日志显示")

        except Exception as e:
            print(f"清空日志失败: {e}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止定时器
            if hasattr(self, 'timer'):
                self.timer.stop()

            if hasattr(self, 'stats_timer'):
                self.stats_timer.stop()

            print("日志窗口已关闭")

        except Exception as e:
            print(f"关闭日志窗口时发生错误: {e}")

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