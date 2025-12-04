"""
功能：可视化引擎 (Visualization Engine)
说明：
    整合 VizAdvisor（决策）和 ChartBuilder（构建），提供统一的可视化接口。
    
    主要功能：
    1. 分析数据结构，推荐图表类型
    2. 生成 ECharts 配置
    3. 构建完整的可视化响应

作者：陈怡坚
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging

from app.modules.viz.advisor import (
    VizAdvisor, 
    VizRecommendation, 
    ChartType,
    get_viz_advisor
)
from app.modules.viz.chart_builder import ChartBuilder, get_chart_builder

logger = logging.getLogger(__name__)


@dataclass
class VizResult:
    """可视化结果"""
    recommended: bool                          # 是否推荐可视化
    chart_type: str                            # 图表类型
    reason: str                                # 推荐原因
    chart_title: Optional[str] = None          # 图表标题
    echarts_option: Optional[Dict] = None      # ECharts 配置（图表类型）
    table_config: Optional[Dict] = None        # 表格配置（TABLE 类型）
    single_value: Optional[Dict] = None        # 单值配置（SINGLE_VALUE 类型）
    raw_data: Optional[List[Dict]] = None      # 原始数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "recommended": self.recommended,
            "chart_type": self.chart_type,
            "reason": self.reason
        }
        if self.chart_title:
            result["chart_title"] = self.chart_title
        if self.echarts_option:
            result["echarts_option"] = self.echarts_option
        if self.table_config:
            result["table_config"] = self.table_config
        if self.single_value:
            result["single_value"] = self.single_value
        if self.raw_data:
            result["raw_data"] = self.raw_data
        return result


class VizEngine:
    """
    可视化引擎
    
    提供端到端的可视化能力：数据 -> 推荐 -> ECharts配置
    
    Author: CYJ
    """
    
    def __init__(self):
        self.advisor = get_viz_advisor()
        self.builder = get_chart_builder()
    
    def visualize(
        self,
        data: List[Dict[str, Any]],
        user_query: str = "",
        intent: Optional[Dict] = None,
        include_raw_data: bool = True
    ) -> VizResult:
        """
        对数据进行可视化处理
        
        Args:
            data: SQL 查询结果
            user_query: 用户原始查询
            intent: 意图识别结果
            include_raw_data: 是否在结果中包含原始数据
            
        Returns:
            VizResult: 完整的可视化结果
            
        Author: CYJ
        """
        logger.info(f"[VizEngine] Processing data with {len(data) if data else 0} rows")
        
        # 1. 获取可视化推荐
        recommendation = self.advisor.recommend(
            data=data,
            user_query=user_query,
            intent=intent
        )
        
        logger.info(f"[VizEngine] Recommendation: {recommendation.chart_type.value}, reason: {recommendation.reason}")
        
        # 2. 如果不推荐可视化，直接返回
        if not recommendation.recommended:
            return VizResult(
                recommended=False,
                chart_type=ChartType.NO_VIZ.value,
                reason=recommendation.reason
            )
        
        # 3. 构建图表配置
        chart_config = self.builder.build(data, recommendation)
        
        # 4. 根据图表类型构建结果
        chart_type = recommendation.chart_type
        
        if chart_type == ChartType.TABLE:
            return VizResult(
                recommended=True,
                chart_type=chart_type.value,
                reason=recommendation.reason,
                chart_title=recommendation.chart_title,
                table_config=chart_config,
                raw_data=data if include_raw_data else None
            )
        
        elif chart_type == ChartType.SINGLE_VALUE:
            return VizResult(
                recommended=True,
                chart_type=chart_type.value,
                reason=recommendation.reason,
                chart_title=recommendation.chart_title,
                single_value=chart_config,
                raw_data=data if include_raw_data else None
            )
        
        else:
            # 折线图、柱状图、饼图等 ECharts 图表
            return VizResult(
                recommended=True,
                chart_type=chart_type.value,
                reason=recommendation.reason,
                chart_title=recommendation.chart_title,
                echarts_option=chart_config,
                raw_data=data if include_raw_data else None
            )
    
    def get_chart_type_description(self, chart_type: str) -> str:
        """获取图表类型的中文描述"""
        descriptions = {
            "no_viz": "无需可视化",
            "single_value": "数字卡片",
            "line": "折线图",
            "multi_line": "多折线图",
            "bar": "柱状图",
            "horizontal_bar": "横向柱状图",
            "grouped_bar": "分组柱状图",
            "pie": "饼图",
            "table": "数据表格",
            "scatter": "散点图"
        }
        return descriptions.get(chart_type, chart_type)


# 单例
_viz_engine: Optional[VizEngine] = None


def get_viz_engine() -> VizEngine:
    """获取 VizEngine 单例"""
    global _viz_engine
    if _viz_engine is None:
        _viz_engine = VizEngine()
    return _viz_engine
