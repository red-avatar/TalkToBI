"""
功能：数据分析 Agent (Analyzer Agent)
说明：
    对 SQL 查询结果进行智能分析，生成数据洞察和可视化推荐。
    
    主要功能：
    1. 基础统计分析（最大、最小、平均、总和）
    2. 趋势分析（上升、下降、平稳）
    3. 异常检测（突增、突降）
    4. 对比分析（TopN、占比）
    5. 集成 VizEngine 生成可视化

作者：陈怡坚
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging
from decimal import Decimal
from datetime import datetime

from app.modules.viz import VizEngine, VizResult, get_viz_engine

logger = logging.getLogger(__name__)


@dataclass
class DataInsight:
    """数据洞察结果"""
    summary: str                           # 一句话总结
    highlights: List[str] = field(default_factory=list)  # 关键发现（3-5条）
    trend: Optional[str] = None            # 趋势描述（上升/下降/平稳）
    anomalies: List[str] = field(default_factory=list)   # 异常点
    statistics: Optional[Dict] = None      # 统计信息
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {"summary": self.summary}
        if self.highlights:
            result["highlights"] = self.highlights
        if self.trend:
            result["trend"] = self.trend
        if self.anomalies:
            result["anomalies"] = self.anomalies
        if self.statistics:
            result["statistics"] = self.statistics
        return result


@dataclass
class AnalysisResult:
    """完整分析结果"""
    insight: DataInsight                   # 数据洞察
    visualization: VizResult               # 可视化结果
    text_answer: str                       # 文字回答
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "data_insight": self.insight.to_dict(),
            "visualization": self.visualization.to_dict(),
            "text_answer": self.text_answer
        }


class AnalyzerAgent:
    """
    数据分析 Agent
    
    对查询结果进行分析，生成洞察和可视化推荐。
    
    Author: CYJ
    """
    
    def __init__(self):
        self.viz_engine = get_viz_engine()
    
    def analyze(
        self,
        data: List[Dict[str, Any]],
        user_query: str = "",
        intent: Optional[Dict] = None,
        sql_query: Optional[str] = None
    ) -> AnalysisResult:
        """
        分析查询结果
        
        Args:
            data: SQL 查询结果
            user_query: 用户原始查询
            intent: 意图识别结果
            sql_query: 执行的 SQL（可选，用于生成解释）
            
        Returns:
            AnalysisResult: 完整的分析结果
            
        Author: CYJ
        """
        logger.info(f"[AnalyzerAgent] Analyzing {len(data) if data else 0} rows of data")
        
        # 1. 数据预处理
        processed_data = self._preprocess_data(data)
        
        # 2. 生成数据洞察
        insight = self._generate_insight(processed_data, user_query, intent)
        
        # 3. 生成可视化推荐
        viz_result = self.viz_engine.visualize(
            data=processed_data,
            user_query=user_query,
            intent=intent,
            include_raw_data=True
        )
        
        # 4. 生成文字回答
        text_answer = self._generate_text_answer(
            data=processed_data,
            insight=insight,
            user_query=user_query,
            intent=intent
        )
        
        return AnalysisResult(
            insight=insight,
            visualization=viz_result,
            text_answer=text_answer
        )
    
    def _preprocess_data(self, data: List[Dict]) -> List[Dict]:
        """预处理数据，转换特殊类型"""
        if not data:
            return []
        
        processed = []
        for row in data:
            new_row = {}
            for k, v in row.items():
                if isinstance(v, Decimal):
                    new_row[k] = float(v)
                elif isinstance(v, datetime):
                    new_row[k] = v.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    new_row[k] = v
            processed.append(new_row)
        return processed
    
    def _generate_insight(
        self,
        data: List[Dict],
        user_query: str,
        intent: Optional[Dict]
    ) -> DataInsight:
        """
        生成数据洞察
        
        Author: CYJ
        """
        if not data:
            return DataInsight(
                summary="查询结果为空",
                highlights=["没有找到符合条件的数据"]
            )
        
        row_count = len(data)
        columns = list(data[0].keys())
        
        # 检测数值列
        numeric_cols = []
        for col in columns:
            sample = data[0].get(col)
            if isinstance(sample, (int, float)) and sample is not None:
                col_lower = col.lower()
                if not any(id_word in col_lower for id_word in ['id', 'pk', 'key']):
                    numeric_cols.append(col)
        
        highlights = []
        statistics = {}
        trend = None
        
        # 单值结果
        if row_count == 1 and len(columns) == 1:
            value = list(data[0].values())[0]
            col_name = columns[0]
            summary = f"{col_name} 的查询结果为 {self._format_number(value)}"
            return DataInsight(summary=summary, statistics={col_name: value})
        
        # 计算数值列统计
        for col in numeric_cols[:3]:  # 最多分析3个数值列
            values = [row.get(col, 0) for row in data if row.get(col) is not None]
            if values:
                stats = {
                    "min": min(values),
                    "max": max(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values),
                    "count": len(values)
                }
                statistics[col] = stats
                
                # 生成 highlights
                if stats["max"] > 0:
                    # 找出最大值对应的行
                    max_row = max(data, key=lambda x: x.get(col, 0))
                    # 尝试找到分类列
                    category_col = None
                    for c in columns:
                        if c != col and isinstance(data[0].get(c), str):
                            category_col = c
                            break
                    
                    if category_col:
                        max_category = max_row.get(category_col, "")
                        highlights.append(
                            f"最高的 {col} 是 {max_category}，达到 {self._format_number(stats['max'])}"
                        )
                    else:
                        highlights.append(f"{col} 最大值为 {self._format_number(stats['max'])}")
                
                # 趋势分析（如果有多行数据）
                if len(values) >= 3:
                    trend = self._analyze_trend(values)
                    if trend:
                        highlights.append(f"{col} 整体呈{trend}趋势")
        
        # 生成总结
        if numeric_cols and statistics:
            main_col = numeric_cols[0]
            main_stats = statistics[main_col]
            summary = f"共 {row_count} 条数据，{main_col} 总计 {self._format_number(main_stats['sum'])}，平均 {self._format_number(main_stats['avg'])}"
        else:
            summary = f"查询返回 {row_count} 条记录"
        
        return DataInsight(
            summary=summary,
            highlights=highlights[:5],  # 最多5条
            trend=trend,
            statistics=statistics
        )
    
    def _analyze_trend(self, values: List[float]) -> Optional[str]:
        """分析数值趋势"""
        if len(values) < 3:
            return None
        
        # 简单的趋势分析：比较前半段和后半段的平均值
        mid = len(values) // 2
        first_half = sum(values[:mid]) / mid if mid > 0 else 0
        second_half = sum(values[mid:]) / (len(values) - mid) if len(values) > mid else 0
        
        if second_half > first_half * 1.1:  # 增长超过10%
            return "上升"
        elif second_half < first_half * 0.9:  # 下降超过10%
            return "下降"
        else:
            return "平稳"
    
    def _format_number(self, value: Any) -> str:
        """格式化数字"""
        if value is None:
            return "N/A"
        if isinstance(value, float):
            if value >= 100000000:
                return f"{value/100000000:.2f}亿"
            elif value >= 10000:
                return f"{value/10000:.2f}万"
            else:
                return f"{value:,.2f}"
        elif isinstance(value, int):
            if value >= 100000000:
                return f"{value/100000000:.1f}亿"
            elif value >= 10000:
                return f"{value/10000:.1f}万"
            else:
                return f"{value:,}"
        return str(value)
    
    def _generate_text_answer(
        self,
        data: List[Dict],
        insight: DataInsight,
        user_query: str,
        intent: Optional[Dict]
    ) -> str:
        """
        生成文字回答
        
        简单场景直接生成，复杂场景可调用 LLM
        
        Author: CYJ
        """
        if not data:
            return "没有找到符合条件的数据。"
        
        # 单值结果
        if len(data) == 1 and len(data[0]) == 1:
            col = list(data[0].keys())[0]
            value = data[0][col]
            return f"{col} 为 {self._format_number(value)}"
        
        # 多行结果
        answer_parts = [insight.summary]
        
        if insight.highlights:
            answer_parts.append("主要发现：")
            for i, h in enumerate(insight.highlights[:3], 1):
                answer_parts.append(f"{i}. {h}")
        
        return "\n".join(answer_parts)


# 单例
_analyzer_agent: Optional[AnalyzerAgent] = None


def get_analyzer_agent() -> AnalyzerAgent:
    """获取 AnalyzerAgent 单例"""
    global _analyzer_agent
    if _analyzer_agent is None:
        _analyzer_agent = AnalyzerAgent()
    return _analyzer_agent
