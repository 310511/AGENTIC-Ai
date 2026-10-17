"""
LangGraph state for a single task execution.

All node functions receive and return this dict.
LangGraph merges returned keys back into the state after each node.
"""
from __future__ import annotations

from typing import TypedDict


class TaskState(TypedDict, total=False):
    # Inputs (set before the graph runs)
    task_id: str
    tenant_id: str
    title: str
    description: str

    # Produced by the plan node
    plan: str

    # Produced by the execute node
    result: str

    # Produced by the verify node
    verified: bool
    verify_feedback: str

    # Retry bookkeeping
    retries: int

    # Terminal error message (set on unrecoverable failure)
    error: str
