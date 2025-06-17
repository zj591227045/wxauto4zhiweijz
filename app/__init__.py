import os
import sys
import logging

# 确保当前目录在Python路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 确保父目录在Python路径中
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from flask import Flask
    logging.info("✓ Flask导入成功")
except ImportError as e:
    logging.error(f"导入Flask失败: {str(e)}")
    logging.error("请确保已安装Flask")
    raise

# 尝试导入flask-limiter，但如果失败则跳过
LIMITER_AVAILABLE = False
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
    logging.info("✓ flask-limiter导入成功")
except ImportError as e:
    logging.warning(f"flask-limiter导入失败: {str(e)}")
    logging.warning("将跳过API限流功能")
except Exception as e:
    logging.warning(f"flask-limiter导入异常: {str(e)}")
    logging.warning("将跳过API限流功能")

try:
    from app.config import Config
except ImportError:
    try:
        # 尝试直接导入
        from config import Config
    except ImportError:
        logging.error("无法导入Config模块，请确保app/config.py文件存在")
        raise

def create_app():
    """创建并配置Flask应用"""
    logging.info("开始创建Flask应用...")

    # 配置 Werkzeug 日志
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)  # 只显示错误级别的日志

    # 确保所有日志处理器立即刷新
    for handler in logging.getLogger().handlers:
        handler.setLevel(logging.DEBUG)
        handler.flush()

    # 初始化微信相关配置（可选）
    try:
        logging.info("正在初始化微信相关配置...")
        from app.wechat_init import initialize as init_wechat
        init_wechat()
        logging.info("微信相关配置初始化完成")
    except ImportError as e:
        logging.warning(f"导入微信初始化模块失败: {str(e)}")
        logging.warning("将继续创建Flask应用，但微信功能可能不可用")
    except Exception as e:
        logging.warning(f"初始化微信配置时出错: {str(e)}")
        logging.warning("将继续创建Flask应用，但微信功能可能不可用")

    # 简约版本跳过插件管理模块
    logging.info("简约版本跳过插件管理模块")

    # 创建 Flask 应用
    logging.info("正在创建Flask实例...")
    app = Flask(__name__)
    app.config.from_object(Config)
    logging.info("Flask实例创建成功")

    # 配置Flask日志处理
    if not app.debug:
        # 在非调试模式下，禁用自动重载器
        app.config['USE_RELOADER'] = False
        logging.info("已禁用Flask自动重载器")

    # 初始化限流器（可选）
    if LIMITER_AVAILABLE:
        try:
            logging.info("正在初始化限流器...")
            limiter = Limiter(
                app=app,
                key_func=get_remote_address,
                default_limits=[Config.RATELIMIT_DEFAULT],
                storage_uri=Config.RATELIMIT_STORAGE_URL
            )
            logging.info("限流器初始化成功")
        except Exception as e:
            logging.warning(f"初始化限流器时出错: {str(e)}")
            logging.warning("将继续创建Flask应用，但API限流功能不可用")
    else:
        logging.info("跳过限流器初始化（flask-limiter不可用）")

    # 注册蓝图（可选）
    try:
        logging.info("正在注册蓝图...")
        
        # 优先尝试导入最小化API路由（不依赖flask-limiter）
        try:
            from app.api.routes_minimal import api_bp
            app.register_blueprint(api_bp, url_prefix='/api')
            logging.info("最小化API蓝图注册成功")
        except ImportError:
            # 如果最小化路由不存在，尝试导入主要的API路由
            try:
                from app.api.routes import api_bp
                app.register_blueprint(api_bp, url_prefix='/api')
                logging.info("主API蓝图注册成功")
            except ImportError as e:
                logging.warning(f"导入API蓝图失败: {str(e)}")
                logging.warning("将创建内置最小化API路由")
                
                # 创建内置最小化API蓝图
                from flask import Blueprint, jsonify
                minimal_api_bp = Blueprint('minimal_api', __name__)
                
                @minimal_api_bp.route('/wechat/status')
                def wechat_status():
                    return jsonify({
                        'code': 2001,
                        'message': '微信未初始化（最小化模式）',
                        'data': None
                    }), 400
                
                @minimal_api_bp.route('/wechat/initialize', methods=['POST'])
                def wechat_initialize():
                    return jsonify({
                        'code': 2001,
                        'message': '微信初始化功能不可用（最小化模式）',
                        'data': None
                    }), 500
                
                @minimal_api_bp.route('/health')
                def api_health():
                    return jsonify({
                        'status': 'ok',
                        'message': 'API服务运行正常（内置模式）'
                    })
                
                app.register_blueprint(minimal_api_bp, url_prefix='/api')
                logging.info("内置最小化API蓝图注册成功")
        
        # 简约版本跳过管理员路由和插件路由
        logging.info("简约版本跳过管理员路由和插件路由")
            
    except Exception as e:
        logging.error(f"注册蓝图时出错: {str(e)}")
        logging.warning("将继续创建Flask应用，但某些功能可能不可用")

    # 添加健康检查路由
    @app.route('/health')
    def health_check():
        """健康检查路由"""
        return {'status': 'ok', 'message': 'API服务运行正常'}

    # 添加简单的测试路由
    @app.route('/test')
    def test_route():
        """测试路由"""
        return {'message': 'Flask应用运行正常', 'status': 'ok'}

    # 添加API信息路由
    @app.route('/api/info')
    def api_info():
        """API信息路由"""
        return {
            'name': '只为记账-微信助手 API',
            'version': '1.0.0',
            'status': 'running',
            'limiter_enabled': LIMITER_AVAILABLE
        }

    logging.info("Flask应用创建完成")
    return app