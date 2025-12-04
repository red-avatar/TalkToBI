"""
Orchestrator 辅助函数模块

从 orchestrator.py 中提取的辅助函数，包括:
- 探针 SQL 生成
- Schema 上下文获取
- 纠正说明格式化
- 数据摘要构建
- 缓存保存

Author: CYJ
Time: 2025-12-03 (从 orchestrator.py 重构)
"""
import re
import json
import logging
from typing import Dict, List, Optional, Any

from app.core.config import get_settings
from app.modules.schema.catalog import get_schema_catalog
from app.services.cache_service import CacheService, get_cache_service

logger = logging.getLogger(__name__)
_settings = get_settings()
cache_service = get_cache_service()

def generate_probe_sql(entity_key: str, entity_value, schema_context: str) -> Optional[str]:
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
        from app.core.llm import get_llm, llm_rate_limit_sync
        from langchain_core.prompts import ChatPromptTemplate
        
        
        if '.' in entity_key:
            table_name, column_name = entity_key.split('.', 1)
        else:
            # 兼容旧格式，默认为 entity_type
            table_name = None
            column_name = entity_key
        
        
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
        
        
        llm = get_llm(temperature=_settings.LLM_TEMPERATURE_PRECISE)
        
        # 处理多值列表
        values_to_process = entity_values if is_list_value else [entity_value_str]
        values_str = ", ".join([f"'{v}'" for v in values_to_process])
        
        prompt = ChatPromptTemplate.from_template("""
你是一个 MySQL 专家。用户的查询返回了 0 条结果，可能是因为过滤条件中的值与数据库中的实际值不匹配。

【已召回 Schema 信息】
{schema_context}

【用户使用的实体值】
- 表.字段：{table_column}
- 用户输入值：{entity_values}

【任务】
生成一个探针 SQL，查找数据库中与用户输入值语义相似的实际值。

【重要】你需要做语义扩展，考虑以下变体：
1. 中英文映射：如"微信"和"wechat"，"成功"和"success"
2. 简称/全称：如"家电"和"家用电器"，"电子"和"电子产品"
3. 同义词：如"手机"和"移动电话/智能手机"，"签收"和"delivered"
4. 编码变体：如"一线"和"tier1/first_tier"，"自营"和"self/self_operated"

【输出要求】
1. 生成: SELECT DISTINCT {column} FROM {table} WHERE ... LIMIT 20
2. WHERE 条件使用多个 LIKE 用 OR 连接，覆盖所有可能的变体
3. 对于每个用户输入值，都要生成对应的 LIKE 条件
4. 只输出纯 SQL，不要任何解释

示例:
- 输入"家电" -> WHERE name LIKE '%家电%' OR name LIKE '%家用电器%' OR name LIKE '%appliance%'
- 输入"签收" -> WHERE status LIKE '%签收%' OR status LIKE '%delivered%' OR status LIKE '%signed%'
""")
        
        chain = prompt | llm
        
        # 构建 table.column 格式
        table_column = f"{table_name}.{column_name}" if table_name else column_name
        
        # 应用 LLM 调用限流 (Author: CYJ, Time: 2025-12-03)
        with llm_rate_limit_sync():
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

def get_schema_context_for_probe() -> str:
    """
    获取用于探针生成的 Schema 上下文（轻量级）
    
    Author: CYJ
    Time: 2025-11-25
    """
    try:
        catalog = get_schema_catalog()
        tables = catalog.list_tables(with_description=True)
        
        # 需要包含列信息的表（维度表 + 常用业务表）
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

def format_correction_note(correction_note: str) -> str:
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
                                    parts.append(f"'{original}' 已纠正为 '{corrected_value}'")
                        except:
                            parts.append(f"'{original}' 已纠正")
                    else:
                        parts.append(f"'{original}' 已纠正")
            
            if parts:
                return "已自动纠正以下实体：" + "、".join(parts)
    except:
        pass
    
    # 如果不是 JSON，直接返回原值
    return correction_note

def build_data_summary(data: List[Dict], user_query: str) -> str:
    """
    构建数据结果的文字摘要，用于多轮对话上下文
    
    这个摘要会被传递给 IntentAgent，让 LLM 知道之前查询了什么数据，
    当用户追问时可以直接基于这些数据回答，而不必重新查询
    
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

def save_to_cache_sync(state: Dict[str, Any], sql: str, res: List[Dict], intent_data: dict):
    """
    同步保存查询结果到缓存
    
    计算缓存评分，如果分数 >= CACHE_SCORE_THRESHOLD 则保存到缓存
    
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
        
        
        semantic_attempted = state.get("semantic_validation_attempted", False)
        semantic_result = state.get("semantic_validation_result")
        semantic_passed = semantic_attempted and semantic_result is None
        
        completeness_attempted = state.get("completeness_validation_attempted", False)
        completeness_result = state.get("completeness_validation_result")
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
            table_patterns = [
                r"FROM\s+(\w+)",
                r"JOIN\s+(\w+)"
            ]
            for pattern in table_patterns:
                matches = re.findall(pattern, sql, re.IGNORECASE)
                tables_used.extend(matches)
            tables_used = list(set(tables_used))
        
        if not original_query:
            logger.warning("[CacheSave] 原始问题为空，不保存缓存")
            return
        
        # 同步保存
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

def check_empty_result(data) -> bool:
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

def analyze_schema_error(error_msg: str) -> Optional[Dict[str, Any]]:
    """
    V10: 分析 SQL 执行错误，识别表/列不存在等 Schema 错误
    
    错误类型:
    1. Table doesn't exist: 表不存在
    2. Unknown column: 列不存在
    
    返回值:
    - 如果是 Schema 错误：返回错误详情 + 是否存在于数据库
    - 如果不是 Schema 错误：返回 None
    
    Author: CYJ
    Time: 2025-11-26
    """
    if not error_msg:
        return None
    
    result = {
        "error_type": None,
        "missing_object": None,
        "exists_in_db": False,
        "suggestion": None
    }
    
    # 模式 1: Table doesn't exist
    table_pattern = r"table\s+['\"]?(?:\w+\.)?([^\s'\"]+)['\"]?\s+doesn't\s+exist"
    table_match = re.search(table_pattern, error_msg, re.IGNORECASE)
    
    if table_match:
        missing_table = table_match.group(1)
        result["error_type"] = "table_not_found"
        result["missing_object"] = missing_table
        
        # 检查表是否存在于数据库 Schema 中
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

def handle_answer_from_history(state: Dict[str, Any], intent: dict) -> dict:
    """
    处理基于历史数据的回答（query_data 的变体分支）
    
    当 intent_type='query_data' 且 can_answer_from_history=true 时，
    不走 SQL 流程，直接基于历史数据回答
    
    Args:
        state: 当前状态
        intent: 意图识别结果
        
    Returns:
        更新的状态字典
        
    Author: CYJ
    Time: 2025-11-27 (V13 重构)
    """
    from app.core.llm import get_llm, llm_rate_limit_sync
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.messages import AIMessage
    
    logger.info("[Responder V13] 基于历史数据回答...")
    
    last_query_context = state.get("last_query_context", {})
    user_query = intent.get("original_query", "")
    rewritten_query = intent.get("rewritten_query", "")
    history_answer_reason = intent.get("history_answer_reason", "")
    
    # 检查是否有历史数据
    if not last_query_context or not last_query_context.get("data_result"):
        logger.warning("[Responder V13] 无历史查询结果，无法基于历史回答")
        answer = "抱歉，我没有找到之前的查询结果。请先查询数据，然后再进行追问"
        return {"final_answer": answer, "messages": [AIMessage(content=answer)]}
    
    data_result = last_query_context.get("data_result", [])
    previous_query = last_query_context.get("query", "")
    
    # 使用 LLM 基于已有数据进行计算和回答
    llm = get_llm(temperature=_settings.LLM_TEMPERATURE_BALANCED)
    
    prompt = ChatPromptTemplate.from_template("""
你是一个 BI 数据分析师。用户基于之前的查询结果提出了问题，请直接基于已有数据回答

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
2. 从已有数据中找到相关数据
3. 如果需要计算（如求差、求比、排名等），进行计算
4. 用自然语言回答用户，并说明依据

### 要求
- 必须基于已有数据回答，不要编造数据
- 说明答案的依据（如 "根据之前的查询结果...")
- 如果有计算，显示计算过程
- 语言自然亲切

请直接回答：
""")
    
    chain = prompt | llm
    
    try:
        data_json = json.dumps(data_result, ensure_ascii=False, indent=2)
        # 应用 LLM 调用限流 (Author: CYJ, Time: 2025-12-03)
        with llm_rate_limit_sync():
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
        "last_query_context": last_query_context
    }
