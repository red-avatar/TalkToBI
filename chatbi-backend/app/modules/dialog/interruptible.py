"""
可中断任务模块

提供可中断的异步任务支持，用于 WebSocket 流式处理

Author: CYJ
Time: 2025-11-26
"""
import asyncio
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

from app.schemas.ws_messages import ProcessingStage

logger = logging.getLogger(__name__)


class TaskInterruptedError(Exception):
    """任务被中断异常"""
    
    def __init__(
        self,
        stage: Optional[ProcessingStage] = None,
        partial_result: Optional[str] = None,
        message: str = "Task was interrupted"
    ):
        self.stage = stage
        self.partial_result = partial_result
        super().__init__(message)


class TaskCancelledError(Exception):
    """任务被取消异常（用户主动取消）"""
    pass


@dataclass
class InterruptibleTask:
    """
    可中断的异步任务
    
    用于在流式处理过程中检查是否需要中断
    
    使用示例:
        task = InterruptibleTask(message_id="msg_001")
        
        try:
            task.set_stage(ProcessingStage.INTENT)
            await task.check_interrupt()
            # ... 执行意图识别 ...
            
            task.set_stage(ProcessingStage.PLANNER)
            await task.check_interrupt()
            # ... 执行SQL规划 ...
            
        except TaskInterruptedError as e:
            # 处理中断
            logger.info(f"Task interrupted at stage {e.stage}")
    """
    
    message_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # 内部状态
    _cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    _current_stage: Optional[ProcessingStage] = field(default=None)
    _partial_result: str = field(default="")
    _is_completed: bool = field(default=False)
    
    def __post_init__(self):
        """确保 Event 对象正确初始化"""
        if not isinstance(self._cancelled, asyncio.Event):
            self._cancelled = asyncio.Event()
    
    def cancel(self) -> None:
        """
        请求取消任务
        
        调用此方法后，下次 check_interrupt() 将抛出 TaskInterruptedError
        """
        logger.info(f"[InterruptibleTask] 请求取消任务: {self.message_id}, stage={self._current_stage}")
        self._cancelled.set()
    
    def is_cancelled(self) -> bool:
        """检查任务是否已被取消"""
        return self._cancelled.is_set()
    
    def is_completed(self) -> bool:
        """检查任务是否已完成"""
        return self._is_completed
    
    def set_stage(self, stage: ProcessingStage) -> None:
        """
        设置当前处理阶段
        
        Args:
            stage: 当前阶段
        """
        self._current_stage = stage
        logger.debug(f"[InterruptibleTask] 进入阶段: {stage.value}")
    
    def get_stage(self) -> Optional[ProcessingStage]:
        """获取当前处理阶段"""
        return self._current_stage
    
    def append_partial_result(self, text: str) -> None:
        """
        追加部分结果
        
        用于在流式输出时保存已生成的内容，中断时可返回
        """
        self._partial_result += text
    
    def get_partial_result(self) -> str:
        """获取部分结果"""
        return self._partial_result
    
    def mark_completed(self) -> None:
        """标记任务完成"""
        self._is_completed = True
    
    async def check_interrupt(self) -> None:
        """
        检查是否需要中断
        
        在关键节点调用此方法，如果任务已被取消，将抛出 TaskInterruptedError
        
        Raises:
            TaskInterruptedError: 任务被中断
        """
        # 让出控制权，允许其他协程运行
        await asyncio.sleep(0)
        
        if self._cancelled.is_set():
            logger.info(f"[InterruptibleTask] 检测到中断信号: {self.message_id}, stage={self._current_stage}")
            raise TaskInterruptedError(
                stage=self._current_stage,
                partial_result=self._partial_result if self._partial_result else None
            )
    
    def reset(self) -> None:
        """
        重置任务状态
        
        用于复用任务对象
        """
        self._cancelled.clear()
        self._current_stage = None
        self._partial_result = ""
        self._is_completed = False


class TaskManager:
    """
    任务管理器
    
    管理多个可中断任务，支持按消息ID查找和取消
    """
    
    def __init__(self):
        self._tasks: dict[str, InterruptibleTask] = {}
    
    def create_task(self, message_id: str) -> InterruptibleTask:
        """
        创建新任务
        
        如果已存在同ID任务，先取消旧任务
        """
        # 取消旧任务
        if message_id in self._tasks:
            self._tasks[message_id].cancel()
        
        # 创建新任务
        task = InterruptibleTask(message_id=message_id)
        self._tasks[message_id] = task
        logger.debug(f"[TaskManager] 创建任务: {message_id}")
        return task
    
    def get_task(self, message_id: str) -> Optional[InterruptibleTask]:
        """获取任务"""
        return self._tasks.get(message_id)
    
    def cancel_task(self, message_id: str) -> bool:
        """
        取消任务
        
        Returns:
            是否成功找到并取消任务
        """
        task = self._tasks.get(message_id)
        if task:
            task.cancel()
            return True
        return False
    
    def cancel_all(self) -> int:
        """
        取消所有任务
        
        Returns:
            取消的任务数量
        """
        count = 0
        for task in self._tasks.values():
            if not task.is_cancelled() and not task.is_completed():
                task.cancel()
                count += 1
        return count
    
    def remove_task(self, message_id: str) -> None:
        """移除任务"""
        self._tasks.pop(message_id, None)
    
    def cleanup_completed(self) -> int:
        """
        清理已完成的任务
        
        Returns:
            清理的任务数量
        """
        to_remove = [
            msg_id for msg_id, task in self._tasks.items()
            if task.is_completed() or task.is_cancelled()
        ]
        for msg_id in to_remove:
            del self._tasks[msg_id]
        return len(to_remove)
    
    def get_active_count(self) -> int:
        """获取活跃任务数量"""
        return sum(
            1 for task in self._tasks.values()
            if not task.is_completed() and not task.is_cancelled()
        )
