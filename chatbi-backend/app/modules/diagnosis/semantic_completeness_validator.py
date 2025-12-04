"""
功能：语义完整性验证器 (Semantic Completeness Validator)
说明：
    验证生成的SQL是否真正满足用户的查询需求，而不仅仅是语法正确。
    
    验证维度：
    1. 排序验证 - 用户要求"降序"，SQL是否有正确的ORDER BY
    2. 分页验证 - 用户要求"前N条"，SQL是否有正确的LIMIT
    3. 分组验证 - 用户要求"按...统计"，SQL的GROUP BY是否覆盖
    4. 指标验证 - 用户要求"订单数、销售金额"，SQL的SELECT是否包含

    核心反思指令：
    请基于生成的SQL，对照用户的原始提问，逐项检查：
    - 用户要求的每一个筛选条件，SQL的WHERE是否都包含了？
    - 用户要求的分组维度，SQL的GROUP BY是否都覆盖了？
    - 用户要求的排序，SQL是否有正确的ORDER BY？
    - 用户要求的数量限制，SQL是否有正确的LIMIT？
    - 用户要求的输出指标，SQL的SELECT是否都包含了？
    如果有任何一项不满足，该SQL就不是用户真正需要的SQL。

Author: CYJ
Time: 2025-11-28
"""
import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CompletenessValidationResult:
    """
    语义完整性验证结果
    
    Author: CYJ
    Time: 2025-11-28
    """
    is_complete: bool  # 是否完整
    failure_type: str = "none"  # 失败类型: "none", "semantic", "recall"
    
    # 语义类问题（Type A - 轻量重试）
    missing_sort: bool = False  # 缺少排序
    missing_limit: bool = False  # 缺少限制
    expected_limit: Optional[int] = None  # 期望的LIMIT值
    actual_limit: Optional[int] = None  # 实际的LIMIT值
    missing_dimensions: List[str] = field(default_factory=list)  # 缺失的分组维度
    missing_metrics: List[str] = field(default_factory=list)  # 缺失的输出指标
    
    # 召回类问题（Type B - 完整重试）
    missing_tables: List[str] = field(default_factory=list)  # 缺失的表
    missing_columns: List[str] = field(default_factory=list)  # 缺失的字段
    
    # 验证证据
    evidence: List[str] = field(default_factory=list)  # 验证过程记录
    suggestion: Optional[str] = None  # 修复建议
    retry_strategy: str = "lightweight"  # 重试策略: "lightweight" or "full"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "is_complete": self.is_complete,
            "failure_type": self.failure_type,
            "missing_sort": self.missing_sort,
            "missing_limit": self.missing_limit,
            "expected_limit": self.expected_limit,
            "actual_limit": self.actual_limit,
            "missing_dimensions": self.missing_dimensions,
            "missing_metrics": self.missing_metrics,
            "missing_tables": self.missing_tables,
            "missing_columns": self.missing_columns,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
            "retry_strategy": self.retry_strategy,
        }


class SemanticCompletenessValidator:
    """
    语义完整性验证器
    
    基于规则验证SQL是否满足用户的查询需求：
    - 排序要求 (ORDER BY)
    - 分页要求 (LIMIT)
    - 分组维度 (GROUP BY)
    - 输出指标 (SELECT聚合)
    
    Author: CYJ
    Time: 2025-11-28
    """
    
    # 指标关键词到SQL聚合函数的映射
    METRIC_PATTERNS = {
        "订单数": ["COUNT", "订单数", "order_count"],
        "销售金额": ["SUM", "销售金额", "金额", "pay_amount", "total_amount", "sales"],
        "销售额": ["SUM", "销售额", "金额", "pay_amount", "total_amount", "sales"],
        "消费金额": ["SUM", "消费金额", "金额", "pay_amount", "total_consumption"],
        "退款金额": ["SUM", "退款金额", "refund_amount"],
        "退款数量": ["COUNT", "退款数量", "refund_count"],
        "平均": ["AVG", "平均"],
        "签收率": ["签收率", "delivery_rate", "/", "CASE"],
        "签收数量": ["COUNT", "签收", "delivered"],
    }
    
    # 维度关键词映射
    DIMENSION_PATTERNS = {
        "省份": ["province", "省份", "省"],
        "城市": ["city", "城市", "市"],
        "品类": ["category", "品类", "categories"],
        "支付方式": ["pay_method", "支付方式", "payment"],
        "物流商": ["logistics_provider", "物流商", "物流"],
        "店铺": ["shop", "店铺"],
        "渠道": ["channel", "渠道"],
        "用户等级": ["level", "用户等级", "会员等级", "user_level"],
        "注册渠道": ["register_channel", "注册渠道", "channel_name"],
        "优惠券类型": ["coupon_type", "优惠券类型", "type"],
    }
    
    def validate(self,
                 sql: str,
                 query_requirements: Dict[str, Any],
                 user_query: str = "") -> CompletenessValidationResult:
        """
        执行语义完整性验证
        
        Args:
            sql: 生成的SQL语句
            query_requirements: 从Intent提取的查询需求
            user_query: 用户原始提问（用于日志）
            
        Returns:
            CompletenessValidationResult: 验证结果
            
        Author: CYJ
        Time: 2025-11-28
        """
        if not sql or not query_requirements:
            return CompletenessValidationResult(
                is_complete=True,
                evidence=["无需验证：SQL或query_requirements为空"]
            )
        
        logger.info(f"[CompletenessValidator] 开始验证SQL语义完整性")
        logger.info(f"[CompletenessValidator] query_requirements: {query_requirements}")
        
        evidence = []
        issues = []
        
        sql_upper = sql.upper()
        
        # 1. 验证排序要求
        sort_by = query_requirements.get("sort_by")
        missing_sort = False
        if sort_by:
            has_order_by = "ORDER BY" in sql_upper
            if not has_order_by:
                missing_sort = True
                issues.append("缺少ORDER BY")
                evidence.append(f"✗ 用户要求按'{sort_by.get('field')}'排序，但SQL无ORDER BY")
            else:
                evidence.append(f"✓ SQL包含ORDER BY，满足排序要求")
        
        # 2. 验证数量限制
        limit = query_requirements.get("limit")
        missing_limit = False
        expected_limit = None
        actual_limit = None
        if limit:
            expected_limit = limit
            limit_match = re.search(r"LIMIT\s+(\d+)", sql_upper)
            if not limit_match:
                missing_limit = True
                issues.append(f"缺少LIMIT {limit}")
                evidence.append(f"✗ 用户要求取前{limit}条，但SQL无LIMIT")
            else:
                actual_limit = int(limit_match.group(1))
                if actual_limit != limit:
                    missing_limit = True
                    issues.append(f"LIMIT值不匹配：期望{limit}，实际{actual_limit}")
                    evidence.append(f"✗ LIMIT值不匹配：期望{limit}，实际{actual_limit}")
                else:
                    evidence.append(f"✓ SQL包含LIMIT {limit}，满足数量限制要求")
        
        # 3. 验证分组维度
        group_dimensions = query_requirements.get("group_dimensions", [])
        missing_dimensions = []
        if group_dimensions:
            has_group_by = "GROUP BY" in sql_upper
            if not has_group_by and query_requirements.get("has_aggregation", False):
                missing_dimensions = group_dimensions
                issues.append(f"缺少GROUP BY: {group_dimensions}")
                evidence.append(f"✗ 用户要求按{group_dimensions}分组，但SQL无GROUP BY")
            else:
                # 检查每个维度是否在GROUP BY中
                for dim in group_dimensions:
                    dim_found = self._check_dimension_in_sql(dim, sql_upper)
                    if not dim_found:
                        missing_dimensions.append(dim)
                        evidence.append(f"? 维度'{dim}'可能未在GROUP BY中")
                    else:
                        evidence.append(f"✓ 维度'{dim}'已包含在SQL中")
        
        # 4. 验证输出指标
        required_metrics = query_requirements.get("required_metrics", [])
        missing_metrics = []
        if required_metrics:
            for metric in required_metrics:
                metric_found = self._check_metric_in_sql(metric, sql_upper)
                if not metric_found:
                    missing_metrics.append(metric)
                    evidence.append(f"? 指标'{metric}'可能未在SELECT中")
                else:
                    evidence.append(f"✓ 指标'{metric}'已包含在SQL中")
        
        # 判断是否完整
        is_complete = not (missing_sort or missing_limit or missing_dimensions)
        
        # 判断失败类型和重试策略
        failure_type = "none"
        retry_strategy = "lightweight"
        if not is_complete:
            failure_type = "semantic"  # 语义理解问题
            retry_strategy = "lightweight"  # 轻量重试
        
        # 生成修复建议
        suggestion = None
        if issues:
            suggestion = self._generate_suggestion(
                missing_sort, sort_by,
                missing_limit, expected_limit,
                missing_dimensions,
                missing_metrics
            )
        
        result = CompletenessValidationResult(
            is_complete=is_complete,
            failure_type=failure_type,
            missing_sort=missing_sort,
            missing_limit=missing_limit,
            expected_limit=expected_limit,
            actual_limit=actual_limit,
            missing_dimensions=missing_dimensions,
            missing_metrics=missing_metrics,
            evidence=evidence,
            suggestion=suggestion,
            retry_strategy=retry_strategy,
        )
        
        logger.info(f"[CompletenessValidator] 验证结果: is_complete={is_complete}, issues={issues}")
        logger.info(f"[CompletenessValidator] suggestion: {suggestion}")
        
        return result
    
    def _check_dimension_in_sql(self, dimension: str, sql_upper: str) -> bool:
        """
        检查维度是否在SQL中
        
        Author: CYJ
        Time: 2025-11-28
        """
        # 获取该维度的所有可能的SQL表示
        patterns = self.DIMENSION_PATTERNS.get(dimension, [dimension])
        
        for pattern in patterns:
            if pattern.upper() in sql_upper:
                return True
        
        # 尝试模糊匹配
        dim_lower = dimension.lower()
        if dim_lower in sql_upper.lower():
            return True
        
        return False
    
    def _check_metric_in_sql(self, metric: str, sql_upper: str) -> bool:
        """
        检查指标是否在SQL中
        
        Author: CYJ
        Time: 2025-11-28
        """
        # 获取该指标的所有可能的SQL表示
        patterns = self.METRIC_PATTERNS.get(metric, [metric])
        
        for pattern in patterns:
            if pattern.upper() in sql_upper:
                return True
        
        # 尝试模糊匹配
        metric_lower = metric.lower()
        if metric_lower in sql_upper.lower():
            return True
        
        # 检查常见聚合函数
        if "数" in metric or "量" in metric:
            if "COUNT" in sql_upper:
                return True
        if "金额" in metric or "额" in metric:
            if "SUM" in sql_upper:
                return True
        if "平均" in metric:
            if "AVG" in sql_upper:
                return True
        
        return False
    
    def _generate_suggestion(self,
                            missing_sort: bool,
                            sort_by: Optional[Dict],
                            missing_limit: bool,
                            expected_limit: Optional[int],
                            missing_dimensions: List[str],
                            missing_metrics: List[str]) -> str:
        """
        生成修复建议
        
        Author: CYJ
        """
        suggestions = []
        
        if missing_sort and sort_by:
            field = sort_by.get("field", "?")
            order = sort_by.get("order", "DESC")
            suggestions.append(f"添加排序: ORDER BY {field} {order}")
        
        if missing_limit and expected_limit:
            suggestions.append(f"添加限制: LIMIT {expected_limit}")
        
        if missing_dimensions:
            suggestions.append(f"检查GROUP BY是否包含: {', '.join(missing_dimensions)}")
        
        if missing_metrics:
            suggestions.append(f"检查SELECT是否包含指标: {', '.join(missing_metrics)}")
        
        return " | ".join(suggestions) if suggestions else "请检查SQL是否满足用户需求"


# 单例实例
_completeness_validator = None


def get_completeness_validator() -> SemanticCompletenessValidator:
    """获取语义完整性验证器单例"""
    global _completeness_validator
    if _completeness_validator is None:
        _completeness_validator = SemanticCompletenessValidator()
    return _completeness_validator
