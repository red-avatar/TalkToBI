"""
功能：对话编排器 (Dialog Orchestrator)
说明：
    使用 LangGraph 构建多 Agent 协同的工作流 (StateGraph)。
    路由逻辑：Start -> Intent -> (Query?) -> Planner -> Executor -> (Error Loop?) -> End
    
    V2 改进：
    - 增强 Reflector：智能实体纠正（广州 -> 广州市）
    - 分层检索支持
作者：CYJ
时间：2025-11-22 (V2: 2025-11-25)
"""
from typing import Literal, Dict, List, Optional, Tuple
import re
import json
import asyncio
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage

from app.core.state import AgentState
from app.core.config import get_settings
# V16: 缓存服务
from app.services.cache_service import CacheService, get_cache_service

_settings = get_settings()
from app.modules.agents.intent_agent import IntentAgent
from app.modules.agents.sql_agent import SqlPlannerAgent
from app.modules.dialog.memory import get_memory_checkpointer
from app.modules.schema.catalog import get_schema_catalog
# V4: 使用统一的诊断和验证模块
from app.modules.diagnosis import (
    SchemaCompleter,
    DiagnosisType,
    SuggestedAction,
    IntelligentAnalyzer,
    get_intelligent_analyzer,
    ResultValidator,
    get_result_validator
)
# V14: 语义完整性验证器
from app.modules.diagnosis.semantic_completeness_validator import (
    SemanticCompletenessValidator,
    get_completeness_validator
)
# V7: 分析与可视化模块
from app.modules.agents.analyzer import AnalyzerAgent, get_analyzer_agent
import logging

logger = logging.getLogger(__name__)

from app.modules.tools.execution import SqlExecutorTool

# Initialize Agents and Tools
intent_agent = IntentAgent()
sql_planner = SqlPlannerAgent()
sql_executor_tool = SqlExecutorTool()
schema_completer = SchemaCompleter()
result_validator = get_result_validator()  # V4: 统一结果验证器
completeness_validator = get_completeness_validator()  # V14: 语义完整性验证器
analyzer_agent = get_analyzer_agent()  # V7: 数据分析与可视化 Agent
cache_service = get_cache_service()  # V16: 查询缓存服务

# =============================================================================
# Cache Check Node (V16: 智能缓存)
# =============================================================================

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
    
    # 同步检查缓存 (V2)
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
                "cache_score": cache_hit.cache_score  # V16.1: 添加评分信息
            },
            "sql_query": cache_hit.sql,  # 直接设置 SQL
            "intent": {
                "original_query": user_input,
                "rewritten_query": cache_hit.rewritten_query or user_input,
                "intent_type": "query_data",
                "from_cache": True
            }
        }
    
    logger.info("[CacheCheck] 缓存未命中，继续正常流程")
    return {"cache_hit": None}


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


# =============================================================================
# Reflector Helper Functions (V2)
# =============================================================================

def _extract_filter_conditions_from_sql(sql: str) -> List[Dict[str, str]]:
    """
    从 SQL 中直接提取筛选条件（表名.字段名 = '值' 或 IN (...)）
    
    V6: 增强支持 IN 操作符，解决 shop_type IN ('自营', '第三方') 等无法提取的问题
    
    设计原理：
    SQL 已经包含了所有需要的信息，不需要重新召回或调用 LLM 推断。
    直接解析 WHERE 子句，提取表名、字段名、筛选值。
    
    Args:
        sql: 执行的 SQL 语句
        
    Returns:
        List[Dict]: [
            {"table": "dim_region", "column": "city", "value": "广州", "alias": "dr"},
            ...
        ]
        
    Author: CYJ
    Time: 2025-11-26
    """
    conditions = []
    
    # 提取 WHERE 子句
    sql_upper = sql.upper()
    where_idx = sql_upper.find('WHERE')
    if where_idx == -1:
        return conditions
    
    where_clause = sql[where_idx:]
    
    # 提取表别名映射：FROM orders o, JOIN dim_region dr -> {"o": "orders", "dr": "dim_region"}
    alias_map = _extract_table_aliases(sql)
    
    # 模式 1: alias.column = 'value'  或 table.column = 'value'
    # 示例: dr.city = '广州' 或 dim_region.city = '广州'
    pattern_eq = r"(\w+)\.(\w+)\s*=\s*['\"]([^'\"]+)['\"]"
    
    # 模式 2: alias.column IN ('value1', 'value2', ...)
    # 示例: s.shop_type IN ('自营', '第三方')
    pattern_in = r"(\w+)\.(\w+)\s+IN\s*\(([^)]+)\)"
    
    # 匹配模式 1 (等于)
    matches_eq = re.findall(pattern_eq, where_clause, re.IGNORECASE)
    for alias_or_table, column, value in matches_eq:
        # 排除常见的非实体值
        if value.upper() in ['NULL', 'TRUE', 'FALSE', '1', '0']:
            continue
        
        # 解析表名
        table_name = alias_map.get(alias_or_table.lower(), alias_or_table)
        
        conditions.append({
            "table": table_name,
            "column": column,
            "value": value,
            "alias": alias_or_table if alias_or_table.lower() in alias_map else None
        })
    
    # 匹配模式 2 (IN 操作符)
    matches_in = re.findall(pattern_in, where_clause, re.IGNORECASE)
    for alias_or_table, column, values_str in matches_in:
        # 解析 IN 括号内的所有值: 'val1', 'val2' -> [val1, val2]
        values = re.findall(r"['\"]([^'\"]+)['\"]", values_str)
        
        # 解析表名
        table_name = alias_map.get(alias_or_table.lower(), alias_or_table)
        
        for value in values:
            if value.upper() in ['NULL', 'TRUE', 'FALSE', '1', '0']:
                continue
            conditions.append({
                "table": table_name,
                "column": column,
                "value": value,
                "alias": alias_or_table if alias_or_table.lower() in alias_map else None
            })
    
    return conditions


def _extract_table_aliases(sql: str) -> Dict[str, str]:
    """
    提取 SQL 中的表别名映射
    
    示例:
        FROM orders o -> {"o": "orders"}
        JOIN dim_region dr ON -> {"dr": "dim_region"}
        
    Author: CYJ
    Time: 2025-11-25
    """
    alias_map = {}
    
    # 模式: FROM/JOIN table_name alias 或 FROM/JOIN table_name AS alias
    patterns = [
        r"FROM\s+(\w+)\s+(?:AS\s+)?(\w+)",  # FROM orders o 或 FROM orders AS o
        r"JOIN\s+(\w+)\s+(?:AS\s+)?(\w+)",  # JOIN dim_region dr
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, sql, re.IGNORECASE)
        for table, alias in matches:
            # 确保 alias 不是 SQL 关键字
            if alias.upper() not in ['ON', 'WHERE', 'AND', 'OR', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'JOIN', 'GROUP', 'ORDER', 'LIMIT']:
                alias_map[alias.lower()] = table
    
    return alias_map


def _extract_filter_entities(sql: str, intent: dict) -> Dict[str, any]:
    """
    从 SQL 和意图中提取过滤条件的实体值
    
    V7: 保留 table.column 完整信息，不再使用粗略的类型分类
    解决探针查询错误表的问题（如 pay_status 被误查为 orders.status）
    
    Args:
        sql: 执行的 SQL 语句
        intent: 意图识别结果
        
    Returns:
        Dict[str, str|List[str]]: {"table.column": 实体值或值列表}
        示例: {"payments.pay_status": "成功", "shops.shop_type": ["自营", "第三方"]}
        
    Author: CYJ
    Time: 2025-11-26
    """
    entities = {}
    
    # 从 SQL 中提取筛选条件
    conditions = _extract_filter_conditions_from_sql(sql)
    
    for cond in conditions:
        table = cond.get("table", "")
        column = cond.get("column", "")
        value = cond.get("value", "")
        
        if not table or not column or not value:
            continue
        
        # V7: 使用 table.column 作为 key，保留完整信息
        entity_key = f"{table}.{column}"
        
        # 支持同一 table.column 的多个值（IN 操作符）
        if entity_key in entities:
            existing = entities[entity_key]
            if isinstance(existing, list):
                if value not in existing:
                    existing.append(value)
            else:
                if existing != value:
                    entities[entity_key] = [existing, value]
        else:
            entities[entity_key] = value
    
    return entities


# V5: 移除所有硬编码映射，完全依赖动态探针发现
# 中英文映射关系应该从以下来源获取：
# 1. Schema注释中的枚举值描述
# 2. 知识图谱中的实体关系
# 3. 探针SQL动态查询数据库实际值
# Author: CYJ
# Time: 2025-11-26


def _get_translation_variants(value) -> List[str]:
    """
    获取实体值的变体列表
    
    V5: 移除硬编码映射，只返回原值
    翻译变体发现完全依赖：
    1. Schema注释中的枚举值描述
    2. 知识图谱中的实体关系  
    3. 探针SQL动态查询数据库实际值
    
    Args:
        value: 原始实体值（可以是 str 或 list）
        
    Returns:
        包含原值的列表（不再包含硬编码翻译变体）
        
    Author: CYJ
    Time: 2025-11-26
    """
    # 处理 list 类型
    if isinstance(value, list):
        all_variants = []
        for v in value:
            all_variants.extend(_get_translation_variants(v))
        return list(set(all_variants))  # 去重
    
    # 确保 value 是字符串
    if not isinstance(value, str):
        value = str(value)
    
    # V5: 只返回原值，不再使用硬编码映射
    # 翻译变体由 _generate_probe_sql 中的 LLM 智能推断
    return [value]


def _classify_entity(value: str, context: str) -> Optional[str]:
    """
    根据上下文推断实体类型
    
    Author: CYJ
    Time: 2025-11-25
    """
    context_lower = context.lower()
    
    # 地理位置相关的列名
    location_patterns = ['city', 'region', 'province', 'country', 'area', 'district', 'shipping_region']
    for pat in location_patterns:
        if pat in context_lower:
            return 'location'
    
    # 店铺相关
    shop_patterns = ['shop', 'store', 'seller']
    for pat in shop_patterns:
        if pat in context_lower:
            return 'shop'
    
    # 品牌相关
    brand_patterns = ['brand', 'manufacturer']
    for pat in brand_patterns:
        if pat in context_lower:
            return 'brand'
    
    # 状态相关
    status_patterns = ['status', 'state']
    for pat in status_patterns:
        if pat in context_lower:
            return 'status'
    
    # 默认归类为通用实体
    return 'entity'


def _generate_probe_sql(entity_key: str, entity_value, schema_context: str) -> Optional[str]:
    """
    根据 table.column 格式生成精准的探针 SQL
    
    V7: 支持 table.column 格式，直接查询指定的表和列
    解决探针查询错误表的问题
    
    Args:
        entity_key: 实体标识（table.column 格式，如 'payments.pay_status'）
        entity_value: 用户输入的实体值（可以是 str 或 list）
        schema_context: 已召回的 Schema 信息
        
    Returns:
        探针 SQL 或 None
        
    Author: CYJ
    Time: 2025-11-26
    """
    try:
        from app.core.llm import get_llm
        from langchain_core.prompts import ChatPromptTemplate
        
        # V7: 解析 table.column 格式
        if '.' in entity_key:
            table_name, column_name = entity_key.split('.', 1)
        else:
            # 兑容旧格式，默认为 entity_type
            table_name = None
            column_name = entity_key
        
        # V8: 处理 list 类型值 - 生成组合查询而非只取第一个
        # Author: CYJ
        # Time: 2025-11-26
        is_list_value = isinstance(entity_value, list)
        if is_list_value:
            if len(entity_value) == 0:
                return None
            # 将所有值转为字符串列表
            entity_values = [str(v) if not isinstance(v, str) else v for v in entity_value]
            entity_value_str = entity_values[0]  # 用于后续中英文映射推断
            logger.info(f"[Reflector V8] entity_value is list with {len(entity_values)} elements: {entity_values}")
        else:
            entity_values = None
            entity_value_str = str(entity_value) if not isinstance(entity_value, str) else entity_value
        
        # V9: 统一使用 LLM 生成探针 SQL，让 LLM 做语义扩展
        # 移除硬编码映射，完全依赖 LLM 的语义理解能力
        # Author: CYJ
        # Time: 2025-11-26
        llm = get_llm(temperature=_settings.LLM_TEMPERATURE_PRECISE)
        
        # 处理多值列表
        values_to_process = entity_values if is_list_value else [entity_value_str]
        values_str = ", ".join([f"'{v}'" for v in values_to_process])
        
        prompt = ChatPromptTemplate.from_template("""
你是一个 MySQL 专家。用户的查询返回了 0 条结果，可能是因为过滤条件中的值与数据库中的实际值不匹配。

【已知 Schema 信息】
{schema_context}

【用户使用的实体】
- 表.字段：{table_column}
- 用户输入值：{entity_values}

【任务】
生成一个探针 SQL，查找数据库中与用户输入值语义相似的实际值。

【重要】你需要做语义扩展，考虑以下变体：
1. 中英文映射：如"微信"→"wechat"，"成功"→"success"
2. 简称/全称：如"家电"→"家用电器"，"电子"→"电子产品"
3. 同义词：如"手机"→"移动电话/智能手机"，"签收"→"delivered"
4. 编码变体：如"一线"→"tier1/first_tier"，"自营"→"self/self_operated"

【输出要求】
1. 生成: SELECT DISTINCT {column} FROM {table} WHERE ... LIMIT 20
2. WHERE 条件使用多个 LIKE 用 OR 连接，覆盖所有可能的变体
3. 对于每个用户输入值，都要生成对应的 LIKE 条件
4. 只输出纯 SQL，不要任何解释

示例：
- 输入"家电" → WHERE name LIKE '%家电%' OR name LIKE '%家用电器%' OR name LIKE '%appliance%'
- 输入"签收" → WHERE status LIKE '%签收%' OR status LIKE '%delivered%' OR status LIKE '%signed%'
""")
        
        chain = prompt | llm
        
        # 构建 table.column 格式
        table_column = f"{table_name}.{column_name}" if table_name else column_name
        
        result = chain.invoke({
            "schema_context": schema_context[:2000],  # 截断避免超长
            "table_column": table_column,
            "entity_values": values_str,
            "column": column_name,
            "table": table_name or "unknown_table"
        })
        
        probe_sql = result.content.strip()
        logger.info(f"[Reflector V9] LLM generated probe SQL: {probe_sql}")
        
        # 清理 markdown 代码块
        if probe_sql.startswith('```'):
            probe_sql = probe_sql.replace('```sql', '').replace('```', '').strip()
        
        return probe_sql
        
    except Exception as e:
        logger.error(f"Generate probe SQL failed: {e}")
        return None


def _get_schema_context_for_probe() -> str:
    """
    获取用于探针生成的 Schema 上下文（轻量级）
    
    Author: CYJ
    Time: 2025-11-25
    """
    try:
        catalog = get_schema_catalog()
        tables = catalog.list_tables(with_description=True)
        
        # 需要包含列信息的表（维度表 + 常用业务表）
        # V7: 添加 refunds 表，解决探针无法找到 refund_status 的问题
        tables_with_columns = [
            'dim_region', 'dim_product', 'dim_date', 'dim_channel',  # 维度表
            'shops', 'products', 'brands', 'users',   # 基础表
            'payments', 'orders', 'refunds', 'coupons'  # 业务表
        ]
        
        lines = []
        for t in tables:
            lines.append(f"Table: {t['name']} - {t.get('description', '')}")
            # 获取列信息
            if t['name'].startswith('dim_') or t['name'] in tables_with_columns:
                cols = catalog.list_columns_by_table(t['name'])
                for c in cols[:10]:  # 限制列数量
                    lines.append(f"  - {c['name']}: {c.get('description', '')}")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to get schema context: {e}")
        return ""


def _format_correction_note(correction_note: str) -> str:
    """
    格式化纠正说明为用户友好的文本
    
    Args:
        correction_note: SQL Agent 传递的纠正信息（可能是 JSON 或普通文本）
        
    Returns:
        用户友好的纠正说明文本
        
    Author: CYJ
    Time: 2025-11-25
    """
    if not correction_note:
        return ""
    
    try:
        # 尝试解析为 JSON（可能来自 verification_result）
        if correction_note.startswith('{'):
            data = json.loads(correction_note)
            parts = []
            for entity_type, info in data.items():
                if isinstance(info, dict):
                    original = info.get('original_value', '')
                    found = info.get('found_values', '')
                    # 解析 found_values（可能是嵌套的 JSON 字符串）
                    if found and found.startswith('['):
                        try:
                            found_list = json.loads(found.replace("'", '"'))
                            if found_list and len(found_list) > 0:
                                # 取第一个结果的第一个值
                                first_item = found_list[0]
                                if isinstance(first_item, dict):
                                    corrected_value = list(first_item.values())[0]
                                    parts.append(f"'{original}' → '{corrected_value}'")
                        except:
                            parts.append(f"'{original}' 已纠正")
                    else:
                        parts.append(f"'{original}' 已纠正")
            
            if parts:
                return "已自动纠正以下实体：" + "；".join(parts)
    except:
        pass
    
    # 如果不是 JSON，直接返回原文
    return correction_note


# =============================================================================
# Node Functions
# =============================================================================

def intent_node(state: AgentState):
    logger.info("--- Node: Intent Recognition ---")
    
    # V6: 保留跨轮字段，不要重置！
    # 这些字段需要跨轮保存，避免重复探针查询
    # Author: CYJ
    # Time: 2025-11-26
    preserved_entity_mappings = state.get("verified_entity_mappings", {})
    preserved_schema_knowledge = state.get("verified_schema_knowledge", {})
    
    intent_result = intent_agent.invoke(state)
    
    # 重置本轮临时字段
    intent_result["verification_attempted"] = False
    intent_result["verification_result"] = None
    intent_result["correction_note"] = None
    intent_result["retry_count"] = 0  # 重置重试计数
    intent_result["cached_schema_context"] = None  # 清除上一轮的缓存
    intent_result["error"] = None  # 清除错误信息
    intent_result["original_failed_sql"] = None  # 清除失败的 SQL
    intent_result["semantic_validation_attempted"] = False  # V6: 重置语义验证状态
    intent_result["diagnosis_attempted"] = False  # V6: 重置诊断状态
    intent_result["diagnosis_count"] = 0  # V6: 重置诊断计数
    intent_result["completeness_validation_attempted"] = False  # V14: 重置语义完整性验证状态
    intent_result["completeness_validation_result"] = None  # V14: 重置验证结果
    
    # V6: 恢复跨轮字段（这些不应被重置）
    intent_result["verified_entity_mappings"] = preserved_entity_mappings
    intent_result["verified_schema_knowledge"] = preserved_schema_knowledge
    
    logger.info(f"[Intent] 跨轮缓存: entity_mappings={len(preserved_entity_mappings)}条, schema_knowledge={len(preserved_schema_knowledge)}条")
    
    return intent_result

def planner_node(state: AgentState):
    logger.info("--- Node: SQL Planner ---")
    return sql_planner.invoke(state)

def executor_node(state: AgentState):
    logger.info("--- Node: SQL Executor ---")
    
    # V16.1: 检查是否为缓存命中的执行
    # 缓存命中时跳过验证逻辑，直接执行 SQL
    cache_hit = state.get("cache_hit")
    is_from_cache = cache_hit is not None
    if is_from_cache:
        logger.info(f"[Executor] 缓存命中模式: 跳过验证流程, cache_score={cache_hit.get('cache_score', 'N/A')}")
    
    # Check for verification SQL (from Reflector logic below)
    # If we are in verification mode, sql_query might be the verification query
    # But to keep it simple, we just use whatever is in 'sql_query'
    
    sql = state.get("sql_query")
    if not sql:
        return {"data_result": [], "error": "No SQL generated"}
    
    # Execute Real SQL
    result_str = sql_executor_tool.invoke(sql)
    
    # Check for ERROR
    if result_str.startswith("ERROR:"):
        current_retries = state.get("retry_count", 0)
        # V3: 保存失败的 SQL，供重试时参考
        # Author: CYJ
        # Time: 2025-11-25
        return {
            "data_result": [{"result": result_str}],
            "error": result_str,
            "retry_count": current_retries + 1,
            "original_failed_sql": sql  # 记录失败的 SQL
        }
    
    # Parse result
    # V2: 使用 json.loads 而非 ast.literal_eval，避免 Decimal 解析失败
    # Author: CYJ
    # Time: 2025-11-26
    data_result = []
    try:
        if result_str.startswith("["):
            data_result = json.loads(result_str)
        else:
            data_result = [{"result": result_str}]
    except json.JSONDecodeError:
        data_result = [{"result": result_str}]

    # === Zero-Result Verification Logic (Reflector V2) ===
    # If result is empty AND we haven't verified yet
    # V3 改进：增强空结果检测，包含 COUNT(*)=0, SUM()=0 等聚合结果
    # Author: CYJ
    # Time: 2025-11-25
    is_empty = False
    if not data_result:
        is_empty = True
    elif len(data_result) == 1:
        # Check for [{'count': 0}] or [{'val': None}] or [{'COUNT(*)': 0}]
        first = data_result[0]
        if all(v is None for v in first.values()):
            is_empty = True
        elif len(first) == 1:
            val = list(first.values())[0]
            # 检测聚合函数返回 0 的情况（COUNT, SUM 等）
            if val == 0 or val is None:
                is_empty = True
        # V3: 检测多列结果中所有值都为 0 或 None 的情况
        elif all(v == 0 or v is None for v in first.values()):
            is_empty = True
            
    # Check if we already tried verification to avoid infinite loops
    verification_attempted = state.get("verification_attempted", False)
    
    # V16.1: 缓存命中时跳过验证逻辑
    if is_from_cache:
        logger.info("[Executor] 缓存命中，跳过 Reflector 验证")
        return {
            "data_result": data_result,
            "error": None,
            "semantic_validation_attempted": True,
            "completeness_validation_attempted": True,
            "final_answer": None
        }
    
    if is_empty and not verification_attempted:
        logger.info("--- Zero Result Detected: Triggering Enhanced Verification (V2) ---")
        
        # V2: 使用新的实体提取 + 智能探针生成
        intent = state.get("intent", {})
        
        # Step 1: 提取过滤条件中的实体
        entities = _extract_filter_entities(sql, intent)
        logger.info(f"[Reflector V2] Extracted Entities: {entities}")
        
        if not entities:
            # 没有提取到实体，无法进行验证
            logger.info("[Reflector V2] No entities extracted, skipping verification")
            return {
                "data_result": data_result,
                "error": None,
                "verification_attempted": True,
                "final_answer": None 
            }
        
        # Step 2: 获取轻量级 Schema 上下文
        schema_context = _get_schema_context_for_probe()
        
        # Step 3: 为每个实体生成探针 SQL 并执行
        # V3: 单次 SQL 包含所有中英文变体，减少数据库查询次数
        all_probe_results = {}
        
        for entity_type, entity_value in entities.items():
            logger.info(f"[Reflector V3] Generating probe for {entity_type}='{entity_value}'")
            
            # V3: 生成单次 SQL，包含所有中英文变体（使用 OR 条件）
            probe_sql = _generate_probe_sql(entity_type, entity_value, schema_context)
            if not probe_sql:
                logger.info(f"[Reflector V3] Failed to generate probe SQL")
                continue
                
            logger.info(f"[Reflector V3] Probe SQL: {probe_sql}")
            
            # 执行探针
            probe_result_str = sql_executor_tool.invoke(probe_sql)
            logger.info(f"[Reflector V3] Probe Result: {probe_result_str}")
            
            # 检查探针结果
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
            
            # 构建纠正信息
            correction_info = json.dumps(all_probe_results, ensure_ascii=False)
            
            # V6: 将探针发现的映射写入跨轮缓存，避免后续重复探针
            # Author: CYJ
            # Time: 2025-11-26
            updated_entity_mappings = state.get("verified_entity_mappings", {}).copy()
            for entity_key, probe_info in all_probe_results.items():
                original_value = probe_info.get("original_value", "")
                found_values_str = probe_info.get("found_values", "")
                if found_values_str and original_value:
                    try:
                        import ast
                        found_list = ast.literal_eval(found_values_str)
                        if found_list and len(found_list) > 0:
                            first_item = found_list[0]
                            if isinstance(first_item, dict):
                                actual_value = list(first_item.values())[0]
                                # 支持原始值为列表的情况
                                if isinstance(original_value, list):
                                    for ov in original_value:
                                        updated_entity_mappings[str(ov)] = actual_value
                                else:
                                    updated_entity_mappings[str(original_value)] = actual_value
                                logger.info(f"[V6 Cache] 缓存实体映射: {original_value} -> {actual_value}")
                    except Exception as e:
                        logger.warning(f"[V6 Cache] 解析探针结果失败: {e}")
            
            # V3: 验证成功回到 Planner 前将重试计数 +1，避免再次完整检索
            current_retries = state.get("retry_count", 0)
            return {
                "data_result": data_result,
                "error": None,
                "verification_attempted": True,
                "verification_result": correction_info,
                "original_failed_sql": sql,
                "retry_count": current_retries + 1,
                "verified_entity_mappings": updated_entity_mappings  # V6: 更新跨轮缓存
            }
        
        # 如果所有探针都失败，可能的确没有数据
        logger.info("[Reflector V2] All probes failed, likely no data exists")
        return {
            "data_result": data_result,
            "error": None,
            "verification_attempted": True,
            "final_answer": None 
        }
    
    # === V4: 成功后的语义验证 (Semantic Validation) ===
    # 即使SQL执行成功，也要验证是否覆盖了所有筛选条件
    # Author: CYJ
    # Time: 2025-11-26
    semantic_validation_attempted = state.get("semantic_validation_attempted", False)
    intent = state.get("intent", {}) or {}  # 确保intent在此作用域内可用
    filter_conditions = intent.get("filter_conditions", [])
    
    if filter_conditions and not semantic_validation_attempted:
        logger.info(f"--- V4: Semantic Validation (filter_conditions: {len(filter_conditions)}) ---")
        
        # V4重构: 使用统一的 ResultValidator
        user_query = intent.get("original_query", "")
        validation_result = result_validator.validate_filter_conditions(sql, filter_conditions, user_query)
        
        logger.info(f"[ResultValidator] is_complete: {validation_result.is_complete}, confidence: {validation_result.confidence}")
        logger.info(f"[ResultValidator] evidence: {validation_result.evidence}")
        
        if not validation_result.is_complete and validation_result.confidence >= 0.7:
            # 发现遗漏的筛选条件，触发重新生成
            logger.info(f"[ResultValidator] Missing conditions detected: {validation_result.missing_conditions}")
            logger.info(f"[ResultValidator] Suggestion: {validation_result.suggestion}")
            
            # 检查是否已达到重试上限
            current_retries = state.get("retry_count", 0)
            if current_retries < 3:  # 最多重试3次
                # 构建补充指令
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
    
    # === V14: 语义完整性验证 (Semantic Completeness Validation) ===
    # 检查SQL是否满足用户的排序、分页、分组、指标等需求
    # Author: CYJ
    # Time: 2025-11-28
    completeness_validation_attempted = state.get("completeness_validation_attempted", False)
    query_requirements = intent.get("query_requirements", {}) if intent else {}
    
    if query_requirements and not completeness_validation_attempted:
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
            # 发现语义不完整，触发重新生成
            logger.info(f"[CompletenessValidator] Missing: sort={completeness_result.missing_sort}, limit={completeness_result.missing_limit}")
            logger.info(f"[CompletenessValidator] Suggestion: {completeness_result.suggestion}")
            
            # 检查是否已达到重试上限
            current_retries = state.get("retry_count", 0)
            if current_retries < 3:  # 最多重试3次
                # 根据重试策略决定是否复用缓存
                if completeness_result.retry_strategy == "lightweight":
                    # 轻量重试：复用缓存，只重新生成SQL
                    return {
                        "data_result": data_result,
                        "error": f"SQL语义不完整: {completeness_result.suggestion}",
                        "completeness_validation_attempted": True,
                        "completeness_validation_result": completeness_result.to_dict(),
                        "original_failed_sql": sql,
                        "retry_count": current_retries + 1
                        # 注: 不清除 cached_schema_context，复用缓存
                    }
                else:
                    # 完整重试：清除缓存，重新召回
                    return {
                        "data_result": data_result,
                        "error": f"召回不完整: {completeness_result.suggestion}",
                        "completeness_validation_attempted": True,
                        "completeness_validation_result": completeness_result.to_dict(),
                        "cached_schema_context": None,  # 清除缓存，触发重新召回
                        "retry_count": current_retries + 1
                    }
            else:
                logger.info("[CompletenessValidator] Max retries reached, proceeding with current result")
    
    return {
        "data_result": data_result,
        "error": None, # Clear error on success
        "semantic_validation_attempted": True,
        "completeness_validation_attempted": True,  # V14: 标记已验证
        "final_answer": None 
    }

# =============================================================================
# Analyzer Node (V7: 数据分析与可视化)
# =============================================================================

def analyzer_node(state: AgentState):
    """
    数据分析节点：对 SQL 执行结果进行分析和可视化决策
    
    功能：
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
        # 调用 AnalyzerAgent 进行分析
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
        logger.error(f"[Analyzer] 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "analysis_result": None,
            "viz_recommendation": {"recommended": False, "reason": f"分析失败: {str(e)}"}
        }


def _handle_answer_from_history(state: AgentState, intent: dict) -> dict:
    """
    处理基于历史数据的回答（query_data 的变体分支）
    
    当 intent_type='query_data' 且 can_answer_from_history=true 时，
    不走 SQL 流程，直接基于历史数据回答。
    
    Args:
        state: 当前状态
        intent: 意图识别结果
        
    Returns:
        更新的状态字典
        
    Author: CYJ
    Time: 2025-11-27 (V13 重构)
    """
    from app.core.llm import get_llm
    from langchain_core.prompts import ChatPromptTemplate
    
    logger.info("[Responder V13] 基于历史数据回答...")
    
    last_query_context = state.get("last_query_context", {})
    user_query = intent.get("original_query", "")
    rewritten_query = intent.get("rewritten_query", "")
    history_answer_reason = intent.get("history_answer_reason", "")
    entities = intent.get("entities", {})
    
    # 检查是否有历史数据
    if not last_query_context or not last_query_context.get("data_result"):
        logger.warning("[Responder V13] 无历史查询结果，无法基于历史回答")
        answer = "抱歉，我没有找到之前的查询结果。请先查询数据，然后再进行追问。"
        return {"final_answer": answer, "messages": [AIMessage(content=answer)]}
    
    data_result = last_query_context.get("data_result", [])
    previous_query = last_query_context.get("query", "")
    
    # 使用 LLM 基于已有数据进行计算和回答
    llm = get_llm(temperature=_settings.LLM_TEMPERATURE_BALANCED)
    
    prompt = ChatPromptTemplate.from_template("""
你是一个 BI 数据分析师。用户基于之前的查询结果提出了问题，请直接基于已有数据回答。

### 之前的查询
问题: {previous_query}
结果数据 (JSON):
{data_json}

### 用户当前问题
原始问题: {user_query}
改写后: {rewritten_query}
回答依据: {history_answer_reason}

### 任务
1. 分析用户的问题
2. 从已有数据中找到相关数值
3. 如果需要计算（如求差、求比、排名等），进行计算
4. 用自然语言回答用户，并说明依据

### 要求
- 必须基于已有数据回答，不要编造数据
- 说明答案的依据（如"根据之前的查询结果..."）
- 如果有计算，显示计算过程
- 语言自然亲切

请直接回答：
""")
    
    chain = prompt | llm
    
    try:
        data_json = json.dumps(data_result, ensure_ascii=False, indent=2)
        result = chain.invoke({
            "previous_query": previous_query,
            "data_json": data_json,
            "user_query": user_query,
            "rewritten_query": rewritten_query or user_query,
            "history_answer_reason": history_answer_reason or "基于历史数据回答"
        })
        answer = result.content
        logger.info(f"[Responder V13] 基于历史回答完成: {answer[:100]}...")
        
    except Exception as e:
        logger.error(f"[Responder V13] 基于历史回答失败: {e}")
        answer = f"抱歉，处理过程中出现错误: {str(e)}"
    
    # 保持 last_query_context 不变，让用户可以继续追问
    return {
        "final_answer": answer,
        "messages": [AIMessage(content=answer)],
        "last_query_context": last_query_context  # 保持上下文
    }


def _build_data_summary(data: List[Dict], user_query: str) -> str:
    """
    构建数据结果的文字摘要，用于多轮对话上下文
    
    这个摘要会被传递给 IntentAgent，让 LLM 知道之前查询了什么数据，
    当用户追问时可以直接基于这些数据回答，而不必重新查询。
    
    Args:
        data: 查询结果列表
        user_query: 用户原始提问
        
    Returns:
        数据摘要字符串
        
    Author: CYJ
    Time: 2025-11-27
    """
    if not data:
        return "无数据"
    
    row_count = len(data)
    columns = list(data[0].keys()) if data else []
    
    # 构建数据预览（取前 10 条）
    preview_rows = data[:10]
    preview_str = json.dumps(preview_rows, ensure_ascii=False, indent=2)
    
    # 如果数据包含数值列，计算统计信息
    stats = []
    for col in columns:
        values = [row.get(col) for row in data if row.get(col) is not None]
        if values and all(isinstance(v, (int, float)) for v in values):
            min_val = min(values)
            max_val = max(values)
            total = sum(values)
            # 找到最大/最小值对应的行
            max_row = next((row for row in data if row.get(col) == max_val), None)
            min_row = next((row for row in data if row.get(col) == min_val), None)
            stats.append(f"  - {col}: 最小={min_val}, 最大={max_val}, 总计={total}")
    
    summary = f"""查询: {user_query}
结果概要: 共 {row_count} 条记录
字段: {', '.join(columns)}
数据预览:
{preview_str}
"""
    
    if stats:
        summary += "\n数值统计:\n" + "\n".join(stats)
    
    return summary


def _async_save_to_cache(state: AgentState, sql: str, res: List[Dict], intent_data: dict):
    """
    异步保存查询结果到缓存
    
    计算缓存评分，如果分数 >= CACHE_SCORE_THRESHOLD 则保存到缓存。
    使用 asyncio.create_task 异步执行，不阻塞响应。
    
    Args:
        state: 当前状态
        sql: 执行的 SQL
        res: 查询结果
        intent_data: 意图识别结果
        
    Author: ChatBI Team
    Time: 2025-11-28
    """
    try:
        # 计算缓存评分
        sql_success = state.get("error") is None
        result_not_empty = bool(res) and len(res) > 0
        
        # V16.2: 修正验证器评分逻辑
        # “验证通过” = “已尝试验证” 且 “未发现问题”
        # semantic_validation_attempted=True 且 semantic_validation_result=None 表示验证通过
        # Author: CYJ
        # Time: 2025-11-28
        semantic_attempted = state.get("semantic_validation_attempted", False)
        semantic_result = state.get("semantic_validation_result")  # 有值表示发现了问题
        semantic_passed = semantic_attempted and semantic_result is None
        
        completeness_attempted = state.get("completeness_validation_attempted", False)
        completeness_result = state.get("completeness_validation_result")  # 有值表示发现了问题
        completeness_passed = completeness_attempted and completeness_result is None
        
        # 路径验证器结果从 intent 中获取
        path_validation = intent_data.get("path_validator_passed", False) if intent_data else False
        
        cache_score = CacheService.calculate_cache_score(
            sql_success=sql_success,
            result_not_empty=result_not_empty,
            result_validator_passed=semantic_passed,
            completeness_validator_passed=completeness_passed,
            path_validator_passed=path_validation
        )
        
        logger.info(f"[CacheSave] 评分: {cache_score} (sql_success={sql_success}, not_empty={result_not_empty}, semantic_passed={semantic_passed}, completeness_passed={completeness_passed}, path={path_validation})")
        
        # 只有分数 >= CACHE_SCORE_THRESHOLD 才保存
        cache_threshold = _settings.CACHE_SCORE_THRESHOLD
        if cache_score < cache_threshold:
            logger.info(f"[CacheSave] 评分 {cache_score} < {cache_threshold}，不保存缓存")
            return
        
        # 提取信息
        original_query = intent_data.get("original_query", "") if intent_data else ""
        rewritten_query = intent_data.get("rewritten_query", "") if intent_data else ""
        
        # 提取使用的表
        tables_used = []
        if sql:
            # 简单提取 FROM 和 JOIN 后的表名
            import re
            table_patterns = [
                r"FROM\s+(\w+)",
                r"JOIN\s+(\w+)"
            ]
            for pattern in table_patterns:
                matches = re.findall(pattern, sql, re.IGNORECASE)
                tables_used.extend(matches)
            tables_used = list(set(tables_used))  # 去重
        
        if not original_query:
            logger.warning("[CacheSave] 原始问题为空，不保存缓存")
            return
        
        # 同步保存 (V2)
        try:
            cache_service.save_to_cache(
                original_query=original_query,
                sql=sql,
                cache_score=cache_score,
                rewritten_query=rewritten_query,
                tables_used=tables_used
            )
            logger.info(f"[CacheSave] 缓存已保存: query='{original_query[:50]}...'")
        except Exception as e:
            logger.error(f"[CacheSave] 保存失败: {e}")
        
    except Exception as e:
        logger.error(f"[CacheSave] 准备保存缓存失败: {e}")


def responder_node(state: AgentState):
    logger.info("--- Node: Responder ---")
    
    intent = state.get("intent", {}) or {}
    intent_type = intent.get("intent_type")
    need_confirm = intent.get("need_user_confirmation", False)
    clarification_q = intent.get("clarification_question")
    
    # 0. 需要用户确认的查询意图：先向用户确认改写/补充信息，再决定是否进入 SQL 流程
    if intent_type == 'query_data' and need_confirm:
        question = clarification_q or "为确保理解准确，请确认：上述改写是否符合您的真实需求？如有不对，请更正或补充时间、城市等条件。"
        return {"final_answer": question, "messages": [AIMessage(content=question)]}
    
    # 1. 处理闲聊
    if intent_type == 'chitchat':
        from app.core.llm import get_llm
        from langchain_core.prompts import ChatPromptTemplate
        
        llm = get_llm(temperature=_settings.LLM_TEMPERATURE_CREATIVE)
        prompt = ChatPromptTemplate.from_template("User says: {input}\nYou are a helpful BI Assistant. Reply naturally to the user's greeting or small talk. Keep it brief.")
        chain = prompt | llm
        
        user_input = state['messages'][-1].content
        res = chain.invoke({"input": user_input})
        answer = res.content
        return {"final_answer": answer, "messages": [AIMessage(content=answer)]}
    
    # V13: 处理 query_data + can_answer_from_history=true 的情况
    # 基于历史数据直接回答，不重新查询
    # Author: CYJ
    # Time: 2025-11-27
    can_answer_from_history = intent.get("can_answer_from_history", False)
    if intent_type == 'query_data' and can_answer_from_history:
        return _handle_answer_from_history(state, intent)
        
    # 2. 处理拒绝与引导 (Intelligent Rejection)
    if intent_type == 'rejection':
        reason = intent.get("reason", "I cannot fulfill this request.")
        guidance = intent.get("guidance", "")
        answer = f"抱歉，我无法回答这个问题。原因：{reason}"
        if guidance:
            answer += f"\n建议：{guidance}"
        return {"final_answer": answer, "messages": [AIMessage(content=answer)]}
    
    # 3. 处理 Unclear 但有关键词的情况 (Keyword Confirmation) - 动态生成
    if intent_type == 'unclear':
        keywords = intent.get("detected_keywords", [])
        user_input = state['messages'][-1].content if state.get('messages') else ""
        
        if keywords:
            # V3: 使用 LLM 动态生成自然的确认回复
            try:
                from app.core.llm import get_llm
                from langchain_core.prompts import ChatPromptTemplate
                
                llm = get_llm(temperature=_settings.LLM_TEMPERATURE_CREATIVE)
                keywords_str = ", ".join(keywords)
                
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
3. 提供几个具体的查询选项供用户选择（如查看数量、金额、趋势等）
4. 保持简洁，不超过100字

【示例】
- 用户说"广州怎么样"，关键词是"广州"
  回复："您想了解广州的哪些数据呢？比如广州的销售额、订单量，还是用户活跃度？"
- 用户说"微信"，关键词是"微信"
  回复："您是想查看微信支付的订单数据吗？比如微信支付的订单数量、总金额？"
- 用户说"最近"，关键词是"最近"
  回复："您想查看最近的哪些数据呢？比如最近的销售趋势、新增用户数，或者订单情况？"

请直接输出确认问题，不要其他内容：
""")
                
                chain = clarify_prompt | llm
                result = chain.invoke({
                    "user_input": user_input,
                    "keywords": keywords_str
                })
                answer = result.content.strip()
                
            except Exception as e:
                logger.error(f"Unclear intent LLM generation failed: {e}")
                # 回退到默认模板
                answer = f"抱歉，我不确定您的具体意图。但我检测到了关键词：【{keywords_str}】。您想查询这些相关的什么数据呢？"
        else:
            answer = "抱歉，我没有理解您的意思。请尝试用更清晰的语言描述您的查询需求。"
        return {"final_answer": answer, "messages": [AIMessage(content=answer)]}

    # 4. 处理 SQL 执行结果 (Data Query Response)
    res = state.get("data_result")
    sql = state.get("sql_query")
    
    # V7: 获取分析结果
    analysis_result = state.get("analysis_result")
    data_insight = state.get("data_insight")
    viz_recommendation = state.get("viz_recommendation")
    echarts_option = state.get("echarts_option")
    
    # Handle Clarification case (Planner didn't generate SQL)
    if not sql:
        intent_data = state.get("intent", {})
        answer = "抱歉，我没有找到相关的数据表或字段。请尝试换一种提问方式。"
        
        return {
            "final_answer": answer,
            "messages": [AIMessage(content=answer)]
        }
        
    answer = f"I found the data using: `{sql}`. Result: {res}"
    
    # Use LLM to interpret the result
    try:
        from app.core.llm import get_llm
        from langchain_core.prompts import ChatPromptTemplate
        
        llm = get_llm(temperature=_settings.LLM_TEMPERATURE_RESPONSE)
        intent_data = state.get("intent", {})
        user_query = intent_data.get("rewritten_query") or intent_data.get("original_query") or "User Query"
        correction_note = state.get("correction_note", "")
        
        # V2: 构建更友好的纠正说明
        correction_display = ""
        if correction_note:
            correction_display = _format_correction_note(correction_note)
        
        # V7: 构建数据洞察信息
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
        
        # V7: 增强 Prompt，包含数据洞察
        prompt = ChatPromptTemplate.from_template("""
你是一个专业的BI数据分析师，请用自然、友好的方式回答用户的数据查询。

【原始提问】{original_query}
【改写后的问题】{query}
【执行的 SQL】{sql}
【查询结果】{result}
【纠正说明】{correction_note}
【数据洞察】{data_insight}

### 回答要求：

1. **纠正情况告知**（如果有纠正说明）：
   - 在回答开头友好地说明做了什么调整

2. **结果呈现**：
   - 数值类结果：直接给出数字，可适当格式化（如千分位）
   - 列表类结果：简洁列举，超过5条可只列主要的
   - 空结果：说明"没有找到符合条件的数据"并给出可能原因

3. **数据洞察**（如果有）：
   - 结合数据洞察信息，给出简单的分析观点
   - 例如："最高的是XX，最低的是YY"
   - 例如："整体呈上升/下降趋势"

4. **语言风格**：
   - 自然亲切，不要太生硬
   - 结合用户的原始问法回答

5. **避免**：
   - 不要暴露SQL细节给用户
   - 不要重复问题本身
   - 不要说"根据查询结果显示"这种废话
   - **【关键】不要编造数据！必须严格基于{result}中的实际数据回答**
   - **【重要】不要省略数据！查询结果共{row_count}条，必须完整列举所有数据**

请直接回答：
""")
        
        chain = prompt | llm
        # V11: 不再截断数据，完整传递给 LLM
        # Author: CYJ
        # Time: 2025-11-26
        res_str = str(res)
        row_count = len(res) if isinstance(res, list) else 1
            
        original_query = intent_data.get("original_query") or user_query
        
        ai_msg = chain.invoke({
            "original_query": original_query,
            "query": user_query, 
            "sql": sql, 
            "result": res_str,
            "row_count": row_count,
            "correction_note": correction_display if correction_display else "",
            "data_insight": insight_display if insight_display else "无"
        })
        answer = ai_msg.content
        
    except Exception as e:
        logger.error(f"Responder LLM failed: {e}")
        # Fallback to raw result
        answer = f"查询结果: {res}"

    # V7: 构建包含可视化信息的响应
    response = {
        "final_answer": answer,
        "messages": [AIMessage(content=answer)]
    }
    
    # V7: 添加可视化相关字段
    if viz_recommendation and viz_recommendation.get("recommended", False):
        response["visualization"] = {
            "chart_type": viz_recommendation.get("chart_type"),
            "echarts_option": echarts_option,
            "raw_data": res
        }
        logger.info(f"[Responder V7] 附加可视化配置: chart_type={viz_recommendation.get('chart_type')}")
    
    if data_insight:
        response["data_insight"] = data_insight
    
    # V12: 保存查询上下文，用于多轮对话的追问优化
    # 让 LLM 在后续追问时可以直接基于之前的数据回答，而不必重新查询
    # Author: CYJ
    # Time: 2025-11-27
    if sql and res and isinstance(res, list) and len(res) > 0:
        # 构建数据摘要（用于追问时的上下文参考）
        data_summary = _build_data_summary(res, user_query)
        response["last_query_context"] = {
            "query": user_query,
            "sql": sql,
            "data_result": res,  # 完整的结构化数据
            "data_summary": data_summary,  # 文字摘要
            "row_count": len(res),
            "columns": list(res[0].keys()) if res else []
        }
        logger.info(f"[Responder V12] 保存查询上下文: row_count={len(res)}, columns={list(res[0].keys()) if res else []}")
        
        # V16: 异步写入缓存（不阻塞响应）
        # 只有非缓存命中的查询才需要写入缓存
        cache_hit = state.get("cache_hit")
        if not cache_hit:
            _async_save_to_cache(state, sql, res, intent_data)
    
    return response

# =============================================================================
# Diagnosis Nodes (诊断与反思机制)
# =============================================================================

def diagnoser_node(state: AgentState) -> dict:
    """
    诊断节点：使用统一的 IntelligentAnalyzer 进行诊断
    
    V4重构：合并原 ResultDiagnoser 功能到 IntelligentAnalyzer
    V10增强：快速路径处理表/列不存在错误
    
    诊断类型：
    - 理解层问题: Schema召回不完整
    - SQL构建层问题: 实体映射、条件错误等
    
    Author: CYJ
    Time: 2025-11-25 (V4: 2025-11-26, V10: 2025-11-26)
    """
    import asyncio
    logger.info("[Diagnoser] 开始智能诊断...")
    
    # 检查诊断次数限制
    diagnosis_count = state.get("diagnosis_count", 0)
    if diagnosis_count >= 2:
        logger.warning("[Diagnoser] 已达到诊断次数上限，跳过诊断")
        return {
            "diagnosis_attempted": True,
            "diagnosis_result": None
        }
    
    # V10: 快速路径 - 如果有 schema_error_info，直接构建诊断结果
    schema_error_info = state.get("schema_error_info")
    if schema_error_info:
        logger.info(f"[Diagnoser V10] 快速路径: 检测到 Schema 错误信息")
        from app.modules.diagnosis.models import DiagnosisResult, DiagnosisType, SuggestedAction, SuggestedActionItem
        
        error_type = schema_error_info.get("error_type")
        missing_object = schema_error_info.get("missing_object")
        exists_in_db = schema_error_info.get("exists_in_db", False)
        suggestion = schema_error_info.get("suggestion", "")
        
        if error_type == "table_not_found":
            if exists_in_db:
                # 表存在于数据库但未召回 -> Schema 不完整
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
                # 表不存在于数据库 -> 模型幻觉，需要重新生成 SQL
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
                            description=f"表 '{missing_object}' 不存在，可能需要使用: {similar_tables}" if similar_tables else f"表 '{missing_object}' 不存在"
                        )
                    ]
                )
                # 将修复建议传递给 planner
                intent = state.get("intent", {}) or {}
                intent["sql_fix_hint"] = {
                    "root_cause": f"表 '{missing_object}' 不存在于数据库",
                    "suggestions": [f"不要使用表 '{missing_object}'"] + ([f"可以考虑使用表: {', '.join(similar_tables)}"] if similar_tables else [])
                }
                state["intent"] = intent
                logger.info(f"[Diagnoser V10] 模型幻觉，表 '{missing_object}' 不存在，建议: {similar_tables}")
        
        elif error_type == "column_not_found":
            # 列不存在 -> SQL 逻辑错误
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
                        description=f"列 '{missing_object}' 不存在，可能需要使用: {similar_columns}" if similar_columns else f"列 '{missing_object}' 不存在"
                    )
                ]
            )
            # 将修复建议传递给 planner
            intent = state.get("intent", {}) or {}
            intent["sql_fix_hint"] = {
                "root_cause": f"列 '{missing_object}' 不存在",
                "suggestions": [f"不要使用列 '{missing_object}'"] + ([f"可以考虑使用列: {', '.join(similar_columns)}"] if similar_columns else [])
            }
            state["intent"] = intent
            logger.info(f"[Diagnoser V10] 列 '{missing_object}' 不存在，建议: {similar_columns}")
        else:
            legacy_result = None
        
        if legacy_result:
            return {
                "diagnosis_result": legacy_result,
                "diagnosis_attempted": True,
                "diagnosis_count": diagnosis_count + 1,
                "schema_error_info": None  # 清除已处理的错误信息
            }
    
    try:
        # 获取必要的状态信息
        sql_query = state.get("sql_query", "") or ""
        user_query = state.get("messages", [{}])[-1].content if state.get("messages") else ""
        intent_data = state.get("intent", {}) or {}
        if intent_data:
            user_query = intent_data.get("original_query", user_query) or user_query
        
        # 获取已选择的表和Schema上下文
        selected_tables = state.get("selected_tables", [])
        schema_context = state.get("cached_schema_context", "")
        data_result = state.get("data_result")
        filter_conditions = intent_data.get("filter_conditions", [])
        verified_mappings = state.get("verified_entity_mappings", {})
        
        # 如果selected_tables为空，从schema_context中提取表名
        if not selected_tables and schema_context:
            table_pattern = r'\[TABLE\]\s+(\w+)\s+\('
            matches = re.findall(table_pattern, schema_context)
            if matches:
                selected_tables = list(set(matches))
                logger.info(f"[Diagnoser] 从schema_context提取表名: {selected_tables}")
        
        logger.info(f"[Diagnoser] SQL: {sql_query[:100] if sql_query else 'None'}...")
        logger.info(f"[Diagnoser] 已选择表: {selected_tables}")
        logger.info(f"[Diagnoser] 用户查询: {user_query}")
        
        # V4: 使用统一的 IntelligentAnalyzer
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
        
        # 转换为兼容格式（供 schema_completer_node 使用）
        legacy_result = None
        if diagnosis_result.need_recall and diagnosis_result.understanding_result:
            # 需要重新召回，构造 Schema 不完整的结果
            from app.modules.diagnosis.models import DiagnosisResult, DiagnosisType, SuggestedAction, SuggestedActionItem
            legacy_result = DiagnosisResult(
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
            # 需要探针验证
            from app.modules.diagnosis.models import DiagnosisResult, DiagnosisType, SuggestedAction, SuggestedActionItem
            legacy_result = DiagnosisResult(
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
            # 数据确实为空
            from app.modules.diagnosis.models import DiagnosisResult, DiagnosisType, SuggestedAction
            legacy_result = DiagnosisResult(
                diagnosis_type=DiagnosisType.DATA_TRULY_EMPTY,
                confidence=0.8,
                root_cause=diagnosis_result.final_recommendation,
                evidence=[diagnosis_result.final_recommendation],
                suggested_action=SuggestedAction.CONFIRM_EMPTY,
                suggested_actions=[]
            )
        
        return {
            "diagnosis_result": legacy_result,
            "intelligent_diagnosis_result": diagnosis_result,  # 保留新格式结果
            "diagnosis_attempted": True,
            "diagnosis_count": diagnosis_count + 1,
            "selected_tables": selected_tables
        }
        
    except Exception as e:
        import traceback
        logger.error(f"[Diagnoser] 诊断失败: {e}")
        traceback.print_exc()
        return {
            "diagnosis_attempted": True,
            "diagnosis_result": None
        }


def schema_completer_node(state: AgentState) -> dict:
    """
    Schema补全节点：当诊断为Schema不完整时，自动补全缺失的表。
    """
    import asyncio
    logger.info("[SchemaCompleter] 开始补全Schema...")
    
    try:
        diagnosis_result = state.get("diagnosis_result")
        if not diagnosis_result:
            return {"schema_completed": False}
        
        # 获取当前已选择的表
        selected_tables = state.get("selected_tables", [])
        
        # 获取建议添加的表
        suggested_tables = []
        for action in diagnosis_result.suggested_actions:
            if action.action_type == "add_table" and action.target:
                suggested_tables.append(action.target)
        
        if not suggested_tables:
            logger.info("[SchemaCompleter] 没有需要补全的表")
            return {"schema_completed": True}
        
        # 合并表列表
        new_tables = list(set(selected_tables + suggested_tables))
        logger.info(f"[SchemaCompleter] 补全表: {selected_tables} -> {new_tables}")
        
        # 重新获取完整的Schema信息
        # 这里需要调用schema_completer来获取完整的DDL
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
            
            # 更新intent中的schema信息，供planner使用
            intent = state.get("intent", {}) or {}
            intent["schema_correction"] = {
                "added_tables": completion_result.added_tables,
                "complete_ddl": completion_result.complete_ddl,
                "diagnosis_hint": diagnosis_result.root_cause
            }
            
            # 关键：更新cached_schema_context，让planner使用补全后的Schema
            current_schema = state.get("cached_schema_context", "")
            updated_schema = current_schema + completion_result.complete_ddl if current_schema else completion_result.complete_ddl
            
            logger.info(f"[SchemaCompleter] 已更新cached_schema_context")
            
            return {
                "selected_tables": new_tables,
                "schema_completed": True,
                "intent": intent,
                "retry_count": 0,  # 重置重试计数
                "cached_schema_context": updated_schema  # 更新Schema缓存
            }
        else:
            logger.warning(f"[SchemaCompleter] Schema补全失败: {completion_result.error}")
            return {"schema_completed": False}
            
    except Exception as e:
        logger.error(f"[SchemaCompleter] Schema补全异常: {e}")
        return {"schema_completed": False}


# =============================================================================
# Edge Logic (Routing)
# =============================================================================

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
            # V13: 可以基于历史数据回答，直接进入 responder
            logger.info("[Router V13] can_answer_from_history=true，跳过 SQL 流程")
            return "responder_node"
        else:
            # 需要查询新数据，走 SQL Planner
            return "planner_node"

    # 其他情况（包括需要确认的 query、rejection、chitchat、unclear）统一先进入 Responder
    return "responder_node"

def route_after_planner(state: AgentState) -> Literal["executor_node", "diagnoser_node", "responder_node"]:
    """
    Planner后的路由决策。
    
    - SQL生成成功 -> executor_node
    - SQL生成失败(clarification) & 未诊断 -> diagnoser_node (新增)
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
    
    V10: 增加表/列不存在错误的快速诊断
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
        
        # V10: 检测表/列不存在错误，快速路由到诊断
        schema_error_info = _analyze_schema_error(error_msg)
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
    # Check if result is empty and diagnosis hasn't been attempted yet
    diagnosis_attempted = state.get("diagnosis_attempted", False)
    if not diagnosis_attempted:
        is_empty_result = _check_empty_result(data)
        if is_empty_result:
            logger.info("[Router] 检测到空结果，路由到诊断节点")
            return "diagnoser_node"
    
    # Case 4: 成功执行，路由到分析节点
    return "analyzer_node"


def _check_empty_result(data) -> bool:
    """检查查询结果是否为空"""
    if not data:
        return True
    if isinstance(data, list):
        if len(data) == 0:
            return True
        # Check for None values or 0 count
        if len(data) > 0:
            first_row = data[0]
            if isinstance(first_row, dict):
                # All values are None
                if all(v is None for v in first_row.values()):
                    return True
                # Single column with 0 value (count result)
                if len(first_row) == 1:
                    val = list(first_row.values())[0]
                    if isinstance(val, (int, float)) and val == 0:
                        return True
    return False


def _analyze_schema_error(error_msg: str) -> Optional[Dict[str, any]]:
    """
    V10: 分析 SQL 执行错误，识别表/列不存在的 Schema 错误
    
    错误类型：
    1. Table doesn't exist: 表不存在
    2. Unknown column: 列不存在
    
    返回：
    - 如果是 Schema 错误：返回错误详情 + 是否存在于数据库
    - 如果不是 Schema 错误：返回 None
    
    Author: CYJ
    Time: 2025-11-26
    """
    if not error_msg:
        return None
    
    error_lower = error_msg.lower()
    result = {
        "error_type": None,
        "missing_object": None,
        "exists_in_db": False,
        "suggestion": None
    }
    
    # 模式 1: Table doesn't exist
    # MySQL: "Table 'db.table_name' doesn't exist"
    table_pattern = r"table\s+['\"]?(?:\w+\.)?([\w]+)['\"]?\s+doesn't\s+exist"
    table_match = re.search(table_pattern, error_msg, re.IGNORECASE)
    
    if table_match:
        missing_table = table_match.group(1)
        result["error_type"] = "table_not_found"
        result["missing_object"] = missing_table
        
        # 检查表是否存在于数据库 Schema 中（可能是召回遗漏）
        try:
            catalog = get_schema_catalog()
            all_tables = catalog.list_table_names()
            if missing_table in all_tables:
                result["exists_in_db"] = True
                result["suggestion"] = f"表 '{missing_table}' 存在于数据库但未被召回，需要补充 Schema"
                logger.info(f"[V10] 表 '{missing_table}' 存在于数据库，Schema 召回遗漏")
            else:
                result["exists_in_db"] = False
                result["suggestion"] = f"表 '{missing_table}' 不存在于数据库，模型产生幻觉"
                # 尝试找到相似的表名
                similar_tables = [t for t in all_tables if missing_table.lower() in t.lower() or t.lower() in missing_table.lower()]
                if similar_tables:
                    result["similar_tables"] = similar_tables
                    result["suggestion"] += f"，可能需要使用: {similar_tables}"
                logger.info(f"[V10] 表 '{missing_table}' 不存在，可能的替代: {similar_tables}")
        except Exception as e:
            logger.warning(f"[V10] 检查表存在性失败: {e}")
        
        return result
    
    # 模式 2: Unknown column
    # MySQL: "Unknown column 'table.column' in 'field list'"
    column_pattern = r"unknown\s+column\s+['\"]?([\w\.]+)['\"]?"
    column_match = re.search(column_pattern, error_msg, re.IGNORECASE)
    
    if column_match:
        missing_column = column_match.group(1)
        result["error_type"] = "column_not_found"
        result["missing_object"] = missing_column
        
        # 解析 table.column 格式
        if '.' in missing_column:
            table_name, col_name = missing_column.rsplit('.', 1)
        else:
            table_name, col_name = None, missing_column
        
        # 检查列是否存在
        try:
            catalog = get_schema_catalog()
            if table_name:
                columns = catalog.list_columns_by_table(table_name)
                col_names = [c['name'] for c in columns]
                if col_name in col_names:
                    result["exists_in_db"] = True
                    result["suggestion"] = f"列 '{missing_column}' 存在但可能别名错误"
                else:
                    result["exists_in_db"] = False
                    similar_cols = [c for c in col_names if col_name.lower() in c.lower() or c.lower() in col_name.lower()]
                    result["suggestion"] = f"列 '{col_name}' 在表 '{table_name}' 中不存在"
                    if similar_cols:
                        result["similar_columns"] = similar_cols
                        result["suggestion"] += f"，可能需要使用: {similar_cols}"
                    logger.info(f"[V10] 列 '{missing_column}' 不存在，可能的替代: {similar_cols}")
        except Exception as e:
            logger.warning(f"[V10] 检查列存在性失败: {e}")
        
        return result
    
    # 不是 Schema 相关错误
    return None


def route_after_diagnosis(state: AgentState) -> Literal["schema_completer_node", "planner_node", "responder_node"]:
    """
    诊断后的路由决策。
    
    - SCHEMA_INCOMPLETE -> schema_completer_node
    - SQL_LOGIC_ERROR -> planner_node (带修复建议)
    - ENTITY_MAPPING -> planner_node (触发探针查询流程)
    - DATA_TRULY_EMPTY -> responder_node
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
        # 将诊断信息传递给planner用于探针查询
        intent = state.get("intent", {}) or {}
        intent["entity_mapping_hint"] = {
            "root_cause": diagnosis_result.root_cause,
            "missing_entities": [a.description for a in diagnosis_result.suggested_actions]
        }
        state["intent"] = intent
        state["retry_count"] = 0  # 重置重试计数
        return "planner_node"
    
    else:  # DATA_TRULY_EMPTY or unknown
        logger.info("[Router] 数据确实为空或未知类型，直接响应")
        return "responder_node"

# =============================================================================
# Graph Construction
# =============================================================================

def build_graph():
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("cache_check_node", cache_check_node)  # V16: 缓存检查节点
    workflow.add_node("intent_node", intent_node)
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("executor_node", executor_node)
    workflow.add_node("analyzer_node", analyzer_node)  # V7: 数据分析与可视化
    workflow.add_node("responder_node", responder_node)
    # 诊断与反思节点
    workflow.add_node("diagnoser_node", diagnoser_node)
    workflow.add_node("schema_completer_node", schema_completer_node)
    
    # Add Edges
    # V16: 缓存检查节点为新的入口点
    workflow.set_entry_point("cache_check_node")
    
    # V16: 缓存检查后的路由
    workflow.add_conditional_edges(
        "cache_check_node",
        route_after_cache_check,
        {
            "executor_node": "executor_node",  # 命中缓存，直接执行 SQL
            "intent_node": "intent_node"       # 未命中，进入意图识别
        }
    )
    
    workflow.add_conditional_edges(
        "intent_node",
        route_after_intent,
        {
            "planner_node": "planner_node",
            "responder_node": "responder_node"
        }
    )
    
    # Add conditional edge after planner (with diagnosis support)
    workflow.add_conditional_edges(
        "planner_node",
        route_after_planner,
        {
            "executor_node": "executor_node",
            "diagnoser_node": "diagnoser_node",
            "responder_node": "responder_node"
        }
    )
    
    # Add conditional edge after executor (with diagnosis support)
    workflow.add_conditional_edges(
        "executor_node",
        route_after_executor,
        {
            "planner_node": "planner_node",
            "diagnoser_node": "diagnoser_node",
            "analyzer_node": "analyzer_node",  # V7: 成功后路由到分析节点
            "responder_node": "responder_node"
        }
    )
    
    # V7: 分析节点完成后进入响应节点
    workflow.add_edge("analyzer_node", "responder_node")
    
    # Add conditional edge after diagnoser
    workflow.add_conditional_edges(
        "diagnoser_node",
        route_after_diagnosis,
        {
            "schema_completer_node": "schema_completer_node",
            "planner_node": "planner_node",
            "responder_node": "responder_node"
        }
    )
    
    # Schema completer 完成后回到 planner 重新生成SQL
    workflow.add_edge("schema_completer_node", "planner_node")
    
    workflow.add_edge("responder_node", END)
    
    # Compile with memory
    checkpointer = get_memory_checkpointer()
    app = workflow.compile(checkpointer=checkpointer)
    return app

# Singleton App
orchestrator_app = build_graph()
