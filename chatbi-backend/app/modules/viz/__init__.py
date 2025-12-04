"""
可视化模块 (Visualization Module)

提供智能可视化决策和 ECharts 配置生成能力。

Author: CYJ
Time: 2025-11-26
"""
from app.modules.viz.advisor import (
    ChartType,
    VizAdvisor,
    VizRecommendation,
    get_viz_advisor
)
from app.modules.viz.chart_builder import (
    ChartBuilder,
    get_chart_builder
)
from app.modules.viz.engine import (
    VizEngine,
    VizResult,
    get_viz_engine
)

__all__ = [
    'ChartType',
    'VizAdvisor',
    'VizRecommendation',
    'get_viz_advisor',
    'ChartBuilder',
    'get_chart_builder',
    'VizEngine',
    'VizResult',
    'get_viz_engine'
]
