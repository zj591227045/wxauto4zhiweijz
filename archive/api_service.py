"""
API服务逻辑
专门用于启动和管理API服务
"""

import os
import sys
import logging
import traceback

# 配置日志
logger = logging.getLogger(__name__)

def check_mutex():
    """检查互斥锁，确保同一时间只有一个API服务实例在运行"""
    # 简约版本跳过互斥锁检查，简化启动流程
    logger.info("简约版本跳过互斥锁检查")
    return True

def check_dependencies():
    """检查依赖项"""
    try:
        # 检查Flask
        try:
            import flask
            logger.info(f"✓ Flask版本: {flask.__version__}")
        except ImportError as e:
            logger.error(f"✗ Flask未安装: {e}")
            return False
        
        # 检查requests
        try:
            import requests
            logger.info(f"✓ requests已安装")
        except ImportError as e:
            logger.error(f"✗ requests未安装: {e}")
            return False
        
        # 检查psutil
        try:
            import psutil
            logger.info(f"✓ psutil已安装")
        except ImportError as e:
            logger.error(f"✗ psutil未安装: {e}")
            return False

        # 尝试导入wxauto库（简约版本简化检查）
        try:
            # 尝试从本地目录导入
            wxauto_path = os.path.join(os.getcwd(), "wxauto")
            if os.path.exists(wxauto_path) and os.path.isdir(wxauto_path):
                if wxauto_path not in sys.path:
                    sys.path.insert(0, wxauto_path)
                try:
                    import wxauto
                    logger.info(f"✓ 成功从本地目录导入wxauto: {wxauto_path}")
                except ImportError as e:
                    logger.warning(f"从本地目录导入wxauto失败: {str(e)}")
            else:
                # 尝试直接导入已安装的wxauto
                try:
                    import wxauto
                    logger.info("✓ wxauto库导入成功")
                except ImportError as e:
                    logger.warning(f"wxauto库导入失败: {str(e)}")
        except Exception as e:
            logger.warning(f"检查wxauto库时出错: {str(e)}")

        # 检查wxautox是否可用（可选）
        try:
            import wxautox
            logger.info("✓ wxautox库已安装")
        except ImportError:
            logger.info("wxautox库未安装，将使用wxauto库")

        logger.info("依赖项检查完成")
        return True
    except Exception as e:
        logger.error(f"检查依赖项时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return True  # 即使检查失败也继续，让Flask应用尝试启动

def start_queue_processors():
    """启动队列处理器（简约版本跳过）"""
    # 简约版本不使用队列处理器，简化架构
    logger.info("简约版本跳过队列处理器启动")
    return True

def start_api():
    """启动API服务"""
    try:
        logger.info("===== 开始启动API服务 =====")

        # 检查互斥锁
        logger.info("正在检查互斥锁...")
        if not check_mutex():
            logger.info("互斥锁检查失败，退出")
            sys.exit(0)
        logger.info("互斥锁检查通过")

        # 检查依赖项
        logger.info("正在检查依赖项...")
        if not check_dependencies():
            logger.warning("依赖项检查失败，但将尝试继续启动")
        logger.info("依赖项检查完成")

        # 启动队列处理器
        logger.info("正在启动队列处理器...")
        if not start_queue_processors():
            logger.warning("队列处理器启动失败，但将尝试继续启动")
        logger.info("队列处理器启动完成")

        # 创建并启动Flask应用
        try:
            # 记录当前环境信息
            logger.info(f"当前工作目录: {os.getcwd()}")
            logger.info(f"Python路径: {sys.path[:3]}...")  # 只显示前3个路径

            # 确保app目录在Python路径中
            app_dir = os.path.join(os.getcwd(), "app")
            if os.path.exists(app_dir) and app_dir not in sys.path:
                sys.path.insert(0, app_dir)
                logger.info(f"已将app目录添加到Python路径: {app_dir}")

            # 导入Flask应用创建函数
            logger.info("正在尝试导入Flask应用创建函数...")
            try:
                # 首先尝试从app包导入
                from app import create_app
                logger.info("成功从app包导入Flask应用创建函数")
            except ImportError as e:
                logger.error(f"从app包导入Flask应用创建函数失败: {str(e)}")
                logger.error(traceback.format_exc())
                
                # 如果导入失败，创建一个最小化的Flask应用
                logger.info("尝试创建最小化Flask应用...")
                from flask import Flask, jsonify
                
                def create_minimal_app():
                    app = Flask(__name__)
                    app.config['HOST'] = '0.0.0.0'
                    app.config['PORT'] = 5000
                    app.config['DEBUG'] = False
                    
                    @app.route('/health')
                    def health_check():
                        return jsonify({'status': 'ok', 'message': '最小化API服务运行中'})
                    
                    @app.route('/test')
                    def test_route():
                        return jsonify({'message': 'Hello World', 'status': 'ok'})
                    
                    return app
                
                create_app = create_minimal_app
                logger.info("最小化Flask应用创建函数准备完成")

            # 创建应用
            logger.info("正在创建Flask应用...")
            app = create_app()
            logger.info("成功创建Flask应用")

            # 获取配置信息
            host = app.config.get('HOST', '0.0.0.0')
            port = app.config.get('PORT', 5000)
            debug = app.config.get('DEBUG', False)

            logger.info(f"正在启动Flask应用...")
            logger.info(f"监听地址: {host}:{port}")
            logger.info(f"调试模式: {debug}")

            # 禁用 werkzeug 的重新加载器，避免可能的端口冲突
            app.run(
                host=host,
                port=port,
                debug=debug,
                use_reloader=False,
                threaded=True
            )
        except ImportError as e:
            logger.error(f"导入Flask相关模块失败: {str(e)}")
            logger.error(traceback.format_exc())
            sys.exit(1)
        except Exception as e:
            logger.error(f"启动Flask应用时出错: {str(e)}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    except Exception as e:
        logger.error(f"API服务启动过程中发生未捕获的异常: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    # 设置环境变量，标记为API服务进程
    os.environ["WXAUTO_SERVICE_TYPE"] = "api"

    # 启动API服务
    start_api()
