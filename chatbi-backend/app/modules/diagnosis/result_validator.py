"""
功能：统一结果验证器 (Unified Result Validator)
说明：
    合并原 SemanticValidator 和 ResultValidator 功能，提供完整的结果验证能力
    
    验证维度：
    1. 筛选条件覆盖 - filter_conditions中的条件是否都被SQL覆盖？
    2. 对比类查询完整性 - 用户要"A vs B对比"，结果是否包含A和B的数据？
    3. 结果相关性 - 执行结果是否真正回答了用户问题？
    4. LLM语义验证 - 深度验证SQL语义与用户需求的匹配度

Author: CYJ
Time: 2025-11-26 (V2: 合并 SemanticValidator)
"""
import re
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from app.core.llm import get_llm
from app.core.config import get_settings
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)
_settings = get_settings()


# ============================================================================
# 字段提示到SQL模式映射（合并自 SemanticValidator）
# ============================================================================
FIELD_HINT_TO_SQL_PATTERNS = {
    "coupon_type": [r"coupons?\.type", r"c\.type", r"cp\.type", r"coupon.*type"],
    "shop_type": [r"shops?\.shop_type", r"s\.shop_type"],
    "category": [r"categories\.name", r"c\.name", r"category.*name"],
    "pay_method": [r"payments?\.pay_method", r"p\.pay_method"],
    "city_level": [r"dim_region\.city_level", r"dr\.city_level", r"city_level"],
    "logistics_provider": [r"logistics_providers?\.name", r"lp\.name"],
    "channel": [r"order_channel_code", r"dim_channel", r"channel_code"],
    "city": [r"dim_region\.city", r"dr\.city", r"\.city\s*="],
    "brand": [r"products?\.brand", r"p\.brand", r"brand\s*="],
    "refund_status": [r"refunds?\.refund_status", r"r\.refund_status", r"refund_status"],
    "pay_status": [r"payments?\.pay_status", r"p\.pay_status", r"pay_status"],
    "order_status": [r"orders?\.status", r"o\.status", r"order.*status"],
}


@dataclass
class ResultValidationResult:
    """
    统一验证结果
    
    合并原 ValidationResult 和 ResultValidationResult
    """
    is_valid: bool  # 结果是否有效
    is_complete: bool = True  # 筛选条件是否完整覆盖
    completeness_score: float = 1.0  # 完整性得分 (0-1)
    confidence: float = 1.0  # 验证置信度
    issues: List[str] = field(default_factory=list)  # 发现的问题
    missing_dimensions: List[str] = field(default_factory=list)  # 缺失的维度
    missing_conditions: List[Dict] = field(default_factory=list)  # 缺失的筛选条件
    evidence: List[str] = field(default_factory=list)  # 验证证据
    suggestion: Optional[str] = None  # 修复建议


class ResultValidator:
    """
    统一结果验证器
    
    合并原 SemanticValidator 和 ResultValidator 功能：
    1. 筛选条件覆盖验证（规则 + LLM）
    2. 对比查询完整性检测
    3. 结果相关性验证
    
    Author: CYJ
    Time: 2025-11-26 (V2: 合并 SemanticValidator)
    """
    
    def __init__(self):
        """初始化结果验证器"""
        self.llm = get_llm(temperature=_settings.LLM_TEMPERATURE_PRECISE)
    
    def validate_filter_conditions(self,
                                   sql: str,
                                   filter_conditions: List[Dict[str, Any]],
                                   user_query: str = "") -> ResultValidationResult:
        """
        验证SQL是否覆盖了所有筛选条件（原 SemanticValidator.validate）
        
        验证流程：
        1. 规则匹配验证（快速）
        2. 如果规则匹配不确定，使用LLM验证（准确）
        
        Args:
            sql: 生成的SQL语句
            filter_conditions: Intent Agent提取的筛选条件列表
            user_query: 用户原始提问（用于LLM验证）
            
        Returns:
            ResultValidationResult: 验证结果
            
        Author: CYJ
        Time: 2025-11-26
        """
        if not filter_conditions:
            return ResultValidationResult(
                is_valid=True,
                is_complete=True,
                confidence=1.0,
                evidence=["无筛选条件需要验证"]
            )
        
        if not sql:
            return ResultValidationResult(
                is_valid=False,
                is_complete=False,
                missing_conditions=filter_conditions,
                confidence=1.0,
                evidence=["SQL为空"],
                suggestion="需要重新生成SQL"
            )
        
        logger.info(f"[ResultValidator] 验证 {len(filter_conditions)} 个筛选条件")
        
        # Step 1: 规则匹配验证
        rule_result = self._rule_based_condition_check(sql, filter_conditions)
        
        if rule_result["confidence"] >= 0.8:
            logger.info(f"[ResultValidator] 规则验证完成: {rule_result['is_complete']}")
            return ResultValidationResult(
                is_valid=rule_result["is_complete"],
                is_complete=rule_result["is_complete"],
                confidence=rule_result["confidence"],
                missing_conditions=rule_result.get("missing", []),
                evidence=rule_result.get("evidence", []),
                suggestion=rule_result.get("suggestion")
            )
        
        # Step 2: 规则匹配不确定时，使用LLM验证
        logger.info("[ResultValidator] 规则验证不确定，使用LLM验证")
        llm_result = self._llm_condition_validation(sql, filter_conditions, user_query)
        
        return ResultValidationResult(
            is_valid=llm_result.get("is_complete", True),
            is_complete=llm_result.get("is_complete", True),
            confidence=0.9,
            missing_conditions=llm_result.get("missing_conditions", []),
            evidence=llm_result.get("evidence", []),
            suggestion=llm_result.get("suggestion")
        )
    
    def validate(self,
                 user_query: str,
                 filter_conditions: List[Dict],
                 sql: str,
                 result: Any,
                 intent_entities: Dict = None) -> ResultValidationResult:
        """
        执行完整的结果后验证
        
        Args:
            user_query: 用户原始提问
            filter_conditions: Intent提取的筛选条件
            sql: 执行的SQL
            result: 查询结果
            intent_entities: 意图中提取的实体
            
        Returns:
            ResultValidationResult: 验证结果
            
        Author: CYJ
        Time: 2025-11-26
        """
        filter_conditions = filter_conditions or []
        intent_entities = intent_entities or {}
        
        logger.info("[ResultValidator] 开始后验证...")
        logger.info(f"[ResultValidator] 用户查询: {user_query}")
        logger.info(f"[ResultValidator] 结果行数: {len(result) if isinstance(result, list) else 'N/A'}")
        
        issues = []
        evidence = []
        missing_dimensions = []
        missing_conditions = []
        
        # 1. 检查筛选条件覆盖（使用规则验证）
        condition_check = self._rule_based_condition_check(sql, filter_conditions)
        if not condition_check.get("is_complete", True):
            issues.append("筛选条件覆盖不完整")
            missing_conditions.extend(condition_check.get("missing", []))
            evidence.extend(condition_check.get("evidence", []))
        else:
            evidence.append("[条件检查] 通过")
        
        # 2. 检查对比类查询完整性
        comparison_check = self._check_comparison_completeness(
            user_query, filter_conditions, result
        )
        if not comparison_check["is_complete"]:
            issues.append(f"对比查询不完整: {comparison_check['detail']}")
            missing_dimensions.extend(comparison_check.get("missing", []))
            evidence.append(f"[对比检查] {comparison_check['detail']}")
        else:
            evidence.append("[对比检查] 通过")
        
        # 3. 使用LLM进行语义验证（仅在有疑问或无结果时调用）
        if issues or not result:
            llm_check = self._llm_semantic_validation(
                user_query, sql, result, filter_conditions
            )
            issues.extend(llm_check.get("issues", []))
            evidence.extend(llm_check.get("evidence", []))
        
        # 计算完整性得分
        total_checks = 3
        passed_checks = sum([
            condition_check.get("is_complete", True),
            comparison_check["is_complete"],
            len(issues) <= 1
        ])
        completeness_score = passed_checks / total_checks
        
        # 生成建议
        suggestion = None
        if issues:
            suggestion = self._generate_suggestion(issues, missing_dimensions, missing_conditions)
        
        is_valid = len(issues) == 0 or completeness_score >= 0.7
        is_complete = condition_check.get("is_complete", True)
        
        return ResultValidationResult(
            is_valid=is_valid,
            is_complete=is_complete,
            completeness_score=completeness_score,
            confidence=condition_check.get("confidence", 0.8),
            issues=issues,
            missing_dimensions=missing_dimensions,
            missing_conditions=missing_conditions,
            evidence=evidence,
            suggestion=suggestion
        )
    
    def _rule_based_condition_check(self,
                                    sql: str,
                                    filter_conditions: List[Dict[str, Any]]) -> Dict:
        """
        基于规则的筛选条件验证（合并自 SemanticValidator）
        
        Author: CYJ
        Time: 2025-11-26
        """
        sql_lower = sql.lower()
        missing_conditions = []
        evidence = []
        
        for cond in filter_conditions:
            if not isinstance(cond, dict):
                continue
                
            field_hint = cond.get("field_hint", "").lower()
            value = cond.get("value", "")
            required = cond.get("required", True)
            
            if not required:
                continue
            
            # 获取该字段类型的SQL模式列表
            patterns = FIELD_HINT_TO_SQL_PATTERNS.get(field_hint, [])
            
            # 检查SQL中是否包含该字段
            field_found = False
            for pattern in patterns:
                if re.search(pattern, sql_lower):
                    field_found = True
                    break
            
            if field_found:
                value_found = self._check_value_in_sql(sql_lower, value)
                if value_found:
                    evidence.append(f"✓ 条件 {field_hint}='{value}' 已包含")
                else:
                    evidence.append(f"? 字段 {field_hint} 存在，值 '{value}' 可能已映射")
            else:
                missing_conditions.append(cond)
                evidence.append(f"✗ 条件 {field_hint}='{value}' 缺失")
        
        # 计算置信度
        total_required = sum(1 for c in filter_conditions if c.get("required", True))
        if total_required == 0:
            confidence = 1.0
        else:
            found_count = total_required - len(missing_conditions)
            confidence = found_count / total_required
        
        is_complete = len(missing_conditions) == 0
        suggestion = None
        if not is_complete:
            missing_hints = [c.get("field_hint", "") for c in missing_conditions]
            suggestion = f"SQL缺少筛选条件: {', '.join(missing_hints)}"
        
        return {
            "is_complete": is_complete,
            "is_covered": is_complete,
            "missing": missing_conditions,
            "confidence": confidence,
            "evidence": evidence,
            "suggestion": suggestion
        }
    
    def _check_value_in_sql(self, sql_lower: str, value: Any) -> bool:
        """
        检查值是否出现在SQL中
        
        Author: CYJ
        Time: 2025-11-26
        """
        if not isinstance(value, str):
            value = str(value)
        
        value_lower = value.lower()
        return value_lower in sql_lower
    
    def _llm_condition_validation(self,
                                  sql: str,
                                  filter_conditions: List[Dict[str, Any]],
                                  user_query: str) -> Dict:
        """
        基于LLM的筛选条件验证（合并自 SemanticValidator）
        
        Author: CYJ
        Time: 2025-11-26
        """
        conditions_str = "\n".join([
            f"- {c.get('field_hint', '?')}: {c.get('value', '?')} (必须: {c.get('required', True)})"
            for c in filter_conditions
        ])
        
        prompt = ChatPromptTemplate.from_template("""你是SQL语义分析专家。请验证SQL是否覆盖了所有筛选条件。

【用户提问】
{user_query}

【筛选条件】
{conditions}

【生成的SQL】
{sql}

【验证任务】
检查SQL的WHERE子句是否包含了每个筛选条件，注意中英文映射：
- 折扣券→discount, 满减→full_reduction
- 自营→self, 第三方→third_party
- 微信→wechat, 支付宝→alipay
- 一线→tier1, 二线→tier2

请严格按以下JSON格式输出：
{{
    "is_complete": true或false,
    "missing_conditions": ["遗漏的field_hint列表"],
    "evidence": ["验证依据列表"],
    "suggestion": "修复建议"
}}""")
        
        try:
            chain = prompt | self.llm
            result = chain.invoke({
                "user_query": user_query,
                "conditions": conditions_str,
                "sql": sql
            })
            
            content = result.content.strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            data = json.loads(content)
            
            missing = []
            missing_hints = data.get("missing_conditions", [])
            for cond in filter_conditions:
                if cond.get("field_hint") in missing_hints:
                    missing.append(cond)
            
            return {
                "is_complete": data.get("is_complete", True),
                "missing_conditions": missing,
                "evidence": data.get("evidence", []),
                "suggestion": data.get("suggestion")
            }
            
        except Exception as e:
            logger.error(f"[ResultValidator] LLM条件验证失败: {e}")
            return {"is_complete": True, "evidence": [f"LLM验证失败: {str(e)}"]}
    
    def _check_comparison_completeness(self,
                                       user_query: str,
                                       filter_conditions: List[Dict],
                                       result: Any) -> Dict:
        """
        检查对比类查询的完整性
        
        用户要"A vs B对比"，结果是否包含A和B的数据？
        
        Author: CYJ
        Time: 2025-11-26
        """
        # 检测是否是对比类查询
        comparison_keywords = ['对比', 'VS', 'vs', '比较', '和', '与', '或']
        is_comparison = any(kw in user_query for kw in comparison_keywords)
        
        if not is_comparison:
            return {"is_complete": True, "detail": "非对比查询"}
        
        # 查找多值筛选条件
        multi_value_conditions = []
        for cond in filter_conditions:
            value = cond.get("value")
            if isinstance(value, list) and len(value) > 1:
                multi_value_conditions.append({
                    "field": cond.get("field_hint", ""),
                    "expected_values": value
                })
        
        if not multi_value_conditions:
            return {"is_complete": True, "detail": "无多值条件"}
        
        # 检查结果中是否包含所有期望值
        if not isinstance(result, list) or len(result) == 0:
            return {
                "is_complete": False,
                "detail": "结果为空，无法验证对比完整性",
                "missing": [c["expected_values"] for c in multi_value_conditions]
            }
        
        # 尝试从结果中提取实际出现的维度值
        result_str = json.dumps(result, ensure_ascii=False).lower()
        missing = []
        
        for cond in multi_value_conditions:
            expected = cond["expected_values"]
            found_count = sum(1 for v in expected if str(v).lower() in result_str)
            
            if found_count < len(expected):
                missing_values = [v for v in expected if str(v).lower() not in result_str]
                missing.extend(missing_values)
        
        if missing:
            return {
                "is_complete": False,
                "detail": f"对比查询缺失维度: {missing}",
                "missing": missing
            }
        
        return {"is_complete": True, "detail": "对比数据完整"}
    
    def _llm_semantic_validation(self,
                                 user_query: str,
                                 sql: str,
                                 result: Any,
                                 filter_conditions: List[Dict]) -> Dict:
        """
        使用LLM进行语义层面的验证
        
        Author: CYJ
        Time: 2025-11-26
        """
        prompt = ChatPromptTemplate.from_template("""你是一个数据分析结果验证专家。请验证查询结果是否真正回答了用户的问题。

【用户原始提问】
{user_query}

【执行的SQL】
{sql}

【查询结果】
{result}

【Intent提取的筛选条件】
{filter_conditions}

请检查以下方面：

1. **结果相关性**：结果是否与用户问题相关？
2. **对比完整性**：如果是对比查询，是否返回了所有要对比的维度？
3. **数据合理性**：数值是否在合理范围内？

请严格按以下JSON格式输出：
{{
    "is_relevant": true或false,
    "issues": ["发现的问题列表"],
    "evidence": ["验证依据列表"],
    "confidence": 0.0到1.0的置信度
}}""")
        
        try:
            chain = prompt | self.llm
            
            # 限制结果长度
            result_str = json.dumps(result, ensure_ascii=False)
            if len(result_str) > 2000:
                result_str = result_str[:2000] + "...(truncated)"
            
            response = chain.invoke({
                "user_query": user_query,
                "sql": sql,
                "result": result_str,
                "filter_conditions": json.dumps(filter_conditions, ensure_ascii=False)
            })
            
            content = response.content.strip()
            
            # 解析JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            try:
                data = json.loads(content)
                return {
                    "issues": data.get("issues", []),
                    "evidence": data.get("evidence", [])
                }
            except:
                pass
            
        except Exception as e:
            logger.error(f"[ResultValidator] LLM验证失败: {e}")
        
        return {"issues": [], "evidence": ["LLM验证跳过"]}
    
    def _generate_suggestion(self,
                            issues: List[str],
                            missing_dimensions: List[str],
                            missing_conditions: List[Dict]) -> str:
        """
        生成修复建议
        
        Author: CYJ
        Time: 2025-11-26
        """
        suggestions = []
        
        if missing_dimensions:
            suggestions.append(f"SQL可能缺少对 {missing_dimensions} 的筛选，导致对比数据不完整")
        
        if missing_conditions:
            fields = [c.get("field_hint", "") for c in missing_conditions]
            suggestions.append(f"SQL未覆盖筛选条件: {fields}")
        
        if issues:
            suggestions.append(f"其他问题: {'; '.join(issues[:2])}")
        
        return " | ".join(suggestions) if suggestions else "建议检查SQL逻辑"


# 单例实例
_result_validator = None

def get_result_validator() -> ResultValidator:
    """获取结果验证器单例"""
    global _result_validator
    if _result_validator is None:
        _result_validator = ResultValidator()
    return _result_validator
