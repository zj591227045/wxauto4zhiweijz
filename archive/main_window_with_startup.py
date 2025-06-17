#!/usr/bin/env python3
"""
带自动启动功能的PyQt6主界面
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
                             QHBoxLayout, QGridLayout, QGroupBox, QLabel, 
                             QPushButton, QLineEdit, QTextEdit, QComboBox, 
                             QListWidget, QSpinBox, QCheckBox, QStatusBar,
                             QMessageBox, QSplitter, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 导入原始主窗口类
from qt_ui.main_window_fixed import MainWindow as BaseMainWindow
from app.qt_ui.state_integrated_window import StateIntegratedMixin
from app.utils.state_manager import state_manager

class StartupThread(QThread):
    """启动线程"""
    log_signal = pyqtSignal(str, str)  # level, message
    countdown_signal = pyqtSignal(int)  # remaining seconds
    startup_complete_signal = pyqtSignal(bool)  # success
    
    def __init__(self):
        super().__init__()
        self.should_stop = False
    
    def run(self):
        """执行启动流程"""
        try:
            # 1. 倒计时5秒
            self.log_signal.emit("INFO", "程序启动倒计时开始...")
            for i in range(5, 0, -1):
                if self.should_stop:
                    return
                self.countdown_signal.emit(i)
                self.log_signal.emit("INFO", f"倒计时: {i} 秒")
                time.sleep(1)
            
            self.countdown_signal.emit(0)
            self.log_signal.emit("INFO", "倒计时结束，开始启动服务...")
            
            # 2. 启动HTTP API服务
            if not self.start_api_service():
                self.log_signal.emit("ERROR", "HTTP API服务启动失败")
                self.startup_complete_signal.emit(False)
                return
            
            # 3. 获取API配置
            port, api_key = self.get_api_config()
            self.log_signal.emit("INFO", f"API配置: 端口={port}, 密钥={api_key}")
            
            # 4. 检查API服务状态
            if not self.check_api_service_status(port):
                self.log_signal.emit("ERROR", "API服务未能正常启动")
                self.startup_complete_signal.emit(False)
                return
            
            # 5. 初始化微信
            wechat_success = self.initialize_wechat_via_api(port, api_key)
            if wechat_success:
                self.log_signal.emit("INFO", "微信初始化成功")
            else:
                self.log_signal.emit("WARNING", "微信初始化失败，但程序将继续运行")
            
            self.log_signal.emit("INFO", "启动流程完成")
            self.startup_complete_signal.emit(True)
            
        except Exception as e:
            self.log_signal.emit("ERROR", f"启动过程中发生异常: {str(e)}")
            self.startup_complete_signal.emit(False)
    
    def start_api_service(self):
        """启动HTTP API服务"""
        try:
            self.log_signal.emit("INFO", "正在启动HTTP API服务...")
            
            # 导入API服务启动函数
            from app.api_service import start_api
            
            # 在新线程中启动API服务
            api_thread = threading.Thread(target=start_api, daemon=True)
            api_thread.start()
            
            self.log_signal.emit("INFO", "HTTP API服务启动线程已创建")
            return True
        except Exception as e:
            self.log_signal.emit("ERROR", f"启动HTTP API服务失败: {str(e)}")
            return False
    
    def check_api_service_status(self, port=5000, max_retries=10, retry_interval=2):
        """检查API服务状态"""
        self.log_signal.emit("INFO", f"正在检查API服务状态 (端口: {port})...")
        
        for attempt in range(1, max_retries + 1):
            if self.should_stop:
                return False
                
            try:
                response = requests.get(f"http://localhost:{port}/api/health", timeout=5)
                if response.status_code == 200:
                    self.log_signal.emit("INFO", f"✓ API服务已启动并运行正常 (尝试 {attempt}/{max_retries})")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            if attempt < max_retries:
                self.log_signal.emit("INFO", f"API服务尚未就绪，等待 {retry_interval} 秒后重试... (尝试 {attempt}/{max_retries})")
                time.sleep(retry_interval)
        
        self.log_signal.emit("ERROR", f"✗ API服务在 {max_retries} 次尝试后仍未就绪")
        return False
    
    def initialize_wechat_via_api(self, port=5000, api_key="test-key-2"):
        """通过HTTP API初始化微信"""
        try:
            self.log_signal.emit("INFO", "正在通过HTTP API初始化微信...")
            
            # 首先检查微信状态
            try:
                response = requests.get(
                    f"http://localhost:{port}/api/wechat/status",
                    headers={"X-API-Key": api_key},
                    timeout=10
                )
                if response.status_code == 200:
                    status_data = response.json()
                    if status_data.get("code") == 0:
                        wechat_status = status_data.get("data", {}).get("status", "unknown")
                        if wechat_status == "online":
                            self.log_signal.emit("INFO", "✓ 微信已经处于在线状态，无需重新初始化")
                            return True
            except Exception as e:
                self.log_signal.emit("WARNING", f"检查微信状态时出错: {str(e)}")
            
            # 执行微信初始化
            response = requests.post(
                f"http://localhost:{port}/api/wechat/initialize",
                headers={"X-API-Key": api_key},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    window_name = result.get("data", {}).get("window_name", "")
                    self.log_signal.emit("INFO", "✓ 微信初始化成功")
                    if window_name:
                        self.log_signal.emit("INFO", f"  微信窗口: {window_name}")
                    return True
                else:
                    self.log_signal.emit("ERROR", f"✗ 微信初始化失败: {result.get('message', '未知错误')}")
                    return False
            else:
                self.log_signal.emit("ERROR", f"✗ 微信初始化请求失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_signal.emit("ERROR", f"✗ 微信初始化过程中出错: {str(e)}")
            return False
    
    def get_api_config(self):
        """获取API配置"""
        try:
            from app.config import Config
            port = Config.PORT
            
            # 尝试获取API密钥
            api_key = "test-key-2"  # 默认值
            try:
                from app import config_manager
                config = config_manager.load_app_config()
                api_keys = config.get('api_keys', ['test-key-2'])
                if api_keys:
                    api_key = api_keys[0]
            except:
                pass
                
            return port, api_key
        except Exception as e:
            self.log_signal.emit("WARNING", f"获取API配置失败: {str(e)}")
            return 5000, "test-key-2"
    
    def stop(self):
        """停止启动线程"""
        self.should_stop = True

class MainWindowWithStartup(BaseMainWindow, StateIntegratedMixin):
    """带自动启动功能的主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 启动相关属性
        self.startup_thread = None
        self.countdown_timer = None
        
        # 修改窗口标题
        self.setWindowTitle("只为记账-微信助手 (高级模式)")
        
        # 添加返回简约模式按钮
        self.add_simple_mode_button()
        
        # 设置状态集成
        self.setup_state_integration()
        
        # 启动自动启动流程
        self.start_auto_startup()
    
    def add_simple_mode_button(self):
        """添加返回简约模式按钮"""
        try:
            # 获取状态栏
            status_bar = self.statusBar()
            
            # 创建返回简约模式按钮
            self.simple_mode_btn = QPushButton("返回简约模式")
            self.simple_mode_btn.setFixedSize(120, 30)
            self.simple_mode_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    border: 1px solid #5a6268;
                    border-radius: 4px;
                    color: white;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                    border-color: #545b62;
                }
                QPushButton:pressed {
                    background-color: #545b62;
                }
            """)
            self.simple_mode_btn.clicked.connect(self.return_to_simple_mode)
            
            # 将按钮添加到状态栏的右侧
            status_bar.addPermanentWidget(self.simple_mode_btn)
            
        except Exception as e:
            print(f"添加简约模式按钮失败: {e}")
    
    def return_to_simple_mode(self):
        """返回简约模式"""
        try:
            print("正在返回简约模式...")
            
            # 断开当前窗口的状态连接，避免循环回调
            self.disconnect_state_connections()
            
            # 停止启动线程
            if self.startup_thread and self.startup_thread.isRunning():
                self.startup_thread.stop()
                self.startup_thread.wait(1000)  # 等待最多1秒
            
            # 导入简约模式窗口
            from app.qt_ui.simple_main_window import SimpleMainWindow
            
            # 创建简约模式窗口
            self.simple_window = SimpleMainWindow()
            
            # 显示简约模式窗口
            self.simple_window.show()
            
            # 关闭当前窗口（而不是隐藏）
            self.close()
            
        except Exception as e:
            print(f"返回简约模式失败: {e}")
            import traceback
            traceback.print_exc()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", f"无法返回简约模式: {str(e)}")
    
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
    
    def start_auto_startup(self):
        """开始自动启动流程"""
        self.log_message("INFO", "=" * 50)
        self.log_message("INFO", "只为记账-微信助手 自动启动")
        self.log_message("INFO", "=" * 50)
        
        # 创建并启动启动线程
        self.startup_thread = StartupThread()
        self.startup_thread.log_signal.connect(self.log_message)
        self.startup_thread.countdown_signal.connect(self.update_countdown)
        self.startup_thread.startup_complete_signal.connect(self.on_startup_complete)
        self.startup_thread.start()
    
    def update_countdown(self, remaining_seconds):
        """更新倒计时显示"""
        if remaining_seconds > 0:
            # 更新窗口标题显示倒计时
            self.setWindowTitle(f"只为记账-微信助手 (启动倒计时: {remaining_seconds}秒)")
        else:
            self.setWindowTitle("只为记账-微信助手 (正在启动服务...)")
    
    def on_startup_complete(self, success):
        """启动完成回调"""
        if success:
            self.setWindowTitle("只为记账-微信助手 (启动完成)")
            self.log_message("INFO", "🎉 自动启动流程已完成！")
            self.log_message("INFO", "您现在可以使用所有功能了。")
        else:
            self.setWindowTitle("只为记账-微信助手 (启动失败)")
            self.log_message("ERROR", "❌ 自动启动流程失败！")
            self.log_message("INFO", "您可以手动启动服务或重试。")
        
        # 清理启动线程
        if self.startup_thread:
            self.startup_thread.stop()
            self.startup_thread = None
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            print("高级模式窗口正在关闭...")
            
            # 断开状态连接
            self.disconnect_state_connections()
            
            # 停止启动线程
            if self.startup_thread and self.startup_thread.isRunning():
                self.startup_thread.stop()
                self.startup_thread.wait(3000)  # 等待最多3秒
            
            # 如果是用户主动关闭窗口，返回简约模式
            if event.spontaneous():  # 用户点击关闭按钮
                event.ignore()  # 忽略关闭事件
                self.return_to_simple_mode()  # 返回简约模式
            else:
                # 程序内部调用的关闭，正常处理
                event.accept()
            
        except Exception as e:
            print(f"关闭窗口时出错: {e}")
            # 如果返回简约模式失败，则正常关闭
            event.accept()
    
    def on_accounting_service_changed(self, config: dict):
        """只为记账服务状态变化"""
        try:
            # 更新UI控件
            if hasattr(self, 'server_url_edit'):
                self.server_url_edit.setText(config.get('server_url', ''))
            if hasattr(self, 'username_edit'):
                self.username_edit.setText(config.get('username', ''))
            
            # 更新用户信息显示
            if hasattr(self, 'user_info_label'):
                if config.get('is_logged_in', False):
                    username = config.get('username', '')
                    self.user_info_label.setText(f"已登录: {username}")
                    self.user_info_label.setStyleSheet("color: green; font-style: normal;")
                else:
                    self.user_info_label.setText("未登录")
                    self.user_info_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
            
            # 更新账本列表
            if hasattr(self, 'account_book_combo'):
                self.account_book_combo.clear()
                account_books = config.get('account_books', [])
                for book in account_books:
                    self.account_book_combo.addItem(book.get('name', ''), book.get('id', ''))
                
                # 设置当前选中的账本
                selected_book = config.get('selected_account_book', '')
                if selected_book:
                    index = self.account_book_combo.findData(selected_book)
                    if index >= 0:
                        self.account_book_combo.setCurrentIndex(index)
        except Exception as e:
            print(f"更新只为记账服务UI失败: {e}")
    
    def on_wechat_status_changed(self, status: dict):
        """微信状态变化"""
        try:
            wechat_status = status.get('status', 'offline')
            window_name = status.get('window_name', '')
            
            # 更新微信状态指示器
            if hasattr(self, 'wechat_status_indicator'):
                self.wechat_status_indicator.set_status(wechat_status == 'online')
            
            # 更新微信状态标签
            if hasattr(self, 'wechat_status_label'):
                if wechat_status == 'online':
                    self.wechat_status_label.setText(f"已连接: {window_name}")
                    self.wechat_status_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.wechat_status_label.setText("未连接")
                    self.wechat_status_label.setStyleSheet("color: red; font-weight: bold;")
        except Exception as e:
            print(f"更新微信状态UI失败: {e}")
    
    def on_api_status_changed(self, status: dict):
        """API状态变化"""
        try:
            api_status = status.get('status', 'stopped')
            
            # 更新API状态指示器
            if hasattr(self, 'api_status_indicator'):
                self.api_status_indicator.set_status(api_status == 'running')
            
            # 更新API状态标签
            if hasattr(self, 'api_status_label'):
                if api_status == 'running':
                    port = status.get('port', 5000)
                    self.api_status_label.setText(f"运行中 (端口: {port})")
                    self.api_status_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.api_status_label.setText("未启动")
                    self.api_status_label.setStyleSheet("color: red; font-weight: bold;")
        except Exception as e:
            print(f"更新API状态UI失败: {e}")
    
    def on_stats_changed(self, stats: dict):
        """统计数据变化"""
        try:
            # 更新统计显示
            processed = stats.get('processed_messages', 0)
            successful = stats.get('successful_records', 0)
            failed = stats.get('failed_records', 0)
            
            # 如果有统计标签，更新它们
            if hasattr(self, 'stats_label'):
                self.stats_label.setText(
                    f"处理消息: {processed} | 成功记账: {successful} | 失败记账: {failed}"
                )
        except Exception as e:
            print(f"更新统计UI失败: {e}")
    
    def on_monitoring_status_changed(self, is_active: bool):
        """监控状态变化"""
        try:
            # 更新监控状态指示器
            if hasattr(self, 'monitor_status_indicator'):
                self.monitor_status_indicator.set_status(is_active)
            
            # 更新监控状态标签
            if hasattr(self, 'monitor_status_label'):
                if is_active:
                    self.monitor_status_label.setText("监控中")
                    self.monitor_status_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.monitor_status_label.setText("未启动")
                    self.monitor_status_label.setStyleSheet("color: red; font-weight: bold;")
            
            # 更新按钮状态
            if hasattr(self, 'start_monitor_btn'):
                self.start_monitor_btn.setEnabled(not is_active)
            if hasattr(self, 'stop_monitor_btn'):
                self.stop_monitor_btn.setEnabled(is_active)
        except Exception as e:
            print(f"更新监控状态UI失败: {e}")
    
    def login_to_accounting_service(self):
        """登录到记账服务"""
        try:
            server_url = self.server_url_edit.text().strip()
            username = self.username_edit.text().strip()
            password = self.password_edit.text().strip()
            
            if not all([server_url, username, password]):
                self.log_message("ERROR", "请填写完整的服务器地址、用户名和密码")
                return
            
            # 更新状态为连接中
            state_manager.update_accounting_service(
                server_url=server_url,
                username=username,
                password=password,
                status='connecting'
            )
            
            self.log_message("INFO", f"正在登录到记账服务: {server_url}")
            
            # 这里应该调用实际的登录逻辑
            # 暂时模拟登录成功
            import threading
            def simulate_login():
                import time
                time.sleep(2)  # 模拟网络延迟
                
                # 模拟登录成功
                state_manager.update_accounting_service(
                    is_logged_in=True,
                    status='connected',
                    token='mock_token_123',
                    account_books=[
                        {'id': 'book1', 'name': '我的账本'},
                        {'id': 'book2', 'name': '家庭账本'}
                    ]
                )
                
                self.log_message("INFO", "登录成功")
            
            threading.Thread(target=simulate_login, daemon=True).start()
            
        except Exception as e:
            self.log_message("ERROR", f"登录失败: {str(e)}")
            state_manager.update_accounting_service(status='error')
    
    def start_monitoring(self):
        """开始监控"""
        try:
            # 从UI获取监控配置
            monitored_chats = []
            if hasattr(self, 'chat_list_widget'):
                for i in range(self.chat_list_widget.count()):
                    chat_name = self.chat_list_widget.item(i).text()
                    monitored_chats.append(chat_name)
            
            check_interval = 5
            if hasattr(self, 'interval_spinbox'):
                check_interval = self.interval_spinbox.value()
            
            # 更新状态
            state_manager.update_monitoring_status(
                True,
                monitored_chats=monitored_chats,
                check_interval=check_interval
            )
            
            # 开始新的会话
            state_manager.start_session()
            
            self.log_message("INFO", f"开始监控 {len(monitored_chats)} 个会话")
            
        except Exception as e:
            self.log_message("ERROR", f"启动监控失败: {str(e)}")
    
    def stop_monitoring(self):
        """停止监控"""
        try:
            state_manager.update_monitoring_status(False)
            self.log_message("INFO", "停止监控")
        except Exception as e:
            self.log_message("ERROR", f"停止监控失败: {str(e)}")
    
    def on_account_book_changed(self):
        """账本选择变化"""
        try:
            if hasattr(self, 'account_book_combo'):
                selected_book_id = self.account_book_combo.currentData()
                if selected_book_id:
                    state_manager.update_accounting_service(
                        selected_account_book=selected_book_id
                    )
        except Exception as e:
            print(f"更新账本选择失败: {e}")

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
    window = MainWindowWithStartup()
    window.show()
    
    # 运行应用
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 