"""
ChatBI 可观测性模块 (Observability)

功能:
1. 链路追踪 - 生成 trace_id，贯穿整个请求生命周期
2. 节点耗时统计 - 记录每个 LangGraph 节点的执行时间
3. LLM 调用统计 - 记录 LLM 调用次数
4. 请求级指标汇总 - 单次请求的完整耗时分解

使用方式:
    from app.core.observability import TraceContext, trace_node, get_request_metrics
    
    # 开始请求追踪
    with TraceContext() as ctx:
        # 节点函数会自动记录耗时
        result = some_node(state)
        
        # 获取当前请求的指标
        metrics = get_request_metrics()

Author: CYJ
"""
import time
import uuid
import logging
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# =============================================================================
# 线程局部存储 - 用于跨函数传递追踪上下文
# =============================================================================
_trace_context = threading.local()

@dataclass
class RequestMetrics:
    """单次请求的指标数据"""
    trace_id: str
    start_time: float
    end_time: Optional[float] = None
    node_timings: Dict[str, float] = field(default_factory=dict)  # {node_name: duration_seconds}
    llm_call_count: int = 0
    llm_total_time: float = 0.0
    error_count: int = 0
    
    @property
    def total_duration(self) -> float:
        """总耗时（秒）"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 API 返回"""
        return {
            "trace_id": self.trace_id,
            "total_duration_ms": round(self.total_duration * 1000, 2),
            "node_timings_ms": {k: round(v * 1000, 2) for k, v in self.node_timings.items()},
            "llm_call_count": self.llm_call_count,
            "llm_total_time_ms": round(self.llm_total_time * 1000, 2),
            "error_count": self.error_count
        }
    
    def summary(self) -> str:
        """生成可读的摘要"""
        lines = [f"[trace_id={self.trace_id[:8]}] 请求指标汇总"]
        lines.append(f"  总耗时: {self.total_duration:.2f}s")
        lines.append(f"  LLM调用: {self.llm_call_count}次, 耗时: {self.llm_total_time:.2f}s")
        if self.node_timings:
            lines.append("  节点耗时:")
            for node, duration in self.node_timings.items():
                lines.append(f"    - {node}: {duration:.2f}s")
        if self.error_count > 0:
            lines.append(f"  错误数: {self.error_count}")
        return "\n".join(lines)

# =============================================================================
# 追踪上下文管理器
# =============================================================================

class TraceContext:
    """
    请求追踪上下文管理器
    
    使用方式:
        with TraceContext() as ctx:
            # 在这个 block 内的所有操作都会被追踪
            result = orchestrator_app.invoke(state)
            
        # 获取指标
        metrics = ctx.metrics
        
    Author: CYJ
    """
    
    def __init__(self, trace_id: Optional[str] = None):
        """
        初始化追踪上下文
        
        Args:
            trace_id: 可选的 trace_id，不传则自动生成
        """
        self.trace_id = trace_id or str(uuid.uuid4())
        self.metrics = RequestMetrics(
            trace_id=self.trace_id,
            start_time=time.time()
        )
    
    def __enter__(self) -> "TraceContext":
        """进入上下文，将当前追踪设置为线程局部变量"""
        _trace_context.current = self
        logger.debug(f"[trace_id={self.trace_id[:8]}] 开始追踪")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，记录结束时间并清理"""
        self.metrics.end_time = time.time()
        
        # 输出指标摘要
        logger.info(self.metrics.summary())
        
        # 清理线程局部变量
        _trace_context.current = None
        return False  # 不吞掉异常

def get_current_trace() -> Optional[TraceContext]:
    """获取当前请求的追踪上下文"""
    return getattr(_trace_context, 'current', None)

def get_trace_id() -> Optional[str]:
    """获取当前 trace_id，用于日志关联"""
    ctx = get_current_trace()
    return ctx.trace_id if ctx else None

def get_request_metrics() -> Optional[RequestMetrics]:
    """获取当前请求的指标"""
    ctx = get_current_trace()
    return ctx.metrics if ctx else None

# =============================================================================
# 指标记录函数
# =============================================================================

def record_node_timing(node_name: str, duration: float) -> None:
    """
    记录节点执行耗时
    
    Args:
        node_name: 节点名称
        duration: 耗时（秒）
    """
    ctx = get_current_trace()
    if ctx:
        ctx.metrics.node_timings[node_name] = duration
        trace_prefix = f"[trace_id={ctx.trace_id[:8]}]"
    else:
        trace_prefix = ""
    
    logger.info(f"{trace_prefix} {node_name} 耗时: {duration:.2f}s")

def record_llm_call(duration: float) -> None:
    """
    记录一次 LLM 调用
    
    Args:
        duration: 调用耗时（秒）
    """
    ctx = get_current_trace()
    if ctx:
        ctx.metrics.llm_call_count += 1
        ctx.metrics.llm_total_time += duration

def record_error() -> None:
    """记录一次错误"""
    ctx = get_current_trace()
    if ctx:
        ctx.metrics.error_count += 1

# =============================================================================
# 装饰器 - 自动记录节点耗时
# =============================================================================

def trace_node(func: Callable) -> Callable:
    """
    节点追踪装饰器 - 自动记录节点执行耗时
    
    使用方式:
        @trace_node
        def intent_node(state: AgentState) -> dict:
            ...
            
    Author: CYJ
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start
            record_node_timing(func.__name__, duration)
    
    return wrapper

@contextmanager
def trace_llm_call():
    """
    LLM 调用追踪上下文管理器
    
    使用方式:
        with trace_llm_call():
            response = llm.invoke(messages)
            
    Author: CYJ
    """
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        record_llm_call(duration)

# =============================================================================
# 全局指标统计（跨请求累积）
# =============================================================================

class GlobalMetrics:
    """
    全局指标统计（进程级别）
    
    用于监控系统整体健康状态
    
    Author: CYJ
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_metrics()
        return cls._instance
    
    def _init_metrics(self):
        """初始化指标"""
        self._lock_stats = threading.Lock()
        self.total_requests = 0
        self.total_errors = 0
        self.total_llm_calls = 0
        self.total_llm_time = 0.0
        self.node_total_times: Dict[str, float] = {}
        self.node_call_counts: Dict[str, int] = {}
    
    def record_request_complete(self, metrics: RequestMetrics) -> None:
        """记录一次请求完成"""
        with self._lock_stats:
            self.total_requests += 1
            self.total_errors += metrics.error_count
            self.total_llm_calls += metrics.llm_call_count
            self.total_llm_time += metrics.llm_total_time
            
            for node, duration in metrics.node_timings.items():
                if node not in self.node_total_times:
                    self.node_total_times[node] = 0.0
                    self.node_call_counts[node] = 0
                self.node_total_times[node] += duration
                self.node_call_counts[node] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取全局统计"""
        with self._lock_stats:
            avg_node_times = {}
            for node in self.node_total_times:
                count = self.node_call_counts.get(node, 1)
                avg_node_times[node] = round(self.node_total_times[node] / count * 1000, 2)
            
            return {
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "error_rate": round(self.total_errors / max(self.total_requests, 1) * 100, 2),
                "total_llm_calls": self.total_llm_calls,
                "avg_llm_calls_per_request": round(self.total_llm_calls / max(self.total_requests, 1), 2),
                "total_llm_time_s": round(self.total_llm_time, 2),
                "avg_node_times_ms": avg_node_times
            }

def get_global_metrics() -> GlobalMetrics:
    """获取全局指标单例"""
    return GlobalMetrics()
