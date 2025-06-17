"""
微信自动化库适配器
支持wxauto和wxautox两种库的动态切换
"""

import importlib
import sys
import os
import threading
import time
import pythoncom
import logging
from typing import Optional, Union, List, Dict, Any

# 尝试导入动态包管理器
try:
    from dynamic_package_manager import get_package_manager
    package_manager = get_package_manager()
except ImportError:
    package_manager = None

# 配置日志
try:
    from app.logs import logger, WeChatLibAdapter
except ImportError:
    # 如果无法导入app.logs，则创建一个默认的logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("wechat_adapter")

    # 创建一个空的适配器类，避免导入错误
    class WeChatLibAdapter:
        @staticmethod
        def set_lib_name(lib_name):
            pass

class WeChatAdapter:
    """微信自动化库适配器，支持wxauto和wxautox"""

    def __init__(self, lib_name: str = 'wxauto'):
        """
        初始化适配器

        Args:
            lib_name: 指定使用的库名称，可选值: 'wxauto', 'wxautox'，默认为'wxauto'
        """
        self._instance = None
        self._lib_name = None
        self._lock = threading.Lock()
        self._listen = {}  # 添加listen属性
        self._cached_window_name = ""  # 添加窗口名称缓存

        logger.info(f"初始化WeChatAdapter，请求的库名称: {lib_name}")
        logger.info(f"当前工作目录: {os.getcwd()}")
        logger.info(f"Python路径: {sys.path}")

        # 根据指定的库名称导入相应的库
        if lib_name.lower() == 'wxautox':
            logger.info("尝试导入wxautox库")
            if not self._try_import_wxautox():
                logger.error("无法导入wxautox库，将尝试回退到wxauto")
                if not self._try_import_wxauto():
                    logger.error("无法导入wxauto库")
                    raise ImportError("无法导入wxauto库，请确保已正确安装")
        else:  # 默认使用wxauto
            logger.info("尝试导入wxauto库")
            if not self._try_import_wxauto():
                logger.error("无法导入wxauto库")
                raise ImportError("无法导入wxauto库，请确保已正确安装")

        logger.info(f"使用微信自动化库: {self._lib_name}")

    @property
    def listen(self):
        """获取监听列表"""
        if self._instance:
            # 直接返回实例的listen属性
            return self._instance.listen
        return self._listen

    def _try_import_wxautox(self) -> bool:
        """尝试导入wxautox库"""
        # 首先尝试使用动态包管理器
        if package_manager:
            #logger.info("使用动态包管理器导入wxautox")
            try:
                module = package_manager.import_package("wxautox")
                if module:
                    #logger.info("动态包管理器成功导入wxautox")
                    self._lib_name = "wxautox"
                    # 更新日志适配器中的库名称
                    WeChatLibAdapter.set_lib_name_static("wxautox")
                    return True
                else:
                    logger.warning("动态包管理器导入wxautox失败")

                    # 检查是否是win32ui模块缺失问题
                    try:
                        import win32ui
                        logger.info("win32ui模块已可用，但wxautox导入仍然失败")
                    except ImportError:
                        logger.error("缺少win32ui模块，这是wxautox的必要依赖")
                        logger.error("请在系统Python环境中安装PyWin32包: pip install pywin32")
            except Exception as e:
                logger.error(f"动态包管理器导入wxautox时出错: {str(e)}")

        # 如果动态包管理器不可用或失败，尝试直接导入
        try:
            # 先检查win32ui模块是否可用
            try:
                import win32ui
                logger.info("win32ui模块已可用")
            except ImportError:
                logger.error("缺少win32ui模块，这是wxautox的必要依赖")
                logger.error("请在系统Python环境中安装PyWin32包: pip install pywin32")
                return False

            # 尝试导入wxautox
            import wxautox
            logger.info("直接导入wxautox成功")
            self._lib_name = "wxautox"
            # 更新日志适配器中的库名称
            WeChatLibAdapter.set_lib_name_static("wxautox")
            return True
        except ImportError as e:
            logger.warning(f"无法导入wxautox库: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"导入wxautox时出现未知错误: {str(e)}")
            return False

    def _try_import_wxauto(self) -> bool:
        """尝试导入wxauto库"""
        try:
            # 使用wxauto_wrapper模块确保wxauto库能够被正确导入
            try:
                from app.wxauto_wrapper import get_wxauto
                wxauto = get_wxauto()
                if wxauto:
                    # 设置库名称
                    self._lib_name = "wxauto"
                    # 更新日志适配器中的库名称
                    WeChatLibAdapter.set_lib_name_static("wxauto")

                    return True
                else:
                    logger.error("wxauto库导入失败")
                    return False
            except ImportError as e:
                logger.warning(f"导入wxauto_wrapper模块失败: {str(e)}")
                logger.warning("尝试使用传统方式导入wxauto...")

                # 确保本地wxauto文件夹在Python路径中
                import sys
                import os

                # 获取应用根目录
                if getattr(sys, 'frozen', False):
                    # 如果是打包后的环境
                    app_root = os.path.dirname(sys.executable)
                    logger.info(f"检测到打包环境，应用根目录: {app_root}")

                    # 在打包环境中，确保_MEIPASS目录也在Python路径中
                    meipass = getattr(sys, '_MEIPASS', None)
                    if meipass and meipass not in sys.path:
                        sys.path.insert(0, meipass)
                        logger.info(f"已将_MEIPASS目录添加到Python路径: {meipass}")
                else:
                    # 如果是开发环境
                    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    logger.info(f"检测到开发环境，应用根目录: {app_root}")

                # 尝试多种可能的wxauto路径
                possible_paths = [
                    os.path.join(app_root, "wxauto"),  # 标准路径
                    os.path.join(app_root, "app", "wxauto"),  # 可能的子目录
                ]

                # 如果是打包环境，添加更多可能的路径
                if getattr(sys, 'frozen', False):
                    meipass = getattr(sys, '_MEIPASS', None)
                    if meipass:
                        possible_paths.extend([
                            os.path.join(meipass, "wxauto"),  # PyInstaller临时目录中的wxauto
                            os.path.join(meipass, "app", "wxauto"),  # PyInstaller临时目录中的app/wxauto
                        ])

                # 记录所有可能的路径
                logger.info(f"尝试以下wxauto路径: {possible_paths}")

                for wxauto_path in possible_paths:
                    if os.path.exists(wxauto_path) and os.path.isdir(wxauto_path):
                        logger.info(f"找到wxauto路径: {wxauto_path}")

                        # 检查wxauto路径下是否有wxauto子目录
                        wxauto_inner_path = os.path.join(wxauto_path, "wxauto")
                        if os.path.exists(wxauto_inner_path) and os.path.isdir(wxauto_inner_path):
                            logger.info(f"找到wxauto内部目录: {wxauto_inner_path}")

                            # 将wxauto/wxauto目录添加到路径
                            if wxauto_inner_path not in sys.path:
                                sys.path.insert(0, wxauto_inner_path)
                                logger.info(f"已将wxauto/wxauto目录添加到Python路径: {wxauto_inner_path}")

                        # 将wxauto目录添加到路径
                        if wxauto_path not in sys.path:
                            sys.path.insert(0, wxauto_path)
                            logger.info(f"已将wxauto目录添加到Python路径: {wxauto_path}")

                        # 尝试导入
                        try:
                            import wxauto
                            self._lib_name = "wxauto"
                            # 更新日志适配器中的库名称
                            WeChatLibAdapter.set_lib_name_static("wxauto")
                            logger.info(f"成功从路径导入wxauto: {wxauto_path}")
                            return True
                        except ImportError as inner_e:
                            logger.warning(f"从路径 {wxauto_path} 导入wxauto失败: {str(inner_e)}")
                            # 继续尝试下一个路径

                # 如果所有路径都失败，尝试直接导入
                logger.info("所有路径尝试失败，尝试直接导入wxauto")
                import wxauto
                self._lib_name = "wxauto"
                WeChatLibAdapter.set_lib_name_static("wxauto")
                logger.info("成功直接导入wxauto")
                return True
        except ImportError as e:
            logger.warning(f"无法导入wxauto库: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"尝试导入wxauto时出现未知错误: {str(e)}")
            return False

    def initialize(self) -> bool:
        """初始化微信实例"""
        with self._lock:
            if not self._instance:
                try:
                    # 初始化COM环境
                    pythoncom.CoInitialize()

                    if self._lib_name == "wxautox":
                        # 优先使用动态包管理器
                        if package_manager:
                            #logger.info("使用动态包管理器导入wxautox.WeChat")
                            module = package_manager.import_package("wxautox")
                            if module:
                                #logger.info("动态包管理器成功导入wxautox")
                                WeChat = getattr(module, 'WeChat')
                                self._instance = WeChat()
                            else:
                                # 如果动态包管理器失败，尝试直接导入
                                logger.warning("动态包管理器导入wxautox失败，尝试直接导入")
                                from wxautox import WeChat
                                self._instance = WeChat()
                        else:
                            # 如果动态包管理器不可用，尝试直接导入
                            logger.info("动态包管理器不可用，尝试直接导入wxautox")
                            from wxautox import WeChat
                            self._instance = WeChat()
                    else:  # wxauto
                        # 使用wxauto_wrapper模块确保wxauto库能够被正确导入
                        try:
                            from app.wxauto_wrapper import get_wxauto
                            wxauto = get_wxauto()
                            if wxauto:

                                # 导入WeChat类
                                if hasattr(wxauto, 'WeChat'):
                                    WeChat = wxauto.WeChat
                                    logger.info("成功从wxauto_wrapper获取WeChat类")
                                else:
                                    logger.error("wxauto模块中没有WeChat类")
                                    raise ImportError("wxauto模块中没有WeChat类")
                            else:
                                logger.error("wxauto库导入失败")
                                raise ImportError("无法导入wxauto库")
                        except ImportError as e:
                            logger.warning(f"导入wxauto_wrapper模块失败: {str(e)}")
                            logger.warning("尝试使用传统方式导入wxauto.WeChat...")

                            # 使用与_try_import_wxauto相同的逻辑来确保wxauto库已正确导入
                            import sys
                            import os

                            # 获取应用根目录
                            if getattr(sys, 'frozen', False):
                                # 如果是打包后的环境
                                app_root = os.path.dirname(sys.executable)
                                logger.info(f"初始化时检测到打包环境，应用根目录: {app_root}")

                                # 在打包环境中，确保_MEIPASS目录也在Python路径中
                                meipass = getattr(sys, '_MEIPASS', None)
                                if meipass and meipass not in sys.path:
                                    sys.path.insert(0, meipass)
                                    logger.info(f"初始化时已将_MEIPASS目录添加到Python路径: {meipass}")
                            else:
                                # 如果是开发环境
                                app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                                logger.info(f"初始化时检测到开发环境，应用根目录: {app_root}")

                            # 尝试多种可能的wxauto路径
                            possible_paths = [
                                os.path.join(app_root, "wxauto"),  # 标准路径
                                os.path.join(app_root, "app", "wxauto"),  # 可能的子目录
                            ]

                            # 如果是打包环境，添加更多可能的路径
                            if getattr(sys, 'frozen', False):
                                meipass = getattr(sys, '_MEIPASS', None)
                                if meipass:
                                    possible_paths.extend([
                                        os.path.join(meipass, "wxauto"),  # PyInstaller临时目录中的wxauto
                                        os.path.join(meipass, "app", "wxauto"),  # PyInstaller临时目录中的app/wxauto
                                    ])

                            # 记录所有可能的路径
                            logger.info(f"初始化时尝试以下wxauto路径: {possible_paths}")

                            # 标记是否找到了wxauto模块
                            found_wxauto = False

                            for wxauto_path in possible_paths:
                                if os.path.exists(wxauto_path) and os.path.isdir(wxauto_path):
                                    logger.info(f"初始化时找到wxauto路径: {wxauto_path}")

                                    # 检查wxauto路径下是否有wxauto子目录
                                    wxauto_inner_path = os.path.join(wxauto_path, "wxauto")
                                    if os.path.exists(wxauto_inner_path) and os.path.isdir(wxauto_inner_path):
                                        logger.info(f"初始化时找到wxauto内部目录: {wxauto_inner_path}")

                                        # 将wxauto/wxauto目录添加到路径
                                        if wxauto_inner_path not in sys.path:
                                            sys.path.insert(0, wxauto_inner_path)
                                            logger.info(f"初始化时已将wxauto/wxauto目录添加到Python路径: {wxauto_inner_path}")

                                    # 将wxauto目录添加到路径
                                    if wxauto_path not in sys.path:
                                        sys.path.insert(0, wxauto_path)
                                        logger.info(f"初始化时已将wxauto目录添加到Python路径: {wxauto_path}")

                                    # 尝试导入
                                    try:
                                        from wxauto import WeChat
                                        found_wxauto = True
                                        logger.info(f"初始化时成功从路径导入wxauto.WeChat: {wxauto_path}")
                                        break  # 成功导入，跳出循环
                                    except ImportError as inner_e:
                                        logger.warning(f"初始化时从路径 {wxauto_path} 导入wxauto.WeChat失败: {str(inner_e)}")
                                        # 继续尝试下一个路径

                            # 如果所有路径都失败，尝试直接导入
                            if not found_wxauto:
                                logger.info("初始化时所有路径尝试失败，尝试直接导入wxauto.WeChat")
                                from wxauto import WeChat

                        # 尝试创建WeChat实例，处理可能的Unicode编码错误
                        try:
                            self._instance = WeChat()
                            logger.info("成功创建wxauto.WeChat实例")
                        except UnicodeEncodeError as e:
                            if 'gbk' in str(e).lower():
                                logger.warning(f"捕获到GBK编码错误: {str(e)}")
                                logger.info("尝试修复Unicode编码问题...")

                                # 修补print函数，处理Unicode编码问题
                                original_print = print
                                def safe_print(*args, **kwargs):
                                    try:
                                        original_print(*args, **kwargs)
                                    except UnicodeEncodeError:
                                        # 如果是GBK编码错误，使用UTF-8编码输出
                                        try:
                                            import sys
                                            if hasattr(sys.stdout, 'buffer'):
                                                message = " ".join(str(arg) for arg in args)
                                                sys.stdout.buffer.write(message.encode('utf-8'))
                                                sys.stdout.buffer.write(b'\n')
                                                sys.stdout.buffer.flush()
                                        except Exception:
                                            pass

                                # 替换print函数
                                import builtins
                                builtins.print = safe_print

                                # 再次尝试创建WeChat实例
                                self._instance = WeChat()
                                logger.info("成功创建wxauto.WeChat实例（已修复Unicode编码问题）")
                            else:
                                # 如果不是GBK编码错误，重新抛出
                                raise

                    # 尝试获取窗口名称并保存
                    try:
                        # 在初始化时，WeChat类会自动打印窗口名称，我们需要手动获取
                        if hasattr(self._instance, "window_name"):
                            window_name = self._instance.window_name
                        elif hasattr(self._instance, "GetWindowName"):
                            window_name = self._instance.GetWindowName()
                        else:
                            window_name = ""

                        if window_name:
                            # 保存到缓存
                            self._cached_window_name = window_name
                            logger.info(f"微信实例初始化成功，获取到已登录窗口：{window_name}，使用库: {self._lib_name}")
                        else:
                            logger.info(f"微信实例初始化成功，但无法获取窗口名称，使用库: {self._lib_name}")

                        # 初始化完成后，自动打开"文件传输助手"窗口
                        try:
                            logger.info("正在打开文件传输助手窗口...")
                            self._instance.ChatWith("文件传输助手")
                            import time
                            time.sleep(1)  # 等待窗口打开
                            logger.info("文件传输助手窗口已打开")
                        except Exception as chat_e:
                            logger.error(f"打开文件传输助手窗口失败: {str(chat_e)}")
                    except Exception as e:
                        logger.warning(f"获取窗口名称失败: {str(e)}")
                        logger.info(f"微信实例初始化成功，使用库: {self._lib_name}")

                        # 即使获取窗口名称失败，也尝试打开文件传输助手窗口
                        try:
                            logger.info("正在打开文件传输助手窗口...")
                            self._instance.ChatWith("文件传输助手")
                            import time
                            time.sleep(1)  # 等待窗口打开
                            logger.info("文件传输助手窗口已打开")
                        except Exception as chat_e:
                            logger.error(f"打开文件传输助手窗口失败: {str(chat_e)}")

                    return True
                except Exception as e:
                    logger.error(f"微信初始化失败: {str(e)}")
                    # 出错时确保COM环境被清理
                    pythoncom.CoUninitialize()
                    return False
            return True

    def get_instance(self):
        """获取微信实例"""
        return self._instance

    def get_lib_name(self) -> str:
        """获取当前使用的库名称"""
        return self._lib_name

    def get_window_name(self) -> str:
        """获取微信窗口名称，优先使用缓存"""
        if not self._instance:
            return ""

        try:
            # 尝试获取最新的窗口名称
            window_name = ""
            if hasattr(self._instance, "window_name"):
                window_name = self._instance.window_name
            elif hasattr(self._instance, "GetWindowName"):
                window_name = self._instance.GetWindowName()

            # 如果获取到了新的窗口名称，更新缓存
            if window_name:
                self._cached_window_name = window_name
                return window_name

            # 如果没有获取到新的窗口名称，但缓存中有值，使用缓存
            if self._cached_window_name:
                logger.debug(f"使用缓存的窗口名称: {self._cached_window_name}")
                return self._cached_window_name

            # 如果缓存也没有，尝试从nickname属性获取
            if hasattr(self._instance, "nickname"):
                nickname = self._instance.nickname
                if nickname:
                    self._cached_window_name = nickname
                    logger.debug(f"从nickname属性获取窗口名称: {nickname}")
                    return nickname

            # 都没有获取到，返回空字符串
            return ""
        except Exception as e:
            logger.warning(f"获取窗口名称失败: {str(e)}")
            # 如果获取失败但缓存中有值，返回缓存
            if self._cached_window_name:
                logger.debug(f"获取失败，使用缓存的窗口名称: {self._cached_window_name}")
                return self._cached_window_name
            return ""

    def check_connection(self) -> bool:
        """检查微信连接状态"""
        if not self._instance:
            return False

        try:
            # 两个库都支持GetSessionList方法
            self._instance.GetSessionList()
            return True
        except Exception as e:
            logger.error(f"微信连接检查失败: {str(e)}")
            return False

    def __getattr__(self, name):
        """代理到实际的微信实例"""
        if self._instance is None:
            raise AttributeError(f"微信实例未初始化，无法调用 {name} 方法")

        # 检查是否需要特殊处理的方法
        handler = getattr(self, f"_handle_{name}", None)
        if handler:
            return handler

        # 直接代理到实际实例
        return getattr(self._instance, name)

    def _handle_ChatWith(self, *args, **kwargs):
        """处理ChatWith方法的差异"""
        if not self._instance:
            raise AttributeError("微信实例未初始化")

        # wxautox的ChatWith方法支持exact参数，而wxauto不支持
        if self._lib_name == "wxauto":
            # 从kwargs中移除exact参数，如果存在的话
            if 'exact' in kwargs:
                kwargs.pop("exact")

            # 调用原始方法
            result = self._instance.ChatWith(*args, **kwargs)
            return result
        else:
            # 直接调用原始方法
            return self._instance.ChatWith(*args, **kwargs)

    def _handle_SendMsg(self, *args, **kwargs):
        """处理SendMsg方法的差异"""
        if not self._instance:
            raise AttributeError("微信实例未初始化")

        # wxauto和wxautox的SendMsg方法参数略有不同
        if self._lib_name == "wxauto":
            # wxauto的clear参数是布尔值，而wxautox是字符串
            if "clear" in kwargs and isinstance(kwargs["clear"], bool):
                kwargs["clear"] = "1" if kwargs["clear"] else "0"

        # 调用原始方法
        return self._instance.SendMsg(*args, **kwargs)

    def _handle_GetNextNewMessage(self, *args, **kwargs):
        """处理GetNextNewMessage方法的差异"""
        if not self._instance:
            raise AttributeError("微信实例未初始化")

        # 确保使用正确的保存路径
        try:
            # 导入配置管理器
            import config_manager

            # 尝试导入wxauto.elements模块
            try:
                # 首先尝试直接导入
                from wxauto.elements import WxParam
                logger.debug("成功直接导入wxauto.elements.WxParam")
            except ImportError as e:
                logger.warning(f"直接导入wxauto.elements.WxParam失败: {str(e)}")

                # 尝试使用与_try_import_wxauto相同的逻辑查找wxauto路径
                import sys
                import os

                # 获取应用根目录
                if getattr(sys, 'frozen', False):
                    # 如果是打包后的环境
                    app_root = os.path.dirname(sys.executable)
                    meipass = getattr(sys, '_MEIPASS', None)
                else:
                    # 如果是开发环境
                    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

                # 尝试多种可能的wxauto路径
                possible_paths = [
                    os.path.join(app_root, "wxauto"),
                    os.path.join(app_root, "app", "wxauto"),
                ]

                # 如果是打包环境，添加更多可能的路径
                if getattr(sys, 'frozen', False) and meipass:
                    possible_paths.extend([
                        os.path.join(meipass, "wxauto"),
                        os.path.join(meipass, "app", "wxauto"),
                    ])

                # 尝试从每个路径导入
                WxParam = None
                for wxauto_path in possible_paths:
                    if os.path.exists(wxauto_path) and os.path.isdir(wxauto_path):
                        # 检查wxauto路径下是否有wxauto子目录
                        wxauto_inner_path = os.path.join(wxauto_path, "wxauto")
                        elements_path = os.path.join(wxauto_inner_path, "elements.py")

                        if os.path.exists(elements_path):
                            logger.debug(f"找到elements.py文件: {elements_path}")

                            # 将wxauto/wxauto目录添加到路径
                            if wxauto_inner_path not in sys.path:
                                sys.path.insert(0, wxauto_inner_path)

                            # 将wxauto目录添加到路径
                            if wxauto_path not in sys.path:
                                sys.path.insert(0, wxauto_path)

                            try:
                                # 尝试导入
                                from wxauto.elements import WxParam
                                logger.debug(f"成功从路径导入wxauto.elements.WxParam: {wxauto_path}")
                                break
                            except ImportError as inner_e:
                                logger.warning(f"从路径 {wxauto_path} 导入wxauto.elements.WxParam失败: {str(inner_e)}")

                # 如果仍然无法导入，抛出异常
                if WxParam is None:
                    raise ImportError("无法导入wxauto.elements.WxParam")

            # 确保目录存在
            config_manager.ensure_dirs()

            # 获取临时目录路径
            temp_dir = str(config_manager.TEMP_DIR.absolute())

            # 记录原始保存路径
            original_path = WxParam.DEFALUT_SAVEPATH
            logger.debug(f"原始wxauto保存路径: {original_path}")

            # 修改为新的保存路径
            WxParam.DEFALUT_SAVEPATH = temp_dir
            logger.debug(f"已修改wxauto保存路径为: {temp_dir}")
        except Exception as path_e:
            logger.error(f"设置wxauto保存路径失败: {str(path_e)}")

        # wxauto不支持savevideo和parseurl参数
        if self._lib_name == "wxauto":
            # 从kwargs中移除不支持的参数
            if "savevideo" in kwargs:
                logger.debug("移除wxauto不支持的参数: savevideo")
                kwargs.pop("savevideo", None)
            if "parseurl" in kwargs:
                logger.debug("移除wxauto不支持的参数: parseurl")
                kwargs.pop("parseurl", None)

        try:
            # 在调用GetNextNewMessage前，先检查是否有打开的聊天窗口
            # 如果没有，先打开一个聊天窗口
            try:
                # 尝试获取当前聊天窗口名称
                current_chat = self._instance.CurrentChat()
                if not current_chat:
                    # 如果没有打开的聊天窗口，先打开一个
                    logger.debug("没有打开的聊天窗口，尝试打开一个")
                    session_dict = self._instance.GetSessionList(reset=True)
                    if session_dict:
                        first_session = list(session_dict.keys())[0]
                        logger.debug(f"打开会话聊天窗口: {first_session}")
                        self._instance.ChatWith(first_session)
                        # 等待窗口打开
                        import time
                        time.sleep(0.5)
                else:
                    logger.debug(f"当前已打开聊天窗口: {current_chat}")
            except Exception as e:
                logger.warning(f"检查聊天窗口状态失败: {str(e)}")
                # 继续执行，让原始的错误处理逻辑处理

            # 调用原始方法
            logger.debug(f"调用GetNextNewMessage方法，参数: {kwargs}")
            return self._instance.GetNextNewMessage(*args, **kwargs)
        except Exception as e:
            error_str = str(e)
            logger.error(f"调用GetNextNewMessage方法失败: {error_str}")

            # 如果是"Find Control Timeout"错误，可能是因为没有打开的聊天窗口
            if "Find Control Timeout" in error_str and "消息" in error_str:
                logger.warning("找不到'消息'控件，可能没有打开的聊天窗口")
                # 我们已经在调用前尝试打开聊天窗口，如果仍然失败，直接返回空结果
                logger.info("返回空列表表示没有新消息")
                return []

            # 如果是参数错误，尝试使用最基本的参数重试
            if "参数" in error_str or "parameter" in error_str.lower() or "argument" in error_str.lower():
                logger.warning("可能是参数错误，尝试使用基本参数重试")
                # 只保留基本参数
                basic_kwargs = {}
                if "savepic" in kwargs:
                    basic_kwargs["savepic"] = kwargs["savepic"]
                if "savefile" in kwargs:
                    basic_kwargs["savefile"] = kwargs["savefile"]
                if "savevoice" in kwargs:
                    basic_kwargs["savevoice"] = kwargs["savevoice"]

                logger.debug(f"使用基本参数重试: {basic_kwargs}")
                try:
                    return self._instance.GetNextNewMessage(*args, **basic_kwargs)
                except Exception as retry_e:
                    logger.error(f"使用基本参数重试失败: {str(retry_e)}")
                    # 如果重试失败，返回空列表表示没有新消息
                    return []

            # 对于其他错误，返回空列表表示没有新消息
            logger.warning(f"无法处理的错误，返回空列表: {error_str}")
            return []

    def _handle_AddListenChat(self, *args, **kwargs):
        """处理AddListenChat方法的差异"""
        if not self._instance:
            raise AttributeError("微信实例未初始化")

        # 根据不同的库处理参数
        if self._lib_name == "wxauto":
            # wxauto不支持savevideo和parseurl参数
            if "savevideo" in kwargs:
                logger.debug("移除wxauto不支持的参数: savevideo")
                kwargs.pop("savevideo", None)
            if "parseurl" in kwargs:
                logger.debug("移除wxauto不支持的参数: parseurl")
                kwargs.pop("parseurl", None)
        elif self._lib_name == "wxautox":
            # 根据文档，wxautox的AddListenChat支持以下参数：
            # who, savepic, savevideo, savefile, savevoice, parseurl, exact
            # 不需要移除任何参数
            pass

        try:
            # 调用原始方法
            logger.debug(f"调用AddListenChat方法，参数: {kwargs}")
            return self._instance.AddListenChat(*args, **kwargs)
        except Exception as e:
            logger.error(f"调用AddListenChat方法失败: {str(e)}")
            # 如果是参数错误，尝试使用最基本的参数重试
            if "参数" in str(e) or "parameter" in str(e).lower() or "argument" in str(e).lower() or "unexpected keyword" in str(e).lower():
                logger.warning("可能是参数错误，尝试使用基本参数重试")
                # 只保留基本参数
                basic_kwargs = {}
                if "who" in kwargs:
                    basic_kwargs["who"] = kwargs["who"]

                # 根据不同的库添加不同的基本参数
                if self._lib_name == "wxauto":
                    # wxauto支持的基本参数
                    if "savepic" in kwargs:
                        basic_kwargs["savepic"] = kwargs["savepic"]
                    if "savefile" in kwargs:
                        basic_kwargs["savefile"] = kwargs["savefile"]
                    if "savevoice" in kwargs:
                        basic_kwargs["savevoice"] = kwargs["savevoice"]
                elif self._lib_name == "wxautox":
                    # wxautox支持的基本参数
                    if "savepic" in kwargs:
                        basic_kwargs["savepic"] = kwargs["savepic"]
                    if "savevideo" in kwargs:
                        basic_kwargs["savevideo"] = kwargs["savevideo"]
                    if "savefile" in kwargs:
                        basic_kwargs["savefile"] = kwargs["savefile"]
                    if "savevoice" in kwargs:
                        basic_kwargs["savevoice"] = kwargs["savevoice"]
                    if "parseurl" in kwargs:
                        basic_kwargs["parseurl"] = kwargs["parseurl"]
                    if "exact" in kwargs:
                        basic_kwargs["exact"] = kwargs["exact"]

                logger.debug(f"使用基本参数重试: {basic_kwargs}")
                return self._instance.AddListenChat(*args, **basic_kwargs)
            # 重新抛出原始异常
            raise

    def _handle_GetListenMessage(self, *args, **kwargs):
        """处理GetListenMessage方法的差异，并添加异常处理"""
        if not self._instance:
            raise AttributeError("微信实例未初始化")

        # 确保使用正确的保存路径
        try:
            # 导入配置管理器
            import config_manager

            # 尝试导入wxauto.elements模块
            try:
                # 首先尝试直接导入
                from wxauto.elements import WxParam
                logger.debug("成功直接导入wxauto.elements.WxParam")
            except ImportError as e:
                logger.warning(f"直接导入wxauto.elements.WxParam失败: {str(e)}")

                # 尝试使用与_try_import_wxauto相同的逻辑查找wxauto路径
                import sys
                import os

                # 获取应用根目录
                if getattr(sys, 'frozen', False):
                    # 如果是打包后的环境
                    app_root = os.path.dirname(sys.executable)
                    meipass = getattr(sys, '_MEIPASS', None)
                else:
                    # 如果是开发环境
                    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

                # 尝试多种可能的wxauto路径
                possible_paths = [
                    os.path.join(app_root, "wxauto"),
                    os.path.join(app_root, "app", "wxauto"),
                ]

                # 如果是打包环境，添加更多可能的路径
                if getattr(sys, 'frozen', False) and meipass:
                    possible_paths.extend([
                        os.path.join(meipass, "wxauto"),
                        os.path.join(meipass, "app", "wxauto"),
                    ])

                # 尝试从每个路径导入
                WxParam = None
                for wxauto_path in possible_paths:
                    if os.path.exists(wxauto_path) and os.path.isdir(wxauto_path):
                        # 检查wxauto路径下是否有wxauto子目录
                        wxauto_inner_path = os.path.join(wxauto_path, "wxauto")
                        elements_path = os.path.join(wxauto_inner_path, "elements.py")

                        if os.path.exists(elements_path):
                            logger.debug(f"找到elements.py文件: {elements_path}")

                            # 将wxauto/wxauto目录添加到路径
                            if wxauto_inner_path not in sys.path:
                                sys.path.insert(0, wxauto_inner_path)

                            # 将wxauto目录添加到路径
                            if wxauto_path not in sys.path:
                                sys.path.insert(0, wxauto_path)

                            try:
                                # 尝试导入
                                from wxauto.elements import WxParam
                                logger.debug(f"成功从路径导入wxauto.elements.WxParam: {wxauto_path}")
                                break
                            except ImportError as inner_e:
                                logger.warning(f"从路径 {wxauto_path} 导入wxauto.elements.WxParam失败: {str(inner_e)}")

                # 如果仍然无法导入，抛出异常
                if WxParam is None:
                    raise ImportError("无法导入wxauto.elements.WxParam")

            # 确保目录存在
            config_manager.ensure_dirs()

            # 获取临时目录路径
            temp_dir = str(config_manager.TEMP_DIR.absolute())

            # 记录原始保存路径
            original_path = WxParam.DEFALUT_SAVEPATH
            logger.debug(f"原始wxauto保存路径: {original_path}")

            # 修改为新的保存路径
            WxParam.DEFALUT_SAVEPATH = temp_dir
            logger.debug(f"已修改wxauto保存路径为: {temp_dir}")
        except Exception as path_e:
            logger.error(f"设置wxauto保存路径失败: {str(path_e)}")

        # 根据不同的库使用不同的处理方法
        if self._lib_name == "wxautox":
            # 对于wxautox库，只传递who参数，不传递其他参数
            try:
                # 根据文档，wxautox的GetListenMessage只接受who参数
                who = args[0] if args else kwargs.get('who')

                # 记录调用信息，帮助调试
                logger.debug(f"调用wxautox GetListenMessage，参数: who={who}")

                # 只传递who参数
                if who:
                    result = self._instance.GetListenMessage(who)
                else:
                    result = self._instance.GetListenMessage()

                # 记录返回类型，帮助调试
                logger.debug(f"wxautox GetListenMessage返回类型: {type(result)}")
                return result
            except Exception as e:
                # 捕获所有异常，避免崩溃
                import traceback
                logger.error(f"wxautox获取监听消息失败: {str(e)}")
                traceback.print_exc()
                # 返回空字典，表示没有新消息
                return {}
        else:
            # 对于wxauto库，使用更健壮的处理方法
            try:
                # wxauto的GetListenMessage只接受who参数，移除其他参数
                who = args[0] if args else kwargs.get('who')

                # 不再手动激活窗口，直接使用wxauto库的内置功能
                # wxauto的GetListenMessage方法内部会调用chat._show()来激活窗口
                logger.debug(f"使用wxauto库内置功能激活聊天窗口: {who if who else '所有窗口'}")

                # 不主动检测窗口句柄是否有效，直接尝试获取消息

                # 调用原始方法，只传递who参数
                if who:
                    result = self._instance.GetListenMessage(who)
                else:
                    result = self._instance.GetListenMessage()

                # 记录返回类型，帮助调试
                logger.debug(f"wxauto GetListenMessage返回类型: {type(result)}")

                # 检查是否指定了who参数
                who = args[0] if args else kwargs.get('who')

                # 如果指定了who参数且返回的是列表，这是正常的
                if who and isinstance(result, list):
                    logger.debug(f"wxauto GetListenMessage为{who}返回了列表，长度: {len(result)}")
                    return result
                # 如果没有指定who参数且返回的是字典，这是正常的
                elif not who and isinstance(result, dict):
                    logger.debug(f"wxauto GetListenMessage返回了字典，键数量: {len(result)}")
                    return result
                # 如果返回的是空值，这是正常的
                elif not result:
                    logger.debug("wxauto GetListenMessage返回了空值")
                    return {}
                # 其他情况可能是异常的
                else:
                    logger.warning(f"wxauto GetListenMessage返回了意外的类型: {type(result)}")
                    # 尝试转换为适当的格式
                    if isinstance(result, list) and not who:
                        # 如果没有指定who参数但返回了列表，尝试转换为字典
                        logger.warning("尝试将列表转换为字典")
                        return {}
                    elif isinstance(result, dict) and who:
                        # 如果指定了who参数但返回了字典，尝试提取相关消息
                        logger.warning("尝试从字典中提取指定聊天对象的消息")
                        for chat_wnd, msg_list in result.items():
                            if hasattr(chat_wnd, 'who') and chat_wnd.who == who:
                                return msg_list
                        return []
                    else:
                        # 无法处理的情况，返回空值
                        logger.error(f"无法处理的返回类型: {type(result)}")
                        return {} if not who else []

            except Exception as e:
                # 捕获所有异常，避免崩溃
                import traceback
                error_str = str(e)
                logger.error(f"wxauto获取监听消息失败: {error_str}")
                traceback.print_exc()

                # 检查是否是窗口激活失败的错误
                if "激活聊天窗口失败" in error_str or "SetWindowPos" in error_str or "无效的窗口句柄" in error_str or "Find Control Timeout" in error_str:
                    # 获取who参数
                    who = args[0] if args else kwargs.get('who')

                    if who:
                        logger.warning(f"检测到窗口激活失败，尝试重新添加监听对象: {who}")
                        try:
                            # 先尝试移除可能存在的无效监听对象
                            try:
                                self.RemoveListenChat(who)
                                logger.info(f"已移除无效的监听对象: {who}")
                            except Exception as remove_e:
                                logger.warning(f"移除无效监听对象失败: {str(remove_e)}")

                            # 尝试先打开聊天窗口
                            try:
                                self.ChatWith(who)
                                logger.info(f"已打开聊天窗口: {who}")
                                # 等待窗口打开
                                import time
                                time.sleep(0.5)
                            except Exception as chat_e:
                                logger.warning(f"打开聊天窗口失败: {str(chat_e)}")

                            # 重新添加监听对象
                            # 构建基本参数
                            add_params = {'who': who}
                            if 'savepic' in kwargs:
                                add_params['savepic'] = kwargs['savepic']
                            if 'savefile' in kwargs:
                                add_params['savefile'] = kwargs['savefile']
                            if 'savevoice' in kwargs:
                                add_params['savevoice'] = kwargs['savevoice']

                            self.AddListenChat(**add_params)
                            logger.info(f"已重新添加监听对象: {who}")

                            # 再次尝试获取消息
                            if who:
                                result = self._instance.GetListenMessage(who)
                            else:
                                result = self._instance.GetListenMessage()
                            return result
                        except Exception as retry_e:
                            logger.error(f"重新添加监听对象后获取消息仍然失败: {str(retry_e)}")
                    else:
                        # 如果没有指定who参数，尝试处理所有监听对象
                        logger.warning("未指定who参数，尝试处理所有监听对象")
                        try:
                            # 获取当前所有监听对象
                            listen_list = {}
                            try:
                                listen_list = self._instance.listen.copy()  # 复制一份以避免迭代过程中修改
                            except Exception as list_e:
                                logger.error(f"获取监听列表失败: {str(list_e)}")
                                return {}

                            # 如果监听列表为空，直接返回
                            if not listen_list:
                                logger.warning("监听列表为空")
                                return {}

                            # 遍历所有监听对象，尝试重新添加
                            for chat_who, chat_obj in listen_list.items():
                                try:
                                    # 先移除
                                    try:
                                        self.RemoveListenChat(chat_who)
                                        logger.info(f"已移除可能无效的监听对象: {chat_who}")
                                    except Exception as remove_e:
                                        logger.warning(f"移除监听对象失败: {str(remove_e)}")

                                    # 尝试先打开聊天窗口
                                    try:
                                        self.ChatWith(chat_who)
                                        logger.info(f"已打开聊天窗口: {chat_who}")
                                        # 等待窗口打开
                                        import time
                                        time.sleep(0.5)
                                    except Exception as chat_e:
                                        logger.warning(f"打开聊天窗口失败: {str(chat_e)}")

                                    # 重新添加
                                    chat_params = {
                                        'who': chat_who,
                                        'savepic': getattr(chat_obj, 'savepic', False),
                                        'savefile': getattr(chat_obj, 'savefile', False),
                                        'savevoice': getattr(chat_obj, 'savevoice', False)
                                    }
                                    self.AddListenChat(**chat_params)
                                    logger.info(f"已重新添加监听对象: {chat_who}")
                                except Exception as chat_e:
                                    logger.error(f"重新添加监听对象 {chat_who} 失败: {str(chat_e)}")
                                    continue

                            # 重新尝试获取所有监听对象的消息
                            try:
                                result = self._instance.GetListenMessage()
                                return result
                            except Exception as retry_e:
                                logger.error(f"重新添加所有监听对象后获取消息仍然失败: {str(retry_e)}")
                        except Exception as all_e:
                            logger.error(f"处理所有监听对象失败: {str(all_e)}")
                elif "激活聊天窗口失败" in traceback.format_exc() or "SetWindowPos" in traceback.format_exc() or "无效的窗口句柄" in traceback.format_exc():
                    # 获取who参数
                    who = args[0] if args else kwargs.get('who')

                    if who:
                        logger.warning(f"从堆栈跟踪中检测到窗口激活失败，尝试重新添加监听对象: {who}")
                        try:
                            # 先尝试移除可能存在的无效监听对象
                            try:
                                self.RemoveListenChat(who)
                                logger.info(f"已移除无效的监听对象: {who}")
                            except Exception as remove_e:
                                logger.warning(f"移除无效监听对象失败: {str(remove_e)}")

                            # 尝试先打开聊天窗口
                            try:
                                self.ChatWith(who)
                                logger.info(f"已打开聊天窗口: {who}")
                                # 等待窗口打开
                                import time
                                time.sleep(0.5)
                            except Exception as chat_e:
                                logger.warning(f"打开聊天窗口失败: {str(chat_e)}")

                            # 重新添加监听对象
                            # 构建基本参数
                            add_params = {'who': who}
                            if 'savepic' in kwargs:
                                add_params['savepic'] = kwargs['savepic']
                            if 'savefile' in kwargs:
                                add_params['savefile'] = kwargs['savefile']
                            if 'savevoice' in kwargs:
                                add_params['savevoice'] = kwargs['savevoice']

                            self.AddListenChat(**add_params)
                            logger.info(f"已重新添加监听对象: {who}")

                            # 再次尝试获取消息
                            if who:
                                result = self._instance.GetListenMessage(who)
                            else:
                                result = self._instance.GetListenMessage()
                            return result
                        except Exception as retry_e:
                            logger.error(f"重新添加监听对象后获取消息仍然失败: {str(retry_e)}")

                # 根据是否指定了who参数返回不同的空值
                who = args[0] if args else kwargs.get('who')
                return [] if who else {}

            except Exception as e:
                # 捕获所有异常，避免崩溃
                import traceback
                error_str = str(e)
                logger.error(f"wxauto获取监听消息失败: {error_str}")
                traceback.print_exc()

                # 检查是否是窗口激活失败的错误
                if "激活聊天窗口失败" in error_str or "SetWindowPos" in error_str or "无效的窗口句柄" in error_str:
                    # 获取who参数
                    who = args[0] if args else kwargs.get('who')

                    if who:
                        logger.warning(f"检测到窗口激活失败，尝试重新添加监听对象: {who}")
                        try:
                            # 先尝试移除可能存在的无效监听对象
                            try:
                                self.RemoveListenChat(who)
                                logger.info(f"已移除无效的监听对象: {who}")
                            except Exception as remove_e:
                                logger.warning(f"移除无效监听对象失败: {str(remove_e)}")

                            # 尝试先打开聊天窗口
                            try:
                                self.ChatWith(who)
                                logger.info(f"已打开聊天窗口: {who}")
                                # 等待窗口打开
                                import time
                                time.sleep(0.5)
                            except Exception as chat_e:
                                logger.warning(f"打开聊天窗口失败: {str(chat_e)}")

                            # 重新添加监听对象
                            # 构建基本参数
                            add_params = {'who': who}
                            if 'savepic' in kwargs:
                                add_params['savepic'] = kwargs['savepic']
                            if 'savefile' in kwargs:
                                add_params['savefile'] = kwargs['savefile']
                            if 'savevoice' in kwargs:
                                add_params['savevoice'] = kwargs['savevoice']

                            self.AddListenChat(**add_params)
                            logger.info(f"已重新添加监听对象: {who}")

                            # 再次尝试获取消息
                            if who:
                                result = self._instance.GetListenMessage(who)
                            else:
                                result = self._instance.GetListenMessage()
                            return result
                        except Exception as retry_e:
                            logger.error(f"重新添加监听对象后获取消息仍然失败: {str(retry_e)}")

                # 根据是否指定了who参数返回不同的空值
                who = args[0] if args else kwargs.get('who')
                return [] if who else {}

    def _handle_RemoveListenChat(self, *args, **kwargs):
        """处理RemoveListenChat方法的差异，并添加异常处理"""
        if not self._instance:
            raise AttributeError("微信实例未初始化")

        # 根据不同的库使用不同的处理方法
        if self._lib_name == "wxautox":
            # 对于wxautox库，直接调用原始方法
            try:
                return self._instance.RemoveListenChat(*args, **kwargs)
            except Exception as e:
                # 捕获所有异常，避免崩溃
                import traceback
                logger.error(f"wxautox移除监听失败: {str(e)}")
                traceback.print_exc()
                # 返回False表示失败
                return False
        else:
            # 对于wxauto库，使用更健壮的处理方法
            try:
                # 获取要移除的聊天对象名称
                who = args[0] if args else kwargs.get('who')
                if not who:
                    logger.error("移除监听失败: 未指定聊天对象名称")
                    return False

                # 检查聊天对象是否在监听列表中
                if who in self._instance.listen:
                    # 获取聊天窗口对象
                    chat_wnd = self._instance.listen[who]

                    try:
                        # 尝试关闭聊天窗口
                        import win32gui
                        import win32con

                        # 使用win32gui.FindWindow直接查找窗口
                        chat_hwnd = win32gui.FindWindow('ChatWnd', who)
                        if chat_hwnd:
                            logger.debug(f"关闭聊天窗口: {who}")
                            win32gui.PostMessage(chat_hwnd, win32con.WM_CLOSE, 0, 0)
                    except Exception as e:
                        logger.error(f"关闭聊天窗口失败: {str(e)}")

                    # 从监听列表中删除
                    del self._instance.listen[who]
                    logger.debug(f"成功移除监听: {who}")
                    return True
                else:
                    logger.warning(f"未找到监听对象: {who}")
                    return False
            except Exception as e:
                # 捕获所有异常，避免崩溃
                import traceback
                logger.error(f"wxauto移除监听失败: {str(e)}")
                traceback.print_exc()
                # 返回False表示失败
                return False

    # 添加对聊天窗口方法的特殊处理
    def _handle_chat_window_method(self, chat_wnd, method_name, *args, **kwargs):
        """处理聊天窗口方法的调用，添加异常处理"""
        if not chat_wnd:
            raise AttributeError(f"聊天窗口对象为空，无法调用 {method_name} 方法")

        # 获取方法
        method = getattr(chat_wnd, method_name, None)
        if not method:
            raise AttributeError(f"聊天窗口对象没有 {method_name} 方法")

        try:
            # 调用方法
            return method(*args, **kwargs)
        except Exception as e:
            # 捕获所有异常，避免崩溃
            import traceback
            logger.error(f"调用聊天窗口方法 {method_name} 失败: {str(e)}")
            traceback.print_exc()
            # 重新抛出异常，让上层处理
            raise

    def _handle_GetAllMessage(self, *args, **kwargs):
        """处理GetAllMessage方法的差异"""
        if not self._instance:
            raise AttributeError("微信实例未初始化")

        # wxauto不支持parseurl参数
        if self._lib_name == "wxauto":
            # 从kwargs中移除不支持的参数
            if "parseurl" in kwargs:
                logger.debug("移除wxauto不支持的参数: parseurl")
                kwargs.pop("parseurl", None)

        try:
            # 调用原始方法
            logger.debug(f"调用GetAllMessage方法，参数: {kwargs}")
            return self._instance.GetAllMessage(*args, **kwargs)
        except Exception as e:
            error_str = str(e)
            logger.error(f"调用GetAllMessage方法失败: {error_str}")
            
            # 如果是递归错误，返回空列表
            if "maximum recursion depth exceeded" in error_str:
                logger.warning("检测到递归错误，返回空列表")
                return []
            
            # 重新抛出其他异常
            raise

# 导入配置
try:
    from app.config import Config
    # 记录配置信息
    logger.info(f"从app.config导入配置成功，WECHAT_LIB={Config.WECHAT_LIB}")

    # 创建全局适配器实例
    wechat_adapter = WeChatAdapter(lib_name=Config.WECHAT_LIB)
    logger.info(f"成功创建全局适配器实例，使用库: {wechat_adapter.get_lib_name()}")
except ImportError as e:
    # 如果无法导入配置，则使用默认值
    logger.error(f"导入app.config失败: {str(e)}，将使用默认值'wxauto'")

    # 尝试从环境变量或.env文件读取配置
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        wechat_lib = os.getenv('WECHAT_LIB', 'wxauto').lower()
        logger.info(f"从环境变量读取WECHAT_LIB={wechat_lib}")
        wechat_adapter = WeChatAdapter(lib_name=wechat_lib)
    except Exception as env_e:
        logger.error(f"从环境变量读取配置失败: {str(env_e)}，将使用默认值'wxauto'")
        wechat_adapter = WeChatAdapter(lib_name='wxauto')

    logger.info(f"成功创建全局适配器实例，使用库: {wechat_adapter.get_lib_name()}")
