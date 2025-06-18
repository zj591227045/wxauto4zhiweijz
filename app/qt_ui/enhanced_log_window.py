#!/usr/bin/env python3
"""
增强版日志窗口
修复信号连接和显示问题，确保日志系统正常工作
"""

import logging
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                             QPushButton, QCheckBox, QLabel, QFrame, QSplitter,
                             QGroupBox, QLineEdit, QComboBox, QFileDialog, 
                             QMessageBox, QProgressBar, QTabWidget)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread, QMutex, QMutexLocker
from PyQt6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

# 导入日志系统
try:
    from app.modules.log_manager import LogManager
    logger = logging.getLogger(__name__)

    # 全局日志管理器实例
    _log_manager_instance = None

    def get_log_manager():
        global _log_manager_instance
        if _log_manager_instance is None:
            _log_manager_instance = LogManager()
            _log_manager_instance.start()
        return _log_manager_instance

except ImportError:
    logger = logging.getLogger(__name__)

    def get_log_manager():
        return None

class RobustLogDisplayWidget(QTextEdit):
    """健壮的日志显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        
        # 基本设置
        self.max_lines = 5000
        self.current_lines = 0
        self.auto_scroll = True
        self.user_scrolled_up = False
        
        # 线程安全
        self.mutex = QMutex()
        
        # 设置字体和样式
        self._setup_appearance()
        
        # 连接滚动事件
        self._setup_scroll_detection()
        
        # 日志缓冲区（用于批量更新）
        self.log_buffer = []
        self.buffer_timer = QTimer()
        self.buffer_timer.timeout.connect(self._flush_log_buffer)
        self.buffer_timer.setSingleShot(True)
        
        # 连接日志信号
        self._connect_log_signals()
        
        # 初始化时加载现有日志
        self._load_existing_logs()
    
    def _setup_appearance(self):
        """设置外观"""
        # 设置字体
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        
        # 设置样式
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                padding: 8px;
                selection-background-color: #264f78;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666666;
            }
        """)
    
    def _setup_scroll_detection(self):
        """设置滚动检测"""
        scrollbar = self.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll_changed)
        scrollbar.sliderPressed.connect(self._on_scroll_pressed)
        scrollbar.sliderReleased.connect(self._on_scroll_released)
    
    def _on_scroll_changed(self, value):
        """滚动位置改变"""
        scrollbar = self.verticalScrollBar()
        max_value = scrollbar.maximum()
        
        # 如果滚动到底部附近，启用自动滚动
        if max_value > 0 and value >= max_value - 10:
            self.user_scrolled_up = False
        elif value < max_value - 50:  # 向上滚动超过50像素
            self.user_scrolled_up = True
    
    def _on_scroll_pressed(self):
        """用户按下滚动条"""
        # 用户主动操作滚动条时，暂时禁用自动滚动
        pass
    
    def _on_scroll_released(self):
        """用户释放滚动条"""
        # 检查是否在底部
        scrollbar = self.verticalScrollBar()
        if scrollbar.value() >= scrollbar.maximum() - 10:
            self.user_scrolled_up = False
    
    def _connect_log_signals(self):
        """连接日志信号"""
        try:
            log_manager = get_log_manager()
            if log_manager and hasattr(log_manager, 'new_log'):
                # 使用队列连接确保线程安全
                log_manager.new_log.connect(
                    self._on_new_log,
                    Qt.ConnectionType.QueuedConnection
                )
                logger.info("日志信号连接成功")
            else:
                logger.warning("日志管理器不可用")

                # 使用定时器定期检查日志
                self.log_check_timer = QTimer()
                self.log_check_timer.timeout.connect(self._check_logs_periodically)
                self.log_check_timer.start(1000)  # 每秒检查一次

        except Exception as e:
            logger.error(f"连接日志信号失败: {e}")

            # 备用方案：使用定时器
            self.log_check_timer = QTimer()
            self.log_check_timer.timeout.connect(self._check_logs_periodically)
            self.log_check_timer.start(1000)
    
    def _on_new_log(self, log_text, log_level):
        """处理新日志信号"""
        try:
            # 添加到缓冲区
            self.log_buffer.append((log_text, log_level))
            
            # 启动缓冲区刷新定时器（延迟50ms批量处理）
            if not self.buffer_timer.isActive():
                self.buffer_timer.start(50)
                
        except Exception as e:
            print(f"处理新日志信号失败: {e}")
    
    def _flush_log_buffer(self):
        """刷新日志缓冲区"""
        try:
            if not self.log_buffer:
                return
            
            with QMutexLocker(self.mutex):
                # 批量处理日志
                for log_text, log_level in self.log_buffer:
                    self._append_log_internal(log_text, log_level)
                
                # 清空缓冲区
                self.log_buffer.clear()
                
                # 自动滚动
                if self.auto_scroll and not self.user_scrolled_up:
                    self._scroll_to_bottom()
                
        except Exception as e:
            print(f"刷新日志缓冲区失败: {e}")
    
    def _append_log_internal(self, log_text, log_level):
        """内部日志添加方法"""
        try:
            # 获取颜色
            color = self._get_log_color(log_level)
            
            # 移动到文档末尾
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            
            # 转义HTML
            escaped_text = (log_text.replace('&', '&amp;')
                                   .replace('<', '&lt;')
                                   .replace('>', '&gt;'))
            
            # 插入带颜色的文本
            cursor.insertHtml(f'<span style="color: {color};">{escaped_text}</span><br>')
            
            # 更新行数
            self.current_lines += 1
            
            # 如果行数过多，清理旧日志
            if self.current_lines > self.max_lines:
                self._trim_logs()
                
        except Exception as e:
            print(f"添加日志失败: {e}")
    
    def _get_log_color(self, log_level):
        """获取日志级别对应的颜色"""
        colors = {
            'DEBUG': '#9cdcfe',    # 浅蓝色
            'INFO': '#d4d4d4',     # 白色
            'WARNING': '#dcdcaa',  # 黄色
            'ERROR': '#f44747',    # 红色
            'CRITICAL': '#ff6b6b'  # 亮红色
        }
        return colors.get(log_level, '#d4d4d4')
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        try:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            
            # 强制滚动条到底部
            scrollbar = self.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
        except Exception as e:
            print(f"滚动到底部失败: {e}")
    
    def _trim_logs(self):
        """清理旧日志"""
        try:
            # 删除前面的1/3日志
            lines_to_delete = self.max_lines // 3
            
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            
            for _ in range(lines_to_delete):
                cursor.select(QTextCursor.SelectionType.LineUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # 删除换行符
            
            self.current_lines -= lines_to_delete
            
        except Exception as e:
            print(f"清理日志失败: {e}")
    
    def _load_existing_logs(self):
        """加载现有日志"""
        try:
            log_manager = get_log_manager()
            if not log_manager:
                return

            # 获取最近的日志
            logs = log_manager.get_logs(limit=1000)

            if logs:
                with QMutexLocker(self.mutex):
                    for log_entry in logs:
                        if isinstance(log_entry, dict):
                            message = log_entry.get('message', '')
                            level = log_entry.get('level', 'INFO')
                            timestamp = log_entry.get('timestamp', '')

                            # 格式化消息
                            if timestamp:
                                formatted_message = f"[{timestamp}] {message}"
                            else:
                                formatted_message = message

                            self._append_log_internal(formatted_message, level)

                # 滚动到底部
                self._scroll_to_bottom()

                logger.info(f"加载了 {len(logs)} 条历史日志")

        except Exception as e:
            logger.error(f"加载现有日志失败: {e}")
    
    def _check_logs_periodically(self):
        """定期检查日志（备用方案）"""
        try:
            log_manager = get_log_manager()
            if not log_manager:
                return

            # 获取最新的日志
            logs = log_manager.get_logs(limit=10)

            if logs:
                # 检查是否有新日志
                for log_entry in logs[-5:]:  # 只检查最后5条
                    if isinstance(log_entry, dict):
                        message = log_entry.get('message', '')
                        level = log_entry.get('level', 'INFO')
                        timestamp = log_entry.get('timestamp', '')

                        # 简单的去重检查（基于消息内容）
                        if message and not self._is_duplicate_log(message):
                            formatted_message = f"[{timestamp}] {message}" if timestamp else message
                            self._on_new_log(formatted_message, level)

        except Exception as e:
            print(f"定期检查日志失败: {e}")
    
    def _is_duplicate_log(self, message):
        """简单的重复日志检查"""
        try:
            # 获取最后几行文本
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.movePosition(QTextCursor.MoveOperation.Up, 
                              QTextCursor.MoveMode.KeepAnchor, 3)
            recent_text = cursor.selectedText()
            
            # 检查消息是否已存在
            return message[:50] in recent_text
            
        except Exception:
            return False
    
    def clear_logs(self):
        """清空日志"""
        with QMutexLocker(self.mutex):
            self.clear()
            self.current_lines = 0
            self.log_buffer.clear()
    
    def export_logs(self, filename):
        """导出日志"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                log_manager = get_log_manager()
                if log_manager:
                    logs = log_manager.get_logs()
                    for log_entry in logs:
                        if isinstance(log_entry, dict):
                            timestamp = log_entry.get('timestamp', '')
                            level = log_entry.get('level', '')
                            message = log_entry.get('message', '')
                            f.write(f"[{timestamp}] {level}: {message}\n")
                else:
                    f.write(self.toPlainText())
            return True
        except Exception as e:
            logger.error(f"导出日志失败: {e}")
            return False

class EnhancedLogWindow(QWidget):
    """增强版日志窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("只为记账-微信助手 - 系统日志")

        # 设置窗口属性，确保独立显示
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinMaxButtonsHint
        )

        # 设置窗口大小和位置
        self.setGeometry(150, 150, 1000, 600)
        self.setMinimumSize(800, 400)

        # 初始化属性
        self.log_display = None

        self.setup_ui()

        # 测试日志系统
        self._test_logging()

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止定时器
            if hasattr(self, 'stats_timer') and self.stats_timer:
                self.stats_timer.stop()

            # 清理日志显示组件
            if self.log_display:
                if hasattr(self.log_display, 'log_check_timer'):
                    self.log_display.log_check_timer.stop()
                if hasattr(self.log_display, 'buffer_timer'):
                    self.log_display.buffer_timer.stop()

            logger.info("日志窗口已关闭")

        except Exception as e:
            print(f"关闭日志窗口时出错: {e}")

        # 接受关闭事件
        event.accept()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 日志显示区域
        self.log_display = RobustLogDisplayWidget()
        layout.addWidget(self.log_display)
        
        # 状态栏
        status_bar = self._create_status_bar()
        layout.addWidget(status_bar)
    
    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.Shape.StyledPanel)
        toolbar.setMaximumHeight(50)
        
        layout = QHBoxLayout(toolbar)
        
        # 清空按钮
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self._clear_logs)
        layout.addWidget(clear_btn)
        
        # 导出按钮
        export_btn = QPushButton("导出日志")
        export_btn.clicked.connect(self._export_logs)
        layout.addWidget(export_btn)
        
        # 自动滚动复选框
        auto_scroll_cb = QCheckBox("自动滚动")
        auto_scroll_cb.setChecked(True)
        auto_scroll_cb.toggled.connect(self._toggle_auto_scroll)
        layout.addWidget(auto_scroll_cb)
        
        # 测试按钮
        test_btn = QPushButton("测试日志")
        test_btn.clicked.connect(self._test_logging)
        layout.addWidget(test_btn)
        
        layout.addStretch()
        
        return toolbar
    
    def _create_status_bar(self):
        """创建状态栏"""
        status_bar = QFrame()
        status_bar.setFrameStyle(QFrame.Shape.StyledPanel)
        status_bar.setMaximumHeight(30)
        
        layout = QHBoxLayout(status_bar)
        
        self.status_label = QLabel("日志系统已就绪")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # 日志统计
        self.stats_label = QLabel("统计: 0 条日志")
        layout.addWidget(self.stats_label)
        
        # 更新统计的定时器
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(5000)  # 每5秒更新一次
        
        return status_bar
    
    def _toggle_auto_scroll(self, enabled):
        """切换自动滚动"""
        self.log_display.auto_scroll = enabled
        if enabled:
            self.log_display.user_scrolled_up = False
            self.log_display._scroll_to_bottom()
    
    def _export_logs(self):
        """导出日志"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "导出日志", 
                f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "文本文件 (*.txt);;所有文件 (*)"
            )
            
            if filename:
                if self.log_display.export_logs(filename):
                    QMessageBox.information(self, "成功", f"日志已导出到: {filename}")
                else:
                    QMessageBox.warning(self, "失败", "导出日志失败")
                    
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出日志异常: {e}")
    
    def _test_logging(self):
        """初始化日志系统状态"""
        try:
            # 不再产生测试日志，只设置状态
            self.status_label.setText("日志系统已就绪")

        except Exception as e:
            self.status_label.setText(f"日志系统初始化失败: {e}")
    
    def _clear_logs(self):
        """清空日志"""
        try:
            if self.log_display:
                self.log_display.clear_logs()
        except Exception as e:
            logger.error(f"清空日志失败: {e}")

    def _update_stats(self):
        """更新统计信息"""
        try:
            log_manager = get_log_manager()
            if log_manager:
                stats = log_manager.get_stats()
                memory_stats = stats.get('memory_stats', {})
                total = memory_stats.get('total_logs', 0)
                errors = memory_stats.get('error_logs', 0)
                self.stats_label.setText(f"统计: {total} 条日志, {errors} 条错误")
            else:
                self.stats_label.setText("统计: 日志管理器不可用")

        except Exception as e:
            self.stats_label.setText(f"统计: 获取失败 - {e}")
