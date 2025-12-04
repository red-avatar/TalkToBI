"""
功能：统一智能诊断分析器 (Unified Intelligent Analyzer)
说明：
    合并原 ResultDiagnoser 和 IntelligentAnalyzer 功能
    
    诊断流程：
    1. 快速规则预检（合并自 ResultDiagnoser）
       - SQL逻辑检查：INNER JOIN过多、WHERE条件过多等
       - 中文实体检测：可能需要映射的字段
    
    2. 阶段A - 理解层诊断（LLM）
       - 召回的Schema是否覆盖用户需求
       - 是否需要重新召回
    
    3. 阶段B - SQL构建层诊断（LLM + CoT）
       - WHERE条件分析，对照DDL推理映射问题
       - 输出需要探针验证的实体列表

Author: CYJ
"""
import re
import json
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from app.core.llm import get_llm
from app.core.config import get_settings
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)
_settings = get_settings()


# ============================================================================
# 常量定义（合并自 ResultDiagnoser）
# ============================================================================
# 常见的需要映射的字段
COMMON_MAPPING_FIELDS = {
    'pay_method', 'payment_method', 'status', 'order_status',
    'refund_status', 'pay_status', 'shop_type', 'city_level',
    'service_level', 'type', 'scope'
}


class DiagnosisPhase(Enum):
    """诊断阶段"""
    UNDERSTANDING = "understanding"  # 理解层
    SQL_BUILDING = "sql_building"    # SQL构建层


@dataclass
class UnderstandingDiagnosis:
    """理解层诊断结果"""
    is_correct: bool  # 理解是否正确
    missing_tables: List[str] = field(default_factory=list)  # 缺失的表
    wrong_tables: List[str] = field(default_factory=list)    # 召回错误的表
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)  # 证据链
    suggestion: Optional[str] = None


@dataclass
class SqlBuildingDiagnosis:
    """SQL构建层诊断结果"""
    is_correct: bool  # SQL构建是否正确
    suspicious_entities: List[Dict[str, Any]] = field(default_factory=list)  # 可疑实体列表
    join_issues: List[str] = field(default_factory=list)  # JOIN问题
    where_issues: List[str] = field(default_factory=list)  # WHERE条件问题
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)  # 证据链（CoT思维过程）
    probe_suggestions: List[Dict[str, Any]] = field(default_factory=list)  # 探针建议


@dataclass
class IntelligentDiagnosisResult:
    """智能诊断综合结果"""
    phase: DiagnosisPhase
    understanding_result: Optional[UnderstandingDiagnosis] = None
    sql_building_result: Optional[SqlBuildingDiagnosis] = None
    need_recall: bool = False  # 是否需要重新召回
    need_probe: bool = False   # 是否需要探针验证
    final_recommendation: str = ""


class IntelligentAnalyzer:
    """
    统一智能诊断分析器
    
    合并原 ResultDiagnoser 和 IntelligentAnalyzer 功能：
    1. 快速规则预检（SQL逻辑、中文实体检测）
    2. LLM理解层诊断
    3. LLM SQL构建层诊断（CoT）
    
    Author: CYJ
    """
    
    def __init__(self):
        """初始化智能分析器"""
        self.llm = get_llm(temperature=_settings.LLM_TEMPERATURE_PRECISE)
    
    async def diagnose(self,
                       user_query: str,
                       sql: str,
                       schema_ddl: str,
                       data_result: Any,
                       filter_conditions: List[Dict] = None,
                       verified_mappings: Dict[str, str] = None) -> IntelligentDiagnosisResult:
        """
        执行智能诊断
        
        诊断流程：
        1. 快速规则预检（SQL逻辑问题）
        2. 理解层诊断（Schema覆盖）
        3. SQL构建层诊断（WHERE条件）
        
        Args:
            user_query: 用户原始提问
            sql: 生成的SQL
            schema_ddl: 已召回的Schema DDL
            data_result: 查询结果
            filter_conditions: Intent提取的筛选条件
            verified_mappings: 已验证的实体映射缓存
            
        Returns:
            IntelligentDiagnosisResult: 诊断结果
            
        Author: CYJ
        """
        filter_conditions = filter_conditions or []
        verified_mappings = verified_mappings or {}
        
        logger.info("[IntelligentAnalyzer] 开始智能诊断...")
        logger.info(f"[IntelligentAnalyzer] 用户查询: {user_query}")
        logger.info(f"[IntelligentAnalyzer] 已缓存映射: {verified_mappings}")
        
        # Step 0: 快速规则预检（合并自 ResultDiagnoser）
        rule_check = self._quick_rule_check(sql, data_result)
        if rule_check.get("has_issues"):
            logger.info(f"[IntelligentAnalyzer] 规则预检发现问题: {rule_check.get('issues')}")
            # 规则检查发现问题，记录到证据中，继续LLM诊断
        
        # Step 1: 理解层诊断
        understanding_result = await self._diagnose_understanding(
            user_query, schema_ddl, filter_conditions
        )
        
        if not understanding_result.is_correct:
            logger.info(f"[IntelligentAnalyzer] 理解层诊断：需要重新召回")
            return IntelligentDiagnosisResult(
                phase=DiagnosisPhase.UNDERSTANDING,
                understanding_result=understanding_result,
                need_recall=True,
                final_recommendation=f"召回不完整，建议补充表: {understanding_result.missing_tables}"
            )
        
        # Step 2: SQL构建层诊断
        sql_building_result = await self._diagnose_sql_building(
            user_query, sql, schema_ddl, filter_conditions, verified_mappings
        )
        
        # 合并规则检查的证据
        if rule_check.get("issues"):
            sql_building_result.evidence.extend([
                f"[规则检查] {issue.get('description', '')}" 
                for issue in rule_check.get("issues", [])
            ])
        
        if not sql_building_result.is_correct:
            logger.info(f"[IntelligentAnalyzer] SQL构建层诊断：需要探针验证")
            return IntelligentDiagnosisResult(
                phase=DiagnosisPhase.SQL_BUILDING,
                understanding_result=understanding_result,
                sql_building_result=sql_building_result,
                need_probe=True,
                final_recommendation=f"SQL条件可能有误，建议探针验证: {[e.get('value') for e in sql_building_result.suspicious_entities]}"
            )
        
        # 两阶段都通过，数据可能确实为空
        logger.info("[IntelligentAnalyzer] 诊断完成，数据可能确实为空")
        return IntelligentDiagnosisResult(
            phase=DiagnosisPhase.SQL_BUILDING,
            understanding_result=understanding_result,
            sql_building_result=sql_building_result,
            need_recall=False,
            need_probe=False,
            final_recommendation="SQL构建正确，数据可能确实为空"
        )
    
    # ========================================================================
    # 快速规则预检（合并自 ResultDiagnoser）
    # ========================================================================
    
    def _quick_rule_check(self, sql: Optional[str], data_result: Any) -> Dict:
        """
        快速规则预检（合并自 ResultDiagnoser._check_sql_logic）
        
        检测常见的SQL逻辑问题：
        1. INNER JOIN过多
        2. WHERE条件过多
        3. 子查询可能为空
        4. 硬编码值过多
        
        Author: CYJ
        """
        if not sql:
            return {"has_issues": False, "issues": []}
        
        issues = []
        sql_upper = sql.upper()
        
        # 检查1: INNER JOIN过多
        explicit_inner = sql_upper.count("INNER JOIN")
        implicit_inner = sql_upper.count(" JOIN ") - sql_upper.count("LEFT JOIN") - sql_upper.count("RIGHT JOIN")
        total_joins = explicit_inner + max(0, implicit_inner)
        
        if total_joins >= 4:
            issues.append({
                "type": "too_many_inner_joins",
                "description": f"SQL包含{total_joins}个INNER JOIN，可能导致过度过滤",
                "suggestion": "考虑将部分INNER JOIN改为LEFT JOIN"
            })
        
        # 检查2: WHERE条件过多
        where_conditions = self._count_where_conditions(sql)
        if where_conditions >= 4:
            issues.append({
                "type": "too_many_conditions",
                "description": f"WHERE子句包含{where_conditions}个条件，组合条件可能过严",
                "suggestion": "考虑逐步放宽条件验证"
            })
        
        # 检查3: 子查询可能为空
        if "IN (SELECT" in sql_upper or "IN(SELECT" in sql_upper:
            issues.append({
                "type": "subquery_may_empty",
                "description": "SQL包含IN子查询，子查询可能返回空集",
                "suggestion": "先验证子查询是否有结果"
            })
        
        # 检查4: 硬编码值过多
        hardcoded_values = self._find_hardcoded_values(sql)
        if len(hardcoded_values) >= 3:
            issues.append({
                "type": "many_hardcoded_values",
                "description": f"SQL包含{len(hardcoded_values)}个硬编码筛选值",
                "suggestion": "检查这些值是否与数据库实际值匹配"
            })
        
        return {
            "has_issues": len(issues) > 0,
            "issues": issues
        }
    
    def _count_where_conditions(self, sql: str) -> int:
        """
        统计WHERE子句中的条件数量
        
        Author: CYJ
        """
        sql_upper = sql.upper()
        where_idx = sql_upper.find('WHERE')
        if where_idx == -1:
            return 0
        
        where_clause = sql_upper[where_idx:]
        for end_keyword in ['GROUP BY', 'ORDER BY', 'LIMIT', 'HAVING']:
            end_idx = where_clause.find(end_keyword)
            if end_idx != -1:
                where_clause = where_clause[:end_idx]
        
        and_count = where_clause.count(' AND ')
        or_count = where_clause.count(' OR ')
        
        return and_count + or_count + 1
    
    def _find_hardcoded_values(self, sql: str) -> List[str]:
        """
        查找SQL中的硬编码值
        
        Author: CYJ
        """
        pattern = r"=\s*['\"]([^'\"]+)['\"]"
        values = re.findall(pattern, sql)
        return values
    
    def _extract_where_conditions(self, sql: str) -> List[Dict[str, str]]:
        """
        从SSQL中提取WHERE子句的条件
        
        Returns:
            List[Dict]: [{"column": "pay_method", "value": "微信支付"}, ...]
            
        Author: CYJ
        Time: 2025-11-26
        """
        conditions = []
        
        sql_upper = sql.upper()
        where_idx = sql_upper.find('WHERE')
        if where_idx == -1:
            return conditions
        
        where_clause = sql[where_idx:]
        pattern = r"(\w+(?:\.\w+)?)\s*=\s*['\"]([^'\"]+)['\"]"
        
        for match in re.finditer(pattern, where_clause, re.IGNORECASE):
            column = match.group(1)
            value = match.group(2)
            
            if value.upper() in ['NULL', 'TRUE', 'FALSE', '1', '0']:
                continue
            
            conditions.append({"column": column, "value": value})
        
        return conditions
    
    def _contains_chinese(self, text: str) -> bool:
        """
        检查文本是否包含中文字符
        
        Author: CYJ
        """
        if not text:
            return False
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return True
        return False
    
    def _extract_tables_from_context(self, schema_context: str) -> List[str]:
        """
        从Schema上下文中提取表名
        
        Author: CYJ
        """
        tables = []
        pattern = r'\[(\w+)\]'
        for match in re.finditer(pattern, schema_context):
            table_name = match.group(1)
            if table_name not in tables and not table_name.startswith('Column'):
                tables.append(table_name)
        return tables
    
    async def _diagnose_understanding(self,
                                      user_query: str,
                                      schema_ddl: str,
                                      filter_conditions: List[Dict]) -> UnderstandingDiagnosis:
        """
        阶段A：理解层诊断
        
        检查召回的Schema是否覆盖用户需求
        
        Author: CYJ
        """
        prompt = ChatPromptTemplate.from_template("""你是一个Schema召回诊断专家。请分析召回的Schema是否覆盖了用户的查询需求。

【用户原始提问】
{user_query}

【从提问中提取的筛选条件】
{filter_conditions}

【已召回的Schema DDL】
{schema_ddl}

请按以下步骤分析（输出你的思考过程）:

1. [需求分析] 用户想查什么数据？涉及哪些业务实体？
   - 列出用户查询涉及的核心实体（如：订单、用户、商品、物流、支付等）

2. [Schema检查] 对照已召回的Schema：
   - 列出已召回的表名
   - 每个用户需求的实体是否有对应的表？
   - 是否有遗漏的关键表？

3. [证据链] 给出你的判断依据

4. [结论] 

请严格按以下JSON格式输出：
{{
    "is_correct": true或false,
    "missing_tables": ["缺失的表名列表"],
    "wrong_tables": ["召回错误的表名列表"],
    "confidence": 0.0到1.0的置信度,
    "evidence": ["证据链列表，记录你的分析过程"],
    "suggestion": "修复建议"
}}""")
        
        try:
            chain = prompt | self.llm
            result = chain.invoke({
                "user_query": user_query,
                "filter_conditions": json.dumps(filter_conditions, ensure_ascii=False, indent=2),
                "schema_ddl": schema_ddl[:4000]  # 限制长度
            })
            
            content = result.content.strip()
            data = self._parse_json_response(content)
            
            return UnderstandingDiagnosis(
                is_correct=data.get("is_correct", True),
                missing_tables=data.get("missing_tables", []),
                wrong_tables=data.get("wrong_tables", []),
                confidence=data.get("confidence", 0.5),
                evidence=data.get("evidence", []),
                suggestion=data.get("suggestion")
            )
            
        except Exception as e:
            logger.error(f"[IntelligentAnalyzer] 理解层诊断失败: {e}")
            return UnderstandingDiagnosis(is_correct=True, confidence=0.3, evidence=[f"诊断异常: {str(e)}"])
    
    async def _diagnose_sql_building(self,
                                     user_query: str,
                                     sql: str,
                                     schema_ddl: str,
                                     filter_conditions: List[Dict],
                                     verified_mappings: Dict[str, str]) -> SqlBuildingDiagnosis:
        """
        阶段B：SQL构建层诊断（CoT思维链）
        
        分析SQL中的WHERE条件是否正确，基于DDL推理可能的映射问题
        
        Author: CYJ
        """
        prompt = ChatPromptTemplate.from_template("""你是一个SQL诊断专家。查询返回0结果，请分析WHERE条件是否正确。

【用户原始提问】
{user_query}

【生成的SQL】
{sql}

【已召回的Schema DDL（包含列注释和枚举值说明）】
{schema_ddl}

【Intent提取的筛选条件】
{filter_conditions}

【已验证的实体映射缓存】
{verified_mappings}

请按以下步骤进行CoT分析（必须输出完整的思考过程）:

1. [条件提取] 从SQL的WHERE子句中提取所有筛选条件：
   - 列出每个 字段=值 或 字段 IN (...) 的条件
   
2. [DDL对照] 对于每个条件，查找DDL中的字段注释：
   - 该字段在DDL中的注释是什么？
   - DDL注释中是否说明了枚举值？（如：-- 支付方式: wechat, alipay）
   - 用户输入的值与DDL描述是否一致？

3. [映射分析] 判断是否存在中英文映射问题：
   - 用户说"微信"，但数据库可能存"wechat"
   - 用户说"一线城市"，但数据库可能存"tier1"
   - 用户说"顺丰"，但数据库可能存"顺丰速运"
   - 地理名称是否需要加"市"后缀？（如杭州→杭州市）

4. [缓存检查] 检查已验证的映射缓存：
   - 如果某个值已经在缓存中有映射，直接使用
   - 只对缓存中没有的值进行探针建议

5. [证据链] 列出所有可疑实体及其推理依据

6. [探针建议] 为每个可疑实体生成探针SQL：
   - 表名、字段名、探针SQL

请严格按以下JSON格式输出：
{{
    "is_correct": true或false,
    "suspicious_entities": [
        {{
            "table": "表名",
            "column": "字段名",
            "value": "用户输入的值",
            "reason": "为什么可疑",
            "possible_values": ["可能的正确值1", "可能的正确值2"],
            "probe_sql": "SELECT DISTINCT 字段 FROM 表 WHERE 字段 LIKE '%xxx%' LIMIT 10"
        }}
    ],
    "join_issues": ["JOIN问题列表"],
    "where_issues": ["WHERE条件问题列表"],
    "confidence": 0.0到1.0的置信度,
    "evidence": ["CoT证据链列表，记录完整的分析过程"]
}}""")
        
        try:
            chain = prompt | self.llm
            result = chain.invoke({
                "user_query": user_query,
                "sql": sql,
                "schema_ddl": schema_ddl[:4000],
                "filter_conditions": json.dumps(filter_conditions, ensure_ascii=False, indent=2),
                "verified_mappings": json.dumps(verified_mappings, ensure_ascii=False)
            })
            
            content = result.content.strip()
            data = self._parse_json_response(content)
            
            # 过滤掉已缓存的映射
            suspicious = data.get("suspicious_entities", [])
            filtered_suspicious = []
            for entity in suspicious:
                value = entity.get("value", "")
                if value not in verified_mappings:
                    filtered_suspicious.append(entity)
                else:
                    logger.info(f"[IntelligentAnalyzer] 跳过已缓存的映射: {value} -> {verified_mappings[value]}")
            
            return SqlBuildingDiagnosis(
                is_correct=data.get("is_correct", True) or len(filtered_suspicious) == 0,
                suspicious_entities=filtered_suspicious,
                join_issues=data.get("join_issues", []),
                where_issues=data.get("where_issues", []),
                confidence=data.get("confidence", 0.5),
                evidence=data.get("evidence", [])
            )
            
        except Exception as e:
            logger.error(f"[IntelligentAnalyzer] SQL构建层诊断失败: {e}")
            return SqlBuildingDiagnosis(is_correct=True, confidence=0.3, evidence=[f"诊断异常: {str(e)}"])
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """
        解析LLM返回的JSON响应
        
        Author: CYJ
        """
        try:
            # 尝试直接解析
            return json.loads(content)
        except:
            pass
        
        # 尝试提取JSON块
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]
        
        # 尝试查找JSON对象
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        
        logger.warning(f"[IntelligentAnalyzer] JSON解析失败: {content[:200]}")
        return {}


# 单例实例
_intelligent_analyzer = None

def get_intelligent_analyzer() -> IntelligentAnalyzer:
    """获取智能分析器单例"""
    global _intelligent_analyzer
    if _intelligent_analyzer is None:
        _intelligent_analyzer = IntelligentAnalyzer()
    return _intelligent_analyzer
