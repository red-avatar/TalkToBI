"""
会话管理器

管理 WebSocket 对话会话，支持多轮对话、历史记录、过期清理

Author: CYJ
Time: 2025-11-26
"""
import asyncio
from typing import Optional, Dict, Any, List, Literal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import threading

from app.core.config import get_settings
from app.modules.dialog.interruptible import InterruptibleTask, TaskManager

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ChatMessage:
    """对话消息"""
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # 仅 assistant 消息有
    sql_query: Optional[str] = None
    data_insight: Optional[Dict[str, Any]] = None
    visualization: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.sql_query:
            data["sql_query"] = self.sql_query
        if self.data_insight:
            data["data_insight"] = self.data_insight
        if self.visualization:
            data["visualization"] = self.visualization
        return data


@dataclass
class ChatSession:
    """
    对话会话
    
    包含会话的所有状态信息，用于多轮对话
    """
    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active_at: datetime = field(default_factory=datetime.utcnow)
    
    # 消息历史（不限制数量）
    messages: List[ChatMessage] = field(default_factory=list)
    
    # 上下文状态（用于多轮对话）
    context: Dict[str, Any] = field(default_factory=dict)
    # context 包含:
    # - verified_entity_mappings: Dict[str, str]  # 实体映射缓存
    # - verified_schema_knowledge: Dict          # Schema知识缓存
    # - last_intent: Dict                        # 上一轮意图
    
    # 当前处理状态
    current_task: Optional[InterruptibleTask] = field(default=None)
    is_processing: bool = field(default=False)
    
    # 任务管理器
    task_manager: TaskManager = field(default_factory=TaskManager)
    
    def update_activity(self) -> None:
        """更新最后活跃时间"""
        self.last_active_at = datetime.utcnow()
    
    def add_user_message(self, message_id: str, content: str) -> ChatMessage:
        """添加用户消息"""
        msg = ChatMessage(
            message_id=message_id,
            role="user",
            content=content
        )
        self.messages.append(msg)
        self.update_activity()
        return msg
    
    def add_assistant_message(
        self,
        message_id: str,
        content: str,
        sql_query: Optional[str] = None,
        data_insight: Optional[Dict[str, Any]] = None,
        visualization: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """添加助手消息"""
        msg = ChatMessage(
            message_id=message_id,
            role="assistant",
            content=content,
            sql_query=sql_query,
            data_insight=data_insight,
            visualization=visualization
        )
        self.messages.append(msg)
        self.update_activity()
        return msg
    
    def get_history(
        self,
        limit: int = 50,
        before_message_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取历史消息
        
        Args:
            limit: 获取数量
            before_message_id: 分页游标（获取此消息之前的消息）
            
        Returns:
            消息列表
        """
        messages = self.messages
        
        # 如果指定了游标，找到对应位置
        if before_message_id:
            cursor_idx = None
            for i, msg in enumerate(messages):
                if msg.message_id == before_message_id:
                    cursor_idx = i
                    break
            if cursor_idx is not None:
                messages = messages[:cursor_idx]
        
        # 取最后 N 条
        result = messages[-limit:] if len(messages) > limit else messages
        return [msg.to_dict() for msg in result]
    
    def get_context_for_llm(self) -> List[Dict[str, str]]:
        """
        获取用于 LLM 的对话上下文
        
        返回最近的对话历史，用于多轮对话
        """
        # 取最近 10 轮对话作为上下文
        recent_messages = self.messages[-20:]  # 10 轮 = 20 条消息
        
        context = []
        for msg in recent_messages:
            context.append({
                "role": msg.role,
                "content": msg.content
            })
        return context
    
    def update_context(self, key: str, value: Any) -> None:
        """更新会话上下文"""
        self.context[key] = value
        self.update_activity()
    
    def get_context_value(self, key: str, default: Any = None) -> Any:
        """获取会话上下文值"""
        return self.context.get(key, default)
    
    def is_expired(self, expire_seconds: int) -> bool:
        """检查会话是否过期"""
        expire_time = self.last_active_at + timedelta(seconds=expire_seconds)
        return datetime.utcnow() > expire_time


class SessionManager:
    """
    会话管理器
    
    管理所有活跃会话，支持：
    - 创建/获取/销毁会话
    - 维护会话上下文
    - 处理中断请求
    - 自动清理过期会话
    """
    
    _instance: Optional['SessionManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._sessions: Dict[str, ChatSession] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._initialized = True
        
        logger.info("[SessionManager] 初始化完成")
    
    def get_or_create(self, session_id: str) -> ChatSession:
        """
        获取或创建会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            ChatSession 对象
        """
        if session_id not in self._sessions:
            session = ChatSession(session_id=session_id)
            self._sessions[session_id] = session
            logger.info(f"[SessionManager] 创建新会话: {session_id}")
        else:
            session = self._sessions[session_id]
            session.update_activity()
            logger.debug(f"[SessionManager] 获取已有会话: {session_id}")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        获取会话（不创建）
        
        Args:
            session_id: 会话ID
            
        Returns:
            ChatSession 或 None
        """
        session = self._sessions.get(session_id)
        if session:
            session.update_activity()
        return session
    
    def destroy_session(self, session_id: str) -> bool:
        """
        销毁会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功销毁
        """
        session = self._sessions.pop(session_id, None)
        if session:
            # 取消所有任务
            session.task_manager.cancel_all()
            logger.info(f"[SessionManager] 销毁会话: {session_id}")
            return True
        return False
    
    def interrupt_session(self, session_id: str, message_id: Optional[str] = None) -> bool:
        """
        中断会话的当前任务
        
        Args:
            session_id: 会话ID
            message_id: 要中断的消息ID（可选）
            
        Returns:
            是否成功中断
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        if message_id:
            return session.task_manager.cancel_task(message_id)
        elif session.current_task:
            session.current_task.cancel()
            return True
        
        return False
    
    def cleanup_expired(self, max_idle_seconds: Optional[int] = None) -> int:
        """
        清理过期会话
        
        Args:
            max_idle_seconds: 最大空闲时间（秒），默认使用配置值
            
        Returns:
            清理的会话数量
        """
        if max_idle_seconds is None:
            max_idle_seconds = settings.CHAT_SESSION_EXPIRE_SECONDS
        
        to_remove = []
        for session_id, session in self._sessions.items():
            if session.is_expired(max_idle_seconds):
                to_remove.append(session_id)
        
        for session_id in to_remove:
            self.destroy_session(session_id)
        
        if to_remove:
            logger.info(f"[SessionManager] 清理 {len(to_remove)} 个过期会话")
        
        return len(to_remove)
    
    def get_active_session_count(self) -> int:
        """获取活跃会话数量"""
        return len(self._sessions)
    
    def get_session_ids(self) -> List[str]:
        """获取所有会话ID"""
        return list(self._sessions.keys())
    
    async def start_cleanup_task(self, interval_seconds: int = 300) -> None:
        """
        启动定期清理任务
        
        Args:
            interval_seconds: 清理间隔（秒），默认5分钟
        """
        if self._cleanup_task and not self._cleanup_task.done():
            return
        
        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_seconds)
                try:
                    self.cleanup_expired()
                except Exception as e:
                    logger.error(f"[SessionManager] 清理任务异常: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"[SessionManager] 启动定期清理任务，间隔 {interval_seconds} 秒")
    
    def stop_cleanup_task(self) -> None:
        """停止定期清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("[SessionManager] 停止定期清理任务")


# 全局会话管理器实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取会话管理器实例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
