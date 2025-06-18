#!/usr/bin/env python3
"""
模块化简约主界面
使用新的模块化架构重构的主界面
"""

import sys
import os
import logging
import time
import threading
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

# 导入新的模块化组件
from app.modules import (
    ConfigManager, AccountingManager, WechatServiceManager, 
    WxautoManager, MessageListener, MessageDelivery, 
    LogManager, ServiceMonitor
)

# 导入UI组件
from app.qt_ui.ui_components import (
    CircularButton, StatusIndicator, StatCard, ConfigDialog
)

logger = logging.getLogger(__name__)


class ModularMainWindow(QMainWindow):
    """模块化主窗口"""
    
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
        
        logger.info("模块化主窗口初始化完成")
    
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
            self.accounting_manager = AccountingManager(parent=self)
            
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
        """初始化UI"""
        self.setWindowTitle("只为记账-微信助手 (模块化版)")
        self.setFixedSize(800, 600)
        
        # 设置深色主题
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
                color: white;
            }
            QWidget {
                background-color: transparent;
                color: white;
            }
            QLabel {
                color: white;
                font-family: 'Microsoft YaHei';
            }
        """)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_label = QLabel("只为记账-微信助手")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #3b82f6; margin-bottom: 20px;")
        main_layout.addWidget(title_label)
        
        # 主控制区域
        control_layout = QHBoxLayout()
        
        # 左侧：主控按钮
        left_layout = QVBoxLayout()
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.main_button = CircularButton("开始监听")
        self.main_button.clicked.connect(self.toggle_monitoring)
        left_layout.addWidget(self.main_button)
        
        # 状态文本
        self.status_text = QLabel("点击开始监听")
        self.status_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_text.setFont(QFont("Microsoft YaHei", 12))
        self.status_text.setStyleSheet("color: #64748b; margin-top: 10px;")
        left_layout.addWidget(self.status_text)
        
        control_layout.addLayout(left_layout)
        control_layout.addSpacing(50)
        
        # 右侧：状态指示器
        right_layout = QVBoxLayout()
        
        # 服务状态指示器
        self.accounting_indicator = StatusIndicator("记账服务", "未连接")
        self.accounting_indicator.clicked.connect(lambda: self.open_config_dialog("记账服务"))
        right_layout.addWidget(self.accounting_indicator)
        
        self.wechat_indicator = StatusIndicator("微信服务", "未连接")
        self.wechat_indicator.clicked.connect(lambda: self.open_config_dialog("微信服务"))
        right_layout.addWidget(self.wechat_indicator)
        
        self.monitor_indicator = StatusIndicator("监控服务", "已停止")
        self.monitor_indicator.clicked.connect(self.show_monitor_details)
        right_layout.addWidget(self.monitor_indicator)
        
        control_layout.addLayout(right_layout)
        main_layout.addLayout(control_layout)
        
        # 统计区域
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        stats_layout = QVBoxLayout(stats_frame)
        
        stats_title = QLabel("统计信息")
        stats_title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        stats_title.setStyleSheet("color: #f1f5f9; margin-bottom: 10px;")
        stats_layout.addWidget(stats_title)
        
        # 统计卡片
        cards_layout = QHBoxLayout()
        
        self.total_card = StatCard("总处理", 0)
        self.success_card = StatCard("成功", 0)
        self.failed_card = StatCard("失败", 0)
        self.irrelevant_card = StatCard("无关", 0)
        
        cards_layout.addWidget(self.total_card)
        cards_layout.addWidget(self.success_card)
        cards_layout.addWidget(self.failed_card)
        cards_layout.addWidget(self.irrelevant_card)
        cards_layout.addStretch()
        
        stats_layout.addLayout(cards_layout)
        main_layout.addWidget(stats_frame)
        
        # 操作按钮区域
        buttons_layout = QHBoxLayout()
        
        self.config_btn = QPushButton("配置管理")
        self.config_btn.clicked.connect(self.show_config_manager)
        self.config_btn.setStyleSheet("""
            QPushButton {
                background-color: #475569;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #64748b;
            }
        """)
        
        self.logs_btn = QPushButton("查看日志")
        self.logs_btn.clicked.connect(self.show_logs)
        self.logs_btn.setStyleSheet(self.config_btn.styleSheet())
        
        self.monitor_btn = QPushButton("服务监控")
        self.monitor_btn.clicked.connect(self.show_service_monitor)
        self.monitor_btn.setStyleSheet(self.config_btn.styleSheet())
        
        buttons_layout.addWidget(self.config_btn)
        buttons_layout.addWidget(self.logs_btn)
        buttons_layout.addWidget(self.monitor_btn)
        buttons_layout.addStretch()
        
        main_layout.addLayout(buttons_layout)
        main_layout.addStretch()
    
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
        if success:
            self.stats['successful_accounting'] += 1
        else:
            self.stats['failed_accounting'] += 1
        
        self.update_stats_display()
    
    def on_monitoring_started(self, chat_names):
        """监控开始"""
        self.monitored_chats = chat_names
        self.monitor_indicator.set_active(True, blinking=True)
        self.monitor_indicator.set_subtitle(f"监控{len(chat_names)}个聊天")
        logger.info(f"监控开始: {chat_names}")
    
    def on_monitoring_stopped(self):
        """监控停止"""
        self.monitored_chats = []
        self.monitor_indicator.set_active(False)
        self.monitor_indicator.set_subtitle("已停止")
        logger.info("监控停止")
    
    def on_stats_updated(self, chat_name, stats):
        """统计更新"""
        # 更新总体统计
        self.stats['total_processed'] = stats.get('total_processed', 0)
        self.stats['successful_accounting'] = stats.get('successful_accounting', 0)
        self.stats['failed_accounting'] = stats.get('failed_accounting', 0)
        self.stats['irrelevant_messages'] = stats.get('irrelevant_messages', 0)
        
        self.update_stats_display()
    
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
        # 发送到消息投递服务处理
        if self.message_delivery:
            self.message_delivery.process_message(
                chat_name,
                message_data.get('content', ''),
                message_data.get('sender_remark', message_data.get('sender', ''))
            )
    
    def on_listening_started(self, chat_names):
        """消息监听开始"""
        logger.info(f"消息监听开始: {chat_names}")
    
    def on_listening_stopped(self):
        """消息监听停止"""
        logger.info("消息监听停止")
    
    def on_delivery_accounting_completed(self, chat_name, success, message, data):
        """投递记账完成"""
        if success:
            self.stats['successful_accounting'] += 1
        else:
            self.stats['failed_accounting'] += 1
        
        self.stats['total_processed'] += 1
        self.update_stats_display()
    
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
        self.total_card.set_value(self.stats['total_processed'])
        self.success_card.set_value(self.stats['successful_accounting'])
        self.failed_card.set_value(self.stats['failed_accounting'])
        self.irrelevant_card.set_value(self.stats['irrelevant_messages'])
    
    # 用户交互方法
    
    def toggle_monitoring(self):
        """切换监控状态"""
        try:
            if not self.is_monitoring:
                # 开始监控
                if self.start_monitoring():
                    self.is_monitoring = True
                    self.main_button.set_listening_state(True)
                    self.status_text.setText("监控运行中...")
                    self.status_text.setStyleSheet("color: #22c55e;")
            else:
                # 停止监控
                if self.stop_monitoring():
                    self.is_monitoring = False
                    self.main_button.set_listening_state(False)
                    self.status_text.setText("监控已停止")
                    self.status_text.setStyleSheet("color: #64748b;")
                    
        except Exception as e:
            logger.error(f"切换监控状态失败: {e}")
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
            if config_type == "记账服务":
                self.show_accounting_config()
            elif config_type == "微信服务":
                self.show_wechat_config()
            else:
                QMessageBox.information(self, "提示", f"{config_type}配置功能开发中")

        except Exception as e:
            logger.error(f"打开配置对话框失败: {e}")
            QMessageBox.warning(self, "错误", f"打开配置对话框失败: {str(e)}")

    def show_accounting_config(self):
        """显示记账服务配置"""
        try:
            from app.qt_ui.config_dialogs import AccountingConfigDialog

            dialog = AccountingConfigDialog(
                config_manager=self.config_manager,
                accounting_manager=self.accounting_manager,
                parent=self
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                logger.info("记账配置已更新")

        except ImportError:
            # 如果配置对话框不存在，使用简单的输入对话框
            self.show_simple_accounting_config()
        except Exception as e:
            logger.error(f"显示记账配置失败: {e}")
            QMessageBox.warning(self, "错误", f"显示记账配置失败: {str(e)}")

    def show_simple_accounting_config(self):
        """显示简单的记账配置对话框"""
        try:
            config = self.config_manager.get_accounting_config()

            # 创建简单的配置对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("记账服务配置")
            dialog.setModal(True)
            dialog.resize(400, 300)

            layout = QVBoxLayout(dialog)

            # 服务器地址
            layout.addWidget(QLabel("服务器地址:"))
            server_edit = QLineEdit(config.server_url)
            layout.addWidget(server_edit)

            # 用户名
            layout.addWidget(QLabel("用户名:"))
            username_edit = QLineEdit(config.username)
            layout.addWidget(username_edit)

            # 密码
            layout.addWidget(QLabel("密码:"))
            password_edit = QLineEdit(config.password)
            password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addWidget(password_edit)

            # 按钮
            button_layout = QHBoxLayout()

            test_btn = QPushButton("测试连接")
            test_btn.clicked.connect(lambda: self.test_accounting_connection(
                server_edit.text(), username_edit.text(), password_edit.text()
            ))

            save_btn = QPushButton("保存")
            save_btn.clicked.connect(lambda: self.save_accounting_config(
                dialog, server_edit.text(), username_edit.text(), password_edit.text()
            ))

            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(dialog.reject)

            button_layout.addWidget(test_btn)
            button_layout.addWidget(save_btn)
            button_layout.addWidget(cancel_btn)

            layout.addLayout(button_layout)

            dialog.exec()

        except Exception as e:
            logger.error(f"显示简单记账配置失败: {e}")
            QMessageBox.warning(self, "错误", f"显示记账配置失败: {str(e)}")

    def test_accounting_connection(self, server_url, username, password):
        """测试记账连接"""
        try:
            if not all([server_url, username, password]):
                QMessageBox.warning(self, "警告", "请填写完整的连接信息")
                return

            # 使用记账管理器测试连接
            if self.accounting_manager:
                success, message = self.accounting_manager.login(server_url, username, password)

                if success:
                    QMessageBox.information(self, "成功", "连接测试成功！")
                else:
                    QMessageBox.warning(self, "失败", f"连接测试失败: {message}")
            else:
                QMessageBox.warning(self, "错误", "记账管理器未初始化")

        except Exception as e:
            logger.error(f"测试记账连接失败: {e}")
            QMessageBox.warning(self, "错误", f"测试连接失败: {str(e)}")

    def save_accounting_config(self, dialog, server_url, username, password):
        """保存记账配置"""
        try:
            if not all([server_url, username, password]):
                QMessageBox.warning(self, "警告", "请填写完整的配置信息")
                return

            # 更新配置
            if self.config_manager:
                success = self.config_manager.update_accounting_config(
                    server_url=server_url,
                    username=username,
                    password=password
                )

                if success:
                    QMessageBox.information(self, "成功", "配置保存成功！")
                    dialog.accept()
                else:
                    QMessageBox.warning(self, "失败", "配置保存失败")
            else:
                QMessageBox.warning(self, "错误", "配置管理器未初始化")

        except Exception as e:
            logger.error(f"保存记账配置失败: {e}")
            QMessageBox.warning(self, "错误", f"保存配置失败: {str(e)}")

    def show_wechat_config(self):
        """显示微信服务配置"""
        try:
            config = self.config_manager.get_wechat_monitor_config()

            # 创建微信配置对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("微信服务配置")
            dialog.setModal(True)
            dialog.resize(400, 400)

            layout = QVBoxLayout(dialog)

            # 启用监控
            enabled_check = QCheckBox("启用微信监控")
            enabled_check.setChecked(config.enabled)
            layout.addWidget(enabled_check)

            # 监控聊天列表
            layout.addWidget(QLabel("监控聊天列表 (每行一个):"))
            chats_edit = QTextEdit()
            chats_edit.setPlainText('\n'.join(config.monitored_chats))
            chats_edit.setMaximumHeight(100)
            layout.addWidget(chats_edit)

            # 自动回复
            auto_reply_check = QCheckBox("启用自动回复")
            auto_reply_check.setChecked(config.auto_reply)
            layout.addWidget(auto_reply_check)

            # 回复模板
            layout.addWidget(QLabel("回复模板:"))
            template_edit = QLineEdit(config.reply_template)
            layout.addWidget(template_edit)

            # 按钮
            button_layout = QHBoxLayout()

            save_btn = QPushButton("保存")
            save_btn.clicked.connect(lambda: self.save_wechat_config(
                dialog, enabled_check.isChecked(),
                chats_edit.toPlainText().strip().split('\n') if chats_edit.toPlainText().strip() else [],
                auto_reply_check.isChecked(), template_edit.text()
            ))

            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(dialog.reject)

            button_layout.addWidget(save_btn)
            button_layout.addWidget(cancel_btn)

            layout.addLayout(button_layout)

            dialog.exec()

        except Exception as e:
            logger.error(f"显示微信配置失败: {e}")
            QMessageBox.warning(self, "错误", f"显示微信配置失败: {str(e)}")

    def save_wechat_config(self, dialog, enabled, monitored_chats, auto_reply, reply_template):
        """保存微信配置"""
        try:
            # 过滤空的聊天名称
            monitored_chats = [chat.strip() for chat in monitored_chats if chat.strip()]

            # 更新配置
            if self.config_manager:
                success = self.config_manager.update_wechat_monitor_config(
                    enabled=enabled,
                    monitored_chats=monitored_chats,
                    auto_reply=auto_reply,
                    reply_template=reply_template
                )

                if success:
                    QMessageBox.information(self, "成功", "配置保存成功！")
                    dialog.accept()

                    # 更新微信服务管理器
                    if self.wechat_service_manager:
                        # 清除现有监控聊天
                        for chat in self.monitored_chats:
                            self.wechat_service_manager.remove_chat(chat)

                        # 添加新的监控聊天
                        for chat in monitored_chats:
                            self.wechat_service_manager.add_chat(chat)

                        self.monitored_chats = monitored_chats
                else:
                    QMessageBox.warning(self, "失败", "配置保存失败")
            else:
                QMessageBox.warning(self, "错误", "配置管理器未初始化")

        except Exception as e:
            logger.error(f"保存微信配置失败: {e}")
            QMessageBox.warning(self, "错误", f"保存配置失败: {str(e)}")

    def show_config_manager(self):
        """显示配置管理器"""
        QMessageBox.information(self, "提示", "配置管理器界面开发中")

    def show_logs(self):
        """显示日志窗口"""
        try:
            from app.qt_ui.enhanced_log_window import EnhancedLogWindow

            # 创建日志窗口
            log_window = EnhancedLogWindow(self)
            log_window.show()

        except Exception as e:
            logger.error(f"显示日志窗口失败: {e}")
            QMessageBox.warning(self, "错误", f"显示日志窗口失败: {str(e)}")

    def show_service_monitor(self):
        """显示服务监控窗口"""
        QMessageBox.information(self, "提示", "服务监控界面开发中")

    def show_monitor_details(self):
        """显示监控详情"""
        try:
            details = []
            details.append(f"监控状态: {'运行中' if self.is_monitoring else '已停止'}")
            details.append(f"监控聊天: {len(self.monitored_chats)}个")

            if self.monitored_chats:
                details.append("聊天列表:")
                for chat in self.monitored_chats:
                    details.append(f"  - {chat}")

            details.append(f"\n统计信息:")
            details.append(f"总处理: {self.stats['total_processed']}")
            details.append(f"成功: {self.stats['successful_accounting']}")
            details.append(f"失败: {self.stats['failed_accounting']}")
            details.append(f"无关: {self.stats['irrelevant_messages']}")

            QMessageBox.information(self, "监控详情", '\n'.join(details))

        except Exception as e:
            logger.error(f"显示监控详情失败: {e}")
            QMessageBox.warning(self, "错误", f"显示监控详情失败: {str(e)}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            logger.info("模块化主窗口正在关闭...")

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
            logger.info("模块化主窗口关闭完成")

        except Exception as e:
            logger.error(f"关闭窗口时出错: {e}")
            event.accept()  # 确保窗口能够关闭


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用程序属性
    app.setApplicationName("只为记账-微信助手 (模块化版)")
    app.setApplicationVersion("2.0.0")

    # 创建并显示主窗口
    window = ModularMainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
