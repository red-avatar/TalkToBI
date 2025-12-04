"""
Orchestrator 图构建模块

构建 LangGraph StateGraph 工作流，组装节点和路由。

Author: CYJ
Time: 2025-12-03 (从 orchestrator.py 重构)
"""
from langgraph.graph import StateGraph, END

from app.core.state import AgentState
from app.modules.dialog.memory import get_memory_checkpointer

from .nodes import (
    cache_check_node,
    intent_node,
    planner_node,
    executor_node,
    analyzer_node,
    responder_node,
    diagnoser_node,
    schema_completer_node
)
from .routes import (
    route_after_cache_check,
    route_after_intent,
    route_after_planner,
    route_after_executor,
    route_after_diagnosis
)

def build_graph():
    """
    构建对话编排工作流
    
    工作流结构:
    Start -> CacheCheck -> (Hit?) -> Executor -> Analyzer -> Responder -> End
                       -> Intent -> (Query?) -> Planner -> Executor -> ...
                                 -> Responder -> End
    
    Author: CYJ
    Time: 2025-11-22 (重构: 2025-12-03)
    """
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("cache_check_node", cache_check_node)
    workflow.add_node("intent_node", intent_node)
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("executor_node", executor_node)
    workflow.add_node("analyzer_node", analyzer_node)
    workflow.add_node("responder_node", responder_node)
    workflow.add_node("diagnoser_node", diagnoser_node)
    workflow.add_node("schema_completer_node", schema_completer_node)
    
    # 设置入口点
    workflow.set_entry_point("cache_check_node")
    
    # 添加条件边
    workflow.add_conditional_edges(
        "cache_check_node",
        route_after_cache_check,
        {
            "executor_node": "executor_node",
            "intent_node": "intent_node"
        }
    )
    
    workflow.add_conditional_edges(
        "intent_node",
        route_after_intent,
        {
            "planner_node": "planner_node",
            "responder_node": "responder_node"
        }
    )
    
    workflow.add_conditional_edges(
        "planner_node",
        route_after_planner,
        {
            "executor_node": "executor_node",
            "diagnoser_node": "diagnoser_node",
            "responder_node": "responder_node"
        }
    )
    
    workflow.add_conditional_edges(
        "executor_node",
        route_after_executor,
        {
            "planner_node": "planner_node",
            "diagnoser_node": "diagnoser_node",
            "analyzer_node": "analyzer_node",
            "responder_node": "responder_node"
        }
    )
    
    # 分析器 -> 响应器
    workflow.add_edge("analyzer_node", "responder_node")
    
    workflow.add_conditional_edges(
        "diagnoser_node",
        route_after_diagnosis,
        {
            "schema_completer_node": "schema_completer_node",
            "planner_node": "planner_node",
            "responder_node": "responder_node"
        }
    )
    
    # Schema补全器 -> 规划器
    workflow.add_edge("schema_completer_node", "planner_node")
    
    # 结束节点
    workflow.add_edge("responder_node", END)
    
    # 编译工作流（带记忆检查点）
    checkpointer = get_memory_checkpointer()
    app = workflow.compile(checkpointer=checkpointer)
    return app


# 单例应用
orchestrator_app = build_graph()
