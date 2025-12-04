"""
功能：可视化决策器 (Visualization Advisor)
说明：
    根据数据特征和用户意图，智能决策是否需要可视化以及使用何种图表类型。
    
    决策逻辑：
    1. 空结果 → 不可视化
    2. 单值结果 → 大数字卡片或纯文字
    3. 时序数据 → 折线图
    4. 分类数据 → 饼图（≤6类）或柱状图（>6类）
    5. 大数据量 → 表格

作者：陈怡坚
"""
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ChartType(Enum):
    """图表类型枚举"""
    NO_VIZ = "no_viz"              # 不需要可视化，纯文字回答
    SINGLE_VALUE = "single_value"  # 单值大数字卡片
    LINE = "line"                  # 折线图（时序趋势）
    MULTI_LINE = "multi_line"      # 多折线图
    BAR = "bar"                    # 柱状图（对比）
    HORIZONTAL_BAR = "horizontal_bar"  # 横向柱状图（长文本标签）
    GROUPED_BAR = "grouped_bar"    # 分组柱状图
    PIE = "pie"                    # 饼图（占比）
    TABLE = "table"                # 表格
    SCATTER = "scatter"            # 散点图


@dataclass
class VizRecommendation:
    """可视化推荐结果"""
    recommended: bool              # 是否推荐可视化
    chart_type: ChartType          # 推荐的图表类型
    reason: str                    # 推荐原因
    chart_title: Optional[str] = None  # 图表标题
    x_field: Optional[str] = None  # X轴字段名
    y_fields: Optional[List[str]] = None  # Y轴字段名列表
    category_field: Optional[str] = None  # 分类字段名


class VizAdvisor:
    """
    可视化决策器
    
    根据数据结构、用户意图、查询结果智能推荐图表类型。
    
    Author: CYJ
    Time: 2025-11-26
    """
    
    # 时间相关的列名模式
    TIME_PATTERNS = [
        r'date', r'time', r'day', r'month', r'year', r'week',
        r'created', r'updated', r'paid', r'ordered', r'refunded',
        r'_at$', r'_date$', r'_time$'
    ]
    
    # 分类相关的列名模式
    CATEGORY_PATTERNS = [
        r'type', r'status', r'category', r'name', r'province', r'city',
        r'region', r'channel', r'brand', r'shop', r'level', r'tier'
    ]
    
    # 数值相关的列名模式
    NUMERIC_PATTERNS = [
        r'amount', r'price', r'count', r'total', r'sum', r'avg',
        r'quantity', r'num', r'rate', r'ratio', r'percent'
    ]
    
    # 用户意图关键词 -> 图表类型映射
    # V2: 增强意图识别关键词  Author: CYJ  Time: 2025-11-26
    INTENT_KEYWORDS = {
        'line': ['趋势', '走势', '变化', '增长', '下降', '波动', '随时间', 'trend'],
        'pie': ['占比', '比例', '分布', '构成', '组成', '各占', 'proportion', 'distribution'],
        'bar': [
            '对比', '比较', '排名', 'top', '最高', '最低', 'ranking', 'compare',
            # V2 新增: 聚合分类意图关键词
            '来自', '分布在', '哪些', '各个', '分别', '按', '根据', '不同', 
            '多少个', '有几个', '有哪些', '各类', '每种', '每个'
        ],
        'table': ['明细', '详情', '列表', '清单', '全部', '所有', 'detail', 'list']
    }
    
    # 需要聚合的意图关键词（原始数据可能是明细，但用户想看聚合结果）
    AGGREGATION_KEYWORDS = [
        '来自哪些', '来自什么', '分布在', '哪些地区', '哪些类型', '哪些渠道',
        '按.*分组', '按.*统计', '按.*分类', '各个.*有多少', '各.*多少',
        '不同.*有多少', '多少个.*来自', '每个.*有多少'
    ]
    
    def recommend(
        self,
        data: List[Dict[str, Any]],
        user_query: str = "",
        intent: Optional[Dict] = None
    ) -> VizRecommendation:
        """
        根据数据和意图推荐可视化方式
        
        Args:
            data: SQL 查询结果 (List of Dict)
            user_query: 用户原始查询
            intent: 意图识别结果
            
        Returns:
            VizRecommendation: 可视化推荐结果
            
        Author: CYJ
        Time: 2025-11-26
        """
        # 1. 空结果检查
        if not data or len(data) == 0:
            return VizRecommendation(
                recommended=False,
                chart_type=ChartType.NO_VIZ,
                reason="查询结果为空，无需可视化"
            )
        
        # 2. 分析数据结构
        row_count = len(data)
        columns = list(data[0].keys()) if data else []
        col_count = len(columns)
        
        # 检测列类型
        time_cols = self._detect_time_columns(columns, data)
        category_cols = self._detect_category_columns(columns, data)
        numeric_cols = self._detect_numeric_columns(columns, data)
        
        logger.info(f"[VizAdvisor] rows={row_count}, cols={col_count}")
        logger.info(f"[VizAdvisor] time_cols={time_cols}, category_cols={category_cols}, numeric_cols={numeric_cols}")
        
        # 3. 检查用户意图关键词
        intent_chart = self._detect_intent_chart_type(user_query)
        
        # 4. 决策逻辑
        
        # Case 1: 单值结果
        if row_count == 1 and col_count == 1:
            value = list(data[0].values())[0]
            if isinstance(value, (int, float)):
                return VizRecommendation(
                    recommended=True,
                    chart_type=ChartType.SINGLE_VALUE,
                    reason="单一数值结果，使用数字卡片展示",
                    y_fields=[columns[0]]
                )
            else:
                return VizRecommendation(
                    recommended=False,
                    chart_type=ChartType.NO_VIZ,
                    reason="单一文本结果，文字回答更清晰"
                )
        
        # Case 2: 单行多列（单条记录详情）
        if row_count == 1 and col_count > 1:
            return VizRecommendation(
                recommended=True,
                chart_type=ChartType.TABLE,
                reason="单条记录详情，使用表格展示"
            )
        
        # Case 3: 数据量过大
        if row_count > 100:
            return VizRecommendation(
                recommended=True,
                chart_type=ChartType.TABLE,
                reason=f"数据量较大({row_count}行)，建议使用表格展示",
                chart_title="查询结果明细"
            )
        
        # Case 4: 有时间列 -> 优先折线图
        if time_cols and numeric_cols:
            if len(numeric_cols) == 1:
                return VizRecommendation(
                    recommended=True,
                    chart_type=ChartType.LINE,
                    reason="检测到时序数据，使用折线图展示趋势",
                    chart_title=self._generate_title(user_query, "趋势"),
                    x_field=time_cols[0],
                    y_fields=numeric_cols
                )
            else:
                return VizRecommendation(
                    recommended=True,
                    chart_type=ChartType.MULTI_LINE,
                    reason="检测到多指标时序数据，使用多折线图",
                    chart_title=self._generate_title(user_query, "趋势对比"),
                    x_field=time_cols[0],
                    y_fields=numeric_cols
                )
        
        # Case 5: 有分类列 + 数值列 -> 饼图或柱状图
        if category_cols and numeric_cols:
            category_col = category_cols[0]
            unique_categories = len(set(row.get(category_col) for row in data))
            
            # 用户意图关键词优先
            if intent_chart == 'pie':
                return VizRecommendation(
                    recommended=True,
                    chart_type=ChartType.PIE,
                    reason="用户关注占比分布，使用饼图",
                    chart_title=self._generate_title(user_query, "占比"),
                    category_field=category_col,
                    y_fields=numeric_cols[:1]
                )
            
            # 根据分类数量决定
            if unique_categories <= 6:
                return VizRecommendation(
                    recommended=True,
                    chart_type=ChartType.PIE,
                    reason=f"分类数量较少({unique_categories}个)，适合饼图展示占比",
                    chart_title=self._generate_title(user_query, "分布"),
                    category_field=category_col,
                    y_fields=numeric_cols[:1]
                )
            elif unique_categories <= 20:
                # 检查标签长度，决定用横向还是纵向柱状图
                max_label_len = max(len(str(row.get(category_col, ''))) for row in data)
                chart_type = ChartType.HORIZONTAL_BAR if max_label_len > 6 else ChartType.BAR
                return VizRecommendation(
                    recommended=True,
                    chart_type=chart_type,
                    reason=f"分类数量适中({unique_categories}个)，使用柱状图对比",
                    chart_title=self._generate_title(user_query, "对比"),
                    category_field=category_col,
                    y_fields=numeric_cols[:1]
                )
            else:
                return VizRecommendation(
                    recommended=True,
                    chart_type=ChartType.TABLE,
                    reason=f"分类数量过多({unique_categories}个)，建议使用表格",
                    chart_title="查询结果"
                )
        
        # Case 6: 多列数值（可能是对比场景）
        if len(numeric_cols) >= 2 and row_count <= 20:
            return VizRecommendation(
                recommended=True,
                chart_type=ChartType.GROUPED_BAR,
                reason="多个数值指标，使用分组柱状图对比",
                chart_title=self._generate_title(user_query, "多指标对比"),
                y_fields=numeric_cols
            )
        
        # Case 7: 默认使用表格
        return VizRecommendation(
            recommended=True,
            chart_type=ChartType.TABLE,
            reason="数据结构复杂，使用表格展示完整信息",
            chart_title="查询结果"
        )
    
    def _detect_time_columns(
        self, 
        columns: List[str], 
        data: List[Dict]
    ) -> List[str]:
        """检测时间类型的列"""
        time_cols = []
        for col in columns:
            col_lower = col.lower()
            # 名称匹配
            if any(re.search(pattern, col_lower) for pattern in self.TIME_PATTERNS):
                time_cols.append(col)
                continue
            # 值类型检测
            if data:
                sample_value = data[0].get(col)
                if isinstance(sample_value, (datetime,)):
                    time_cols.append(col)
                elif isinstance(sample_value, str):
                    # 尝试解析日期格式
                    if re.match(r'\d{4}[-/]\d{2}[-/]\d{2}', sample_value):
                        time_cols.append(col)
        return time_cols
    
    def _detect_category_columns(
        self, 
        columns: List[str], 
        data: List[Dict]
    ) -> List[str]:
        """检测分类类型的列"""
        category_cols = []
        for col in columns:
            col_lower = col.lower()
            # 名称匹配
            if any(re.search(pattern, col_lower) for pattern in self.CATEGORY_PATTERNS):
                category_cols.append(col)
                continue
            # 值类型检测：字符串且唯一值较少
            if data:
                sample_value = data[0].get(col)
                if isinstance(sample_value, str) and len(data) > 1:
                    unique_count = len(set(row.get(col) for row in data))
                    if unique_count <= len(data) * 0.5:  # 唯一值不超过总数一半
                        category_cols.append(col)
        return category_cols
    
    def _detect_numeric_columns(
        self, 
        columns: List[str], 
        data: List[Dict]
    ) -> List[str]:
        """检测数值类型的列"""
        numeric_cols = []
        for col in columns:
            if data:
                sample_value = data[0].get(col)
                if isinstance(sample_value, (int, float)) and sample_value is not None:
                    # 排除可能是 ID 的列
                    col_lower = col.lower()
                    if not any(id_word in col_lower for id_word in ['id', 'pk', 'key']):
                        numeric_cols.append(col)
        return numeric_cols
    
    def _detect_intent_chart_type(self, user_query: str) -> Optional[str]:
        """从用户查询中检测意图对应的图表类型"""
        query_lower = user_query.lower()
        for chart_type, keywords in self.INTENT_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                return chart_type
        return None
    
    def _generate_title(self, user_query: str, suffix: str = "") -> str:
        """生成图表标题"""
        # 简化用户查询作为标题
        title = user_query[:30] if len(user_query) > 30 else user_query
        # 移除常见的问句词
        for word in ['查询', '查看', '显示', '请', '帮我', '我想', '统计']:
            title = title.replace(word, '')
        title = title.strip()
        if suffix and suffix not in title:
            title = f"{title}{suffix}"
        return title or "数据分析"
    
    def detect_aggregation_need(
        self,
        user_query: str,
        data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        检测是否需要前端聚合
        
        场景：用户问"订单来自哪些地区"，但 SQL 返回的是明细数据而非聚合结果。
        此时需要前端自行聚合，或提示用户数据尚未聚合。
        
        Args:
            user_query: 用户原始查询
            data: SQL 查询结果
            
        Returns:
            Dict 包含:
                - needs_aggregation: bool - 是否需要聚合
                - suggested_group_by: str - 建议的分组字段
                - suggested_agg_func: str - 建议的聚合函数 (count/sum/avg)
                - reason: str - 原因说明
                
        Author: CYJ
        Time: 2025-11-26
        """
        if not data or len(data) <= 1:
            return {"needs_aggregation": False, "reason": "数据量过小，无需聚合"}
        
        # 检查用户查询是否包含聚合意图
        query_lower = user_query.lower()
        has_agg_intent = any(
            re.search(pattern, query_lower) 
            for pattern in self.AGGREGATION_KEYWORDS
        )
        
        if not has_agg_intent:
            return {"needs_aggregation": False, "reason": "未检测到聚合意图"}
        
        # 检查数据是否已经聚合
        columns = list(data[0].keys())
        category_cols = self._detect_category_columns(columns, data)
        
        if not category_cols:
            return {"needs_aggregation": False, "reason": "未检测到可分组的分类字段"}
        
        # 检查是否有重复的分类值（说明未聚合）
        first_cat_col = category_cols[0]
        cat_values = [row.get(first_cat_col) for row in data]
        unique_count = len(set(cat_values))
        
        if unique_count == len(data):
            # 每行都是唯一的，可能已经聚合或是明细数据
            return {
                "needs_aggregation": True,
                "suggested_group_by": first_cat_col,
                "suggested_agg_func": "count",
                "reason": f"用户想看分类统计，建议按 '{first_cat_col}' 分组计数"
            }
        elif unique_count < len(data):
            # 有重复值，可以聚合
            return {
                "needs_aggregation": True,
                "suggested_group_by": first_cat_col,
                "suggested_agg_func": "count",
                "reason": f"检测到 '{first_cat_col}' 字段有 {unique_count} 个唯一值，建议聚合统计"
            }
        
        return {"needs_aggregation": False, "reason": "数据已聚合或不适合聚合"}
    
    def suggest_aggregation(
        self,
        data: List[Dict[str, Any]],
        group_by: str,
        agg_func: str = "count"
    ) -> List[Dict[str, Any]]:
        """
        在 Python 层面执行简单聚合（供前端参考或备用）
        
        Args:
            data: 原始数据
            group_by: 分组字段
            agg_func: 聚合函数 (count/sum/avg)
            
        Returns:
            聚合后的数据列表
            
        Author: CYJ
        Time: 2025-11-26
        """
        from collections import defaultdict
        
        if not data or group_by not in data[0]:
            return data
        
        groups = defaultdict(list)
        for row in data:
            key = row.get(group_by)
            groups[key].append(row)
        
        result = []
        for key, rows in groups.items():
            if agg_func == "count":
                result.append({group_by: key, "count": len(rows)})
            # 可扩展 sum/avg 等
        
        # 按数量降序排列
        result.sort(key=lambda x: x.get("count", 0), reverse=True)
        return result


# 单例
_viz_advisor: Optional[VizAdvisor] = None


def get_viz_advisor() -> VizAdvisor:
    """获取 VizAdvisor 单例"""
    global _viz_advisor
    if _viz_advisor is None:
        _viz_advisor = VizAdvisor()
    return _viz_advisor
