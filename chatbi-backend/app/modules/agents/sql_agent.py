"""
功能：SQL 生成 Agent (SQL Planner Agent) - Manual Orchestration Version
说明：
    1. 摒弃不稳定的 LangChain AgentExecutor，采用显式流程控制。
    2. 流程：Intent -> Retrieval (Tool) -> Context -> LLM -> SQL。
    3. 确保在生成 SQL 前，必须先获取 Schema 信息。
作者：CYJ
"""
from typing import List, Optional
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.llm import get_llm
from app.core.config import get_settings
from app.core.state import AgentState
from app.modules.tools.retrieval import VectorRetrievalTool, GraphTraversalTool
from app.modules.validators.path_intent_validator import get_path_intent_validator

_settings = get_settings()

# 1. 定义 Prompt
# 我们将 Schema 直接作为上下文注入，而不是让 LLM 自己去多次调用工具
SYSTEM_PROMPT = """You are an expert SQL Data Analyst for a MySQL database.

### Task
Generate a correct, executable MySQL query to answer the user's question based ONLY on the provided Schema Information.

### Schema Information
{schema_context}

### Guidelines
1. **Schema Compliance**: Use ONLY tables and columns listed in the "Schema Information". Do NOT hallucinate columns.

2. **Join Logic**: If multiple tables are needed, infer the JOIN condition based on:
   - Column naming conventions (e.g. `orders.user_id = users.id`)
   - Foreign key patterns (`*_id` typically references another table's `id`)
   - Dimension tables (e.g. `orders.shipping_region_id = dim_region.id`)

3. **Negation Logic (CRITICAL)**:
   When the user asks for entities that "do NOT have" or "have NOT used" something:
   - Use LEFT JOIN + IS NULL pattern
   - Example: "Orders without coupons" means orders that have NO record in order_coupons
   - Correct SQL pattern:
     SELECT COUNT(*) FROM orders o
     LEFT JOIN order_coupons oc ON o.id = oc.order_id
     WHERE oc.id IS NULL
   - Do NOT confuse "unused coupons" (status='unused') with "orders without any coupon records"
   - "没有使用优惠券的订单" = orders with no matching record in order_coupons (LEFT JOIN + IS NULL)
   - "未使用的优惠券" = coupons with status='unused' (different meaning!)

4. **Rejection**: 
   - If the Schema Information is empty or insufficient, return: {{"clarification": "Explanation..."}}
   - Do NOT generate invalid SQL.

5. **Date Handling**: {date_context}

6. **Output Format**: 
   - Return ONLY the SQL query (no markdown blocks)
   - If clarifying, return the JSON object

7. **MySQL Version Compatibility (MySQL 5.7)**:
   - DO NOT use WITH...AS (CTE) - MySQL 5.7 does not support CTE
   - DO NOT use window functions (ROW_NUMBER, RANK, OVER, etc.) - MySQL 5.7 does not support them
   - DO NOT nest aggregate functions like SUM(COUNT(*)) - this is invalid in MySQL
   - For ratio calculations, use subqueries or JOIN with pre-aggregated data
   - For top N per group, use variables or self-joins instead of ROW_NUMBER()
   - Example for ratio: SELECT a.cnt / b.total FROM (SELECT COUNT(*) as cnt...) a, (SELECT COUNT(*) as total...) b

8. **CRITICAL: Single SQL Statement Only (单条SQL约束)**:
   - You MUST output exactly ONE complete, executable SQL statement
   - DO NOT output multiple SQL statements separated by comments or semicolons
   - DO NOT split the query into "Step 1" and "Step 2" - combine everything into ONE query
   - For complex logic (e.g., TopN per group), use nested subqueries within a single SELECT
   - Example of WRONG output:
     ```
     SELECT ... FROM table1;  -- Step 1
     SELECT ... FROM (above result) WHERE rn <= 3;  -- Step 2
     ```
   - Example of CORRECT output:
     ```
     SELECT * FROM (
       SELECT *, @rn := IF(@prev = category, @rn + 1, 1) AS rn, @prev := category
       FROM (SELECT ... ORDER BY category, value DESC) t, (SELECT @rn := 0, @prev := '') vars
     ) ranked WHERE rn <= 3;
     ```

9. **Entity Value Replacement (CRITICAL - 必须执行)**:
   {value_replacement_instructions}

10. **Filter Conditions Enforcement (筛选条件强制 - 必须遵守！)**:
   以下是从用户提问中提取的筛选条件，每个条件都【必须】在SQL的WHERE子句中体现：
   {filter_conditions_instructions}
   
   【重要规则】：
   - 每个required=true的条件都必须出现在WHERE子句中
   - 如果field_hint是"coupon_type"，请查找coupons表的type字段
   - 如果field_hint是"shop_type"，请查找shops表的shop_type字段
   - 如果field_hint是"category"，请查找categories表的name字段
   - 如果field_hint是"pay_method"，请查找payments表的pay_method字段
   - 如果field_hint是"city_level"，请查找dim_region表的city_level字段
   - 如果field_hint是"logistics_provider"，请查找logistics_providers表的name字段
   - 如果field_hint是"channel"，请查找dim_channel表或orders.order_channel_code字段
   
   ❗ 禁止遗漏任何筛选条件！生成SQL前请自检每个条件是否都已包含。

### Intent Entities
{intent_entities}

### User Question
{input}
"""

class SqlPlannerAgent:
    """
    SQL 规划器 Agent
    
    负责根据用户问题和 Schema 信息生成可执行的 SQL 查询
    
    Author: CYJ
    """
    
    def __init__(self):
        """Initialize the SQL Planner Agent"""
        # 精确任务使用低温度（从配置读取）
        self.llm = get_llm(temperature=_settings.LLM_TEMPERATURE_PRECISE)
        self.retrieval_tool = VectorRetrievalTool()
        self.graph_tool = GraphTraversalTool()
        self.path_validator = get_path_intent_validator()  # V15: 关联路径意图验证器
        
        self.prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT)
        self.chain = self.prompt | self.llm | StrOutputParser()
    
    def _parse_verification_result(self, verification_result: str) -> str:
        """
        解析 verification_result，生成清晰的值替换指令
        
        V6: 支持多值映射，提取探针返回的所有实际值
        
        Args:
            verification_result: Reflector 返回的验证结果 JSON 字符串
            
        Returns:
            str: 清晰的替换指令文本
            
        Author: CYJ
        """
        if not verification_result:
            return ""
        
        try:
            import json
            import ast
            
            data = json.loads(verification_result)
            field_mappings = []  # 存储字段级别的映射信息
            
            for entity_type, info in data.items():
                if not isinstance(info, dict):
                    continue
                    
                original_value = info.get('original_value', '')
                found_values_str = info.get('found_values', '')
                
                if not found_values_str:
                    continue
                
                # 解析 found_values
                try:
                    found_list = ast.literal_eval(found_values_str)
                    if not found_list or not isinstance(found_list, list):
                        continue
                    
                    # V6: 提取所有返回的实际值
                    # 探针返回格式: [{'字段名': '实际值1'}, {'字段名': '实际值2'}, ...]
                    actual_values = []
                    field_name = None
                    
                    for item in found_list:
                        if isinstance(item, dict) and len(item) > 0:
                            # 获取字段名和值
                            for k, v in item.items():
                                if field_name is None:
                                    field_name = k
                                if v not in actual_values:
                                    actual_values.append(v)
                    
                    if actual_values:
                        # 处理 original_value 可能是列表的情况
                        if isinstance(original_value, list):
                            original_str = ", ".join([f"'{v}'" for v in original_value])
                        else:
                            original_str = f"'{original_value}'"
                        
                        field_mappings.append({
                            'entity_type': entity_type,
                            'field_name': field_name,
                            'original': original_str,
                            'actual_values': actual_values
                        })
                        
                except Exception as e:
                    print(f"DEBUG: Failed to parse found_values: {found_values_str}, error: {e}")
                    continue
            
            if not field_mappings:
                return ""
            
            # 生成更清晰的替换指令
            lines = [
                "⚠️ **MANDATORY VALUE REPLACEMENT（必须执行的值替换）**:",
                "上一次查询返回 0 行结果，经探针验证发现是因为使用了不存在于数据库的值。",
                "请按以下信息修正 SQL：",
                ""
            ]
            
            for mapping in field_mappings:
                field = mapping['field_name'] or mapping['entity_type']
                original = mapping['original']
                actuals = mapping['actual_values']
                actuals_str = ", ".join([f"'{v}'" for v in actuals])
                
                lines.append(f"- 字段 `{field}`：")
                lines.append(f"  - 用户输入的值: {original} （不存在于数据库！）")
                lines.append(f"  - 数据库中的实际值: {actuals_str}")
                lines.append(f"  - → 请使用: WHERE {field} IN ({actuals_str})")
                lines.append("")
            
            lines.append("❗ 这是强制性的！必须使用数据库中的实际值，否则查询将返回 0 结果。")
            
            return "\n".join(lines)
            
        except Exception as e:
            print(f"DEBUG: Failed to parse verification_result: {e}")
            return ""
    
    def _generate_date_context(self) -> str:
        """
        动态生成日期处理上下文
        
        Author: CYJ
        """
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        current_year = now.year
        last_year = current_year - 1
        current_month = now.month
        last_month = current_month - 1 if current_month > 1 else 12
        last_month_year = current_year if current_month > 1 else current_year - 1
        next_month = current_month + 1 if current_month < 12 else 1
        next_month_year = current_year if current_month < 12 else current_year + 1
        
        return f"""Today is {today_str}.
   - 「今年」= {current_year}年 -> WHERE YEAR(created_at) = {current_year} 或 created_at >= '{current_year}-01-01'
   - 「去年」= {last_year}年 -> WHERE YEAR(created_at) = {last_year}
   - 「本月」= {current_year}年{current_month}月 -> WHERE created_at >= '{current_year}-{current_month:02d}-01' AND created_at < '{next_month_year}-{next_month:02d}-01'
   - 「上个月」= {last_month_year}年{last_month}月 -> WHERE created_at >= '{last_month_year}-{last_month:02d}-01' AND created_at < '{current_year}-{current_month:02d}-01'
   - 「最近N天」-> WHERE created_at >= DATE_SUB('{today_str}', INTERVAL N DAY)
   - 请勿将「今年」误解为{last_year}年！"""
    
    def _extract_tables_from_schema(self, schema_context: str) -> list:
        """
        从 schema_context 中提取召回的表名
        
        Args:
            schema_context: 向量检索返回的 Schema 上下文
            
        Returns:
            list: 表名列表
            
        Author: CYJ
        """
        import re
        tables = set()
        
        # 匹配 "Table: table_name" 格式
        pattern1 = r'Table:\s*(\w+)'
        matches1 = re.findall(pattern1, schema_context)
        tables.update(matches1)
        
        # 匹配 "[Table] table_name" 格式
        pattern2 = r'\[Table\]\s*(\w+)'
        matches2 = re.findall(pattern2, schema_context)
        tables.update(matches2)
        
        # 匹配 "table: table_name" 格式（小写）
        pattern3 = r'table:\s*(\w+)'
        matches3 = re.findall(pattern3, schema_context, re.IGNORECASE)
        tables.update(matches3)
        
        # 匹配 "[Column Details]" 下的 "table_name.column_name" 格式
        pattern4 = r'(\w+)\.\w+\s*[:-]'
        matches4 = re.findall(pattern4, schema_context)
        tables.update(matches4)
        
        # 过滤掉常见的非表名关键词
        exclude = {'Column', 'Table', 'Type', 'Description', 'type', 'table', 'column', 'VARCHAR', 'INT', 'BIGINT', 'DECIMAL', 'DATETIME', 'TEXT'}
        tables = [t for t in tables if t not in exclude and len(t) > 2]
        
        return list(tables)
    
    def _format_filter_conditions(self, filter_conditions: list) -> str:
        """
        格式化筛选条件为LLM可理解的指令
        
        Args:
            filter_conditions: Intent Agent提取的结构化筛选条件列表
            
        Returns:
            str: 格式化后的筛选条件指令
            
        Author: CYJ
        """
        if not filter_conditions:
            return "(无明确的筛选条件)"
        
        lines = []
        for i, cond in enumerate(filter_conditions, 1):
            if not isinstance(cond, dict):
                continue
                
            field_hint = cond.get("field_hint", "未知")
            value = cond.get("value", "")
            operator = cond.get("operator", "=")
            required = cond.get("required", True)
            
            status = "【必须】" if required else "【可选】"
            lines.append(f"  {i}. {status} 字段类型: {field_hint}, 值: '{value}', 操作符: {operator}")
        
        if not lines:
            return "(无明确的筛选条件)"
        
        result = "\n".join(lines)
        result += "\n\n  ❗ 以上每个【必须】条件都必须在WHERE子句中体现！"
        return result

    def invoke(self, state: AgentState) -> dict:
        """
        Run the SQL Planner manually.
        
        V3 优化：重试时复用首次召回的 Schema 缓存
        - 第1次执行：执行 Retrieval，缓存结果
        - 第1-2次重试：复用缓存 + 错误信息修正
        - 第3次兆底：重新执行 Retrieval（可能是召回的表/列不对）
        
        Author: CYJ
        """
        intent_data = state.get("intent", {})
        if not intent_data or intent_data.get("intent_type") != "query_data":
            return {"sql_query": None}

        query = intent_data.get("rewritten_query") or intent_data.get("original_query")
        retry_count = state.get("retry_count", 0)
        cached_schema = state.get("cached_schema_context")
        current_error = state.get("error")
        
        # Step 1: 决定是否复用缓存的 Schema
        # 新策略：
        # - 缓存缺失 → 必须检索
        # - 第3次及以上重试（兜底）→ 重新检索
        should_retrieve = (not cached_schema) or (retry_count >= 3)
        
        if should_retrieve:
            try:
                base_schema_context = self.retrieval_tool.invoke({"query": query, "top_k": 10})
                print(f"DEBUG: [Retrieval] Schema Context for '{query}' (retry={retry_count}):\n{base_schema_context[:500]}...") 
                
                # V15: 关联路径意图验证 - 验证召回的表之间的 JOIN 路径是否符合业务意图
                # Author: CYJ
                # Time: 2025-11-28
                try:
                    # 从 schema_context 中提取召回的表
                    selected_tables = self._extract_tables_from_schema(base_schema_context)
                    if selected_tables:
                        join_hints = self.path_validator.get_join_hints_for_planner(query, selected_tables)
                        if join_hints:
                            base_schema_context += join_hints
                            print(f"DEBUG: [PathIntentValidator] Added JOIN hints for tables: {selected_tables}")
                except Exception as path_err:
                    print(f"DEBUG: [PathIntentValidator] Path validation skipped: {path_err}")
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                base_schema_context = f"Error retrieving schema: {str(e)}"
        else:
            # 复用缓存
            base_schema_context = cached_schema
            print(f"DEBUG: [Cache Hit] Reusing cached schema (retry={retry_count})")

        # Step 2: Check if we are in verification mode or retry mode
        verification_result = state.get("verification_result")
        correction_note = ""
        schema_context = base_schema_context
        
        # V3: 重试时添加错误信息，帮助 LLM 修正 SQL
        # Author: CYJ
        if retry_count > 0 and current_error:
            failed_sql = state.get("original_failed_sql") or state.get("sql_query", "")
            
            # V5: 检查是否是语义验证失败（计条件遗漏）
            # Author: CYJ
            semantic_validation_result = state.get("semantic_validation_result")
            completeness_validation_result = state.get("completeness_validation_result")  # V14
            
            if completeness_validation_result and "SQL语义不完整" in current_error:
                # V14: 语义完整性验证失败，需要补充ORDER BY/LIMIT/GROUP BY等
                # Author: CYJ
                missing_sort = completeness_validation_result.get("missing_sort", False)
                missing_limit = completeness_validation_result.get("missing_limit", False)
                expected_limit = completeness_validation_result.get("expected_limit")
                missing_dimensions = completeness_validation_result.get("missing_dimensions", [])
                suggestion = completeness_validation_result.get("suggestion", "")
                
                fix_instructions = []
                if missing_sort:
                    fix_instructions.append("添加 ORDER BY 子句实现排序")
                if missing_limit:
                    fix_instructions.append(f"添加 LIMIT {expected_limit} 限制结果数量")
                if missing_dimensions:
                    fix_instructions.append(f"检查 GROUP BY 是否包含: {', '.join(missing_dimensions)}")
                
                schema_context += f"""

[❗❗ COMPLETENESS VALIDATION FAILED - 语义完整性不足]
上一次生成的 SQL 未完全满足用户的查询需求：
- 失败的 SQL: {failed_sql}
- 问题: {current_error}
- 详情: {suggestion}

【必须修正 - 灵魂拷问】：
请基于生成的SQL，对照用户的原始提问，逐项检查：
1. 用户要求的每一个筛选条件，SQL的WHERE是否都包含了？
2. 用户要求的分组维度（如"按省份、品类统计"），SQL的GROUP BY是否都覆盖了？
3. 用户要求的排序（如"降序"、"从高到低"），SQL是否有正确的ORDER BY？
4. 用户要求的数量限制（如"前10条"），SQL是否有正确的LIMIT？
5. 用户要求的输出指标（如"订单数、销售金额"），SQL的SELECT是否都包含了？

具体修复要求:
{chr(10).join(['- ' + inst for inst in fix_instructions])}

如果有任何一项不满足，该SQL就不是用户真正需要的SQL！
"""
            elif semantic_validation_result and "SQL语义不完整" in current_error:
                # 语义验证失败，需要补充遗漏的筛选条件
                schema_context += f"""

[❗ SEMANTIC VALIDATION FAILED - 筛选条件遗漏]
上一次生成的 SQL 缺少必要的筛选条件：
- 失败的 SQL: {failed_sql}
- 问题: {current_error}
- 详情: {semantic_validation_result}

【必须修正】：
请确保所有 filter_conditions 中的筛选条件都出现在 WHERE 子句中！
不要遗漏任何筛选条件，特别是：
- 优惠券类型（coupon_type）
- 店铺类型（shop_type）
- 支付方式（pay_method）
- 物流商（logistics_provider）
"""
            else:
                # 普通执行错误
                # V6: 重试时强调保留核心逻辑，不要简化
                # Author: CYJ
                # Time: 2025-11-27
                schema_context += f"""

[RETRY MODE - 第{retry_count}次重试]
上一次生成的 SQL 执行失败：
- 失败的 SQL: {failed_sql}
- 错误信息: {current_error}

请分析错误原因并修正：
1. 如果是 "Unknown column" 错误，请检查该列实际在哪个表中，可能需要 JOIN
2. 如果是语法错误，请修正 SQL 语法（但不要丢失核心逻辑！）
3. 请严格按照 Schema Information 中的表和列生成 SQL

⚠️ **CRITICAL - 重试时必须遵守**：
- 不要为了避免错误而简化SQL，丢失核心的过滤条件（如 WHERE rn <= N, LIMIT, 日期范围等）
- 如果原SQL有TopN逻辑（如"前3名"、"TOP 5"），修正后的SQL必须保留该限制
- 如果原SQL有日期筛选、分组排名等条件，修正后必须保留
- 只修复具体的语法错误，不要改变查询的业务逻辑
"""
        
        # V4: 解析 verification_result 生成清晰的替换指令
        # Author: CYJ
        value_replacement_instructions = ""
        if verification_result:
            # 解析并生成清晰的替换指令
            parsed_instructions = self._parse_verification_result(verification_result)
            if parsed_instructions:
                value_replacement_instructions = parsed_instructions
                correction_note = "已根据数据库实际值自动纠正查询条件"
            else:
                # 解析失败，使用原始信息
                value_replacement_instructions = f"""
⚠️ **上一次查询返回 0 结果**:
探针验证结果: {verification_result}
请根据探针结果中的 found_values 修正 SQL 中的实体值。
"""
                correction_note = "已尝试自动纠正查询条件"
        else:
            # V5: 移除硬编码映射，完全依赖Schema注释和知识图谱
            # Author: CYJ
            value_replacement_instructions = """用户可能用中文描述实体，但数据库可能存储英文值。
请从 Schema Information 中的列注释/枚举值描述中获取正确的字段值。
不要自行猜测映射关系，如果Schema中没有明确指明，请直接使用用户提供的原始值。"""

        # Step 2: Generate dynamic date context
        date_context = self._generate_date_context()
        
        # Step 2.5: Extract intent entities for guidance
        # V3: 将 Intent 中提取的实体传递给 LLM，辅助生成正确的 SQL
        # Author: CYJ
        intent_entities = intent_data.get("entities", {})
        intent_entities_str = ""
        if intent_entities:
            intent_entities_str = "\n".join([f"- {k}: {v}" for k, v in intent_entities.items()])
        else:
            intent_entities_str = "(无已提取实体)"
        
        # V4: 提取结构化筛选条件，生成强制性WHERE指令
        # Author: CYJ
        filter_conditions = intent_data.get("filter_conditions", [])
        filter_conditions_str = self._format_filter_conditions(filter_conditions)
        
        # Step 3: LLM Generation
        try:
            response = self.chain.invoke({
                "schema_context": schema_context,
                "input": query,
                "date_context": date_context,
                "intent_entities": intent_entities_str,
                "value_replacement_instructions": value_replacement_instructions,
                "filter_conditions_instructions": filter_conditions_str
            })
            print(f"DEBUG: LLM Response: {response}")
            print(f"DEBUG: Value Replacement Instructions: {value_replacement_instructions[:200] if value_replacement_instructions else 'None'}...")
            
            generated_sql = response.strip()
            
            # Clean up Markdown if present
            if generated_sql.startswith("```"):
                generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
            
            # Check for clarification/rejection in text
            if "clarification" in generated_sql.lower() and "{" in generated_sql:
                # V4: 即使SQL生成失败也保存cached_schema_context，供诊断器使用
                # Author: CYJ
                return {
                    "sql_query": None, 
                    "clarification": generated_sql, 
                    "verification_result": None,
                    "cached_schema_context": base_schema_context
                }
            
            # V3: 首次执行时缓存 Schema，重试时复用
            # Author: CYJ
            result = {
                "sql_query": generated_sql, 
                "verification_result": None,
                "correction_note": correction_note
            }
            
            # 缓存 Schema：首次执行或兜底重检索后都更新缓存
            if should_retrieve:
                result["cached_schema_context"] = base_schema_context
                
            return result
            
        except Exception as e:
            return {"error": f"SQL Generation failed: {str(e)}"}
