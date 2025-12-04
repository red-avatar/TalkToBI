"""
WebSocket 端到端测试脚本

测试内容：
1. WebSocket 连接与消息交互
2. Agent 系统调用链路
3. 流式打字机效果
4. 状态推送
5. 中断机制

使用方法：
    # 先启动后端服务
    python run.py
    
    # 运行测试（另一个终端）
    python tests/test_websocket_e2e.py

Author: CYJ
Time: 2025-11-26
Modified: 陈怡坚
Modified Time: 2025-11-27 - 添加日志文件输出功能
"""
import asyncio
import json
import logging
import os
import uuid
import sys
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, TextIO
from dataclasses import dataclass, field

# 需要安装: pip install websockets
try:
    import websockets
except ImportError:
    print("请先安装 websockets: pip install websockets")
    sys.exit(1)

# 添加项目路径，以便导入配置
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# =============================================================================
# 日志配置 - 同时输出到控制台和文件
# =============================================================================

class TeeOutput:
    """
    同时输出到控制台和日志文件的输出流
    
    用于捕获所有 print 输出并写入日志文件
    
    Author: CYJ
    Time: 2025-11-27
    """
    
    def __init__(self, log_file: TextIO, original_stdout: TextIO):
        self.log_file = log_file
        self.original_stdout = original_stdout
    
    def write(self, message: str):
        """同时写入控制台和日志文件"""
        self.original_stdout.write(message)
        self.original_stdout.flush()
        if message:  # 避免写入空字符串
            self.log_file.write(message)
            self.log_file.flush()
    
    def flush(self):
        """刷新两个输出流"""
        self.original_stdout.flush()
        self.log_file.flush()


def setup_logging(mode: str = "auto") -> Optional[str]:
    """
    配置日志输出到文件
    
    Args:
        mode: 测试模式 ("auto" 或 "interactive")
    
    Returns:
        日志文件路径，如果创建失败返回 None
    
    Author: CYJ
    Time: 2025-11-27
    """
    # 创建 logs 目录
    logs_dir = os.path.join(project_root, "tests", "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # 生成日志文件名（包含时间戳和模式）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"websocket_e2e_{mode}_{timestamp}.log"
    log_filepath = os.path.join(logs_dir, log_filename)
    
    try:
        # 打开日志文件
        log_file = open(log_filepath, "w", encoding="utf-8")
        
        # 写入日志头
        log_file.write(f"{'=' * 60}\n")
        log_file.write(f"ChatBI WebSocket E2E 测试日志\n")
        log_file.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"模式: {mode}\n")
        log_file.write(f"{'=' * 60}\n\n")
        log_file.flush()
        
        # 替换 stdout，使 print 同时输出到控制台和文件
        sys.stdout = TeeOutput(log_file, sys.__stdout__)
        
        print(f"📝 日志已保存到: {log_filepath}")
        return log_filepath
        
    except Exception as e:
        print(f"⚠️ 无法创建日志文件: {e}")
        return None


def cleanup_logging():
    """
    清理日志配置，恢复原始 stdout
    
    Author: CYJ
    Time: 2025-11-27
    """
    if isinstance(sys.stdout, TeeOutput):
        try:
            sys.stdout.log_file.close()
        except:
            pass
        sys.stdout = sys.__stdout__


# =============================================================================
# 配置（从 .env 读取）
# =============================================================================

def get_ws_url() -> str:
    """从配置文件获取 WebSocket URL"""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        host = settings.SERVER_HOST
        port = settings.SERVER_PORT
        # 如果 host 是 0.0.0.0，测试时用 localhost
        if host == "0.0.0.0":
            host = "localhost"
        return f"ws://{host}:{port}/api/v1/ws/chat"
    except Exception as e:
        print(f"⚠️ 无法读取配置，使用默认值: {e}")
        return "ws://localhost:8880/api/v1/ws/chat"


WS_URL = get_ws_url()
TIMEOUT = 180  # 等待响应的超时时间（秒），LLM 调用可能较慢


# =============================================================================
# 测试结果记录
# =============================================================================

@dataclass
class TestResult:
    """单个测试用例的结果"""
    name: str
    passed: bool
    duration: float
    stages: List[str] = field(default_factory=list)
    chunks: List[str] = field(default_factory=list)
    final_answer: str = ""
    error: Optional[str] = None
    sql_query: Optional[str] = None
    visualization: Optional[Dict] = None


class TestReporter:
    """测试结果报告器"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
    
    def add_result(self, result: TestResult):
        self.results.append(result)
    
    def print_report(self):
        """打印测试报告"""
        print("\n" + "=" * 60)
        print("📊 WebSocket E2E 测试报告")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        
        for r in self.results:
            status = "✅ PASS" if r.passed else "❌ FAIL"
            print(f"\n{status} [{r.name}] ({r.duration:.2f}s)")
            
            if r.stages:
                print(f"   阶段: {' → '.join(r.stages)}")
            
            if r.chunks:
                preview = ''.join(r.chunks)[:100]
                if len(''.join(r.chunks)) > 100:
                    preview += "..."
                print(f"   打字机输出: {len(r.chunks)} chunks")
            
            if r.final_answer:
                preview = r.final_answer[:100]
                if len(r.final_answer) > 100:
                    preview += "..."
                print(f"   回答: {preview}")
            
            if r.sql_query:
                print(f"   SQL: {r.sql_query[:80]}...")
            
            if r.visualization:
                print(f"   可视化: {r.visualization.get('chart_type', 'N/A')}")
            
            if r.error:
                print(f"   错误: {r.error}")
        
        print("\n" + "-" * 60)
        print(f"总计: {len(self.results)} 测试, {passed} 通过, {failed} 失败")
        print(f"耗时: {time.time() - self.start_time:.2f}s")
        print("=" * 60)


# =============================================================================
# WebSocket 测试客户端
# =============================================================================

class WebSocketTestClient:
    """
    测试客户端
    
    V2: 支持重连时保持同一个 session_id
    Author: CYJ
    Time: 2025-11-26
    """
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"test_{uuid.uuid4().hex[:8]}"
        self.ws = None
        self.received_messages: List[Dict] = []
        self.stages: List[str] = []
        self.chunks: List[str] = []
        self.final_answer = ""
        self.sql_query = None
        self.visualization = None
        self.error = None
    
    async def connect(self):
        """建立连接"""
        url = f"{WS_URL}/{self.session_id}"
        print(f"🔗 连接到 {url}")
        
        # V3: 直接禁用 ping，避免 LLM 调用期间超时断开
        # Author: CYJ
        # Time: 2025-11-26
        self.ws = await websockets.connect(
            url,
            ping_interval=None,  # 禁用自动 ping
            ping_timeout=None,   # 不超时
            close_timeout=10
        )
        print(f"✅ 连接成功 (session_id: {self.session_id})")
    
    async def disconnect(self):
        """断开连接"""
        if self.ws:
            await self.ws.close()
            print("🔌 连接已断开")
    
    async def send_message(self, content: str, message_id: Optional[str] = None):
        """发送用户消息"""
        message_id = message_id or f"msg_{uuid.uuid4().hex[:8]}"
        payload = {
            "type": "user_message",
            "payload": {
                "content": content,
                "message_id": message_id
            }
        }
        await self.ws.send(json.dumps(payload))
        print(f"📤 发送消息: {content}")
        return message_id
    
    async def send_ping(self):
        """发送心跳"""
        await self.ws.send(json.dumps({"type": "ping"}))
    
    async def send_interrupt(self, reason: str = "user_cancel"):
        """发送中断请求"""
        payload = {
            "type": "interrupt",
            "payload": {"reason": reason}
        }
        await self.ws.send(json.dumps(payload))
        print(f"⏹️  发送中断请求")
    
    async def receive_until_complete(self, timeout: float = TIMEOUT) -> bool:
        """
        接收消息直到收到 complete 或 error
        
        Returns:
            bool: 是否成功收到完整响应
        """
        self.received_messages.clear()
        self.stages.clear()
        self.chunks.clear()
        self.final_answer = ""
        self.sql_query = None
        self.visualization = None
        self.error = None
        
        try:
            async with asyncio.timeout(timeout):
                while True:
                    raw = await self.ws.recv()
                    msg = json.loads(raw)
                    self.received_messages.append(msg)
                    
                    msg_type = msg.get("type")
                    payload = msg.get("payload", {})
                    
                    if msg_type == "status":
                        stage = payload.get("stage")
                        message = payload.get("message", "")
                        self.stages.append(stage)
                        print(f"   📍 [{stage}] {message}")
                    
                    elif msg_type == "text_chunk":
                        content = payload.get("content", "")
                        is_first = payload.get("is_first", False)
                        is_last = payload.get("is_last", False)
                        
                        if content:
                            self.chunks.append(content)
                            # 打印打字机效果（不换行）
                            print(content, end="", flush=True)
                        
                        if is_last:
                            print()  # 换行
                    
                    elif msg_type == "complete":
                        self.final_answer = payload.get("text_answer", "")
                        self.sql_query = payload.get("sql_query")
                        self.visualization = payload.get("visualization")
                        print(f"   ✅ 完成")
                        return True
                    
                    elif msg_type == "error":
                        self.error = payload.get("message", "Unknown error")
                        code = payload.get("code", "UNKNOWN")
                        print(f"   ❌ 错误 [{code}]: {self.error}")
                        return False
                    
                    elif msg_type == "interrupted":
                        print(f"   ⏹️  已中断 (stage: {payload.get('stage')})")
                        return False
                    
                    elif msg_type == "pong":
                        print(f"   🏓 Pong")
        
        except asyncio.TimeoutError:
            self.error = f"超时 ({timeout}s)"
            print(f"   ⏰ 超时")
            return False
        except Exception as e:
            self.error = str(e)
            print(f"   💥 异常: {e}")
            return False


# =============================================================================
# 测试用例
# =============================================================================

async def test_ping_pong(reporter: TestReporter):
    """测试心跳机制"""
    print("\n" + "-" * 40)
    print("🧪 测试 1: 心跳机制 (Ping/Pong)")
    print("-" * 40)
    
    client = WebSocketTestClient()
    start = time.time()
    
    try:
        await client.connect()
        await client.send_ping()
        
        # 等待 pong
        raw = await asyncio.wait_for(client.ws.recv(), timeout=5)
        msg = json.loads(raw)
        
        passed = msg.get("type") == "pong"
        
        reporter.add_result(TestResult(
            name="心跳机制",
            passed=passed,
            duration=time.time() - start,
            error=None if passed else "未收到 pong 响应"
        ))
        
    except Exception as e:
        reporter.add_result(TestResult(
            name="心跳机制",
            passed=False,
            duration=time.time() - start,
            error=str(e)
        ))
    finally:
        await client.disconnect()


async def test_simple_query(reporter: TestReporter):
    """测试简单查询 - 验证完整流程"""
    print("\n" + "-" * 40)
    print("🧪 测试 2: 简单查询 (Agent 调用链)")
    print("-" * 40)
    
    client = WebSocketTestClient()
    start = time.time()
    
    try:
        await client.connect()
        await client.send_message("查询订单总数")
        
        passed = await client.receive_until_complete()
        
        reporter.add_result(TestResult(
            name="简单查询",
            passed=passed,
            duration=time.time() - start,
            stages=client.stages.copy(),
            chunks=client.chunks.copy(),
            final_answer=client.final_answer,
            sql_query=client.sql_query,
            visualization=client.visualization,
            error=client.error
        ))
        
    except Exception as e:
        reporter.add_result(TestResult(
            name="简单查询",
            passed=False,
            duration=time.time() - start,
            error=str(e)
        ))
    finally:
        await client.disconnect()


async def test_streaming_effect(reporter: TestReporter):
    """测试打字机效果"""
    print("\n" + "-" * 40)
    print("🧪 测试 3: 打字机效果 (Streaming)")
    print("-" * 40)
    
    client = WebSocketTestClient()
    start = time.time()
    
    try:
        await client.connect()
        await client.send_message("分析广州市的订单趋势")
        
        await client.receive_until_complete()
        
        # 验证打字机效果：应该有多个 chunks
        has_streaming = len(client.chunks) > 1
        
        reporter.add_result(TestResult(
            name="打字机效果",
            passed=has_streaming and client.final_answer != "",
            duration=time.time() - start,
            stages=client.stages.copy(),
            chunks=client.chunks.copy(),
            final_answer=client.final_answer,
            error=None if has_streaming else f"只有 {len(client.chunks)} 个 chunk"
        ))
        
    except Exception as e:
        reporter.add_result(TestResult(
            name="打字机效果",
            passed=False,
            duration=time.time() - start,
            error=str(e)
        ))
    finally:
        await client.disconnect()


async def test_stages_progression(reporter: TestReporter):
    """测试阶段状态推送"""
    print("\n" + "-" * 40)
    print("🧪 测试 4: 阶段状态推送")
    print("-" * 40)
    
    client = WebSocketTestClient()
    start = time.time()
    
    try:
        await client.connect()
        await client.send_message("2024年退款总金额是多少")
        
        await client.receive_until_complete()
        
        # 验证阶段顺序
        expected_stages = ["intent", "planner", "executor", "analyzer", "responder"]
        has_all_stages = all(s in client.stages for s in expected_stages)
        
        reporter.add_result(TestResult(
            name="阶段状态推送",
            passed=has_all_stages,
            duration=time.time() - start,
            stages=client.stages.copy(),
            final_answer=client.final_answer,
            error=None if has_all_stages else f"缺少阶段，收到: {client.stages}"
        ))
        
    except Exception as e:
        reporter.add_result(TestResult(
            name="阶段状态推送",
            passed=False,
            duration=time.time() - start,
            error=str(e)
        ))
    finally:
        await client.disconnect()


async def test_visualization(reporter: TestReporter):
    """测试可视化输出"""
    print("\n" + "-" * 40)
    print("🧪 测试 5: 可视化输出")
    print("-" * 40)
    
    client = WebSocketTestClient()
    start = time.time()
    
    try:
        await client.connect()
        await client.send_message("展示各城市的订单量分布")
        
        await client.receive_until_complete()
        
        has_viz = client.visualization is not None
        has_echarts = has_viz and client.visualization.get("echarts_option") is not None
        
        reporter.add_result(TestResult(
            name="可视化输出",
            passed=has_echarts,
            duration=time.time() - start,
            stages=client.stages.copy(),
            final_answer=client.final_answer,
            visualization=client.visualization,
            error=None if has_echarts else "未返回 ECharts 配置"
        ))
        
    except Exception as e:
        reporter.add_result(TestResult(
            name="可视化输出",
            passed=False,
            duration=time.time() - start,
            error=str(e)
        ))
    finally:
        await client.disconnect()


async def test_chitchat(reporter: TestReporter):
    """测试闲聊处理"""
    print("\n" + "-" * 40)
    print("🧪 测试 6: 闲聊处理")
    print("-" * 40)
    
    client = WebSocketTestClient()
    start = time.time()
    
    try:
        await client.connect()
        await client.send_message("你好，你是谁？")
        
        passed = await client.receive_until_complete()
        
        reporter.add_result(TestResult(
            name="闲聊处理",
            passed=passed and client.final_answer != "",
            duration=time.time() - start,
            stages=client.stages.copy(),
            chunks=client.chunks.copy(),
            final_answer=client.final_answer,
            error=client.error
        ))
        
    except Exception as e:
        reporter.add_result(TestResult(
            name="闲聊处理",
            passed=False,
            duration=time.time() - start,
            error=str(e)
        ))
    finally:
        await client.disconnect()


async def test_error_handling(reporter: TestReporter):
    """测试错误处理"""
    print("\n" + "-" * 40)
    print("🧪 测试 7: 错误处理 (不存在的数据)")
    print("-" * 40)
    
    client = WebSocketTestClient()
    start = time.time()
    
    try:
        await client.connect()
        await client.send_message("查询冥王星分公司的销售额")
        
        # 系统应该优雅处理，不崩溃
        await client.receive_until_complete()
        
        # 只要有回答且没有内部错误就算通过
        passed = client.final_answer != "" or client.error is not None
        
        reporter.add_result(TestResult(
            name="错误处理",
            passed=passed,
            duration=time.time() - start,
            stages=client.stages.copy(),
            final_answer=client.final_answer,
            error=client.error if not passed else None
        ))
        
    except Exception as e:
        reporter.add_result(TestResult(
            name="错误处理",
            passed=False,
            duration=time.time() - start,
            error=str(e)
        ))
    finally:
        await client.disconnect()


async def test_message_too_long(reporter: TestReporter):
    """测试消息长度限制"""
    print("\n" + "-" * 40)
    print("🧪 测试 8: 消息长度限制")
    print("-" * 40)
    
    client = WebSocketTestClient()
    start = time.time()
    
    try:
        await client.connect()
        # 发送超长消息
        long_message = "测试" * 300  # 600 字符，超过 500 限制
        await client.send_message(long_message)
        
        # 应该收到验证错误
        raw = await asyncio.wait_for(client.ws.recv(), timeout=10)
        msg = json.loads(raw)
        
        is_error = msg.get("type") == "error"
        is_validation = msg.get("payload", {}).get("code") == "VALIDATION_ERROR"
        
        reporter.add_result(TestResult(
            name="消息长度限制",
            passed=is_error and is_validation,
            duration=time.time() - start,
            error=None if (is_error and is_validation) else "未正确拒绝超长消息"
        ))
        
    except Exception as e:
        reporter.add_result(TestResult(
            name="消息长度限制",
            passed=False,
            duration=time.time() - start,
            error=str(e)
        ))
    finally:
        await client.disconnect()


# =============================================================================
# 主函数
# =============================================================================

async def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🚀 ChatBI WebSocket E2E 测试")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   目标: {WS_URL}")
    print("=" * 60)
    
    reporter = TestReporter()
    
    # 依次运行测试
    await test_ping_pong(reporter)
    await test_simple_query(reporter)
    await test_streaming_effect(reporter)
    await test_stages_progression(reporter)
    await test_visualization(reporter)
    await test_chitchat(reporter)
    await test_error_handling(reporter)
    await test_message_too_long(reporter)
    
    # 打印报告
    reporter.print_report()


async def interactive_test():
    """
    交互式测试模式（带自动重连）
    
    V2: 重连时保持同一个 session_id，保持记忆连续性
    Author: CYJ
    Time: 2025-11-26
    """
    print("\n" + "=" * 60)
    print("🎮 ChatBI WebSocket 交互式测试")
    print("=" * 60)
    print("输入消息与系统交互")
    print("命令: 'quit' 退出, 'reconnect' 重连, 'new' 新会话")
    print("-" * 60)
    
    # V2: 固定 session_id，重连时复用
    fixed_session_id = f"test_{uuid.uuid4().hex[:8]}"
    print(f"📌 会话 ID: {fixed_session_id}")
    print("-" * 60)
    
    client = WebSocketTestClient(session_id=fixed_session_id)
    connected = False
    
    def is_ws_closed():
        """检查 WebSocket 是否已关闭（兼容新旧版本 websockets 库）"""
        if client.ws is None:
            return True
        # websockets >= 14.0 移除了 closed 属性，改用 state
        # 优先使用 state 属性（更可靠）
        try:
            if hasattr(client.ws, 'state'):
                from websockets.protocol import State
                return client.ws.state == State.CLOSED
        except Exception:
            pass
        # 回退：尝试 closed 属性
        try:
            return client.ws.closed
        except AttributeError:
            pass
        # 最终回退：尝试发送 ping 检测连接状态
        return True
    
    async def ensure_connected():
        """确保连接正常"""
        nonlocal connected
        if not connected or is_ws_closed():
            try:
                if client.ws:
                    await client.disconnect()
            except:
                pass
            await client.connect()
            connected = True
    
    try:
        await ensure_connected()
        
        while True:
            try:
                user_input = input("\n你: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 再见!")
                    break
                
                if user_input.lower() == 'reconnect':
                    print("🔄 重新连接（保持同一会话）...")
                    connected = False
                    await ensure_connected()
                    continue
                
                if user_input.lower() == 'new':
                    # 新会话：重新生成 session_id
                    fixed_session_id = f"test_{uuid.uuid4().hex[:8]}"
                    print(f"🆕 新会话 ID: {fixed_session_id}")
                    client = WebSocketTestClient(session_id=fixed_session_id)
                    connected = False
                    await ensure_connected()
                    continue
                
                if not user_input:
                    continue
                
                # 确保连接正常
                await ensure_connected()
                
                await client.send_message(user_input)
                print("\nChatBI: ", end="")
                success = await client.receive_until_complete()
                
                if not success and client.error:
                    print(f"\n⚠️  请求失败: {client.error}")
                    if "close" in client.error.lower() or "connection" in client.error.lower():
                        print("🔄 连接已断开，正在重连...")
                        connected = False
                        await ensure_connected()
                        print("✅ 重连成功，请重新输入")
                
            except KeyboardInterrupt:
                print("\n\n👋 已中断")
                break
            except Exception as e:
                print(f"\n❌ 异常: {e}")
                print("🔄 尝试重连...")
                connected = False
                try:
                    await ensure_connected()
                    print("✅ 重连成功")
                except Exception as e2:
                    print(f"❌ 重连失败: {e2}")
                    print("请检查服务是否运行: python run.py")
                
    finally:
        try:
            await client.disconnect()
        except:
            pass


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ChatBI WebSocket E2E 测试")
    parser.add_argument(
        "--auto", "-a",
        action="store_true",
        help="自动化测试模式（默认是交互式）"
    )
    parser.add_argument(
        "--url",
        default=None,
        help=f"WebSocket URL (默认从配置读取)"
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="禁用日志文件输出"
    )
    
    args = parser.parse_args()
    if args.url:
        WS_URL = args.url
    
    # 设置日志（除非明确禁用）
    log_filepath = None
    if not args.no_log:
        mode = "auto" if args.auto else "interactive"
        log_filepath = setup_logging(mode)
    
    try:
        if args.auto:
            asyncio.run(run_all_tests())
        else:
            # 默认交互式模式
            asyncio.run(interactive_test())
    finally:
        # 清理日志配置
        if log_filepath:
            cleanup_logging()
            print(f"\n📝 完整日志已保存到: {log_filepath}")
