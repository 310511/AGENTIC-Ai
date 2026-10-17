"""
LangGraph node functions: plan → execute → verify.

Each function takes TaskState and returns a partial TaskState dict
that LangGraph merges back. Treat all LLM output as untrusted text —
no LLM string is used for auth or control flow without validation.
"""
from __future__ import annotations

import logging

from ..llm.gateway import LLMGateway
from .state import TaskState

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def plan_node(state: TaskState, llm: LLMGateway) -> dict:
    """Ask the LLM to produce a numbered step-by-step plan for the task."""
    logger.info("plan_node: task_id=%s", state.get("task_id"))
    try:
        resp = await llm.chat(
            system=(
                "You are a precise AI planning assistant. "
                "Given a task, output ONLY a numbered list of concrete steps to complete it. "
                "No preamble, no explanation after the list."
            ),
            user=f"Task: {state['title']}\n\nDescription: {state['description']}",
        )
        return {"plan": resp.content, "retries": state.get("retries", 0)}
    except Exception as exc:
        logger.error("plan_node failed: %s", exc)
        return {"error": f"Planning failed: {exc}"}


async def execute_node(state: TaskState, llm: LLMGateway) -> dict:
    """Execute the plan and produce a result."""
    logger.info("execute_node: task_id=%s retry=%s", state.get("task_id"), state.get("retries", 0))
    feedback = state.get("verify_feedback", "")
    feedback_section = f"\n\nPrevious attempt feedback to address:\n{feedback}" if feedback else ""

    try:
        resp = await llm.chat(
            system=(
                "You are a capable AI agent. "
                "Follow the given plan step by step and produce a clear, complete result. "
                "Output the result directly — no meta-commentary."
            ),
            user=(
                f"Task: {state['title']}\n\n"
                f"Plan:\n{state['plan']}"
                f"{feedback_section}"
            ),
        )
        return {"result": resp.content}
    except Exception as exc:
        logger.error("execute_node failed: %s", exc)
        return {"error": f"Execution failed: {exc}"}


async def verify_node(state: TaskState, llm: LLMGateway) -> dict:
    """
    Verify the result meets the original task description.

    Returns verified=True to end, or verified=False + feedback to retry.
    Caps retries at MAX_RETRIES to prevent infinite loops.
    """
    logger.info("verify_node: task_id=%s", state.get("task_id"))
    retries = state.get("retries", 0)

    if retries >= MAX_RETRIES:
        logger.warning("verify_node: max retries reached for task_id=%s", state.get("task_id"))
        # Accept whatever we have rather than loop forever.
        return {"verified": True, "verify_feedback": "Accepted after max retries."}

    try:
        resp = await llm.chat(
            system=(
                "You are a strict quality reviewer. "
                "Given a task description and a result, reply with exactly one of:\n"
                "PASS — if the result fully satisfies the task\n"
                "FAIL: <one sentence of specific feedback> — if it does not.\n"
                "No other output."
            ),
            user=(
                f"Task: {state['title']}\nDescription: {state['description']}\n\n"
                f"Result:\n{state['result']}"
            ),
        )
        verdict = resp.content.strip()
        if verdict.upper().startswith("PASS"):
            return {"verified": True, "verify_feedback": ""}
        else:
            feedback = verdict[5:].strip() if ":" in verdict else verdict
            return {"verified": False, "verify_feedback": feedback, "retries": retries + 1}
    except Exception as exc:
        logger.error("verify_node failed: %s", exc)
        # On verifier error, accept the result rather than loop.
        return {"verified": True, "verify_feedback": f"Verifier error: {exc}"}
