#!/usr/bin/env python3
"""
增强版主界面
集成服务健康检查和自动恢复机制
"""

import sys
import os
import time
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QLabel, QPushButton, 
                             QFrame, QDialog, QMessageBox, QTabWidget,
                             QGroupBox, QProgressBar, QTextEdit, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 导入健康监控系统
from app.utils.service_health_monitor import health_monitor, ServiceStatus
from app.utils.service_health_checkers import create_health_checkers
from app.utils.service_recovery_handlers import create_recovery_handlers

# 导入状态管理器
from app.utils.state_manager import state_manager

# 导入增强版组件
from app.services.enhanced_zero_history_monitor import EnhancedZeroHistoryMonitor
from app.services.robust_message_processor import RobustMessageProcessor
from app.services.robust_message_delivery import RobustMessageDelivery
from app.utils.enhanced_async_wechat import async_wechat_manager
from app.qt_ui.enhanced_log_window import EnhancedLogWindow

# 导入日志系统
try:
    from app.logs import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class ServiceStatusWidget(QWidget):
    """服务状态显示组件"""
    
    def __init__(self, service_name: str, display_name: str, parent=None):
        super().__init__(parent)
        self.service_name = service_name
        self.display_name = display_name
        self.status = ServiceStatus.UNKNOWN
        self.last_check_time = None
        self.error_message = ""
        
        self.setFixedSize(280, 100)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        
        # 服务名称和状态
        header_layout = QHBoxLayout()
        
        self.name_label = QLabel(self.display_name)
        self.name_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.name_label.setStyleSheet("color: white;")
        header_layout.addWidget(self.name_label)
        
        header_layout.addStretch()
        
        self.status_indicator = QLabel("●")
        self.status_indicator.setFont(QFont("Arial", 12))
        self.status_indicator.setStyleSheet("color: #6b7280;")  # 默认灰色
        header_layout.addWidget(self.status_indicator)
        
        self.status_label = QLabel("未知")
        self.status_label.setFont(QFont("Microsoft YaHei", 9))
        self.status_label.setStyleSheet("color: #9ca3af;")
        header_layout.addWidget(self.status_label)
        
        layout.addLayout(header_layout)
        
        # 详细信息
        self.details_label = QLabel("等待检查...")
        self.details_label.setFont(QFont("Microsoft YaHei", 8))
        self.details_label.setStyleSheet("color: #6b7280;")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)
        
        # 最后检查时间
        self.time_label = QLabel("")
        self.time_label.setFont(QFont("Microsoft YaHei", 7))
        self.time_label.setStyleSheet("color: #4b5563;")
        layout.addWidget(self.time_label)
    
    def update_status(self, status: ServiceStatus, message: str = "", details: dict = None):
        """更新服务状态"""
        self.status = status
        self.error_message = message
        self.last_check_time = datetime.now()
        
        # 更新状态指示器和文本
        if status == ServiceStatus.HEALTHY:
            self.status_indicator.setStyleSheet("color: #10b981;")  # 绿色
            self.status_label.setText("正常")
            self.status_label.setStyleSheet("color: #10b981;")
        elif status == ServiceStatus.DEGRADED:
            self.status_indicator.setStyleSheet("color: #f59e0b;")  # 黄色
            self.status_label.setText("降级")
            self.status_label.setStyleSheet("color: #f59e0b;")
        elif status == ServiceStatus.UNHEALTHY:
            self.status_indicator.setStyleSheet("color: #ef4444;")  # 红色
            self.status_label.setText("异常")
            self.status_label.setStyleSheet("color: #ef4444;")
        elif status == ServiceStatus.RECOVERING:
            self.status_indicator.setStyleSheet("color: #8b5cf6;")  # 紫色
            self.status_label.setText("恢复中")
            self.status_label.setStyleSheet("color: #8b5cf6;")
        else:
            self.status_indicator.setStyleSheet("color: #6b7280;")  # 灰色
            self.status_label.setText("未知")
            self.status_label.setStyleSheet("color: #6b7280;")
        
        # 更新详细信息
        if message:
            self.details_label.setText(message)
        elif details:
            # 从详细信息中提取关键信息
            detail_parts = []
            if 'response_time' in details:
                detail_parts.append(f"响应时间: {details['response_time']:.2f}s")
            if 'failure_count' in details:
                detail_parts.append(f"失败次数: {details['failure_count']}")
            
            if detail_parts:
                self.details_label.setText(" | ".join(detail_parts))
            else:
                self.details_label.setText("运行正常")
        
        # 更新检查时间
        self.time_label.setText(f"最后检查: {self.last_check_time.strftime('%H:%M:%S')}")
    
    def paintEvent(self, event):
        """绘制背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制卡片背景
        rect = self.rect()
        painter.setBrush(QBrush(QColor(45, 55, 72)))
        painter.setPen(QPen(QColor(74, 85, 104), 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)

class ServiceControlPanel(QWidget):
    """服务控制面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("服务健康监控")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: white; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # 服务状态网格
        self.services_layout = QGridLayout()
        self.services_layout.setSpacing(10)
        
        # 创建服务状态组件
        self.service_widgets = {}
        services = [
            ("accounting_service", "记账服务"),
            ("wechat_service", "微信服务"),
            ("message_processing", "消息处理"),
            ("log_system", "日志系统")
        ]
        
        for i, (service_name, display_name) in enumerate(services):
            widget = ServiceStatusWidget(service_name, display_name)
            self.service_widgets[service_name] = widget
            row = i // 2
            col = i % 2
            self.services_layout.addWidget(widget, row, col)
        
        layout.addLayout(self.services_layout)
        
        # 控制按钮
        controls_layout = QHBoxLayout()
        
        self.start_monitoring_btn = QPushButton("启动监控")
        self.start_monitoring_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:disabled {
                background-color: #6b7280;
            }
        """)
        controls_layout.addWidget(self.start_monitoring_btn)
        
        self.stop_monitoring_btn = QPushButton("停止监控")
        self.stop_monitoring_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
            QPushButton:disabled {
                background-color: #6b7280;
            }
        """)
        self.stop_monitoring_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_monitoring_btn)
        
        self.force_check_btn = QPushButton("立即检查")
        self.force_check_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        controls_layout.addWidget(self.force_check_btn)
        
        controls_layout.addStretch()
        
        self.auto_recovery_checkbox = QPushButton("自动恢复: 开启")
        self.auto_recovery_checkbox.setCheckable(True)
        self.auto_recovery_checkbox.setChecked(True)
        self.auto_recovery_checkbox.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                color: white;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
            QPushButton:checked {
                background-color: #10b981;
            }
        """)
        controls_layout.addWidget(self.auto_recovery_checkbox)
        
        layout.addLayout(controls_layout)
        
        # 统计信息
        stats_group = QGroupBox("监控统计")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #374151;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background-color: #1e293b;
            }
        """)
        
        stats_layout = QGridLayout(stats_group)
        
        self.stats_labels = {}
        stats_items = [
            ("total_checks", "总检查次数"),
            ("failed_checks", "失败次数"),
            ("recoveries", "恢复次数"),
            ("uptime", "运行时间")
        ]
        
        for i, (key, label) in enumerate(stats_items):
            label_widget = QLabel(f"{label}:")
            label_widget.setStyleSheet("color: #9ca3af; font-size: 11px;")
            value_widget = QLabel("0")
            value_widget.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
            
            row = i // 2
            col = (i % 2) * 2
            stats_layout.addWidget(label_widget, row, col)
            stats_layout.addWidget(value_widget, row, col + 1)
            
            self.stats_labels[key] = value_widget
        
        layout.addWidget(stats_group)
    
    def setup_connections(self):
        """设置信号连接"""
        self.start_monitoring_btn.clicked.connect(self.start_monitoring)
        self.stop_monitoring_btn.clicked.connect(self.stop_monitoring)
        self.force_check_btn.clicked.connect(self.force_check)
        self.auto_recovery_checkbox.toggled.connect(self.toggle_auto_recovery)
    
    def start_monitoring(self):
        """启动监控"""
        try:
            # 注册健康检查器和恢复处理器
            health_checkers = create_health_checkers(state_manager)
            recovery_handlers = create_recovery_handlers(state_manager, async_wechat_manager)
            
            # 注册服务
            for service_name, checker in health_checkers.items():
                recovery_handler = recovery_handlers.get(service_name)
                health_monitor.register_service(
                    service_name,
                    checker.check_health,
                    recovery_handler
                )
            
            # 启动监控
            if health_monitor.start_monitoring():
                self.start_monitoring_btn.setEnabled(False)
                self.stop_monitoring_btn.setEnabled(True)
                logger.info("服务健康监控已启动")
            else:
                QMessageBox.warning(self, "错误", "启动监控失败")
                
        except Exception as e:
            logger.error(f"启动监控异常: {e}")
            QMessageBox.critical(self, "错误", f"启动监控异常: {e}")
    
    def stop_monitoring(self):
        """停止监控"""
        try:
            if health_monitor.stop_monitoring():
                self.start_monitoring_btn.setEnabled(True)
                self.stop_monitoring_btn.setEnabled(False)
                logger.info("服务健康监控已停止")
            else:
                QMessageBox.warning(self, "错误", "停止监控失败")
                
        except Exception as e:
            logger.error(f"停止监控异常: {e}")
            QMessageBox.critical(self, "错误", f"停止监控异常: {e}")
    
    def force_check(self):
        """强制检查所有服务"""
        try:
            health_monitor.force_check()
            logger.info("已触发强制健康检查")
        except Exception as e:
            logger.error(f"强制检查异常: {e}")
            QMessageBox.warning(self, "错误", f"强制检查失败: {e}")
    
    def toggle_auto_recovery(self, enabled):
        """切换自动恢复"""
        text = "自动恢复: 开启" if enabled else "自动恢复: 关闭"
        self.auto_recovery_checkbox.setText(text)
        logger.info(f"自动恢复已{'开启' if enabled else '关闭'}")
    
    def update_service_status(self, service_name: str, status: ServiceStatus, message: str = "", details: dict = None):
        """更新服务状态"""
        if service_name in self.service_widgets:
            self.service_widgets[service_name].update_status(status, message, details)
    
    def update_stats(self, stats: dict):
        """更新统计信息"""
        for key, value in stats.items():
            if key in self.stats_labels:
                if key == "uptime" and isinstance(value, (int, float)):
                    # 格式化运行时间
                    hours = int(value // 3600)
                    minutes = int((value % 3600) // 60)
                    self.stats_labels[key].setText(f"{hours:02d}:{minutes:02d}")
                else:
                    self.stats_labels[key].setText(str(value))

class EnhancedMainWindow(QMainWindow):
    """增强版主界面"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("微信自动记账助手 - 增强版")
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e293b;
            }
        """)
        
        self.setup_ui()
        self.setup_health_monitoring()
        self.setup_timers()

        # 初始化系统信息
        self.update_system_info()

        logger.info("增强版主界面初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：服务控制面板
        self.control_panel = ServiceControlPanel()
        splitter.addWidget(self.control_panel)
        
        # 右侧：标签页
        right_widget = QTabWidget()
        right_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #374151;
                background-color: #1e293b;
            }
            QTabBar::tab {
                background-color: #374151;
                color: white;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #1e293b;
                border-bottom: 2px solid #3b82f6;
            }
            QTabBar::tab:hover {
                background-color: #4b5563;
            }
        """)

        # 日志标签页
        self.log_window = EnhancedLogWindow()
        right_widget.addTab(self.log_window, "系统日志")

        # 消息监控标签页
        self.message_monitor_widget = self.create_message_monitor_widget()
        right_widget.addTab(self.message_monitor_widget, "消息监控")

        # 系统状态标签页
        self.system_status_widget = self.create_system_status_widget()
        right_widget.addTab(self.system_status_widget, "系统状态")

        splitter.addWidget(right_widget)

        # 设置分割比例
        splitter.setSizes([400, 800])

        main_layout.addWidget(splitter)

    def create_message_monitor_widget(self):
        """创建消息监控组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 标题
        title = QLabel("消息监控状态")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: white; margin-bottom: 10px;")
        layout.addWidget(title)

        # 监控控制
        control_layout = QHBoxLayout()

        self.start_monitor_btn = QPushButton("启动监控")
        self.start_monitor_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #6b7280; }
        """)
        control_layout.addWidget(self.start_monitor_btn)

        self.stop_monitor_btn = QPushButton("停止监控")
        self.stop_monitor_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #dc2626; }
            QPushButton:disabled { background-color: #6b7280; }
        """)
        self.stop_monitor_btn.setEnabled(False)
        control_layout.addWidget(self.stop_monitor_btn)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        # 监控状态显示
        self.monitor_status_text = QTextEdit()
        self.monitor_status_text.setReadOnly(True)
        self.monitor_status_text.setMaximumHeight(200)
        self.monitor_status_text.setStyleSheet("""
            QTextEdit {
                background-color: #374151;
                border: 1px solid #4b5563;
                border-radius: 4px;
                color: white;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.monitor_status_text)

        # 消息统计
        stats_group = QGroupBox("消息统计")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #374151;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background-color: #1e293b;
            }
        """)

        stats_layout = QGridLayout(stats_group)

        self.message_stats_labels = {}
        message_stats = [
            ("total_messages", "总消息数"),
            ("processed_messages", "已处理"),
            ("successful_records", "成功记账"),
            ("failed_records", "失败记录")
        ]

        for i, (key, label) in enumerate(message_stats):
            label_widget = QLabel(f"{label}:")
            label_widget.setStyleSheet("color: #9ca3af; font-size: 11px;")
            value_widget = QLabel("0")
            value_widget.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")

            row = i // 2
            col = (i % 2) * 2
            stats_layout.addWidget(label_widget, row, col)
            stats_layout.addWidget(value_widget, row, col + 1)

            self.message_stats_labels[key] = value_widget

        layout.addWidget(stats_group)
        layout.addStretch()

        return widget

    def create_system_status_widget(self):
        """创建系统状态组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 标题
        title = QLabel("系统状态概览")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: white; margin-bottom: 10px;")
        layout.addWidget(title)

        # 系统信息
        info_group = QGroupBox("系统信息")
        info_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #374151;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background-color: #1e293b;
            }
        """)

        info_layout = QVBoxLayout(info_group)

        self.system_info_labels = {}
        system_info = [
            ("python_version", "Python版本"),
            ("qt_version", "Qt版本"),
            ("memory_usage", "内存使用"),
            ("uptime", "运行时间")
        ]

        for key, label in system_info:
            info_layout_item = QHBoxLayout()
            label_widget = QLabel(f"{label}:")
            label_widget.setStyleSheet("color: #9ca3af; font-size: 11px;")
            label_widget.setFixedWidth(80)

            value_widget = QLabel("获取中...")
            value_widget.setStyleSheet("color: white; font-size: 11px;")

            info_layout_item.addWidget(label_widget)
            info_layout_item.addWidget(value_widget)
            info_layout_item.addStretch()

            info_layout.addLayout(info_layout_item)
            self.system_info_labels[key] = value_widget

        layout.addWidget(info_group)

        # 性能监控
        perf_group = QGroupBox("性能监控")
        perf_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #374151;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background-color: #1e293b;
            }
        """)

        perf_layout = QVBoxLayout(perf_group)

        # CPU使用率进度条
        cpu_layout = QHBoxLayout()
        cpu_layout.addWidget(QLabel("CPU使用率:"))
        self.cpu_progress = QProgressBar()
        self.cpu_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #4b5563;
                border-radius: 4px;
                text-align: center;
                color: white;
                background-color: #374151;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 3px;
            }
        """)
        cpu_layout.addWidget(self.cpu_progress)
        perf_layout.addLayout(cpu_layout)

        # 内存使用率进度条
        memory_layout = QHBoxLayout()
        memory_layout.addWidget(QLabel("内存使用率:"))
        self.memory_progress = QProgressBar()
        self.memory_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #4b5563;
                border-radius: 4px;
                text-align: center;
                color: white;
                background-color: #374151;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 3px;
            }
        """)
        memory_layout.addWidget(self.memory_progress)
        perf_layout.addLayout(memory_layout)

        layout.addWidget(perf_group)
        layout.addStretch()

        return widget

    def setup_health_monitoring(self):
        """设置健康监控"""
        try:
            # 连接健康监控信号
            health_monitor.service_status_changed.connect(self.on_service_status_changed)
            health_monitor.service_recovered.connect(self.on_service_recovered)
            health_monitor.service_failed.connect(self.on_service_failed)
            health_monitor.health_report_updated.connect(self.on_health_report_updated)
            
            logger.info("健康监控信号连接完成")

        except Exception as e:
            logger.error(f"设置健康监控失败: {e}")

    def setup_timers(self):
        """设置定时器"""
        try:
            # 系统状态更新定时器
            self.system_timer = QTimer()
            self.system_timer.timeout.connect(self.update_system_info)
            self.system_timer.start(5000)  # 每5秒更新一次

            # 消息统计更新定时器
            self.stats_timer = QTimer()
            self.stats_timer.timeout.connect(self.update_message_stats)
            self.stats_timer.start(2000)  # 每2秒更新一次

            logger.info("定时器设置完成")

        except Exception as e:
            logger.error(f"设置定时器失败: {e}")

    def update_system_info(self):
        """更新系统信息"""
        try:
            import sys
            import psutil
            from PyQt6.QtCore import QT_VERSION_STR

            # Python版本
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            self.system_info_labels["python_version"].setText(python_version)

            # Qt版本
            self.system_info_labels["qt_version"].setText(QT_VERSION_STR)

            # 内存使用
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            self.system_info_labels["memory_usage"].setText(f"{memory_mb:.1f} MB")

            # 运行时间
            if hasattr(self, 'start_time'):
                uptime_seconds = time.time() - self.start_time
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                self.system_info_labels["uptime"].setText(f"{hours:02d}:{minutes:02d}")
            else:
                self.start_time = time.time()
                self.system_info_labels["uptime"].setText("00:00")

            # 更新性能监控
            try:
                cpu_percent = psutil.cpu_percent()
                self.cpu_progress.setValue(int(cpu_percent))

                memory_percent = psutil.virtual_memory().percent
                self.memory_progress.setValue(int(memory_percent))
            except:
                pass

        except ImportError:
            # 如果psutil不可用，显示基本信息
            self.system_info_labels["python_version"].setText(f"{sys.version_info.major}.{sys.version_info.minor}")
            self.system_info_labels["qt_version"].setText("未知")
            self.system_info_labels["memory_usage"].setText("未知")
            self.system_info_labels["uptime"].setText("未知")
        except Exception as e:
            logger.error(f"更新系统信息失败: {e}")

    def update_message_stats(self):
        """更新消息统计"""
        try:
            # 从状态管理器获取统计信息
            stats = state_manager.get_stats()

            for key in self.message_stats_labels:
                value = stats.get(key, 0)
                self.message_stats_labels[key].setText(str(value))

        except Exception as e:
            logger.error(f"更新消息统计失败: {e}")
    
    def on_service_status_changed(self, service_name: str, old_status: str, new_status: str):
        """服务状态变化处理"""
        try:
            status_enum = ServiceStatus(new_status)
            self.control_panel.update_service_status(service_name, status_enum)
            logger.info(f"服务状态变化: {service_name} {old_status} -> {new_status}")
        except Exception as e:
            logger.error(f"处理服务状态变化失败: {e}")
    
    def on_service_recovered(self, service_name: str, message: str):
        """服务恢复处理"""
        logger.info(f"服务恢复: {service_name} - {message}")
    
    def on_service_failed(self, service_name: str, error_message: str):
        """服务失败处理"""
        logger.error(f"服务失败: {service_name} - {error_message}")
    
    def on_health_report_updated(self, report: dict):
        """健康报告更新处理"""
        try:
            # 更新服务状态
            services = report.get('services', {})
            for service_name, service_info in services.items():
                status_str = service_info.get('status', 'unknown')
                try:
                    status = ServiceStatus(status_str)
                    last_result = service_info.get('last_result', {})
                    message = last_result.get('message', '')
                    details = last_result.get('details', {})
                    
                    self.control_panel.update_service_status(service_name, status, message, details)
                except ValueError:
                    logger.warning(f"未知服务状态: {status_str}")
            
            # 更新统计信息
            summary = report.get('summary', {})
            self.control_panel.update_stats(summary)
            
        except Exception as e:
            logger.error(f"处理健康报告更新失败: {e}")
    
    def closeEvent(self, event):
        """关闭事件处理"""
        try:
            # 停止健康监控
            health_monitor.stop_monitoring()
            
            # 清理异步微信管理器
            async_wechat_manager.cleanup()
            
            logger.info("应用程序正在关闭...")
            event.accept()
            
        except Exception as e:
            logger.error(f"关闭应用程序时发生错误: {e}")
            event.accept()

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序属性
    app.setApplicationName("微信自动记账助手")
    app.setApplicationVersion("2.0.0")
    
    # 创建主窗口
    window = EnhancedMainWindow()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
