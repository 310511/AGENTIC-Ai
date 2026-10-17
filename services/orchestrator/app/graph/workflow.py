"""
LangGraph workflow assembly.

Graph shape:
    plan → execute → verify → END
                  ↑           |
                  └── retry ──┘  (when verified=False)

build_workflow() returns a compiled graph. Pass it the LLMGateway at
runtime via functools.partial so nodes stay pure functions.
"""
from __future__ import annotations

import functools

from langgraph.graph import END, StateGraph

from ..llm.gateway import LLMGateway
from .nodes import execute_node, plan_node, verify_node
from .state import TaskState


def _should_retry(state: TaskState) -> str:
    """Conditional edge: loop back to execute or finish."""
    if state.get("error"):
        return END
    if state.get("verified"):
        return END
    return "execute"


def build_workflow(llm: LLMGateway) -> object:
    """
    Compile and return the LangGraph StateGraph.

    The llm gateway is injected via partial so nodes are testable
    without a real LLM.
    """
    graph = StateGraph(TaskState)

    # Bind the LLM gateway into each node.
    graph.add_node("plan",    functools.partial(plan_node,    llm=llm))
    graph.add_node("execute", functools.partial(execute_node, llm=llm))
    graph.add_node("verify",  functools.partial(verify_node,  llm=llm))

    graph.set_entry_point("plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "verify")
    graph.add_conditional_edges("verify", _should_retry, {"execute": "execute", END: END})

    return graph.compile()
