"""
功能：全局 Agent 状态定义 (State Management)
说明：
    定义 LangGraph 中多 Agent 共享的状态结构 (StateSchema)。
    这是跨 Agent 记忆和信息传递的核心。
作者：CYJ
"""
from typing import TypedDict, List, Optional, Dict, Annotated, Union, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class QueryRequirements(TypedDict, total=False):
    """
    查询需求结构化提取 - 用于执行后语义完整性验证
    
    从用户提问中提取的查询要求，用于验证生成的SQL是否真正满足用户需求。
    
    Author: CYJ
    """
    sort_by: Optional[Dict[str, str]]      # 排序要求: {"field": "销售金额", "order": "DESC"}
    limit: Optional[int]                    # 数量限制: 10
    group_dimensions: Optional[List[str]]   # 分组维度: ["省份", "品类", "支付方式"]
    required_metrics: Optional[List[str]]   # 输出指标: ["订单数量", "销售金额"]
    has_aggregation: Optional[bool]         # 是否需要聚合: True


class IntentSchema(TypedDict):
    """意图结构

    Author: CYJ
    """
    original_query: str
    rewritten_query: Optional[str]
    intent_type: str  # 'query_data', 'chitchat', 'unclear', 'rejection'
    entities: Dict[str, str]  # e.g. {"city": "Hangzhou", "time": "last_quarter"}
    # V2: 新增结构化筛选条件 - 明确告知SQL Agent哪些条件必须转为WHERE
    # Author: CYJ
    # Time: 2025-11-26
    filter_conditions: Optional[List[Dict[str, Any]]]  # [{"field_hint": "coupon_type", "value": "折扣券", "required": true}]
    # V14: 新增查询需求结构化提取 - 用于语义完整性验证
    # Author: CYJ
    # Time: 2025-11-28
    query_requirements: Optional[QueryRequirements]  # 排序、限制、分组、指标等需求
    reason: Optional[str]  # Reasoning for the classification
    guidance: Optional[str]  # Guidance for user if rejection or unclear
    detected_keywords: Optional[List[str]]  # Keywords detected even if unclear
    # 是否需要在执行 SQL 之前让用户确认改写结果/补充关键信息
    need_user_confirmation: Optional[bool]
    # 如果需要确认，应该向用户提出的问题文案
    clarification_question: Optional[str]
    
    # V13: 基于历史数据回答（query_data 的变体分支）
    # Author: CYJ
    # Time: 2025-11-27
    can_answer_from_history: Optional[bool]  # 是否可以基于历史数据直接回答，无需新查询
    history_answer_reason: Optional[str]  # 为什么可以/不可以基于历史回答的原因

class AgentState(TypedDict):
    """
    LangGraph 全局状态对象
    
    Attributes:
        messages: 对话历史 (HumanMessage, AIMessage, ToolMessage...)
                  Annotated[..., add_messages] 表示该字段是"追加"模式，而不是覆盖。
        intent: 当前轮次的意图分析结果
        sql_query: 生成的 SQL 语句
        data_result: 执行 SQL 后的结果数据 (List of Dict)
        error: 错误信息 (用于 Self-Correction)
        next_step: 下一步路由指示 (可选)
    """
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Context Variables (会被每一轮覆盖)
    intent: Optional[IntentSchema]
    sql_query: Optional[str]
    data_result: Optional[List[Dict[str, Any]]]
    error: Optional[str]
    
    # UI/Streaming 辅助
    final_answer: Optional[str]
    
    # SQL Retry / Verification State
    retry_count: Optional[int]
    verification_attempted: Optional[bool]
    verification_result: Optional[str]
    original_failed_sql: Optional[str]
    correction_note: Optional[str] # Message to inform user about corrections (e.g. "Corrected 'Hangzhou' to 'Hangzhou City'")
    
    # V3: Schema 缓存优化 - 重试时复用首次召回结果
    # Author: CYJ
    cached_schema_context: Optional[str]  # 缓存首次 Retrieval 的 Schema 信息
    
    # V4: 多层诊断与反思机制
    # Author: CYJ
    selected_tables: Optional[List[str]]  # 已召回的表列表
    diagnosis_result: Optional[Dict[str, Any]]  # 诊断结果
    diagnosis_attempted: Optional[bool]  # 是否已尝试诊断
    schema_completed: Optional[bool]  # 是否已进行Schema补全
    diagnosis_count: Optional[int]  # 诊断次数（防止无限循环）
    
    # V5: 语义验证机制
    # Author: CYJ
    semantic_validation_attempted: Optional[bool]  # 是否已尝试语义验证
    semantic_validation_result: Optional[str]  # 语义验证结果（遗漏的条件）
    
    # V6: 跨轮累积的已验证实体映射（不应每轮重置）
    # 用于记住探针发现的中英文映射，避免重复探针查询
    # Author: CYJ
    verified_entity_mappings: Optional[Dict[str, str]]  # {"顺丰": "顺丰速运", "微信": "wechat"}
    
    # V6: 跨轮累积的Schema知识（已验证的表关联路径）
    # 用于记住已验证的表关联关系，避免重复召回验证
    # Author: CYJ
    verified_schema_knowledge: Optional[Dict[str, Any]]  # {"verified_joins": [...], "verified_columns": [...]}
    
    # V7: 分析与可视化相关字段
    # Author: CYJ
    analysis_result: Optional[Dict[str, Any]]  # AnalyzerAgent 生成的分析结果
    viz_recommendation: Optional[Dict[str, Any]]  # 可视化推荐结果
    echarts_option: Optional[Dict[str, Any]]  # ECharts 图表配置
    data_insight: Optional[Dict[str, Any]]  # 数据洞察信息
    
    # V10: Schema 错误快速诊断
    # Author: CYJ
    schema_error_info: Optional[Dict[str, Any]]  # Schema 错误信息（表/列不存在）
    
    # V11: 上一轮查询结果摘要（用于追问上下文）
    # Author: CYJ
    last_query_context: Optional[Dict[str, Any]]  # {"query": "...", "sql": "...", "data_summary": "...", "row_count": 9}
    
    # V14: 语义完整性验证 (Semantic Completeness Validation)
    # Author: CYJ

    completeness_validation_attempted: Optional[bool]  # 是否已尝试语义完整性验证
    completeness_validation_result: Optional[Dict[str, Any]]  # 验证结果（缺失项）

    cache_hit: Optional[Dict[str, Any]]  # 缓存命中结果 {id, sql, original_query, rewritten_query, tables_used, hit_count}
