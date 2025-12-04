"""
SQL 解析工具模块

从 orchestrator.py 中提取的 SQL 解析相关工具函数，包括:
- extract_filter_conditions_from_sql: 从 SQL 提取筛选条件
- extract_table_aliases: 提取表别名映射
- extract_filter_entities: 提取过滤条件中的实体值

Author: CYJ
Time: 2025-12-03 (从 orchestrator.py 重构)
"""
import re
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

def extract_table_aliases(sql: str) -> Dict[str, str]:
    """
    提取 SQL 中的表别名映射
    
    示例:
        FROM orders o -> {"o": "orders"}
        JOIN dim_region dr ON -> {"dr": "dim_region"}
        
    Args:
        sql: SQL 语句
        
    Returns:
        Dict[str, str]: {别名: 表名}
        
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

def extract_filter_conditions_from_sql(sql: str) -> List[Dict[str, str]]:
    """
    从 SQL 中直接提取筛选条件（表名.字段名 = '值' 或 IN (...)）
    
    V6: 增强支持 IN 操作符，解决 shop_type IN ('自营', '第三方') 等无法提取的问题
    
    设计原理:
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
    alias_map = extract_table_aliases(sql)
    
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

def extract_filter_entities(sql: str, intent: dict) -> Dict[str, any]:
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
    conditions = extract_filter_conditions_from_sql(sql)
    
    for cond in conditions:
        table = cond.get("table", "")
        column = cond.get("column", "")
        value = cond.get("value", "")
        
        if not table or not column or not value:
            continue
        
        
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

def get_translation_variants(value) -> List[str]:
    """
    获取实体值的变体列表
    
    V5: 移除硬编码映射，只返回原值
    翻译变体发现完全依赖于:
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
            all_variants.extend(get_translation_variants(v))
        return list(set(all_variants))  # 去重
    
    # 确保 value 是字符串
    if not isinstance(value, str):
        value = str(value)
    
    
    # 翻译变体由 _generate_probe_sql 中的 LLM 智能推断
    return [value]

def classify_entity(value: str, context: str) -> Optional[str]:
    """
    根据上下文推断实体类型
    
    Args:
        value: 实体值
        context: 上下文（如列名）
    
    Returns:
        实体类型字符串，如 'location', 'shop', 'brand', 'status', 'entity'
        
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

def analyze_schema_error(error_msg: str) -> Optional[Dict[str, any]]:
    """
    V10: 分析 SQL 执行错误，识别表/列不存在的 Schema 错误
    
    错误类型:
    1. Table doesn't exist: 表不存在
    2. Unknown column: 列不存在
    
    返回:
    - 如果是 Schema 错误：返回错误详情
    - 如果不是 Schema 错误：返回 None
    
    注意：此函数不检查表/列是否存在于数据库，只解析错误消息。
    存在性检查应在调用方进行。
    
    Args:
        error_msg: SQL 执行错误消息
        
    Returns:
        错误详情字典或 None
        
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
    # MySQL: "Table 'db.table_name' doesn't exist"
    table_pattern = r"table\s+['\"]?(?:\w+\.)?([^\s'\"]+)['\"]?\s+doesn't\s+exist"
    table_match = re.search(table_pattern, error_msg, re.IGNORECASE)
    
    if table_match:
        missing_table = table_match.group(1)
        result["error_type"] = "table_not_found"
        result["missing_object"] = missing_table
        result["suggestion"] = f"表 '{missing_table}' 不存在"
        return result
    
    # 模式 2: Unknown column
    # MySQL: "Unknown column 'table.column' in 'field list'"
    column_pattern = r"unknown\s+column\s+['\"]?([\w\.]+)['\"]?"
    column_match = re.search(column_pattern, error_msg, re.IGNORECASE)
    
    if column_match:
        missing_column = column_match.group(1)
        result["error_type"] = "column_not_found"
        result["missing_object"] = missing_column
        result["suggestion"] = f"列 '{missing_column}' 不存在"
        return result
    
    # 不是 Schema 相关错误
    return None
