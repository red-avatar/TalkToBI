"""
WebSocket 对话端点

处理 WebSocket 连接、消息路由、中断请求

Author: CYJ
"""
import asyncio
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional
import logging

from app.core.config import get_settings
from app.schemas.ws_messages import (
    MessageType,
    ErrorCode,
    ProcessingStage,
    create_error_message,
    create_interrupted_message,
    create_history_message,
    create_pong_message,
)
from app.modules.dialog.session_manager import get_session_manager, ChatSession
from app.modules.dialog.stream_orchestrator import get_stream_orchestrator
from app.modules.dialog.interruptible import InterruptibleTask, TaskInterruptedError

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


class ConnectionManager:
    """
    WebSocket 连接管理器
    
    管理活跃的 WebSocket 连接
    """
    
    def __init__(self):
        # session_id -> WebSocket
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """接受连接"""
        await websocket.accept()
        
        # 如果已有相同 session_id 的连接，关闭旧连接
        if session_id in self.active_connections:
            old_ws = self.active_connections[session_id]
            try:
                await old_ws.close(code=1000, reason="New connection established")
            except:
                pass
        
        self.active_connections[session_id] = websocket
        logger.info(f"[WebSocket] 连接建立: {session_id}")
    
    def disconnect(self, session_id: str) -> None:
        """断开连接"""
        self.active_connections.pop(session_id, None)
        logger.info(f"[WebSocket] 连接断开: {session_id}")
    
    async def send_json(self, session_id: str, data: dict) -> bool:
        """发送 JSON 消息"""
        websocket = self.active_connections.get(session_id)
        if websocket:
            try:
                await websocket.send_json(data)
                return True
            except Exception as e:
                logger.error(f"[WebSocket] 发送消息失败: {e}")
                return False
        return False
    
    def get_connection_count(self) -> int:
        """获取连接数"""
        return len(self.active_connections)


# 全局连接管理器
connection_manager = ConnectionManager()


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    WebSocket 对话端点
    
    URL: ws://host/api/v1/ws/chat/{session_id}
    
    消息协议：
    - 客户端发送: user_message, interrupt, ping, get_history
    - 服务端发送: status, text_chunk, complete, error, interrupted, history, pong
    """
    session_manager = get_session_manager()
    stream_orchestrator = get_stream_orchestrator()
    
    # 接受连接
    await connection_manager.connect(session_id, websocket)
    
    # 获取或创建会话
    session = session_manager.get_or_create(session_id)
    
    # 启动清理任务（如果还没启动）
    try:
        await session_manager.start_cleanup_task()
    except:
        pass
    
    try:
        while True:
            # 接收客户端消息
            try:
                data = await websocket.receive_json()
            except Exception as e:
                logger.error(f"[WebSocket] 接收消息失败: {e}")
                break
            
            message_type = data.get("type")
            payload = data.get("payload", {})
            
            logger.debug(f"[WebSocket] 收到消息: type={message_type}")
            
            # 路由处理
            if message_type == MessageType.PING.value:
                await handle_ping(websocket)
                
            elif message_type == MessageType.USER_MESSAGE.value:
                await handle_user_message(
                    websocket, session, stream_orchestrator, payload
                )
                
            elif message_type == MessageType.INTERRUPT.value:
                await handle_interrupt(websocket, session, payload)
                
            elif message_type == MessageType.GET_HISTORY.value:
                await handle_get_history(websocket, session, payload)
                
            else:
                await websocket.send_json(create_error_message(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Unknown message type: {message_type}",
                    recoverable=True
                ))
                
    except WebSocketDisconnect:
        logger.info(f"[WebSocket] 客户端断开连接: {session_id}")
        # 中断当前任务
        if session.current_task and not session.current_task.is_cancelled():
            session.current_task.cancel()
            
    except Exception as e:
        logger.error(f"[WebSocket] 连接异常: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            await websocket.send_json(create_error_message(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"连接异常: {str(e)}",
                recoverable=False
            ))
        except:
            pass
            
    finally:
        connection_manager.disconnect(session_id)
        # 注意：不销毁会话，用户可能重连


async def handle_ping(websocket: WebSocket) -> None:
    """处理心跳"""
    await websocket.send_json(create_pong_message())


async def handle_user_message(
    websocket: WebSocket,
    session: ChatSession,
    orchestrator,
    payload: dict
) -> None:
    """处理用户消息"""
    content = payload.get("content", "").strip()
    client_message_id = payload.get("message_id") or f"msg_{uuid.uuid4().hex[:12]}"
    
    # 验证消息长度
    if len(content) > settings.CHAT_MESSAGE_MAX_LENGTH:
        await websocket.send_json(create_error_message(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"消息长度超过限制（最大 {settings.CHAT_MESSAGE_MAX_LENGTH} 字符）",
            message_id=client_message_id,
            recoverable=True
        ))
        return
    
    if not content:
        await websocket.send_json(create_error_message(
            code=ErrorCode.VALIDATION_ERROR,
            message="消息内容不能为空",
            message_id=client_message_id,
            recoverable=True
        ))
        return
    
    # 检查并发限制
    active_count = session.task_manager.get_active_count()
    if active_count >= settings.CHAT_MAX_CONCURRENT_REQUESTS:
        await websocket.send_json(create_error_message(
            code=ErrorCode.CONCURRENT_LIMIT,
            message=f"请求过于频繁，请稍后再试（最大并发: {settings.CHAT_MAX_CONCURRENT_REQUESTS}）",
            message_id=client_message_id,
            recoverable=True
        ))
        return
    
    # 如果有正在处理的任务，先中断
    if session.current_task and not session.current_task.is_cancelled():
        old_message_id = session.current_task.message_id
        session.current_task.cancel()
        await websocket.send_json(create_interrupted_message(
            message_id=old_message_id,
            stage=session.current_task.get_stage()
        ))
    
    # 创建新任务
    task = session.task_manager.create_task(client_message_id)
    session.current_task = task
    session.is_processing = True
    
    # 添加用户消息到历史
    session.add_user_message(client_message_id, content)
    
    logger.info(f"[WebSocket] 开始处理消息: {content[:50]}...")
    
    try:
        # 流式处理
        async for msg in orchestrator.process_stream(
            message=content,
            session=session,
            task=task,
            client_message_id=client_message_id
        ):
            await websocket.send_json(msg)
            
    except TaskInterruptedError as e:
        # 任务被中断
        await websocket.send_json(create_interrupted_message(
            message_id=client_message_id,
            stage=e.stage,
            partial_answer=e.partial_result
        ))
        
    except Exception as e:
        logger.error(f"[WebSocket] 处理消息异常: {e}")
        import traceback
        traceback.print_exc()
        
        await websocket.send_json(create_error_message(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"处理消息时发生错误: {str(e)}",
            message_id=client_message_id,
            stage=task.get_stage(),
            recoverable=False
        ))
        
    finally:
        session.is_processing = False
        session.current_task = None
        session.task_manager.remove_task(client_message_id)


async def handle_interrupt(
    websocket: WebSocket,
    session: ChatSession,
    payload: dict
) -> None:
    """处理中断请求"""
    reason = payload.get("reason", "user_cancel")
    target_message_id = payload.get("target_message_id")
    
    interrupted = False
    stage = None
    
    if target_message_id:
        # 中断指定任务
        task = session.task_manager.get_task(target_message_id)
        if task and not task.is_cancelled():
            stage = task.get_stage()
            task.cancel()
            interrupted = True
    elif session.current_task and not session.current_task.is_cancelled():
        # 中断当前任务
        target_message_id = session.current_task.message_id
        stage = session.current_task.get_stage()
        session.current_task.cancel()
        interrupted = True
    
    if interrupted:
        logger.info(f"[WebSocket] 中断任务: {target_message_id}, reason={reason}")
        # interrupted 消息会在 handle_user_message 的 except 中发送
    else:
        logger.debug(f"[WebSocket] 无任务可中断")


async def handle_get_history(
    websocket: WebSocket,
    session: ChatSession,
    payload: dict
) -> None:
    """处理获取历史请求"""
    limit = payload.get("limit", 50)
    before_message_id = payload.get("before_message_id")
    
    # 获取历史消息
    messages = session.get_history(limit=limit, before_message_id=before_message_id)
    
    # 判断是否还有更多
    has_more = len(session.messages) > len(messages)
    
    await websocket.send_json(create_history_message(
        messages=messages,
        has_more=has_more,
        session_created_at=session.created_at
    ))
    
    logger.debug(f"[WebSocket] 返回历史消息: {len(messages)} 条")
