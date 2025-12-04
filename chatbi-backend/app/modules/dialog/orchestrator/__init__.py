"""
对话编排器模块 (Dialog Orchestrator)

使用 LangGraph 构建多 Agent 协同的工作流

模块结构:
- graph.py: 工作流图构建与 orchestrator_app 单例
- nodes.py: 所有节点函数
- routes.py: 所有路由决策函数
- helpers.py: 辅助函数

使用方式:
    from app.modules.dialog.orchestrator import orchestrator_app
    result = orchestrator_app.invoke(state, config)

Author: CYJ
Time: 2025-12-03 (重构自 orchestrator.py)
"""
from .graph import orchestrator_app, build_graph

__all__ = ["orchestrator_app", "build_graph"]
