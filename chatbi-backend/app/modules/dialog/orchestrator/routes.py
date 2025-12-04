"""
Orchestrator 路由函数模块

LangGraph 工作流的所有路由决策函数，包括:
- route_after_cache_check: 缓存检查后路由
- route_after_intent: 意图识别后路由
- route_after_planner: SQL 规划后路由
- route_after_executor: SQL 执行后路由
- route_after_diagnosis: 诊断后路由

Author: CYJ
Time: 2025-12-03 (从 orchestrator.py 重构)
"""
import logging
from typing import Literal

from app.core.state import AgentState
from .helpers import analyze_schema_error, check_empty_result

logger = logging.getLogger(__name__)

def route_after_cache_check(state: AgentState) -> Literal["executor_node", "intent_node"]:
    """
    缓存检查后的路由决策
    
    - 命中缓存 -> 直接执行 SQL
    - 未命中 -> 进入意图识别
    
    Author: ChatBI Team
    Time: 2025-11-28
    """
    cache_hit = state.get("cache_hit")
    
    if cache_hit:
        logger.info("[Router] 缓存命中，路由到执行节点")
        return "executor_node"
    
    logger.info("[Router] 缓存未命中，路由到意图识别")
    return "intent_node"

def route_after_intent(state: AgentState) -> Literal["planner_node", "responder_node"]:
    """
    意图识别后的路由决策
    
    V13: 移除 follow_up_calculation，改为检查 can_answer_from_history
    
    Author: CYJ
    Time: 2025-11-27
    """
    intent = state.get("intent", {}) or {}
    intent_type = intent.get("intent_type")
    need_confirm = intent.get("need_user_confirmation", False)
    can_answer_from_history = intent.get("can_answer_from_history", False)
    
    # query_data 的两个分支：
    if intent_type == "query_data" and not need_confirm:
        if can_answer_from_history:
            
            logger.info("[Router V13] can_answer_from_history=true，跳过 SQL 流程")
            return "responder_node"
        else:
            # 需要查询新数据，走 SQL Planner
            return "planner_node"

    # 其他情况统一先进入 Responder
    return "responder_node"

def route_after_planner(state: AgentState) -> Literal["executor_node", "diagnoser_node", "responder_node"]:
    """
    Planner后的路由决策
    
    - SQL生成成功 -> executor_node
    - SQL生成失败(clarification) & 未诊断 -> diagnoser_node
    - SQL生成失败 & 已诊断 -> responder_node
    
    Author: CYJ
    Time: 2025-11-25
    """
    sql = state.get("sql_query")
    
    # Case 1: SQL生成成功
    if sql and "clarification" not in str(sql).lower():
        return "executor_node"
    
    # Case 2: SQL生成失败 - 检查是否需要诊断
    diagnosis_attempted = state.get("diagnosis_attempted", False)
    if not diagnosis_attempted:
        logger.info("[Router] SQL生成失败，路由到诊断节点检查Schema完整性")
        return "diagnoser_node"
    
    # Case 3: 已诊断过仍失败，响应用户
    return "responder_node"

def route_after_executor(state: AgentState) -> Literal["planner_node", "diagnoser_node", "analyzer_node", "responder_node"]:
    """
    Determine next step after execution.
    
    V10: 增加对表/列不存在错误的快速诊断
    - 检测到 "Table X doesn't exist" 或 "Unknown column" 错误时
    - 立即检查是否为 Schema 召回遗漏（表存在于数据库但未召回）
    - 或模型幻觉（表根本不存在于数据库）
    - 跳过无效重试，直接路由到诊断节点
    
    Author: CYJ
    Time: 2025-11-26
    """
    data = state.get("data_result")
    verification_result = state.get("verification_result")
    
    # Case 1: Verification succeeded (we found the correct entity name)
    if verification_result:
        return "planner_node"

    # Case 2: SQL Error - V10 增强错误分析
    is_error = False
    error_msg = ""
    if isinstance(data, list) and len(data) > 0 and "result" in data[0]:
         val = data[0]["result"]
         if isinstance(val, str) and val.startswith("ERROR:"):
             is_error = True
             error_msg = val
             state["error"] = val
    
    if is_error:
        retry_count = state.get("retry_count", 0)
        
        
        schema_error_info = analyze_schema_error(error_msg)
        if schema_error_info:
            logger.info(f"[Router V10] 检测到 Schema 错误: {schema_error_info}")
            # 将错误信息存入 state，供诊断节点使用
            state["schema_error_info"] = schema_error_info
            # 直接路由到诊断节点，跳过无效重试
            return "diagnoser_node"
        
        # 其他错误类型：语法错误等，继续重试
        if retry_count < 3:
            return "planner_node"
    
    # Case 3: Empty Result - Route to Diagnoser
    diagnosis_attempted = state.get("diagnosis_attempted", False)
    if not diagnosis_attempted:
        is_empty_result = check_empty_result(data)
        if is_empty_result:
            logger.info("[Router] 检测到空结果，路由到诊断节点")
            return "diagnoser_node"
    
    # Case 4: 成功执行，路由到分析节点
    return "analyzer_node"

def route_after_diagnosis(state: AgentState) -> Literal["schema_completer_node", "planner_node", "responder_node"]:
    """
    诊断后的路由决策
    
    - SCHEMA_INCOMPLETE -> schema_completer_node
    - SQL_LOGIC_ERROR -> planner_node (带修复建议)
    - ENTITY_MAPPING -> planner_node (触发探针查询流程)
    - DATA_TRULY_EMPTY -> responder_node
    
    Author: CYJ
    Time: 2025-11-25
    """
    from app.modules.diagnosis.models import DiagnosisType
    
    diagnosis_result = state.get("diagnosis_result")
    
    if not diagnosis_result:
        logger.warning("[Router] 诊断结果为空，直接响应")
        return "responder_node"
    
    diagnosis_type = diagnosis_result.diagnosis_type
    logger.info(f"[Router] 诊断类型: {diagnosis_type.value}，置信度: {diagnosis_result.confidence}")
    
    # 低置信度时直接响应
    if diagnosis_result.confidence < 0.5:
        logger.info("[Router] 诊断置信度过低，直接响应")
        return "responder_node"
    
    if diagnosis_type == DiagnosisType.SCHEMA_INCOMPLETE:
        logger.info("[Router] Schema不完整，路由到Schema补全节点")
        return "schema_completer_node"
    
    elif diagnosis_type == DiagnosisType.SQL_LOGIC_ERROR:
        logger.info("[Router] SQL逻辑错误，路由回规划节点重新生成")
        # 将诊断信息传递给planner
        intent = state.get("intent", {}) or {}
        intent["sql_fix_hint"] = {
            "root_cause": diagnosis_result.root_cause,
            "suggestions": [a.description for a in diagnosis_result.suggested_actions]
        }
        state["intent"] = intent
        state["retry_count"] = 0  # 重置重试计数
        return "planner_node"
    
    elif diagnosis_type == DiagnosisType.ENTITY_MAPPING:
        # 实体映射问题回到planner，触发探针查询机制
        logger.info("[Router] 实体映射问题，路由回规划节点触发探针查询")
        intent = state.get("intent", {}) or {}
        intent["entity_mapping_hint"] = {
            "root_cause": diagnosis_result.root_cause,
            "missing_entities": [a.description for a in diagnosis_result.suggested_actions]
        }
        state["intent"] = intent
        state["retry_count"] = 0
        return "planner_node"
    
    else:  # DATA_TRULY_EMPTY or unknown
        logger.info("[Router] 数据确实为空或未知类型，直接响应")
        return "responder_node"
