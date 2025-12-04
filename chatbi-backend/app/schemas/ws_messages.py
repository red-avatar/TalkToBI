"""
WebSocket 消息模型

定义客户端和服务端的所有消息类型

Author: CYJ
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from enum import Enum


# =============================================================================
# 枚举定义
# =============================================================================

class MessageType(str, Enum):
    """消息类型枚举"""
    # 客户端消息
    USER_MESSAGE = "user_message"
    INTERRUPT = "interrupt"
    PING = "ping"
    GET_HISTORY = "get_history"
    
    # 服务端消息
    STATUS = "status"
    TEXT_CHUNK = "text_chunk"
    COMPLETE = "complete"
    ERROR = "error"
    INTERRUPTED = "interrupted"
    HISTORY = "history"
    PONG = "pong"


class ProcessingStage(str, Enum):
    """处理阶段枚举"""
    INTENT = "intent"           # 意图识别
    PLANNER = "planner"         # SQL规划
    EXECUTOR = "executor"       # 执行查询
    ANALYZER = "analyzer"       # 数据分析
    RESPONDER = "responder"     # 生成回答


class ErrorCode(str, Enum):
    """错误码枚举"""
    INTENT_ERROR = "INTENT_ERROR"
    PLANNER_ERROR = "PLANNER_ERROR"
    EXECUTOR_ERROR = "EXECUTOR_ERROR"
    ANALYZER_ERROR = "ANALYZER_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONCURRENT_LIMIT = "CONCURRENT_LIMIT"


class InterruptReason(str, Enum):
    """中断原因"""
    USER_CANCEL = "user_cancel"     # 用户主动取消
    NEW_MESSAGE = "new_message"     # 发送新消息


# =============================================================================
# 客户端消息载荷
# =============================================================================

class UserMessagePayload(BaseModel):
    """用户消息载荷"""
    content: str = Field(..., description="消息内容")
    message_id: Optional[str] = Field(default=None, description="客户端生成的消息ID")


class InterruptPayload(BaseModel):
    """中断请求载荷"""
    reason: InterruptReason = Field(..., description="中断原因")
    target_message_id: Optional[str] = Field(default=None, description="要中断的消息ID")


class GetHistoryPayload(BaseModel):
    """获取历史载荷"""
    limit: int = Field(default=50, description="获取数量")
    before_message_id: Optional[str] = Field(default=None, description="分页游标")


# =============================================================================
# 服务端消息载荷
# =============================================================================

class StatusPayload(BaseModel):
    """状态更新载荷"""
    stage: ProcessingStage = Field(..., description="当前处理阶段")
    message: str = Field(..., description="状态描述")
    message_id: Optional[str] = Field(default=None, description="关联的消息ID")
    progress: Optional[int] = Field(default=None, description="进度百分比")
    details: Optional[Dict[str, Any]] = Field(default=None, description="详细信息")


class TextChunkPayload(BaseModel):
    """文本块载荷（打字机效果）"""
    content: str = Field(..., description="文本内容")
    message_id: Optional[str] = Field(default=None, description="关联的消息ID")
    chunk_index: int = Field(default=0, description="块序号")
    is_first: bool = Field(default=False, description="是否是第一个块")
    is_last: bool = Field(default=False, description="是否是最后一个块")


class DataInsightPayload(BaseModel):
    """数据洞察"""
    summary: Optional[str] = Field(default=None, description="数据摘要")
    highlights: Optional[List[str]] = Field(default=None, description="数据亮点")
    trend: Optional[str] = Field(default=None, description="趋势分析")
    statistics: Optional[Dict[str, Any]] = Field(default=None, description="统计信息")


class VisualizationPayload(BaseModel):
    """可视化配置"""
    recommended: bool = Field(default=False, description="是否推荐可视化")
    chart_type: Optional[str] = Field(default=None, description="图表类型")
    echarts_option: Optional[Dict[str, Any]] = Field(default=None, description="ECharts配置")
    raw_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="原始数据")
    # V2: 聚合建议（前端可根据此配置进行数据聚合）
    # Author: CYJ
    # Time: 2025-11-26
    aggregation: Optional[Dict[str, Any]] = Field(default=None, description="聚合建议，如 {group_by: 'region', metric: 'count'}")


class DebugInfoPayload(BaseModel):
    """
    调试信息载荷（仅 DEBUG_MODE=True 时返回）
    
    Author: CYJ
    """
    sql_query: Optional[str] = Field(default=None, description="执行的 SQL 语句")
    raw_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="原始查询结果")
    row_count: Optional[int] = Field(default=None, description="结果行数")
    execution_time_ms: Optional[int] = Field(default=None, description="执行耗时(ms)")
    selected_tables: Optional[List[str]] = Field(default=None, description="选中的表")
    intent: Optional[Dict[str, Any]] = Field(default=None, description="意图识别结果")


class CompletePayload(BaseModel):
    """完成消息载荷"""
    message_id: str = Field(..., description="服务端消息ID")
    reply_to: Optional[str] = Field(default=None, description="回复的用户消息ID")
    text_answer: str = Field(..., description="文本回答")
    sql_query: Optional[str] = Field(default=None, description="执行的SQL（产品模式下不返回）")
    data_insight: Optional[DataInsightPayload] = Field(default=None, description="数据洞察")
    visualization: Optional[VisualizationPayload] = Field(default=None, description="可视化配置")
    # V2: 调试信息（仅 DEBUG_MODE=True 时返回）
    # Author: CYJ
    # Time: 2025-11-26
    debug: Optional[DebugInfoPayload] = Field(default=None, description="调试信息（仅调试模式）")


class ErrorPayload(BaseModel):
    """错误载荷"""
    code: ErrorCode = Field(..., description="错误码")
    message: str = Field(..., description="错误描述")
    message_id: Optional[str] = Field(default=None, description="关联的消息ID")
    stage: Optional[ProcessingStage] = Field(default=None, description="错误发生阶段")
    recoverable: bool = Field(default=True, description="是否可恢复")
    details: Optional[Dict[str, Any]] = Field(default=None, description="详细错误信息")


class InterruptedPayload(BaseModel):
    """中断确认载荷"""
    message_id: str = Field(..., description="被中断的消息ID")
    stage: Optional[ProcessingStage] = Field(default=None, description="中断时的阶段")
    partial_answer: Optional[str] = Field(default=None, description="部分回答")


class HistoryMessageItem(BaseModel):
    """历史消息项"""
    message_id: str = Field(..., description="消息ID")
    role: Literal["user", "assistant"] = Field(..., description="角色")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(..., description="时间戳")
    visualization: Optional[VisualizationPayload] = Field(default=None, description="可视化")


class HistoryPayload(BaseModel):
    """历史消息载荷"""
    messages: List[HistoryMessageItem] = Field(default_factory=list, description="消息列表")
    has_more: bool = Field(default=False, description="是否有更多")
    session_created_at: Optional[datetime] = Field(default=None, description="会话创建时间")


class PongPayload(BaseModel):
    """心跳响应载荷"""
    server_time: datetime = Field(default_factory=datetime.utcnow, description="服务器时间")


# =============================================================================
# 通用消息封装
# =============================================================================

class WebSocketMessage(BaseModel):
    """WebSocket 消息基类"""
    type: MessageType = Field(..., description="消息类型")
    payload: Dict[str, Any] = Field(default_factory=dict, description="消息载荷")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="时间戳")
    message_id: Optional[str] = Field(default=None, description="消息ID")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        data = {
            "type": self.type.value,
            "payload": self.payload,
        }
        if self.timestamp:
            data["timestamp"] = self.timestamp.isoformat()
        if self.message_id:
            data["message_id"] = self.message_id
        return data


# =============================================================================
# 消息工厂函数
# =============================================================================

def create_status_message(
    stage: ProcessingStage,
    message: str,
    message_id: Optional[str] = None,
    progress: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """创建状态消息"""
    payload = StatusPayload(
        stage=stage,
        message=message,
        message_id=message_id,
        progress=progress,
        details=details
    )
    return {
        "type": MessageType.STATUS.value,
        "payload": payload.model_dump(exclude_none=True),
        "timestamp": datetime.utcnow().isoformat()
    }


def create_text_chunk_message(
    content: str,
    message_id: Optional[str] = None,
    chunk_index: int = 0,
    is_first: bool = False,
    is_last: bool = False
) -> Dict[str, Any]:
    """创建文本块消息"""
    payload = TextChunkPayload(
        content=content,
        message_id=message_id,
        chunk_index=chunk_index,
        is_first=is_first,
        is_last=is_last
    )
    return {
        "type": MessageType.TEXT_CHUNK.value,
        "payload": payload.model_dump(exclude_none=True),
        "timestamp": datetime.utcnow().isoformat()
    }


def create_complete_message(
    message_id: str,
    text_answer: str,
    reply_to: Optional[str] = None,
    sql_query: Optional[str] = None,
    data_insight: Optional[Dict[str, Any]] = None,
    visualization: Optional[Dict[str, Any]] = None,
    debug: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建完成消息
    
    Args:
        message_id: 消息ID
        text_answer: 文本回答
        reply_to: 回复的消息ID
        sql_query: SQL查询语句
        data_insight: 数据洞察
        visualization: 可视化配置
        debug: 调试信息（仅在 DEBUG_MODE=true 时返回）
    
    Returns:
        完成消息字典
    
    Author: CYJ
    """
    payload = {
        "message_id": message_id,
        "text_answer": text_answer,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    if sql_query:
        payload["sql_query"] = sql_query
    if data_insight:
        payload["data_insight"] = data_insight
    if visualization:
        payload["visualization"] = visualization
    if debug:
        payload["debug"] = debug
    
    return {
        "type": MessageType.COMPLETE.value,
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat()
    }


def create_error_message(
    code: ErrorCode,
    message: str,
    message_id: Optional[str] = None,
    stage: Optional[ProcessingStage] = None,
    recoverable: bool = True,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """创建错误消息"""
    payload = ErrorPayload(
        code=code,
        message=message,
        message_id=message_id,
        stage=stage,
        recoverable=recoverable,
        details=details
    )
    return {
        "type": MessageType.ERROR.value,
        "payload": payload.model_dump(exclude_none=True),
        "timestamp": datetime.utcnow().isoformat()
    }


def create_interrupted_message(
    message_id: str,
    stage: Optional[ProcessingStage] = None,
    partial_answer: Optional[str] = None
) -> Dict[str, Any]:
    """创建中断确认消息"""
    payload = InterruptedPayload(
        message_id=message_id,
        stage=stage,
        partial_answer=partial_answer
    )
    return {
        "type": MessageType.INTERRUPTED.value,
        "payload": payload.model_dump(exclude_none=True),
        "timestamp": datetime.utcnow().isoformat()
    }


def create_history_message(
    messages: List[Dict[str, Any]],
    has_more: bool = False,
    session_created_at: Optional[datetime] = None
) -> Dict[str, Any]:
    """创建历史消息"""
    return {
        "type": MessageType.HISTORY.value,
        "payload": {
            "messages": messages,
            "has_more": has_more,
            "session_created_at": session_created_at.isoformat() if session_created_at else None
        },
        "timestamp": datetime.utcnow().isoformat()
    }


def create_pong_message() -> Dict[str, Any]:
    """创建心跳响应消息"""
    return {
        "type": MessageType.PONG.value,
        "payload": {
            "server_time": datetime.utcnow().isoformat()
        }
    }


# =============================================================================
# 阶段描述映射
# =============================================================================

STAGE_DESCRIPTIONS = {
    ProcessingStage.INTENT: "🔍 正在理解您的问题...",
    ProcessingStage.PLANNER: "📝 正在生成查询方案...",
    ProcessingStage.EXECUTOR: "⚡ 正在执行数据查询...",
    ProcessingStage.ANALYZER: "📊 正在分析数据...",
    ProcessingStage.RESPONDER: "💬 正在生成回答...",
}


def get_stage_description(stage: ProcessingStage) -> str:
    """获取阶段描述"""
    return STAGE_DESCRIPTIONS.get(stage, "处理中...")
