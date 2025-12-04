"""
流式编排器 (V2)

设计理念：
- 复用现有的 orchestrator_app (LangGraph)，不重复实现 agent 调用逻辑
- orchestrator_app 已经带有记忆功能 (MemorySaver)
- 本模块只做传输层：
  - 传输状态更新
  - 传输打字机效果
  - 传输分析结果

Author: CYJ
Time: 2025-11-26 (V2)
"""
import asyncio
import uuid
from typing import AsyncGenerator, Dict, Any, Optional, List
from langchain_core.messages import HumanMessage, AIMessage
import logging

from app.core.config import get_settings
from app.schemas.ws_messages import (
    ProcessingStage,
    ErrorCode,
    create_status_message,
    create_text_chunk_message,
    create_complete_message,
    create_error_message,
    get_stage_description,
)
from app.modules.dialog.interruptible import InterruptibleTask, TaskInterruptedError
from app.modules.dialog.session_manager import ChatSession
# 复用现有的 orchestrator_app
from app.modules.dialog.orchestrator import orchestrator_app
# Phase 6: 执行日志记录 (Author: CYJ, Time: 2025-11-29)
from app.services.execution_log_service import get_execution_log_service
import time

logger = logging.getLogger(__name__)
settings = get_settings()


# 节点名称到处理阶段的映射
NODE_TO_STAGE = {
    "intent_node": ProcessingStage.INTENT,
    "planner_node": ProcessingStage.PLANNER,
    "executor_node": ProcessingStage.EXECUTOR,
    "analyzer_node": ProcessingStage.ANALYZER,
    "responder_node": ProcessingStage.RESPONDER,
    "diagnoser_node": ProcessingStage.PLANNER,
    "schema_completer_node": ProcessingStage.PLANNER,
}

NODE_TO_PROGRESS = {
    "intent_node": 15,
    "planner_node": 35,
    "executor_node": 55,
    "analyzer_node": 75,
    "responder_node": 90,
}


class StreamOrchestrator:
    """
    流式编排器 (V2)
    
    核心设计：
    1. 复用 orchestrator_app（LangGraph 编排器，带 MemorySaver 记忆）
    2. 通过 stream() 获取各节点输出
    3. 推送状态更新到 WebSocket
    4. 最终回答模拟打字机效果
    """
    
    async def process_stream(
        self,
        message: str,
        session: ChatSession,
        task: InterruptibleTask,
        client_message_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式处理用户消息
        
        使用 orchestrator_app.stream() 复用完整的 agent 系统（带记忆）
        
        Args:
            message: 用户消息内容
            session: 会话对象（用于 WebSocket 层记录）
            task: 可中断任务对象
            client_message_id: 客户端消息ID
            
        Yields:
            WebSocket 消息字典
        """
        server_message_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        # 使用 session_id 作为 LangGraph 的 thread_id（记忆隔离）
        thread_id = session.session_id
        config = {"configurable": {"thread_id": thread_id}}
        
        # 构建输入状态
        state_input = {"messages": [HumanMessage(content=message)]}
        
        logger.info(f"[StreamOrchestrator] 开始处理: thread_id={thread_id}, message={message[:50]}...")
        
        # Phase 6: 记录执行日志 (Author: CYJ, Time: 2025-11-29)
        log_service = get_execution_log_service()
        start_time = time.time()
        log_id = log_service.log_execution(
            query_text=message,
            status="pending",
            session_id=thread_id,
            message_id=client_message_id
        )
        
        try:
            # 记录最终状态
            final_state = {}
            
            # 使用 orchestrator_app.stream() 流式获取各节点输出（线程内同步 -> 队列异步消费，实时推送）
            # 注意：必须使用 get_running_loop() 而不是 get_event_loop()，后者在 Python 3.10+ 中可能返回错误的循环
            loop = asyncio.get_running_loop()
            from asyncio import Queue
            q: Queue = Queue()
            SENTINEL = object()
            
            def stream_worker():
                """在工作线程里同步迭代 LangGraph 流，并把事件推到异步队列。"""
                try:
                    for event in orchestrator_app.stream(state_input, config=config):
                        # 把事件线程安全地放入队列
                        loop.call_soon_threadsafe(q.put_nowait, event)
                except Exception as e:
                    # 将异常以错误事件形式传回主循环
                    loop.call_soon_threadsafe(q.put_nowait, {"__error__": str(e)})
                finally:
                    # 通知消费端结束
                    loop.call_soon_threadsafe(q.put_nowait, SENTINEL)
            
            # 启动工作线程
            worker_fut = loop.run_in_executor(None, stream_worker)
            
            # 实时消费事件并推送阶段状态
            while True:
                await task.check_interrupt()
                event = await q.get()
                if event is SENTINEL:
                    break
                if isinstance(event, dict) and "__error__" in event:
                    raise RuntimeError(event["__error__"])  # 由下方统一异常处理
                
                for node_name, node_output in event.items():
                    # 更新最终状态
                    if isinstance(node_output, dict):
                        final_state.update(node_output)
                    
                    # 获取对应的处理阶段
                    stage = NODE_TO_STAGE.get(node_name)
                    progress = NODE_TO_PROGRESS.get(node_name, 50)
                    
                    if stage:
                        task.set_stage(stage)
                        
                        # 推送状态更新（实时）
                        yield create_status_message(
                            stage=stage,
                            message=get_stage_description(stage),
                            message_id=client_message_id,
                            progress=progress
                        )
                    
                    logger.debug(f"[StreamOrchestrator] 节点完成: {node_name}")
            
            # 获取最终回答
            final_answer = final_state.get("final_answer", "")
            
            if not final_answer:
                yield create_error_message(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="未能生成回答，请重试",
                    message_id=client_message_id,
                    recoverable=True
                )
                return
            
            # 打字机效果：将回答拆分成块
            task.set_stage(ProcessingStage.RESPONDER)
            chunks = self._split_into_chunks(final_answer, chunk_size=3)
            
            for i, chunk in enumerate(chunks):
                await task.check_interrupt()
                task.append_partial_result(chunk)
                
                yield create_text_chunk_message(
                    content=chunk,
                    message_id=client_message_id,
                    chunk_index=i,
                    is_first=(i == 0),
                    is_last=False
                )
                await asyncio.sleep(0.02)  # 模拟打字延迟
            
            # 最后一个 chunk
            yield create_text_chunk_message(
                content="",
                message_id=client_message_id,
                chunk_index=len(chunks),
                is_first=False,
                is_last=True
            )
            
            # 构建可视化配置
            visualization = self._build_visualization(final_state)
            
            # 构建调试信息（仅在 DEBUG_MODE 开启时）
            debug_info = self._build_debug_info(final_state) if settings.DEBUG_MODE else None
            
            # 完成消息
            yield create_complete_message(
                message_id=server_message_id,
                text_answer=final_answer,
                reply_to=client_message_id,
                sql_query=final_state.get("sql_query"),
                data_insight=final_state.get("data_insight"),
                visualization=visualization,
                debug=debug_info
            )
            
            # 保存到 WebSocket 会话历史（用于前端展示）
            session.add_assistant_message(
                message_id=server_message_id,
                content=final_answer,
                sql_query=final_state.get("sql_query"),
                data_insight=final_state.get("data_insight"),
                visualization=visualization
            )
            
            task.mark_completed()
            logger.info(f"[StreamOrchestrator] 处理完成: answer_len={len(final_answer)}")
            
            # Phase 6: 更新执行日志为成功 (Author: CYJ, Time: 2025-11-29)
            if log_id:
                execution_time_ms = int((time.time() - start_time) * 1000)
                data_result = final_state.get("data_result", [])
                log_service.update_execution(
                    log_id=log_id,
                    status="success",
                    sql_generated=final_state.get("sql_query"),
                    tables_used=final_state.get("tables_used"),
                    result_row_count=len(data_result) if data_result else 0,
                    execution_time_ms=execution_time_ms,
                    cache_score=final_state.get("cache_score"),
                    chart_type=visualization.get("chart_type") if visualization else None
                )
            
        except TaskInterruptedError as e:
            logger.info(f"[StreamOrchestrator] 任务被中断: stage={e.stage}")
            # Phase 6: 更新执行日志为超时 (Author: CYJ, Time: 2025-11-29)
            if log_id:
                execution_time_ms = int((time.time() - start_time) * 1000)
                log_service.update_execution(
                    log_id=log_id,
                    status="timeout",
                    error_message=f"任务被中断: stage={e.stage}",
                    execution_time_ms=execution_time_ms
                )
            raise
            
        except Exception as e:
            logger.error(f"[StreamOrchestrator] 处理异常: {e}")
            import traceback
            traceback.print_exc()
            
            # Phase 6: 更新执行日志为错误 (Author: CYJ, Time: 2025-11-29)
            if log_id:
                execution_time_ms = int((time.time() - start_time) * 1000)
                log_service.update_execution(
                    log_id=log_id,
                    status="error",
                    error_message=str(e),
                    execution_time_ms=execution_time_ms
                )
            
            yield create_error_message(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"处理请求时发生错误: {str(e)}",
                message_id=client_message_id,
                stage=task.get_stage(),
                recoverable=False
            )
    
    def _split_into_chunks(self, text: str, chunk_size: int = 3) -> list:
        """将文本拆分成块用于打字机效果"""
        chunks = []
        current = ""
        for char in text:
            current += char
            if len(current) >= chunk_size:
                chunks.append(current)
                current = ""
        if current:
            chunks.append(current)
        return chunks
    
    def _build_visualization(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        构建可视化配置
        
        V2: 增加聚合检测，为前端提供聚合建议
        
        Author: CYJ
        Time: 2025-11-26
        """
        viz_rec = state.get("viz_recommendation")
        print(f"[_build_visualization] viz_recommendation={viz_rec}")  # 临时调试
        
        if not viz_rec or not viz_rec.get("recommended", False):
            print(f"[_build_visualization] 不推荐可视化, viz_rec={viz_rec}")  # 临时调试
            return None
        
        result = {
            "recommended": True,
            "chart_type": viz_rec.get("chart_type"),
            "echarts_option": state.get("echarts_option"),
            "raw_data": state.get("data_result")
        }
        
        # V2: 检测是否需要聚合
        data_result = state.get("data_result", [])
        intent = state.get("intent", {}) or {}
        user_query = intent.get("original_query", "")
        
        if data_result and user_query:
            from app.modules.viz.advisor import get_viz_advisor
            advisor = get_viz_advisor()
            agg_info = advisor.detect_aggregation_need(user_query, data_result)
            
            if agg_info.get("needs_aggregation"):
                result["aggregation"] = {
                    "needed": True,
                    "group_by": agg_info.get("suggested_group_by"),
                    "agg_func": agg_info.get("suggested_agg_func"),
                    "reason": agg_info.get("reason")
                }
        
        return result
    
    def _build_debug_info(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        构建调试信息（仅在 DEBUG_MODE=true 时调用）
        
        包含完整的中间状态数据，供前端开发调试使用
        
        Args:
            state: LangGraph 最终状态
            
        Returns:
            调试信息字典，包含原始数据、SQL、各阶段输出等
        
        Author: CYJ
        Time: 2025-11-26
        """
        debug = {
            "raw_sql": state.get("sql_query"),
            "full_data_result": state.get("data_result"),
            "data_row_count": len(state.get("data_result", []) or []),
            "intent_result": state.get("intent_result"),
            "plan_result": state.get("plan_result"),
            "viz_recommendation": state.get("viz_recommendation"),
            "analyzer_output": state.get("analyzer_output"),
        }
        
        # 移除 None 值以减少响应体积
        return {k: v for k, v in debug.items() if v is not None}


# 全局流式编排器实例
_stream_orchestrator: Optional[StreamOrchestrator] = None


def get_stream_orchestrator() -> StreamOrchestrator:
    """获取流式编排器实例"""
    global _stream_orchestrator
    if _stream_orchestrator is None:
        _stream_orchestrator = StreamOrchestrator()
    return _stream_orchestrator
