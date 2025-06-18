"""
最小化API路由
不依赖flask-limiter，提供基本的API功能
"""

from flask import Blueprint, jsonify, request, g, Response, send_file
import os
import time
import logging
from typing import Optional, List
from urllib.parse import quote
import functools
import json

# 配置日志
logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# 记录程序启动时间
start_time = time.time()

@api_bp.before_request
def before_request():
    g.start_time = time.time()
    # 记录请求信息
    logger.info(f"收到请求: {request.method} {request.path}")

@api_bp.after_request
def after_request(response):
    if hasattr(g, 'start_time'):
        duration = time.time() - g.start_time
        logger.info(f"请求处理完成: {request.method} {request.path} - 状态码: {response.status_code} - 耗时: {duration:.2f}秒")
    return response

@api_bp.errorhandler(Exception)
def handle_error(error):
    # 记录未捕获的异常
    logger.error(f"未捕获的异常: {str(error)}", exc_info=True)
    return jsonify({
        'code': 5000,
        'message': '服务器内部错误',
        'data': None
    }), 500

# 简单的API密钥验证装饰器
def require_api_key(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({
                'code': 1001,
                'message': '缺少API密钥',
                'data': None
            }), 401
        
        # 简单的API密钥验证
        valid_keys = ['test-key-2']  # 默认密钥
        try:
            from app.config import Config
            valid_keys = Config.API_KEYS
        except:
            pass
        
        if api_key not in valid_keys:
            return jsonify({
                'code': 1001,
                'message': 'API密钥无效',
                'data': None
            }), 401
            
        return f(*args, **kwargs)
    return decorated_function

def format_at_message(message: str, at_list: Optional[List[str]] = None) -> str:
    if not at_list:
        return message

    result = message
    if result and not result.endswith('\n'):
        result += '\n'

    for user in at_list:
        result += f"{{@{user}}}"
        if user != at_list[-1]:
            result += '\n'
    return result

# 健康检查接口
@api_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'message': 'API服务运行正常',
        'uptime': int(time.time() - start_time)
    })

# 认证相关接口
@api_bp.route('/auth/verify', methods=['POST'])
@require_api_key
def verify_api_key():
    return jsonify({
        'code': 0,
        'message': '验证成功',
        'data': {'valid': True}
    })

# 微信初始化接口
@api_bp.route('/wechat/initialize', methods=['POST'])
@require_api_key
def initialize_wechat():
    try:
        # 尝试导入微信管理器
        try:
            from app.wechat import wechat_manager
            success = wechat_manager.initialize()
            if success:
                # 获取微信窗口名称
                wx_instance = wechat_manager.get_instance()
                window_name = ""
                try:
                    window_name = wx_instance.get_window_name()
                    if window_name:
                        logger.info(f"初始化成功，获取到已登录窗口：{window_name}")

                    # 尝试打开文件传输助手
                    try:
                        current_chat = wx_instance._instance.CurrentChat()
                        if current_chat != "文件传输助手":
                            logger.info("当前聊天窗口不是文件传输助手，尝试打开文件传输助手窗口...")
                            wx_instance._instance.ChatWith("文件传输助手")
                            import time
                            time.sleep(0.5)
                            logger.info("文件传输助手窗口已打开")
                    except Exception as chat_e:
                        logger.warning(f"检查或打开文件传输助手窗口失败: {str(chat_e)}")
                except Exception as e:
                    logger.warning(f"获取窗口名称失败: {str(e)}")

                return jsonify({
                    'code': 0,
                    'message': '初始化成功',
                    'data': {
                        'status': 'connected',
                        'window_name': window_name
                    }
                })
            else:
                return jsonify({
                    'code': 2001,
                    'message': '初始化失败',
                    'data': None
                }), 500
        except ImportError as e:
            logger.error(f"导入微信管理器失败: {str(e)}")
            return jsonify({
                'code': 2001,
                'message': '微信管理器不可用（最小化模式）',
                'data': None
            }), 500
    except Exception as e:
        logger.error(f"初始化异常: {str(e)}")
        return jsonify({
            'code': 2001,
            'message': f'初始化失败: {str(e)}',
            'data': None
        }), 500

# 微信状态查询接口
@api_bp.route('/wechat/status', methods=['GET'])
@require_api_key
def get_wechat_status():
    try:
        # 尝试导入微信管理器
        try:
            from app.wechat import wechat_manager
            wx_instance = wechat_manager.get_instance()
            if not wx_instance:
                return jsonify({
                    'code': 2001,
                    'message': '微信未初始化',
                    'data': None
                }), 400

            is_connected = wechat_manager.check_connection()

            # 获取微信窗口名称
            window_name = ""
            if is_connected:
                try:
                    window_name = wx_instance.get_window_name()
                    if window_name:
                        logger.debug(f"状态检查：获取到已登录窗口：{window_name}")
                except Exception as e:
                    logger.warning(f"获取窗口名称失败: {str(e)}")

            return jsonify({
                'code': 0,
                'message': '获取成功',
                'data': {
                    'status': 'online' if is_connected else 'offline',
                    'window_name': window_name
                }
            })
        except ImportError as e:
            logger.error(f"导入微信管理器失败: {str(e)}")
            return jsonify({
                'code': 2001,
                'message': '微信管理器不可用（最小化模式）',
                'data': None
            }), 400
    except Exception as e:
        logger.error(f"获取微信状态异常: {str(e)}")
        return jsonify({
            'code': 2001,
            'message': f'获取状态失败: {str(e)}',
            'data': None
        }), 500

# 消息相关接口
@api_bp.route('/message/send', methods=['POST'])
@require_api_key
def send_message():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json()
        receiver = data.get('receiver')
        message = data.get('message')
        at_list = data.get('at_list', [])
        clear = data.get('clear', True)

        if not receiver or not message:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 格式化@消息
        formatted_message = format_at_message(message, at_list)
        
        # 使用ChatWith切换到指定聊天窗口，然后发送消息
        chat_name = wx_instance.ChatWith(receiver)
        if not chat_name:
            return jsonify({
                'code': 3001,
                'message': f'找不到联系人: {receiver}',
                'data': None
            }), 404

        # 发送消息
        wx_instance.SendMsg(formatted_message, clear=clear)
        
        return jsonify({
            'code': 0,
            'message': '发送成功',
            'data': {'message_id': 'success'}
        })
            
    except Exception as e:
        logger.error(f"发送消息失败: {str(e)}")
        return jsonify({
            'code': 3001,
            'message': f'发送失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/message/send-typing', methods=['POST'])
@require_api_key
def send_typing_message():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json()
        receiver = data.get('receiver')
        message = data.get('message')
        at_list = data.get('at_list', [])
        clear = data.get('clear', True)

        if not receiver or not message:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 格式化@消息
        formatted_message = format_at_message(message, at_list)
        
        # 使用ChatWith切换到指定聊天窗口
        chat_name = wx_instance.ChatWith(receiver)
        if not chat_name:
            return jsonify({
                'code': 3001,
                'message': f'找不到联系人: {receiver}',
                'data': None
            }), 404

        # 检查库类型，使用相应的方法发送打字机消息
        lib_name = getattr(wx_instance, '_lib_name', 'wxauto')
        if lib_name == 'wxautox':
            # wxautox支持SendTypingText方法
            wx_instance.SendTypingText(formatted_message, clear=clear)
        else:
            # wxauto使用SendMsg方法
            wx_instance.SendMsg(formatted_message, clear=clear)
        
        return jsonify({
            'code': 0,
            'message': '发送成功',
            'data': {'message_id': 'success'}
        })
            
    except Exception as e:
        logger.error(f"发送打字机消息失败: {str(e)}")
        return jsonify({
            'code': 3001,
            'message': f'发送失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/message/send-file', methods=['POST'])
@require_api_key
def send_file():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json()
        receiver = data.get('receiver')
        file_paths = data.get('file_paths', [])

        if not receiver or not file_paths:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 使用ChatWith切换到指定聊天窗口
        chat_name = wx_instance.ChatWith(receiver)
        if not chat_name:
            return jsonify({
                'code': 3001,
                'message': f'找不到联系人: {receiver}',
                'data': None
            }), 404

        # 发送文件
        success_count = 0
        failed_files = []
        
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    wx_instance.SendFiles(file_path)
                    success_count += 1
                else:
                    failed_files.append(file_path)
            except Exception as e:
                logger.error(f"发送文件失败 {file_path}: {str(e)}")
                failed_files.append(file_path)
        
        return jsonify({
            'code': 0,
            'message': '发送完成',
            'data': {
                'success_count': success_count,
                'failed_files': failed_files
            }
        })
            
    except Exception as e:
        logger.error(f"发送文件失败: {str(e)}")
        return jsonify({
            'code': 3001,
            'message': f'发送失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/message/get-next-new', methods=['GET'])
@require_api_key
def get_next_new_message():
    try:
        from app.wechat import wechat_manager
        
        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 解析查询参数
        def parse_bool(value):
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)

        savepic = parse_bool(request.args.get('savepic', False))
        savevideo = parse_bool(request.args.get('savevideo', False))
        savefile = parse_bool(request.args.get('savefile', False))
        savevoice = parse_bool(request.args.get('savevoice', False))
        parseurl = parse_bool(request.args.get('parseurl', False))

        # 构建参数
        lib_name = getattr(wx_instance, '_lib_name', 'wxauto')
        if lib_name == 'wxautox':
            # wxautox支持所有参数
            params = {
                'savepic': savepic,
                'savevideo': savevideo,
                'savefile': savefile,
                'savevoice': savevoice,
                'parseurl': parseurl
            }
        else:
            # wxauto不支持savevideo和parseurl参数
            params = {
                'savepic': savepic,
                'savefile': savefile,
                'savevoice': savevoice
            }

        # 获取未读消息
        messages = wx_instance.GetNextNewMessage(**params)
        
        return jsonify({
            'code': 0,
            'message': '获取成功',
            'data': {'messages': messages}
        })
            
    except Exception as e:
        logger.error(f"获取未读消息失败: {str(e)}")
        return jsonify({
            'code': 3002,
            'message': f'获取失败: {str(e)}',
            'data': None
        }), 500

# 消息监听相关接口
@api_bp.route('/message/listen/add', methods=['POST'])
@require_api_key
def add_listen_chat():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json()
        who = data.get('who')
        
        if not who:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 解析选项参数
        savepic = data.get('savepic', False)
        savevideo = data.get('savevideo', False)
        savefile = data.get('savefile', False)
        savevoice = data.get('savevoice', False)
        parseurl = data.get('parseurl', False)
        exact = data.get('exact', False)

        # 构建参数
        lib_name = getattr(wx_instance, '_lib_name', 'wxauto')
        if lib_name == 'wxautox':
            # wxautox支持所有参数
            params = {
                'who': who,
                'savepic': savepic,
                'savevideo': savevideo,
                'savefile': savefile,
                'savevoice': savevoice,
                'parseurl': parseurl,
                'exact': exact
            }
        else:
            # wxauto不支持savevideo、parseurl和exact参数
            params = {
                'who': who,
                'savepic': savepic,
                'savefile': savefile,
                'savevoice': savevoice
            }

        # 添加监听
        wx_instance.AddListenChat(**params)
        
        return jsonify({
            'code': 0,
            'message': '添加监听成功',
            'data': {'who': who}
        })
            
    except Exception as e:
        logger.error(f"添加监听失败: {str(e)}")
        return jsonify({
            'code': 3001,
            'message': f'添加监听失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/message/listen/add-current', methods=['POST'])
@require_api_key
def add_current_chat_to_listen():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json() or {}

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 解析选项参数
        def parse_bool(value, default=False):
            if value is None:
                return default
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)

        savepic = parse_bool(data.get('savepic'), False)
        savevideo = parse_bool(data.get('savevideo'), False)
        savefile = parse_bool(data.get('savefile'), False)
        savevoice = parse_bool(data.get('savevoice'), False)
        parseurl = parse_bool(data.get('parseurl'), False)

        # 获取当前聊天窗口名称
        try:
            current_chat = wx_instance.CurrentChat()
            if not current_chat:
                return jsonify({
                    'code': 3001,
                    'message': '未找到当前聊天窗口',
                    'data': None
                }), 404

            # 如果窗口名称以 "微信" 开头，说明不是聊天窗口
            if current_chat.startswith('微信'):
                return jsonify({
                    'code': 3001,
                    'message': '当前窗口不是聊天窗口',
                    'data': None
                }), 400
        except Exception as e:
            logger.error(f"获取当前聊天窗口失败: {str(e)}")
            return jsonify({
                'code': 3001,
                'message': '获取当前聊天窗口失败',
                'data': None
            }), 500

        # 构建参数
        lib_name = getattr(wx_instance, '_lib_name', 'wxauto')
        if lib_name == 'wxautox':
            # wxautox支持所有参数
            params = {
                'who': current_chat,
                'savepic': savepic,
                'savevideo': savevideo,
                'savefile': savefile,
                'savevoice': savevoice,
                'parseurl': parseurl
            }
        else:
            # wxauto不支持savevideo和parseurl参数
            params = {
                'who': current_chat,
                'savepic': savepic,
                'savefile': savefile,
                'savevoice': savevoice
            }

        # 添加当前聊天到监听
        wx_instance.AddListenChat(**params)
        
        return jsonify({
            'code': 0,
            'message': '添加监听成功',
            'data': {
                'who': current_chat,
                'options': {
                    'savepic': savepic,
                    'savevideo': savevideo,
                    'savefile': savefile,
                    'savevoice': savevoice,
                    'parseurl': parseurl
                }
            }
        })
            
    except Exception as e:
        logger.error(f"添加当前聊天监听失败: {str(e)}")
        return jsonify({
            'code': 3001,
            'message': f'添加监听失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/message/listen/get', methods=['GET'])
@require_api_key
def get_listen_messages():
    try:
        from app.wechat import wechat_manager
        
        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        who = request.args.get('who')
        
        # 获取监听消息
        if who:
            messages = wx_instance.GetListenMessage(who)
        else:
            messages = wx_instance.GetListenMessage()
        
        # 序列化消息对象
        serialized_messages = serialize_messages(messages)
        
        return jsonify({
            'code': 0,
            'message': '获取成功',
            'data': {'messages': serialized_messages}
        })
            
    except Exception as e:
        logger.error(f"获取监听消息失败: {str(e)}")
        return jsonify({
            'code': 3002,
            'message': f'获取失败: {str(e)}',
            'data': None
        }), 500

def serialize_messages(messages):
    """序列化消息对象为可JSON序列化的格式"""
    if not messages:
        return []
    
    serialized = []
    for msg in messages:
        try:
            # 基础消息信息
            msg_data = {
                'type': getattr(msg, 'type', 'unknown'),
                'sender': getattr(msg, 'sender', ''),
                'content': getattr(msg, 'content', ''),
                'id': getattr(msg, 'id', ''),
            }
            
            # 根据消息类型添加特定字段
            if hasattr(msg, 'type'):
                if msg.type == 'friend':
                    # 好友消息
                    msg_data['sender_remark'] = getattr(msg, 'sender_remark', '')
                elif msg.type == 'time':
                    # 时间消息
                    msg_data['time'] = getattr(msg, 'time', '')
                elif msg.type == 'sys':
                    # 系统消息
                    pass  # 基础字段已足够
                elif msg.type == 'recall':
                    # 撤回消息
                    pass  # 基础字段已足够
                elif msg.type == 'self':
                    # 自己的消息
                    pass  # 基础字段已足够
            
            # 添加原始信息（如果存在且可序列化）
            if hasattr(msg, 'info') and isinstance(msg.info, (list, tuple)):
                try:
                    # 尝试序列化info，如果包含不可序列化的对象则跳过
                    json.dumps(msg.info)  # 测试是否可序列化
                    msg_data['info'] = msg.info
                except (TypeError, ValueError):
                    # 如果info不能序列化，则提取基本信息
                    if len(msg.info) >= 2:
                        msg_data['info'] = [str(msg.info[0]), str(msg.info[1])]
                    else:
                        msg_data['info'] = [str(item) for item in msg.info]
            
            serialized.append(msg_data)
            
        except Exception as e:
            # 如果单个消息序列化失败，记录错误但继续处理其他消息
            logger.warning(f"序列化消息失败: {str(e)}, 消息类型: {type(msg)}")
            # 添加一个错误消息对象
            serialized.append({
                'type': 'error',
                'sender': 'system',
                'content': f'消息序列化失败: {str(e)}',
                'id': '',
                'error': True
            })
    
    return serialized

@api_bp.route('/message/listen/remove', methods=['POST'])
@require_api_key
def remove_listen_chat():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json()
        who = data.get('who')
        
        if not who:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 移除监听
        wx_instance.RemoveListenChat(who)
        
        return jsonify({
            'code': 0,
            'message': '移除监听成功',
            'data': {'who': who}
        })
            
    except Exception as e:
        logger.error(f"移除监听失败: {str(e)}")
        return jsonify({
            'code': 3001,
            'message': f'移除监听失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/message/get-all', methods=['GET'])
@require_api_key
def get_all_messages():
    """获取监听消息（新消息，不是历史消息）- 已弃用，建议使用GetListenMessage"""
    try:
        from app.wechat import wechat_manager
        
        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 获取查询参数
        who = request.args.get('who')  # 可选参数，指定聊天对象
        
        # 如果指定了聊天对象，先切换到该聊天窗口
        if who:
            try:
                current_chat = wx_instance.ChatWith(who)
                if not current_chat:
                    return jsonify({
                        'code': 3001,
                        'message': f'无法切换到聊天窗口: {who}',
                        'data': None
                    }), 404
                logger.info(f"已切换到聊天窗口: {current_chat}")
            except Exception as e:
                logger.error(f"切换聊天窗口失败: {str(e)}")
                return jsonify({
                    'code': 3001,
                    'message': f'切换聊天窗口失败: {str(e)}',
                    'data': None
                }), 500
        
        # 获取当前聊天窗口的所有消息
        try:
            # 使用GetListenMessage获取新消息，而不是GetAllMessage获取历史消息
            # 获取指定聊天对象的监听消息（只获取新消息）
            messages = wx_instance.GetListenMessage(who)

            # 处理返回的消息格式
            if isinstance(messages, dict):
                # 如果返回的是字典格式 {ChatWnd: [Message]}
                all_messages = []
                for chat_wnd, msg_list in messages.items():
                    if isinstance(msg_list, list):
                        all_messages.extend(msg_list)
                    else:
                        all_messages.append(msg_list)
                messages = all_messages
            elif not isinstance(messages, list):
                # 如果不是列表，转换为列表
                messages = [messages] if messages else []
            
            # 获取当前聊天窗口名称
            current_chat_name = ""
            try:
                current_chat_name = wx_instance._instance.CurrentChat()
            except Exception as e:
                logger.warning(f"获取当前聊天窗口名称失败: {str(e)}")
            
            # 序列化消息对象
            serialized_messages = serialize_messages(messages)
            
            return jsonify({
                'code': 0,
                'message': '获取成功',
                'data': {
                    'messages': serialized_messages,
                    'count': len(serialized_messages),
                    'current_chat': current_chat_name,
                    'note': '此接口已弃用，只返回新消息，不返回历史消息。建议使用/message/listen接口'
                }
            })
            
        except Exception as e:
            logger.error(f"获取消息失败: {str(e)}")
            return jsonify({
                'code': 3002,
                'message': f'获取消息失败: {str(e)}',
                'data': None
            }), 500
            
    except Exception as e:
        logger.error(f"获取所有消息失败: {str(e)}")
        return jsonify({
            'code': 3002,
            'message': f'获取失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/chat-window/get-all-messages', methods=['GET'])
@require_api_key
def get_chat_window_all_messages():
    """获取指定聊天窗口的监听消息（新消息，不是历史消息）"""
    try:
        from app.wechat import wechat_manager

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 获取查询参数
        who = request.args.get('who')  # 必需参数，指定聊天对象
        if not who:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数: who',
                'data': None
            }), 400

        # 检查聊天窗口是否在监听列表中
        listen = wx_instance.listen
        if not listen or who not in listen:
            return jsonify({
                'code': 3001,
                'message': f'聊天窗口 {who} 未在监听列表中，请先添加到监听列表',
                'data': None
            }), 404

        # 使用GetListenMessage获取新消息，而不是GetAllMessage获取历史消息
        try:
            # 获取指定聊天对象的监听消息（只获取新消息）
            messages = wx_instance.GetListenMessage(who)

            # 处理返回的消息格式
            if isinstance(messages, dict):
                # 如果返回的是字典格式 {ChatWnd: [Message]}
                all_messages = []
                for chat_wnd, msg_list in messages.items():
                    if isinstance(msg_list, list):
                        all_messages.extend(msg_list)
                    else:
                        all_messages.append(msg_list)
                messages = all_messages
            elif not isinstance(messages, list):
                # 如果不是列表，转换为列表
                messages = [messages] if messages else []

            # 序列化消息对象
            serialized_messages = serialize_messages(messages)

            return jsonify({
                'code': 0,
                'message': '获取成功',
                'data': {
                    'messages': serialized_messages,
                    'count': len(serialized_messages),
                    'chat_window': who,
                    'note': '此接口只返回新消息，不返回历史消息'
                }
            })

        except Exception as e:
            logger.error(f"获取聊天窗口监听消息失败: {str(e)}")
            return jsonify({
                'code': 3002,
                'message': f'获取聊天窗口监听消息失败: {str(e)}',
                'data': None
            }), 500

    except Exception as e:
        logger.error(f"获取聊天窗口监听消息失败: {str(e)}")
        return jsonify({
            'code': 3002,
            'message': f'获取失败: {str(e)}',
            'data': None
        }), 500

# 聊天窗口操作相关接口
@api_bp.route('/chat-window/message/send', methods=['POST'])
@require_api_key
def chat_window_send_message():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json()
        who = data.get('who')
        message = data.get('message')
        at_list = data.get('at_list', [])
        clear = data.get('clear', True)

        if not who or not message:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 检查监听列表
        listen = wx_instance.listen
        if not listen or who not in listen:
            return jsonify({
                'code': 3001,
                'message': f'聊天窗口 {who} 未在监听列表中',
                'data': None
            }), 404

        chat_wnd = listen[who]

        # 格式化@消息
        formatted_message = format_at_message(message, at_list)
        
        # 检查库类型，使用相应的方法
        lib_name = getattr(wx_instance, '_lib_name', 'wxauto')
        if lib_name == 'wxautox':
            # wxautox支持clear参数
            if at_list:
                chat_wnd.SendMsg(formatted_message, clear=clear, at=at_list)
            else:
                chat_wnd.SendMsg(formatted_message, clear=clear)
        else:
            # wxauto不支持clear参数
            if at_list:
                chat_wnd.SendMsg(formatted_message, at=at_list)
            else:
                chat_wnd.SendMsg(formatted_message)
        
        return jsonify({
            'code': 0,
            'message': '发送成功',
            'data': {'message_id': 'success'}
        })
            
    except Exception as e:
        logger.error(f"聊天窗口发送消息失败: {str(e)}")
        return jsonify({
            'code': 3001,
            'message': f'发送失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/chat-window/message/send-typing', methods=['POST'])
@require_api_key
def chat_window_send_typing_message():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json()
        who = data.get('who')
        message = data.get('message')
        at_list = data.get('at_list', [])
        clear = data.get('clear', True)

        if not who or not message:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 检查监听列表
        listen = wx_instance.listen
        if not listen or who not in listen:
            return jsonify({
                'code': 3001,
                'message': f'聊天窗口 {who} 未在监听列表中',
                'data': None
            }), 404

        chat_wnd = listen[who]

        # 格式化@消息
        formatted_message = format_at_message(message, at_list)
        
        # 检查库类型，使用相应的方法
        lib_name = getattr(wx_instance, '_lib_name', 'wxauto')
        if lib_name == 'wxautox':
            # wxautox支持SendTypingText方法
            chat_wnd.SendTypingText(formatted_message, clear=clear)
        else:
            # wxauto使用SendMsg方法代替
            chat_wnd.SendMsg(formatted_message)
        
        return jsonify({
            'code': 0,
            'message': '发送成功',
            'data': {'message_id': 'success'}
        })
            
    except Exception as e:
        logger.error(f"聊天窗口发送打字机消息失败: {str(e)}")
        return jsonify({
            'code': 3001,
            'message': f'发送失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/chat-window/message/send-file', methods=['POST'])
@require_api_key
def chat_window_send_file():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json()
        who = data.get('who')
        file_paths = data.get('file_paths', [])

        if not who or not file_paths:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 检查监听列表
        listen = wx_instance.listen
        if not listen or who not in listen:
            return jsonify({
                'code': 3001,
                'message': f'聊天窗口 {who} 未在监听列表中',
                'data': None
            }), 404

        chat_wnd = listen[who]

        # 发送文件
        success_count = 0
        failed_files = []
        
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    chat_wnd.SendFiles(file_path)
                    success_count += 1
                else:
                    failed_files.append(file_path)
            except Exception as e:
                logger.error(f"聊天窗口发送文件失败 {file_path}: {str(e)}")
                failed_files.append(file_path)
        
        return jsonify({
            'code': 0,
            'message': '发送完成',
            'data': {
                'success_count': success_count,
                'failed_files': failed_files
            }
        })
            
    except Exception as e:
        logger.error(f"聊天窗口发送文件失败: {str(e)}")
        return jsonify({
            'code': 3001,
            'message': f'发送失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/chat-window/message/at-all', methods=['POST'])
@require_api_key
def chat_window_at_all():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json()
        who = data.get('who')
        message = data.get('message', '')

        if not who:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 检查监听列表
        listen = wx_instance.listen
        if not listen or who not in listen:
            return jsonify({
                'code': 3001,
                'message': f'聊天窗口 {who} 未在监听列表中',
                'data': None
            }), 404

        chat_wnd = listen[who]

        # @所有人
        chat_wnd.AtAll(message)
        
        return jsonify({
            'code': 0,
            'message': '发送成功',
            'data': {'message_id': 'success'}
        })
            
    except Exception as e:
        logger.error(f"@所有人失败: {str(e)}")
        return jsonify({
            'code': 3001,
            'message': f'发送失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/chat-window/info', methods=['GET'])
@require_api_key
def get_chat_window_info():
    try:
        from app.wechat import wechat_manager
        
        who = request.args.get('who')
        
        if not who:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 检查监听列表
        listen = wx_instance.listen
        if not listen or who not in listen:
            return jsonify({
                'code': 3001,
                'message': f'聊天窗口 {who} 未在监听列表中',
                'data': None
            }), 404

        chat_wnd = listen[who]

        # 获取聊天窗口信息
        try:
            # 尝试获取群成员数量（如果是群聊）
            member_count = getattr(chat_wnd, 'member_count', 0)
            members = getattr(chat_wnd, 'members', [])
            
            info = {
                'name': who,
                'member_count': member_count,
                'members': members
            }
        except Exception as e:
            logger.warning(f"获取详细信息失败: {str(e)}")
            info = {
                'name': who,
                'member_count': 0,
                'members': []
            }
        
        return jsonify({
            'code': 0,
            'message': '获取成功',
            'data': info
        })
            
    except Exception as e:
        logger.error(f"获取聊天窗口信息失败: {str(e)}")
        return jsonify({
            'code': 3002,
            'message': f'获取失败: {str(e)}',
            'data': None
        }), 500

# 群组相关接口
@api_bp.route('/group/list', methods=['GET'])
@require_api_key
def get_group_list():
    try:
        from app.wechat import wechat_manager
        
        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 获取群列表
        try:
            # 尝试获取群列表，不同库可能有不同的方法
            groups = []
            if hasattr(wx_instance, 'GetGroupList'):
                groups = wx_instance.GetGroupList()
            elif hasattr(wx_instance, 'GetChatList'):
                # 获取所有聊天列表，然后筛选群聊
                all_chats = wx_instance.GetChatList()
                groups = [chat for chat in all_chats if '(' in chat and ')' in chat]
            else:
                # 如果没有专门的方法，返回空列表
                groups = []
            
            # 格式化群列表
            formatted_groups = []
            for group in groups:
                if isinstance(group, str):
                    # 尝试从群名中提取成员数量
                    import re
                    match = re.search(r'\((\d+)\)$', group)
                    member_count = int(match.group(1)) if match else 0
                    clean_name = re.sub(r'\s*\(\d+\)$', '', group)
                    
                    formatted_groups.append({
                        'name': clean_name,
                        'member_count': member_count
                    })
                else:
                    formatted_groups.append({
                        'name': str(group),
                        'member_count': 0
                    })
        except Exception as e:
            logger.warning(f"获取群列表失败: {str(e)}")
            formatted_groups = []
        
        return jsonify({
            'code': 0,
            'message': '获取成功',
            'data': {'groups': formatted_groups}
        })
            
    except Exception as e:
        logger.error(f"获取群列表失败: {str(e)}")
        return jsonify({
            'code': 4001,
            'message': f'获取失败: {str(e)}',
            'data': None
        }), 500

@api_bp.route('/group/manage', methods=['POST'])
@require_api_key
def manage_group():
    try:
        from app.wechat import wechat_manager
        
        data = request.get_json()
        group_name = data.get('group_name')
        action = data.get('action')
        params = data.get('params', {})

        if not group_name or not action:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 执行群管理操作
        try:
            if action == 'rename':
                new_name = params.get('new_name')
                if not new_name:
                    return jsonify({
                        'code': 1002,
                        'message': '缺少新群名参数',
                        'data': None
                    }), 400
                
                # 切换到群聊窗口
                wx_instance.ChatWith(group_name)
                # 这里需要实现重命名逻辑，具体方法取决于使用的库
                # 暂时返回成功，实际实现需要根据具体库的API
                result = True
                
            elif action == 'quit':
                # 切换到群聊窗口
                wx_instance.ChatWith(group_name)
                # 这里需要实现退群逻辑，具体方法取决于使用的库
                # 暂时返回成功，实际实现需要根据具体库的API
                result = True
                
            else:
                return jsonify({
                    'code': 1002,
                    'message': f'不支持的操作: {action}',
                    'data': None
                }), 400
        except Exception as e:
            logger.error(f"群管理操作失败: {str(e)}")
            result = False
        
        if result:
            return jsonify({
                'code': 0,
                'message': '操作成功',
                'data': {'success': True}
            })
        else:
            return jsonify({
                'code': 4001,
                'message': '操作失败',
                'data': None
            }), 500
            
    except Exception as e:
        logger.error(f"群管理操作失败: {str(e)}")
        return jsonify({
            'code': 4001,
            'message': f'操作失败: {str(e)}',
            'data': None
        }), 500

# 好友相关接口
@api_bp.route('/contact/list', methods=['GET'])
@require_api_key
def get_contact_list():
    try:
        from app.wechat import wechat_manager
        
        wx_instance = wechat_manager.get_instance()
        if not wx_instance:
            return jsonify({
                'code': 2001,
                'message': '微信未初始化',
                'data': None
            }), 400

        # 获取好友列表
        try:
            # 尝试获取好友列表，不同库可能有不同的方法
            friends = []
            if hasattr(wx_instance, 'GetContactList'):
                friends = wx_instance.GetContactList()
            elif hasattr(wx_instance, 'GetFriendList'):
                friends = wx_instance.GetFriendList()
            elif hasattr(wx_instance, 'GetChatList'):
                # 获取所有聊天列表，然后筛选好友（不包含群聊）
                all_chats = wx_instance.GetChatList()
                friends = [chat for chat in all_chats if not ('(' in chat and ')' in chat)]
            else:
                # 如果没有专门的方法，返回空列表
                friends = []
            
            # 格式化好友列表
            formatted_friends = []
            for friend in friends:
                if isinstance(friend, str):
                    formatted_friends.append({
                        'name': friend,
                        'remark': friend  # 暂时使用名称作为备注
                    })
                else:
                    formatted_friends.append({
                        'name': str(friend),
                        'remark': str(friend)
                    })
        except Exception as e:
            logger.warning(f"获取好友列表失败: {str(e)}")
            formatted_friends = []
        
        return jsonify({
            'code': 0,
            'message': '获取成功',
            'data': {'friends': formatted_friends}
        })
            
    except Exception as e:
        logger.error(f"获取好友列表失败: {str(e)}")
        return jsonify({
            'code': 5001,
            'message': f'获取失败: {str(e)}',
            'data': None
        }), 500

# 文件下载接口
@api_bp.route('/file/download', methods=['POST'])
@require_api_key
def download_file():
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({
                'code': 1002,
                'message': '缺少文件路径参数',
                'data': None
            }), 400
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({
                'code': 3003,
                'message': '文件不存在',
                'data': {'error': '文件不存在或无法访问'}
            }), 404
        
        # 检查文件大小（限制100MB）
        file_size = os.path.getsize(file_path)
        if file_size > 100 * 1024 * 1024:  # 100MB
            return jsonify({
                'code': 3003,
                'message': '文件过大',
                'data': {'error': '文件大小超过100MB限制'}
            }), 413
        
        # 获取文件名
        filename = os.path.basename(file_path)
        
        # 返回文件
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"文件下载失败: {str(e)}")
        return jsonify({
            'code': 3003,
            'message': '文件下载失败',
            'data': {'error': str(e)}
        }), 500

# API信息接口
@api_bp.route('/info', methods=['GET'])
def api_info():
    """API信息"""
    return jsonify({
        'name': '只为记账-微信助手 API',
        'version': '1.0.0',
        'status': 'running',
        'mode': 'minimal',
        'uptime': int(time.time() - start_time)
    })

# 系统资源接口
@api_bp.route('/system/resources', methods=['GET'])
@require_api_key
def get_resources():
    """获取系统资源信息"""
    try:
        import psutil
        
        # 获取CPU信息
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # 获取内存信息
        memory = psutil.virtual_memory()
        
        return jsonify({
            'code': 0,
            'message': '获取成功',
            'data': {
                'cpu': {
                    'usage_percent': cpu_percent,
                    'core_count': cpu_count
                },
                'memory': {
                    'total': int(memory.total / (1024 * 1024)),  # 转换为MB
                    'used': int(memory.used / (1024 * 1024)),    # 转换为MB
                    'free': int(memory.available / (1024 * 1024)),  # 转换为MB
                    'usage_percent': memory.percent
                }
            }
        })
    except Exception as e:
        logger.error(f"获取系统资源失败: {str(e)}")
        return jsonify({
            'code': 5001,
            'message': f'获取系统资源失败: {str(e)}',
            'data': None
        }), 500 