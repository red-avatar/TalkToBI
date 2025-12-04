"""
Chat API 端点

功能：
- 对话请求处理
- 返回文本回答 + 可视化配置

Author: CYJ
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from langchain_core.messages import HumanMessage
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(default=None, description="会话ID，用于多轮对话")
    

class DataInsight(BaseModel):
    """数据洞察"""
    summary: Optional[str] = Field(default=None, description="数据摘要")
    highlights: Optional[List[str]] = Field(default=None, description="数据亮点")
    trend: Optional[str] = Field(default=None, description="趋势分析")
    statistics: Optional[Dict[str, Any]] = Field(default=None, description="统计信息")


class Visualization(BaseModel):
    """可视化配置"""
    chart_type: str = Field(..., description="图表类型: line/bar/pie/table/single_value")
    echarts_option: Optional[Dict[str, Any]] = Field(default=None, description="ECharts 配置")
    raw_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="原始数据")


class ChatResponse(BaseModel):
    """对话响应"""
    text_answer: str = Field(..., description="文本回答")
    session_id: str = Field(..., description="会话ID")
    data_insight: Optional[DataInsight] = Field(default=None, description="数据洞察")
    visualization: Optional[Visualization] = Field(default=None, description="可视化配置")
    sql_query: Optional[str] = Field(default=None, description="执行的SQL（调试用）")
    

# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    对话接口
    
    接收用户消息，返回文本回答和可视化配置（如果需要）
    
    示例请求：
    ```json
    {
        "message": "广州市最近一周的订单量趋势",
        "session_id": "xxx-xxx-xxx"
    }
    ```
    
    示例响应：
    ```json
    {
        "text_answer": "广州市最近一周订单量呈上升趋势...",
        "session_id": "xxx-xxx-xxx",
        "data_insight": {
            "summary": "订单量整体呈上升趋势",
            "highlights": ["周一最低: 100笔", "周日最高: 200笔"],
            "trend": "上升"
        },
        "visualization": {
            "chart_type": "line",
            "echarts_option": {...}
        }
    }
    ```
    """
    try:
        from app.modules.dialog.orchestrator import orchestrator_app
        
        # 生成或使用传入的 session_id
        session_id = request.session_id or str(uuid.uuid4())
        
        logger.info(f"[Chat API] 收到消息: {request.message[:50]}... session={session_id}")
        
        # 构建初始状态
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "intent": None,
            "sql_query": None,
            "data_result": None,
            "final_answer": None,
            "error": None,
            # V7: 分析与可视化字段
            "analysis_result": None,
            "viz_recommendation": None,
            "echarts_option": None,
            "data_insight": None
        }
        
        # 调用 orchestrator
        config = {"configurable": {"thread_id": session_id}}
        result = orchestrator_app.invoke(initial_state, config)
        
        logger.info(f"[Chat API] 处理完成: answer_len={len(result.get('final_answer', ''))}")
        
        # 构建响应
        response = ChatResponse(
            text_answer=result.get("final_answer", "抱歉，处理您的请求时出现问题。"),
            session_id=session_id,
            sql_query=result.get("sql_query")  # 调试用
        )
        
        # 添加数据洞察
        data_insight = result.get("data_insight")
        if data_insight:
            response.data_insight = DataInsight(
                summary=data_insight.get("summary"),
                highlights=data_insight.get("highlights"),
                trend=data_insight.get("trend"),
                statistics=data_insight.get("statistics")
            )
        
        # 添加可视化配置
        viz_data = result.get("visualization")
        if viz_data and viz_data.get("echarts_option"):
            response.visualization = Visualization(
                chart_type=viz_data.get("chart_type", "table"),
                echarts_option=viz_data.get("echarts_option"),
                raw_data=viz_data.get("raw_data")
            )
            logger.info(f"[Chat API] 返回可视化: chart_type={viz_data.get('chart_type')}")
        
        return response
        
    except Exception as e:
        logger.error(f"[Chat API] 处理失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"处理请求失败: {str(e)}")


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    获取对话历史（基于 LangGraph 的 checkpointer）
    
    TODO: 实现对话历史查询
    """
    # 当前使用 MemorySaver，重启后历史丢失
    # 生产环境应使用持久化存储（如 PostgreSQL）
    return {
        "session_id": session_id,
        "messages": [],
        "note": "当前使用内存存储，重启后历史丢失"
    }
