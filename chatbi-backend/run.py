"""
ChatBI 后端服务启动入口

启动方式：
    python run.py              # 开发模式
    python run.py --prod       # 生产模式

服务包含：
    - HTTP API:     http://localhost:8880/api/v1/
    - WebSocket:    ws://localhost:8880/api/v1/ws/chat/{session_id}
    - API 文档:     http://localhost:8880/docs
    - 健康检查:     http://localhost:8880/health

Agent 系统说明：
    Agent 系统（IntentAgent、SqlPlannerAgent 等）是延迟初始化的，
    会在第一次收到用户请求时自动加载，无需单独启动。

Author: CYJ
Time: 2025-11-26
"""
import os
import sys
import argparse
import logging

# 确保项目根目录在 Python 路径中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def setup_logging(debug: bool = False):
    """配置日志"""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 降低第三方库的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.INFO)


def print_banner(host: str, port: int):
    """打印启动横幅"""
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                    ChatBI Backend Server                     ║
╠══════════════════════════════════════════════════════════════╣
║  HTTP API:     http://{host}:{port}/api/v1/                     ║
║  WebSocket:    ws://{host}:{port}/api/v1/ws/chat/{{session_id}}   ║
║  API 文档:     http://{host}:{port}/docs                         ║
║  健康检查:     http://{host}:{port}/health                       ║
╠══════════════════════════════════════════════════════════════╣
║  Agent 系统:   延迟加载（首次请求时初始化）                  ║
║  存储类型:     内存（重启后会话丢失）                        ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def run_server(
    host: str = None,
    port: int = None,
    reload: bool = True,
    workers: int = 1,
    debug: bool = False
):
    """
    启动服务器
    
    Args:
        host: 监听地址
        port: 监听端口
        reload: 是否开启热重载（开发模式）
        workers: 工作进程数（生产模式）
        debug: 是否开启调试模式
    """
    import uvicorn
    from app.core.config import get_settings
    
    settings = get_settings()
    
    # 使用配置或参数
    host = host or settings.SERVER_HOST
    port = port or settings.SERVER_PORT
    
    setup_logging(debug)
    print_banner(host, port)
    
    # 启动前检查
    print("🔍 启动前检查...")
    try:
        from app.core.health import check_mysql, check_postgres, check_neo4j, check_llm
        import asyncio
        
        async def quick_check():
            results = {
                "MySQL": await check_mysql(),
                "PostgreSQL": await check_postgres(),
                "Neo4j": await check_neo4j(),
                "LLM": await check_llm()
            }
            return results
        
        results = asyncio.run(quick_check())
        
        for name, status in results.items():
            emoji = "✅" if "ok" in str(status).lower() else "⚠️"
            print(f"   {emoji} {name}: {status}")
        
        print()
    except Exception as e:
        print(f"   ⚠️ 健康检查失败: {e}")
        print("   (服务仍将启动，但某些功能可能不可用)")
        print()
    
    # 启动服务
    print(f"🚀 启动服务 @ http://{host}:{port}")
    print("   按 Ctrl+C 停止服务\n")
    
    # V12: 禁用 WebSocket ping，避免 LLM 调用时间过长导致超时断开
    # ws_ping_interval=None 禁用服务端的 ping
    # ws_ping_timeout=None 不超时
    # Author: CYJ
    # Time: 2025-11-27
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,  # reload 模式只能单进程
        log_level="debug" if debug else "info",
        access_log=debug,
        ws_ping_interval=None,  # 禁用 WebSocket ping
        ws_ping_timeout=None    # 不超时
    )


def main():
    parser = argparse.ArgumentParser(
        description="ChatBI 后端服务启动器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                    # 开发模式（热重载）
  python run.py --prod             # 生产模式（多进程）
  python run.py --host 0.0.0.0     # 指定监听地址
  python run.py --port 8000        # 指定端口
  python run.py --debug            # 调试模式
        """
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="监听地址 (默认从 .env 读取)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="监听端口 (默认从 .env 读取)"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="生产模式（关闭热重载，启用多进程）"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="工作进程数 (仅生产模式有效，默认 4)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="调试模式（详细日志）"
    )
    
    args = parser.parse_args()
    
    run_server(
        host=args.host,
        port=args.port,
        reload=not args.prod,
        workers=args.workers,
        debug=args.debug
    )


if __name__ == "__main__":
    main()
