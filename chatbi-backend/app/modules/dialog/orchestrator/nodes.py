"""
Orchestrator 节点函数模块

LangGraph 工作流的所有节点函数，包括:
- cache_check_node: 缓存检查节点
- intent_node: 意图识别节点
- planner_node: SQL 规划节点
- executor_node: SQL 执行节点
- analyzer_node: 数据分析节点
- responder_node: 响应生成节点
- diagnoser_node: 诊断节点
- schema_completer_node: Schema 补全节点

Author: CYJ
Time: 2025-12-03 (从 orchestrator.py 重构)
"""
import re
import json
import ast
import logging
from typing import Dict, List

from langchain_core.messages import AIMessage

from app.core.state import AgentState
from app.core.config import get_settings
from app.services.cache_service import get_cache_service
from app.modules.agents.intent_agent import IntentAgent
from app.modules.agents.sql_agent import SqlPlannerAgent
from app.modules.tools.execution import SqlExecutorTool
from app.modules.schema.catalog import get_schema_catalog
from app.modules.diagnosis import (
    SchemaCompleter,
    DiagnosisType,
    SuggestedAction,
    SuggestedActionItem,
    IntelligentAnalyzer,
    get_intelligent_analyzer,
    ResultValidator,
    get_result_validator
)
from app.modules.diagnosis.models import DiagnosisResult
from app.modules.diagnosis.semantic_completeness_validator import (
    SemanticCompletenessValidator,
    get_completeness_validator
)
from app.modules.agents.analyzer import AnalyzerAgent, get_analyzer_agent
from app.utils.sql_parser import extract_filter_entities

from .helpers import (
    generate_probe_sql,
    get_schema_context_for_probe,
    format_correction_note,
    build_data_summary,
    save_to_cache_sync,
    handle_answer_from_history
)
from app.core.observability import (
    trace_node,
    trace_llm_call,
    record_error,
    get_trace_id
)

logger = logging.getLogger(__name__)
_settings = get_settings()

# Initialize Agents and Tools
intent_agent = IntentAgent()
sql_planner = SqlPlannerAgent()
sql_executor_tool = SqlExecutorTool()
schema_completer = SchemaCompleter()
result_validator = get_result_validator()
completeness_validator = get_completeness_validator()
analyzer_agent = get_analyzer_agent()
cache_service = get_cache_service()

# =============================================================================
# Cache Check Node (V16)
# =============================================================================

@trace_node
def cache_check_node(state: AgentState) -> dict:
    """
    缓存检查节点：在进入 IntentAgent 之前检查缓存
    
    如果命中缓存，直接返回缓存的 SQL，跳过所有 LLM 调用
    
    Author: ChatBI Team
    Time: 2025-11-28
    """
    logger.info("--- Node: Cache Check (V16) ---")
    
    messages = state.get('messages', [])
    if not messages:
        return {"cache_hit": None}
    
    user_input = messages[-1].content
    
    # 同步检查缓存
    try:
        cache_hit = cache_service.check_cache(user_input)
    except Exception as e:
        logger.warning(f"[CacheCheck] 缓存检查失败: {e}")
        cache_hit = None
    
    if cache_hit:
        logger.info(f"[CacheCheck] 缓存命中! SQL={cache_hit.sql[:100]}..., cache_score={cache_hit.cache_score}")
        return {
            "cache_hit": {
                "id": cache_hit.id,
                "sql": cache_hit.sql,
                "original_query": cache_hit.original_query,
                "rewritten_query": cache_hit.rewritten_query,
                "tables_used": cache_hit.tables_used,
                "hit_count": cache_hit.hit_count,
                "cache_score": cache_hit.cache_score
            },
            "sql_query": cache_hit.sql,
            "intent": {
                "original_query": user_input,
                "rewritten_query": cache_hit.rewritten_query or user_input,
                "intent_type": "query_data",
                "from_cache": True
            }
        }
    
    logger.info("[CacheCheck] 缓存未命中，继续正常流程")
    return {"cache_hit": None}

# =============================================================================
# Intent Node
# =============================================================================

@trace_node
def intent_node(state: AgentState):
    """意图识别节点"""
    logger.info("--- Node: Intent Recognition ---")
    
    
    preserved_entity_mappings = state.get("verified_entity_mappings", {})
    preserved_schema_knowledge = state.get("verified_schema_knowledge", {})
    
    intent_result = intent_agent.invoke(state)
    
    # 重置本轮临时字段
    intent_result["verification_attempted"] = False
    intent_result["verification_result"] = None
    intent_result["correction_note"] = None
    intent_result["retry_count"] = 0
    intent_result["cached_schema_context"] = None
    intent_result["error"] = None
    intent_result["original_failed_sql"] = None
    intent_result["semantic_validation_attempted"] = False
    intent_result["diagnosis_attempted"] = False
    intent_result["diagnosis_count"] = 0
    intent_result["completeness_validation_attempted"] = False
    intent_result["completeness_validation_result"] = None
    
    
    intent_result["verified_entity_mappings"] = preserved_entity_mappings
    intent_result["verified_schema_knowledge"] = preserved_schema_knowledge
    
    logger.info(f"[Intent] 跨轮缓存: entity_mappings={len(preserved_entity_mappings)}, schema_knowledge={len(preserved_schema_knowledge)}")
    
    return intent_result

# =============================================================================
# Planner Node
# =============================================================================

@trace_node
def planner_node(state: AgentState):
    """SQL 规划节点"""
    logger.info("--- Node: SQL Planner ---")
    return sql_planner.invoke(state)

# =============================================================================
# Executor Node
# =============================================================================

@trace_node
def executor_node(state: AgentState):
    """
    SQL 执行节点
    
    包含 Reflector 逻辑：
    - 零结果验证
    - 语义验证
    - 完整性验证
    """
    logger.info("--- Node: SQL Executor ---")
    
    
    cache_hit = state.get("cache_hit")
    is_from_cache = cache_hit is not None
    if is_from_cache:
        logger.info(f"[Executor] 缓存命中模式: 跳过验证流程, cache_score={cache_hit.get('cache_score', 'N/A')}")
    
    sql = state.get("sql_query")
    if not sql:
        return {"data_result": [], "error": "No SQL generated"}
    
    # 执行 SQL
    result_str = sql_executor_tool.invoke(sql)
    
    # 检查错误
    if result_str.startswith("ERROR:"):
        current_retries = state.get("retry_count", 0)
        return {
            "data_result": [{"result": result_str}],
            "error": result_str,
            "retry_count": current_retries + 1,
            "original_failed_sql": sql
        }
    
    # 解析结果
    data_result = []
    try:
        if result_str.startswith("["):
            data_result = json.loads(result_str)
        else:
            data_result = [{"result": result_str}]
    except json.JSONDecodeError:
        data_result = [{"result": result_str}]

    # 检查是否为空结果
    is_empty = _check_is_empty(data_result)
    
    verification_attempted = state.get("verification_attempted", False)
    
    
    if is_from_cache:
        logger.info("[Executor] 缓存命中，跳过 Reflector 验证")
        return {
            "data_result": data_result,
            "error": None,
            "semantic_validation_attempted": True,
            "completeness_validation_attempted": True,
            "final_answer": None
        }
    
    # === Zero-Result Verification Logic (Reflector V2) ===
    if is_empty and not verification_attempted:
        return _handle_zero_result_verification(state, sql, data_result)
    
    # === V4: 成功后的语义验证 ===
    intent = state.get("intent", {}) or {}
    semantic_validation_attempted = state.get("semantic_validation_attempted", False)
    filter_conditions = intent.get("filter_conditions", [])
    
    if filter_conditions and not semantic_validation_attempted:
        semantic_result = _handle_semantic_validation(state, sql, intent, data_result)
        if semantic_result:
            return semantic_result
    
    # === V14: 语义完整性验证 ===
    completeness_validation_attempted = state.get("completeness_validation_attempted", False)
    query_requirements = intent.get("query_requirements", {}) if intent else {}
    
    if query_requirements and not completeness_validation_attempted:
        completeness_result = _handle_completeness_validation(state, sql, intent, data_result)
        if completeness_result:
            return completeness_result
    
    return {
        "data_result": data_result,
        "error": None,
        "semantic_validation_attempted": True,
        "completeness_validation_attempted": True,
        "final_answer": None
    }

def _check_is_empty(data_result) -> bool:
    """检查结果是否为空"""
    if not data_result:
        return True
    if len(data_result) == 1:
        first = data_result[0]
        if all(v is None for v in first.values()):
            return True
        if len(first) == 1:
            val = list(first.values())[0]
            if val == 0 or val is None:
                return True
        elif all(v == 0 or v is None for v in first.values()):
            return True
    return False

def _handle_zero_result_verification(state: AgentState, sql: str, data_result: list) -> dict:
    """处理零结果验证逻辑"""
    logger.info("--- Zero Result Detected: Triggering Enhanced Verification (V2) ---")
    
    intent = state.get("intent", {})
    
    # Step 1: 提取过滤条件中的实体
    entities = extract_filter_entities(sql, intent)
    logger.info(f"[Reflector V2] Extracted Entities: {entities}")
    
    if not entities:
        logger.info("[Reflector V2] No entities extracted, skipping verification")
        return {
            "data_result": data_result,
            "error": None,
            "verification_attempted": True,
            "final_answer": None
        }
    
    # Step 2: 获取轻量级 Schema 上下文
    schema_context = get_schema_context_for_probe()
    
    # Step 3: 为每个实体生成探针 SQL 并执行
    all_probe_results = {}
    
    for entity_type, entity_value in entities.items():
        logger.info(f"[Reflector V3] Generating probe for {entity_type}='{entity_value}'")
        
        probe_sql = generate_probe_sql(entity_type, entity_value, schema_context)
        if not probe_sql:
            logger.info("[Reflector V3] Failed to generate probe SQL")
            continue
            
        logger.info(f"[Reflector V3] Probe SQL: {probe_sql}")
        
        probe_result_str = sql_executor_tool.invoke(probe_sql)
        logger.info(f"[Reflector V3] Probe Result: {probe_result_str}")
        
        if probe_result_str and not probe_result_str.startswith("ERROR:") and probe_result_str != "[]":
            all_probe_results[entity_type] = {
                "original_value": entity_value,
                "found_values": probe_result_str
            }
            logger.info(f"[Reflector V3] Found match for '{entity_value}'")
        else:
            logger.info(f"[Reflector V3] No match found for '{entity_value}'")
    
    # Step 4: 如果找到了匹配结果，返回给 Planner 重写
    if all_probe_results:
        logger.info(f"[Reflector V2] Found corrections: {all_probe_results}")
        
        correction_info = json.dumps(all_probe_results, ensure_ascii=False)
        
        
        updated_entity_mappings = state.get("verified_entity_mappings", {}).copy()
        for entity_key, probe_info in all_probe_results.items():
            original_value = probe_info.get("original_value", "")
            found_values_str = probe_info.get("found_values", "")
            if found_values_str and original_value:
                try:
                    found_list = ast.literal_eval(found_values_str)
                    if found_list and len(found_list) > 0:
                        first_item = found_list[0]
                        if isinstance(first_item, dict):
                            actual_value = list(first_item.values())[0]
                            if isinstance(original_value, list):
                                for ov in original_value:
                                    updated_entity_mappings[str(ov)] = actual_value
                            else:
                                updated_entity_mappings[str(original_value)] = actual_value
                            logger.info(f"[V6 Cache] 缓存实体映射: {original_value} -> {actual_value}")
                except Exception as e:
                    logger.warning(f"[V6 Cache] 解析探针结果失败: {e}")
        
        current_retries = state.get("retry_count", 0)
        return {
            "data_result": data_result,
            "error": None,
            "verification_attempted": True,
            "verification_result": correction_info,
            "original_failed_sql": sql,
            "retry_count": current_retries + 1,
            "verified_entity_mappings": updated_entity_mappings
        }
    
    logger.info("[Reflector V2] All probes failed, likely no data exists")
    return {
        "data_result": data_result,
        "error": None,
        "verification_attempted": True,
        "final_answer": None
    }

def _handle_semantic_validation(state: AgentState, sql: str, intent: dict, data_result: list) -> dict:
    """处理语义验证"""
    filter_conditions = intent.get("filter_conditions", [])
    logger.info(f"--- V4: Semantic Validation (filter_conditions: {len(filter_conditions)}) ---")
    
    user_query = intent.get("original_query", "")
    validation_result = result_validator.validate_filter_conditions(sql, filter_conditions, user_query)
    
    logger.info(f"[ResultValidator] is_complete: {validation_result.is_complete}, confidence: {validation_result.confidence}")
    logger.info(f"[ResultValidator] evidence: {validation_result.evidence}")
    
    if not validation_result.is_complete and validation_result.confidence >= 0.7:
        logger.info(f"[ResultValidator] Missing conditions detected: {validation_result.missing_conditions}")
        logger.info(f"[ResultValidator] Suggestion: {validation_result.suggestion}")
        
        current_retries = state.get("retry_count", 0)
        if current_retries < 3:
            missing_info = json.dumps({
                "missing_conditions": validation_result.missing_conditions,
                "suggestion": validation_result.suggestion
            }, ensure_ascii=False)
            
            return {
                "data_result": data_result,
                "error": f"SQL语义不完整: {validation_result.suggestion}",
                "semantic_validation_attempted": True,
                "semantic_validation_result": missing_info,
                "original_failed_sql": sql,
                "retry_count": current_retries + 1
            }
        else:
            logger.info("[ResultValidator] Max retries reached, proceeding with current result")
    
    return None

def _handle_completeness_validation(state: AgentState, sql: str, intent: dict, data_result: list) -> dict:
    """处理语义完整性验证"""
    query_requirements = intent.get("query_requirements", {})
    logger.info(f"--- V14: Completeness Validation (query_requirements: {query_requirements}) ---")
    
    user_query = intent.get("original_query", "")
    completeness_result = completeness_validator.validate(
        sql=sql,
        query_requirements=query_requirements,
        user_query=user_query
    )
    
    logger.info(f"[CompletenessValidator] is_complete: {completeness_result.is_complete}")
    logger.info(f"[CompletenessValidator] evidence: {completeness_result.evidence}")
    
    if not completeness_result.is_complete:
        logger.info(f"[CompletenessValidator] Missing: sort={completeness_result.missing_sort}, limit={completeness_result.missing_limit}")
        logger.info(f"[CompletenessValidator] Suggestion: {completeness_result.suggestion}")
        
        current_retries = state.get("retry_count", 0)
        if current_retries < 3:
            if completeness_result.retry_strategy == "lightweight":
                return {
                    "data_result": data_result,
                    "error": f"SQL语义不完整: {completeness_result.suggestion}",
                    "completeness_validation_attempted": True,
                    "completeness_validation_result": completeness_result.to_dict(),
                    "original_failed_sql": sql,
                    "retry_count": current_retries + 1
                }
            else:
                return {
                    "data_result": data_result,
                    "error": f"召回不完整: {completeness_result.suggestion}",
                    "completeness_validation_attempted": True,
                    "completeness_validation_result": completeness_result.to_dict(),
                    "cached_schema_context": None,
                    "retry_count": current_retries + 1
                }
        else:
            logger.info("[CompletenessValidator] Max retries reached, proceeding with current result")
    
    return None

# =============================================================================
# Analyzer Node (V7)
# =============================================================================

@trace_node
def analyzer_node(state: AgentState):
    """
    数据分析节点：对 SQL 执行结果进行分析和可视化决策
    
    功能:
    1. 生成数据洞察（最大、最小、趋势等）
    2. 决策是否需要可视化
    3. 生成 ECharts 配置
    
    Author: CYJ
    Time: 2025-11-26
    """
    logger.info("--- Node: Analyzer (V7) ---")
    
    data_result = state.get("data_result", [])
    intent = state.get("intent", {}) or {}
    user_query = intent.get("original_query", "") or intent.get("rewritten_query", "")
    sql_query = state.get("sql_query", "")
    
    # 检查是否有有效数据
    if not data_result or not isinstance(data_result, list):
        logger.info("[Analyzer] 无有效数据，跳过分析")
        return {
            "analysis_result": None,
            "viz_recommendation": {"recommended": False, "reason": "无数据"}
        }
    
    # 检查数据是否为错误结果
    if len(data_result) == 1 and "result" in data_result[0]:
        val = data_result[0]["result"]
        if isinstance(val, str) and val.startswith("ERROR:"):
            logger.info("[Analyzer] 数据为错误结果，跳过分析")
            return {
                "analysis_result": None,
                "viz_recommendation": {"recommended": False, "reason": "执行错误"}
            }
    
    try:
        analysis_result = analyzer_agent.analyze(
            data=data_result,
            user_query=user_query,
            intent=intent,
            sql_query=sql_query
        )
        
        logger.info(f"[Analyzer] 分析完成: chart_type={analysis_result.visualization.chart_type}")
        logger.info(f"[Analyzer] 洞察摘要: {analysis_result.insight.summary}")
        
        return {
            "analysis_result": analysis_result.to_dict(),
            "viz_recommendation": analysis_result.visualization.to_dict(),
            "data_insight": analysis_result.insight.to_dict(),
            "echarts_option": analysis_result.visualization.echarts_option
        }
        
    except Exception as e:
        logger.exception(f"[Analyzer] 分析失败: {e}")
        return {
            "analysis_result": None,
            "viz_recommendation": {"recommended": False, "reason": f"分析失败: {str(e)}"}
        }

# =============================================================================
# Responder Node
# =============================================================================

@trace_node
def responder_node(state: AgentState):
    """响应生成节点"""
    logger.info("--- Node: Responder ---")
    
    intent = state.get("intent", {}) or {}
    intent_type = intent.get("intent_type")
    need_confirm = intent.get("need_user_confirmation", False)
    clarification_q = intent.get("clarification_question")
    
    # 0. 需要用户确认的查询意图
    if intent_type == 'query_data' and need_confirm:
        question = clarification_q or "为确保理解准确，请确认：上述改写是否符合您的真实需求？"
        return {"final_answer": question, "messages": [AIMessage(content=question)]}
    
    # 1. 处理闲聊
    if intent_type == 'chitchat':
        return _handle_chitchat(state)
    
    
    can_answer_from_history = intent.get("can_answer_from_history", False)
    if intent_type == 'query_data' and can_answer_from_history:
        return handle_answer_from_history(state, intent)
        
    # 2. 处理拒绝与引导
    if intent_type == 'rejection':
        return _handle_rejection(intent)
    
    # 3. 处理 Unclear
    if intent_type == 'unclear':
        return _handle_unclear(state, intent)

    # 4. 处理 SQL 执行结果
    return _handle_data_response(state, intent)

def _handle_chitchat(state: AgentState) -> dict:
    """处理闲聊意图"""
    from app.core.llm import get_llm, llm_rate_limit_sync
    from langchain_core.prompts import ChatPromptTemplate
    
    user_input = state['messages'][-1].content if state.get('messages') else ""
    
    try:
        llm = get_llm(temperature=_settings.LLM_TEMPERATURE_CREATIVE)
        prompt = ChatPromptTemplate.from_template(
            "User says: {input}\nYou are a helpful BI Assistant. Reply naturally to the user's greeting or small talk. Keep it brief."
        )
        chain = prompt | llm
        
        # 应用 LLM 调用限流 (Author: CYJ, Time: 2025-12-03)
        with trace_llm_call(), llm_rate_limit_sync():
            res = chain.invoke({"input": user_input})
        answer = res.content
    except Exception as e:
        logger.exception(f"[Chitchat] LLM 调用失败: {e}")
        record_error()
        # 错误降级：返回友好的默认问候
        answer = "你好！我是 ChatBI 助手，有什么数据查询需求可以告诉我？"
    
    return {"final_answer": answer, "messages": [AIMessage(content=answer)]}

def _handle_rejection(intent: dict) -> dict:
    """处理拒绝意图"""
    reason = intent.get("reason", "I cannot fulfill this request.")
    guidance = intent.get("guidance", "")
    answer = f"抱歉，我无法回答这个问题。原因：{reason}"
    if guidance:
        answer += f"\n建议：{guidance}"
    return {"final_answer": answer, "messages": [AIMessage(content=answer)]}

def _handle_unclear(state: AgentState, intent: dict) -> dict:
    """处理不清晰的意图"""
    from app.core.llm import get_llm, llm_rate_limit_sync
    from langchain_core.prompts import ChatPromptTemplate
    
    keywords = intent.get("detected_keywords", [])
    user_input = state['messages'][-1].content if state.get('messages') else ""
    keywords_str = ", ".join(keywords) if keywords else ""
    
    if keywords:
        try:
            llm = get_llm(temperature=_settings.LLM_TEMPERATURE_CREATIVE)
            
            clarify_prompt = ChatPromptTemplate.from_template("""
你是一个友好的 BI 助手。用户的提问意图不太清晰，但你检测到了一些关键词。
请生成一个自然、友好的确认问题，引导用户明确他们的查询需求。

【用户原始提问】
{user_input}

【检测到的关键词】
{keywords}

【要求】
1. 语气自然亲切，不要太死板
2. 根据用户的提问方式和关键词，推测可能的查询意图
3. 提供几个具体的查询选项供用户选择
4. 保持简洁，不超过100字

请直接输出确认问题，不要其他内容。
""")
            
            chain = clarify_prompt | llm
            # 应用 LLM 调用限流 (Author: CYJ, Time: 2025-12-03)
            with trace_llm_call(), llm_rate_limit_sync():
                result = chain.invoke({
                    "user_input": user_input,
                    "keywords": keywords_str
                })
            answer = result.content.strip()
            
        except Exception as e:
            logger.exception(f"[Unclear] LLM 调用失败: {e}")
            record_error()
            # 错误降级：返回带关键词的标准提示
            answer = f"抱歉，我不确定您的具体意图。但我检测到了关键词：【{keywords_str}】。您想查询这些关键词相关的哪些数据？"
    else:
        answer = "抱歉，我没有理解您的意思。请尝试用更清晰的语言描述您的查询需求。"
    
    return {"final_answer": answer, "messages": [AIMessage(content=answer)]}

def _handle_data_response(state: AgentState, intent: dict) -> dict:
    """处理数据查询响应"""
    from app.core.llm import get_llm, llm_rate_limit_sync
    from langchain_core.prompts import ChatPromptTemplate
    
    res = state.get("data_result")
    sql = state.get("sql_query")
    
    
    analysis_result = state.get("analysis_result")
    data_insight = state.get("data_insight")
    viz_recommendation = state.get("viz_recommendation")
    echarts_option = state.get("echarts_option")
    
    # Handle Clarification case
    if not sql:
        answer = "抱歉，我没有找到相关的数据表或字段。请尝试换一种提问方式。"
        return {
            "final_answer": answer,
            "messages": [AIMessage(content=answer)]
        }
        
    # Use LLM to interpret the result
    try:
        llm = get_llm(temperature=_settings.LLM_TEMPERATURE_RESPONSE)
        intent_data = state.get("intent", {})
        user_query = intent_data.get("rewritten_query") or intent_data.get("original_query") or "User Query"
        correction_note = state.get("correction_note", "")
        
        correction_display = ""
        if correction_note:
            correction_display = format_correction_note(correction_note)
        
        
        insight_display = ""
        if data_insight:
            insight_parts = []
            if data_insight.get("summary"):
                insight_parts.append(f"摘要: {data_insight['summary']}")
            if data_insight.get("highlights"):
                highlights = data_insight["highlights"]
                if isinstance(highlights, list) and highlights:
                    insight_parts.append(f"亮点: {'; '.join(highlights[:3])}")
            if data_insight.get("trend"):
                insight_parts.append(f"趋势: {data_insight['trend']}")
            insight_display = "\n".join(insight_parts)
        
        prompt = ChatPromptTemplate.from_template("""
你是一个专业的 BI 数据分析师，请用自然、友好的方式回答用户的数据查询。

【原始提问】{original_query}
【改写后的问题】{query}
【执行的 SQL】{sql}
【查询结果】{result}
【纠正说明】{correction_note}
【数据洞察】{data_insight}

### 回答要求

1. 纠正情况告知（如果有纠正说明）：
   - 在回答开头友好地说明做了哪些调整（如字段名/取值改正）

2. 结果呈现：
   - 数值类结果：直接给出数字，可适当格式化（如千分位）
   - 列表类结果：简洁列举，超过 5 条可只列主要条目
   - 空结果：说明“没有找到符合条件的数据”，并给出可能原因和下一步建议

3. 数据洞察（如果有）：
   - 结合数据洞察信息，给出简短分析观点（如“最高的是 XX，最低的是 YY” 或 “整体呈上升趋势”）

4. 语言风格：
   - 自然亲切，不要太生硬；尽量贴近用户原始问法

5. 避免：
   - 不要暴露 SQL 细节给用户
   - 不要重复问题本身
   - 不要输出“根据查询结果显示”这类空话
   - 【关键】不要编造数据！必须严格基于 {result} 中的实际数据回答

请直接输出回答内容。
""")
        
        chain = prompt | llm
        res_str = str(res)
        row_count = len(res) if isinstance(res, list) else 1
            
        original_query = intent_data.get("original_query") or user_query
        
        # 应用 LLM 调用限流 (Author: CYJ, Time: 2025-12-03)
        with llm_rate_limit_sync():
            ai_msg = chain.invoke({
                "original_query": original_query,
                "query": user_query, 
                "sql": sql, 
                "result": res_str,
                "row_count": row_count,
                "correction_note": correction_display if correction_display else "",
                "data_insight": insight_display if insight_display else ""
            })
        answer = ai_msg.content
        
    except Exception as e:
        logger.exception(f"[Responder] LLM 调用失败: {e}")
        record_error()
        # 错误降级：返回友好提示，不暴露原始数据
        row_count = len(res) if isinstance(res, list) else 0
        if row_count > 0:
            answer = f"查询已完成，共获取到 {row_count} 条数据。由于系统繁忙，暂时无法生成详细分析，请稍后重试。"
        else:
            answer = "查询已完成，但由于系统繁忙，暂时无法生成回答。请稍后重试。"

    
    response = {
        "final_answer": answer,
        "messages": [AIMessage(content=answer)]
    }
    
    
    if viz_recommendation and viz_recommendation.get("recommended", False):
        response["visualization"] = {
            "chart_type": viz_recommendation.get("chart_type"),
            "echarts_option": echarts_option,
            "raw_data": res
        }
        logger.info(f"[Responder V7] 附加可视化配置 chart_type={viz_recommendation.get('chart_type')}")
    
    if data_insight:
        response["data_insight"] = data_insight
    
    
    if sql and res and isinstance(res, list) and len(res) > 0:
        data_summary = build_data_summary(res, user_query)
        response["last_query_context"] = {
            "query": user_query,
            "sql": sql,
            "data_result": res,
            "data_summary": data_summary,
            "row_count": len(res),
            "columns": list(res[0].keys()) if res else []
        }
        logger.info(f"[Responder V12] 保存查询上下文 row_count={len(res)}, columns={list(res[0].keys()) if res else []}")
        
        
        cache_hit = state.get("cache_hit")
        if not cache_hit:
            save_to_cache_sync(state, sql, res, intent_data)
    
    return response

# =============================================================================
# Diagnosis Nodes
# =============================================================================

@trace_node
def diagnoser_node(state: AgentState) -> dict:
    """
    诊断节点：使用统一的 IntelligentAnalyzer 进行诊断
    
    V4重构：合并原 ResultDiagnoser 功能为 IntelligentAnalyzer
    V10增强：快速路径处理表/列不存在错误
    
    Author: CYJ
    Time: 2025-11-25
    """
    import asyncio
    from .helpers import analyze_schema_error
    
    logger.info("[Diagnoser] 开始智能诊断...")
    
    # 检查诊断次数限制
    diagnosis_count = state.get("diagnosis_count", 0)
    if diagnosis_count >= 2:
        logger.warning("[Diagnoser] 已达到诊断次数上限，跳过诊断")
        return {
            "diagnosis_attempted": True,
            "diagnosis_result": None
        }
    
    
    schema_error_info = state.get("schema_error_info")
    if schema_error_info:
        result = _handle_schema_error_diagnosis(state, schema_error_info, diagnosis_count)
        if result:
            return result
    
    try:
        # 获取必要的状态信息
        sql_query = state.get("sql_query", "") or ""
        user_query = state.get("messages", [{}])[-1].content if state.get("messages") else ""
        intent_data = state.get("intent", {}) or {}
        if intent_data:
            user_query = intent_data.get("original_query", user_query) or user_query
        
        selected_tables = state.get("selected_tables", [])
        schema_context = state.get("cached_schema_context", "")
        data_result = state.get("data_result")
        filter_conditions = intent_data.get("filter_conditions", [])
        verified_mappings = state.get("verified_entity_mappings", {})
        
        # 从 schema_context 中提取表名
        if not selected_tables and schema_context:
            table_pattern = r'\[TABLE\]\s+(\w+)\s+\('
            matches = re.findall(table_pattern, schema_context)
            if matches:
                selected_tables = list(set(matches))
                logger.info(f"[Diagnoser] 从schema_context提取表名: {selected_tables}")
        
        logger.info(f"[Diagnoser] SQL: {sql_query[:100] if sql_query else 'None'}...")
        logger.info(f"[Diagnoser] 已选择表: {selected_tables}")
        logger.info(f"[Diagnoser] 用户查询: {user_query}")
        
        
        intelligent_analyzer = get_intelligent_analyzer()
        diagnosis_result = asyncio.get_event_loop().run_until_complete(
            intelligent_analyzer.diagnose(
                user_query=user_query,
                sql=sql_query,
                schema_ddl=schema_context,
                data_result=data_result,
                filter_conditions=filter_conditions,
                verified_mappings=verified_mappings
            )
        )
        
        logger.info(f"[Diagnoser] 诊断阶段: {diagnosis_result.phase.value}")
        logger.info(f"[Diagnoser] 需要重新召回: {diagnosis_result.need_recall}")
        logger.info(f"[Diagnoser] 需要探针验证: {diagnosis_result.need_probe}")
        logger.info(f"[Diagnoser] 建议: {diagnosis_result.final_recommendation}")
        
        # 转换为兼容格式
        legacy_result = _convert_diagnosis_result(diagnosis_result)
        
        return {
            "diagnosis_result": legacy_result,
            "intelligent_diagnosis_result": diagnosis_result,
            "diagnosis_attempted": True,
            "diagnosis_count": diagnosis_count + 1,
            "selected_tables": selected_tables
        }
        
    except Exception as e:
        logger.exception(f"[Diagnoser] 诊断失败: {e}")
        return {
            "diagnosis_attempted": True,
            "diagnosis_result": None
        }

def _handle_schema_error_diagnosis(state: AgentState, schema_error_info: dict, diagnosis_count: int) -> dict:
    """处理 Schema 错误诊断"""
    logger.info(f"[Diagnoser V10] 快速路径：检测到 Schema 错误信息")
    
    error_type = schema_error_info.get("error_type")
    missing_object = schema_error_info.get("missing_object")
    exists_in_db = schema_error_info.get("exists_in_db", False)
    suggestion = schema_error_info.get("suggestion", "")
    
    if error_type == "table_not_found":
        if exists_in_db:
            # 表存在于数据库但未召回
            legacy_result = DiagnosisResult(
                diagnosis_type=DiagnosisType.SCHEMA_INCOMPLETE,
                confidence=0.95,
                root_cause=suggestion,
                evidence=[f"SQL 执行报错: 表 '{missing_object}' 不存在，但该表存在于数据库 Schema 中"],
                suggested_action=SuggestedAction.RECALL_MORE_TABLES,
                suggested_actions=[
                    SuggestedActionItem(
                        action_type="add_table",
                        target=missing_object,
                        description=f"需要添加表 {missing_object}"
                    )
                ],
                missing_tables=[missing_object]
            )
            logger.info(f"[Diagnoser V10] Schema 召回遗漏，需要补充表: {missing_object}")
        else:
            # 表不存在于数据库
            similar_tables = schema_error_info.get("similar_tables", [])
            legacy_result = DiagnosisResult(
                diagnosis_type=DiagnosisType.SQL_LOGIC_ERROR,
                confidence=0.95,
                root_cause=f"模型引用了不存在的表 '{missing_object}'",
                evidence=[suggestion],
                suggested_action=SuggestedAction.REGENERATE_SQL,
                suggested_actions=[
                    SuggestedActionItem(
                        action_type="fix_table",
                        target=missing_object,
                        description=f"表 '{missing_object}' 不存在，可能需要使用 {similar_tables}" if similar_tables else f"表 '{missing_object}' 不存在"
                    )
                ]
            )
            # 将修复建议传递给 planner
            intent = state.get("intent", {}) or {}
            intent["sql_fix_hint"] = {
                "root_cause": f"表 '{missing_object}' 不存在于数据库",
                "suggestions": [f"不要使用表 '{missing_object}'"] + ([f"可以考虑使用 {', '.join(similar_tables)}"] if similar_tables else [])
            }
            state["intent"] = intent
            logger.info(f"[Diagnoser V10] 模型幻觉，表 '{missing_object}' 不存在，建议: {similar_tables}")
    
    elif error_type == "column_not_found":
        similar_columns = schema_error_info.get("similar_columns", [])
        legacy_result = DiagnosisResult(
            diagnosis_type=DiagnosisType.SQL_LOGIC_ERROR,
            confidence=0.9,
            root_cause=f"列 '{missing_object}' 不存在",
            evidence=[suggestion],
            suggested_action=SuggestedAction.REGENERATE_SQL,
            suggested_actions=[
                SuggestedActionItem(
                    action_type="fix_column",
                    target=missing_object,
                    description=f"列 '{missing_object}' 不存在，可能需要使用 {similar_columns}" if similar_columns else f"列 '{missing_object}' 不存在"
                )
            ]
        )
        # 将修复建议传递给 planner
        intent = state.get("intent", {}) or {}
        intent["sql_fix_hint"] = {
            "root_cause": f"列 '{missing_object}' 不存在",
            "suggestions": [f"不要使用列 '{missing_object}'"] + ([f"可以考虑使用 {', '.join(similar_columns)}"] if similar_columns else [])
        }
        state["intent"] = intent
        logger.info(f"[Diagnoser V10] 列 '{missing_object}' 不存在，建议: {similar_columns}")
    else:
        return None
    
    return {
        "diagnosis_result": legacy_result,
        "diagnosis_attempted": True,
        "diagnosis_count": diagnosis_count + 1,
        "schema_error_info": None
    }

def _convert_diagnosis_result(diagnosis_result) -> DiagnosisResult:
    """转换诊断结果为兼容格式"""
    if diagnosis_result.need_recall and diagnosis_result.understanding_result:
        return DiagnosisResult(
            diagnosis_type=DiagnosisType.SCHEMA_INCOMPLETE,
            confidence=diagnosis_result.understanding_result.confidence,
            root_cause=diagnosis_result.final_recommendation,
            evidence=diagnosis_result.understanding_result.evidence,
            suggested_action=SuggestedAction.RECALL_MORE_TABLES,
            suggested_actions=[
                SuggestedActionItem(
                    action_type="add_table",
                    target=table,
                    description=f"需要添加表 {table}"
                )
                for table in diagnosis_result.understanding_result.missing_tables
            ],
            missing_tables=diagnosis_result.understanding_result.missing_tables
        )
    elif diagnosis_result.need_probe and diagnosis_result.sql_building_result:
        return DiagnosisResult(
            diagnosis_type=DiagnosisType.ENTITY_MAPPING,
            confidence=diagnosis_result.sql_building_result.confidence,
            root_cause=diagnosis_result.final_recommendation,
            evidence=diagnosis_result.sql_building_result.evidence,
            suggested_action=SuggestedAction.PROBE_ENTITIES,
            suggested_actions=[
                SuggestedActionItem(
                    action_type="probe_entity",
                    target=e.get("column"),
                    description=f"探测字段 {e.get('column')} 的实际值",
                    details=e
                )
                for e in diagnosis_result.sql_building_result.suspicious_entities
            ],
            entities_to_probe=diagnosis_result.sql_building_result.suspicious_entities
        )
    else:
        return DiagnosisResult(
            diagnosis_type=DiagnosisType.DATA_TRULY_EMPTY,
            confidence=0.8,
            root_cause=diagnosis_result.final_recommendation,
            evidence=[diagnosis_result.final_recommendation],
            suggested_action=SuggestedAction.CONFIRM_EMPTY,
            suggested_actions=[]
        )

@trace_node
def schema_completer_node(state: AgentState) -> dict:
    """
    Schema 补全节点：当诊断为 Schema 不完整时，自动补全缺失的表
    """
    import asyncio
    logger.info("[SchemaCompleter] 开始补全Schema...")
    
    try:
        diagnosis_result = state.get("diagnosis_result")
        if not diagnosis_result:
            return {"schema_completed": False}
        
        selected_tables = state.get("selected_tables", [])
        
        # 获取建议添加的表
        suggested_tables = []
        for action in diagnosis_result.suggested_actions:
            if action.action_type == "add_table" and action.target:
                suggested_tables.append(action.target)
        
        if not suggested_tables:
            logger.info("[SchemaCompleter] 没有需要补全的项")
            return {"schema_completed": True}
        
        # 合并表列表
        new_tables = list(set(selected_tables + suggested_tables))
        logger.info(f"[SchemaCompleter] 补全: {selected_tables} -> {new_tables}")
        
        # 重新获取完整的Schema信息
        user_query = state.get("messages", [{}])[-1].content if state.get("messages") else ""
        intent_data = state.get("intent", {})
        if intent_data:
            user_query = intent_data.get("original_query", user_query) or user_query
        
        completion_result = asyncio.get_event_loop().run_until_complete(schema_completer.complete_schema(
            user_query=user_query,
            current_tables=selected_tables,
            missing_tables=suggested_tables
        ))
        
        if completion_result.success:
            logger.info(f"[SchemaCompleter] Schema补全成功，新增表: {completion_result.added_tables}")
            
            intent = state.get("intent", {}) or {}
            intent["schema_correction"] = {
                "added_tables": completion_result.added_tables,
                "complete_ddl": completion_result.complete_ddl,
                "diagnosis_hint": diagnosis_result.root_cause
            }
            
            current_schema = state.get("cached_schema_context", "")
            updated_schema = current_schema + completion_result.complete_ddl if current_schema else completion_result.complete_ddl
            
            logger.info(f"[SchemaCompleter] 已更新cached_schema_context")
            
            return {
                "selected_tables": new_tables,
                "schema_completed": True,
                "intent": intent,
                "retry_count": 0,
                "cached_schema_context": updated_schema
            }
        else:
            logger.warning(f"[SchemaCompleter] Schema补全失败: {completion_result.error}")
            return {"schema_completed": False}
            
    except Exception as e:
        logger.error(f"[SchemaCompleter] Schema补全异常: {e}")
        return {"schema_completed": False}
