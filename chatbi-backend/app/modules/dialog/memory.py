"""
功能：共享记忆与状态持久化 (Shared Memory)
说明：
    提供基于 LangGraph Checkpointer 的记忆机制。
    目前使用内存存储 (MemorySaver)，未来可替换为 RedisSaver 或 PostgresSaver 实现持久化。
作者：CYJ
时间：2025-11-22
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
import logging

logger = logging.getLogger(__name__)

class SharedMemory:
    _instance = None
    _checkpointer: BaseCheckpointSaver = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SharedMemory, cls).__new__(cls)
            # Initialize Checkpointer
            # In production, use AsyncSqliteSaver or RedisSaver
            cls._checkpointer = MemorySaver()
            logger.info("Initialized In-Memory Shared Memory")
        return cls._instance

    def get_checkpointer(self) -> BaseCheckpointSaver:
        """获取 LangGraph 检查点保存器"""
        return self._checkpointer

    def get_state(self, thread_id: str):
        """Get current state snapshot for a thread."""
        config = {"configurable": {"thread_id": thread_id}}
        return self._checkpointer.get(config)

# Global accessor
def get_memory_checkpointer():
    return SharedMemory().get_checkpointer()
