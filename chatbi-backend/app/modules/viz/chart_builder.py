"""
功能：ECharts 图表配置生成器 (Chart Builder)
说明：
    根据 VizAdvisor 的推荐和数据，生成 ECharts 5.x 配置对象。
    支持折线图、柱状图、饼图、表格等常用图表类型。

作者：陈怡坚
"""
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, date
import logging

from app.modules.viz.advisor import ChartType, VizRecommendation

logger = logging.getLogger(__name__)


class ChartBuilder:
    """
    ECharts 图表配置生成器
    
    将原始数据 + 可视化推荐 转换为 ECharts option 配置。
    
    Author: CYJ
    """
    
    # 图表颜色方案
    COLOR_PALETTE = [
        '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
        '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#48b8d0'
    ]
    
    def build(
        self,
        data: List[Dict[str, Any]],
        recommendation: VizRecommendation
    ) -> Optional[Dict[str, Any]]:
        """
        根据推荐构建 ECharts 配置
        
        Args:
            data: SQL 查询结果
            recommendation: 可视化推荐结果
            
        Returns:
            ECharts option 配置字典，如果不需要可视化返回 None
            
        Author: CYJ
        Time: 2025-11-26
        """
        if not recommendation.recommended:
            return None
        
        chart_type = recommendation.chart_type
        
        # 数据预处理：转换 Decimal/datetime 等特殊类型
        data = self._preprocess_data(data)
        
        builders = {
            ChartType.LINE: self._build_line_chart,
            ChartType.MULTI_LINE: self._build_multi_line_chart,
            ChartType.BAR: self._build_bar_chart,
            ChartType.HORIZONTAL_BAR: self._build_horizontal_bar_chart,
            ChartType.GROUPED_BAR: self._build_grouped_bar_chart,
            ChartType.PIE: self._build_pie_chart,
            ChartType.SINGLE_VALUE: self._build_single_value,
            ChartType.TABLE: self._build_table,
        }
        
        builder = builders.get(chart_type)
        if builder:
            try:
                return builder(data, recommendation)
            except Exception as e:
                logger.error(f"[ChartBuilder] Failed to build {chart_type}: {e}")
                return self._build_table(data, recommendation)
        
        return None
    
    def _preprocess_data(self, data: List[Dict]) -> List[Dict]:
        """预处理数据，转换特殊类型"""
        processed = []
        for row in data:
            new_row = {}
            for k, v in row.items():
                if isinstance(v, Decimal):
                    new_row[k] = float(v)
                elif isinstance(v, (datetime, date)):
                    new_row[k] = v.strftime('%Y-%m-%d') if isinstance(v, date) else v.strftime('%Y-%m-%d %H:%M')
                else:
                    new_row[k] = v
            processed.append(new_row)
        return processed
    
    def _build_line_chart(
        self, 
        data: List[Dict], 
        rec: VizRecommendation
    ) -> Dict[str, Any]:
        """构建折线图配置"""
        x_field = rec.x_field or list(data[0].keys())[0]
        y_field = rec.y_fields[0] if rec.y_fields else list(data[0].keys())[1]
        
        x_data = [row.get(x_field, '') for row in data]
        y_data = [row.get(y_field, 0) for row in data]
        
        return {
            "title": {
                "text": rec.chart_title or "趋势图",
                "left": "center"
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "cross"}
            },
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "3%",
                "containLabel": True
            },
            "xAxis": {
                "type": "category",
                "data": x_data,
                "axisLabel": {"rotate": 45 if len(x_data) > 10 else 0}
            },
            "yAxis": {
                "type": "value",
                "name": y_field
            },
            "series": [{
                "name": y_field,
                "type": "line",
                "data": y_data,
                "smooth": True,
                "areaStyle": {"opacity": 0.3},
                "itemStyle": {"color": self.COLOR_PALETTE[0]}
            }]
        }
    
    def _build_multi_line_chart(
        self, 
        data: List[Dict], 
        rec: VizRecommendation
    ) -> Dict[str, Any]:
        """构建多折线图配置"""
        x_field = rec.x_field or list(data[0].keys())[0]
        y_fields = rec.y_fields or [k for k in data[0].keys() if k != x_field][:5]
        
        x_data = [row.get(x_field, '') for row in data]
        
        series = []
        for i, y_field in enumerate(y_fields):
            series.append({
                "name": y_field,
                "type": "line",
                "data": [row.get(y_field, 0) for row in data],
                "smooth": True,
                "itemStyle": {"color": self.COLOR_PALETTE[i % len(self.COLOR_PALETTE)]}
            })
        
        return {
            "title": {
                "text": rec.chart_title or "多指标趋势",
                "left": "center"
            },
            "tooltip": {
                "trigger": "axis"
            },
            "legend": {
                "data": y_fields,
                "bottom": 0
            },
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "10%",
                "containLabel": True
            },
            "xAxis": {
                "type": "category",
                "data": x_data,
                "axisLabel": {"rotate": 45 if len(x_data) > 10 else 0}
            },
            "yAxis": {
                "type": "value"
            },
            "series": series
        }
    
    def _build_bar_chart(
        self, 
        data: List[Dict], 
        rec: VizRecommendation
    ) -> Dict[str, Any]:
        """构建纵向柱状图配置"""
        category_field = rec.category_field or list(data[0].keys())[0]
        value_field = rec.y_fields[0] if rec.y_fields else list(data[0].keys())[1]
        
        categories = [str(row.get(category_field, '')) for row in data]
        values = [row.get(value_field, 0) for row in data]
        
        return {
            "title": {
                "text": rec.chart_title or "对比图",
                "left": "center"
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"}
            },
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "3%",
                "containLabel": True
            },
            "xAxis": {
                "type": "category",
                "data": categories,
                "axisLabel": {"rotate": 45 if len(categories) > 8 else 0}
            },
            "yAxis": {
                "type": "value",
                "name": value_field
            },
            "series": [{
                "name": value_field,
                "type": "bar",
                "data": values,
                "itemStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": self.COLOR_PALETTE[0]},
                            {"offset": 1, "color": self.COLOR_PALETTE[4]}
                        ]
                    }
                },
                "label": {
                    "show": len(data) <= 10,
                    "position": "top"
                }
            }]
        }
    
    def _build_horizontal_bar_chart(
        self, 
        data: List[Dict], 
        rec: VizRecommendation
    ) -> Dict[str, Any]:
        """构建横向柱状图配置（适合长标签）"""
        category_field = rec.category_field or list(data[0].keys())[0]
        value_field = rec.y_fields[0] if rec.y_fields else list(data[0].keys())[1]
        
        # 按数值排序
        sorted_data = sorted(data, key=lambda x: x.get(value_field, 0), reverse=True)
        
        categories = [str(row.get(category_field, '')) for row in sorted_data]
        values = [row.get(value_field, 0) for row in sorted_data]
        
        return {
            "title": {
                "text": rec.chart_title or "排名对比",
                "left": "center"
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"}
            },
            "grid": {
                "left": "3%",
                "right": "10%",
                "bottom": "3%",
                "containLabel": True
            },
            "xAxis": {
                "type": "value",
                "name": value_field
            },
            "yAxis": {
                "type": "category",
                "data": categories,
                "inverse": True  # 从上到下排列
            },
            "series": [{
                "name": value_field,
                "type": "bar",
                "data": values,
                "itemStyle": {"color": self.COLOR_PALETTE[0]},
                "label": {
                    "show": True,
                    "position": "right"
                }
            }]
        }
    
    def _build_grouped_bar_chart(
        self, 
        data: List[Dict], 
        rec: VizRecommendation
    ) -> Dict[str, Any]:
        """构建分组柱状图配置"""
        columns = list(data[0].keys())
        # 假设第一列为分类，其余为数值
        category_field = columns[0]
        value_fields = rec.y_fields or columns[1:]
        
        categories = [str(row.get(category_field, '')) for row in data]
        
        series = []
        for i, field in enumerate(value_fields):
            series.append({
                "name": field,
                "type": "bar",
                "data": [row.get(field, 0) for row in data],
                "itemStyle": {"color": self.COLOR_PALETTE[i % len(self.COLOR_PALETTE)]}
            })
        
        return {
            "title": {
                "text": rec.chart_title or "分组对比",
                "left": "center"
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"}
            },
            "legend": {
                "data": value_fields,
                "bottom": 0
            },
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "10%",
                "containLabel": True
            },
            "xAxis": {
                "type": "category",
                "data": categories
            },
            "yAxis": {
                "type": "value"
            },
            "series": series
        }
    
    def _build_pie_chart(
        self, 
        data: List[Dict], 
        rec: VizRecommendation
    ) -> Dict[str, Any]:
        """构建饼图配置"""
        category_field = rec.category_field or list(data[0].keys())[0]
        value_field = rec.y_fields[0] if rec.y_fields else list(data[0].keys())[1]
        
        pie_data = [
            {"name": str(row.get(category_field, '')), "value": row.get(value_field, 0)}
            for row in data
        ]
        
        # 按值排序
        pie_data.sort(key=lambda x: x['value'], reverse=True)
        
        return {
            "title": {
                "text": rec.chart_title or "占比分布",
                "left": "center"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c} ({d}%)"
            },
            "legend": {
                "orient": "vertical",
                "left": "left",
                "top": "middle"
            },
            "series": [{
                "name": value_field,
                "type": "pie",
                "radius": ["40%", "70%"],
                "center": ["60%", "50%"],
                "avoidLabelOverlap": True,
                "itemStyle": {
                    "borderRadius": 10,
                    "borderColor": "#fff",
                    "borderWidth": 2
                },
                "label": {
                    "show": True,
                    "formatter": "{b}: {d}%"
                },
                "emphasis": {
                    "label": {
                        "show": True,
                        "fontSize": 16,
                        "fontWeight": "bold"
                    }
                },
                "data": pie_data
            }],
            "color": self.COLOR_PALETTE
        }
    
    def _build_single_value(
        self, 
        data: List[Dict], 
        rec: VizRecommendation
    ) -> Dict[str, Any]:
        """构建单值大数字卡片配置"""
        value = list(data[0].values())[0] if data else 0
        field_name = list(data[0].keys())[0] if data else "值"
        
        # 格式化数值
        if isinstance(value, float):
            if value >= 10000:
                formatted = f"{value/10000:.2f}万"
            else:
                formatted = f"{value:,.2f}"
        elif isinstance(value, int):
            if value >= 10000:
                formatted = f"{value/10000:.1f}万"
            else:
                formatted = f"{value:,}"
        else:
            formatted = str(value)
        
        return {
            "type": "single_value",
            "title": rec.chart_title or field_name,
            "value": value,
            "formatted_value": formatted,
            "field_name": field_name
        }
    
    def _build_table(
        self, 
        data: List[Dict], 
        rec: VizRecommendation
    ) -> Dict[str, Any]:
        """构建表格配置"""
        if not data:
            return {"type": "table", "columns": [], "data": []}
        
        columns = [
            {"title": col, "dataIndex": col, "key": col}
            for col in data[0].keys()
        ]
        
        # 添加序号
        table_data = []
        for i, row in enumerate(data):
            table_data.append({"_index": i + 1, **row})
        
        columns.insert(0, {"title": "#", "dataIndex": "_index", "key": "_index", "width": 60})
        
        return {
            "type": "table",
            "title": rec.chart_title or "查询结果",
            "columns": columns,
            "data": table_data,
            "pagination": len(data) > 20
        }


# 单例
_chart_builder: Optional[ChartBuilder] = None


def get_chart_builder() -> ChartBuilder:
    """获取 ChartBuilder 单例"""
    global _chart_builder
    if _chart_builder is None:
        _chart_builder = ChartBuilder()
    return _chart_builder
