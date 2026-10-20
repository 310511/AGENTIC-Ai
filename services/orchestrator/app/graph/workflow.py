"""
LangGraph workflow assembly.

Graph shape:
    plan → tool_call → execute → verify → END
                                    |
                                    └── retry → execute (when verified=False)

build_workflow() returns a compiled graph. Pass LLMGateway and MCPClient
at runtime via functools.partial so nodes stay pure functions.
"""
from __future__ import annotations

import functools

from langgraph.graph import END, StateGraph

from ..llm.gateway import LLMGateway
from ..mcp_client import MCPClient
from .nodes import execute_node, plan_node, tool_call_node, verify_node
from .state import TaskState


def _should_retry(state: TaskState) -> str:
    """Conditional edge: loop back to execute or finish."""
    if state.get("error"):
        return END
    if state.get("verified"):
        return END
    return "execute"


def build_workflow(llm: LLMGateway, mcp: MCPClient) -> object:
    """
    Compile and return the LangGraph StateGraph.

    Both llm and mcp are injected via partial so nodes are testable
    without real backends.
    """
    graph = StateGraph(TaskState)

    graph.add_node("plan",      functools.partial(plan_node,      llm=llm))
    graph.add_node("tool_call", functools.partial(tool_call_node, mcp=mcp))
    graph.add_node("execute",   functools.partial(execute_node,   llm=llm))
    graph.add_node("verify",    functools.partial(verify_node,    llm=llm))

    graph.set_entry_point("plan")
    graph.add_edge("plan",      "tool_call")
    graph.add_edge("tool_call", "execute")
    graph.add_edge("execute",   "verify")
    graph.add_conditional_edges(
        "verify", _should_retry, {"execute": "execute", END: END}
    )

    return graph.compile()
