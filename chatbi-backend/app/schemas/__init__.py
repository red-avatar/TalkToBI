"""
Pydantic 模型定义

Author: CYJ
Time: 2025-11-26
"""
from app.schemas.ws_messages import (
    # 枚举
    MessageType,
    ProcessingStage,
    ErrorCode,
    InterruptReason,
    # 载荷模型
    UserMessagePayload,
    InterruptPayload,
    GetHistoryPayload,
    StatusPayload,
    TextChunkPayload,
    DataInsightPayload,
    VisualizationPayload,
    CompletePayload,
    ErrorPayload,
    InterruptedPayload,
    HistoryMessageItem,
    HistoryPayload,
    PongPayload,
    WebSocketMessage,
    # 工厂函数
    create_status_message,
    create_text_chunk_message,
    create_complete_message,
    create_error_message,
    create_interrupted_message,
    create_history_message,
    create_pong_message,
    get_stage_description,
    STAGE_DESCRIPTIONS,
)

__all__ = [
    # 枚举
    "MessageType",
    "ProcessingStage",
    "ErrorCode",
    "InterruptReason",
    # 载荷模型
    "UserMessagePayload",
    "InterruptPayload",
    "GetHistoryPayload",
    "StatusPayload",
    "TextChunkPayload",
    "DataInsightPayload",
    "VisualizationPayload",
    "CompletePayload",
    "ErrorPayload",
    "InterruptedPayload",
    "HistoryMessageItem",
    "HistoryPayload",
    "PongPayload",
    "WebSocketMessage",
    # 工厂函数
    "create_status_message",
    "create_text_chunk_message",
    "create_complete_message",
    "create_error_message",
    "create_interrupted_message",
    "create_history_message",
    "create_pong_message",
    "get_stage_description",
    "STAGE_DESCRIPTIONS",
]
