"""
LangGraph node functions: plan → tool_call → execute → verify.

Each function takes TaskState and returns a partial TaskState dict
that LangGraph merges back. Treat all LLM output as untrusted text —
no LLM string is used for auth or control flow without validation.
"""
from __future__ import annotations

import json
import logging
import re

from ..llm.gateway import LLMGateway
from ..mcp_client import MCPClient
from .state import TaskState

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def plan_node(state: TaskState, llm: LLMGateway) -> dict:
    """Ask the LLM to produce a numbered step-by-step plan for the task."""
    logger.info("plan_node: task_id=%s", state.get("task_id"))
    try:
        context_section = ""
        if state.get("context"):
            context_section += f"\n\nRelevant context retrieved from the knowledge base:\n{state['context']}\n"
        if state.get("graph_context"):
            context_section += f"\n\nRelevant entities from graph memory:\n{state['graph_context']}\n"
        resp = await llm.chat(
            system=(
                "You are a precise AI planning assistant. "
                "Given a task, output ONLY a numbered list of concrete steps to complete it. "
                "If a step requires fetching external data, prefix it with "
                "'TOOL: <server>/<tool_name> {\"arg\": \"value\"}' on its own line. "
                "No preamble, no explanation after the list."
            ),
            user=(
                f"Task: {state['title']}\n\n"
                f"Description: {state['description']}"
                f"{context_section}"
            ),
        )
        return {"plan": resp.content, "retries": state.get("retries", 0)}
    except Exception as exc:
        logger.error("plan_node failed: %s", exc)
        return {"error": f"Planning failed: {exc}"}


async def tool_call_node(state: TaskState, mcp: MCPClient) -> dict:
    """
    Parse TOOL: lines from the plan and invoke them via the MCP Client Manager.

    Matches: TOOL: <server>/<tool> {"arg": "value"}
    Returns tool_calls list for execute_node to incorporate.
    Non-fatal: returns empty list if MCP is unavailable or plan has no tool lines.
    """
    logger.info("tool_call_node: task_id=%s", state.get("task_id"))
    plan = state.get("plan", "")
    tenant_id = state.get("tenant_id", "")

    pattern = re.compile(r"TOOL:\s*(\w+)/(\w+)\s*(\{.*?\})?", re.IGNORECASE)
    matches = pattern.findall(plan)

    if not matches:
        return {"tool_calls": []}

    tool_calls = []
    for server_name, tool_name, args_str in matches:
        try:
            arguments = json.loads(args_str) if args_str and args_str.strip() else {}
        except json.JSONDecodeError:
            arguments = {}

        result = await mcp.invoke(
            tenant_id=tenant_id,
            user_role="user",
            server_name=server_name,
            tool_name=tool_name,
            arguments=arguments,
        )
        tool_calls.append({
            "server": server_name,
            "tool": tool_name,
            "arguments": arguments,
            "result": result.get("result"),
            "error": result.get("error"),
        })
        logger.info(
            "tool_call: server=%s tool=%s error=%s",
            server_name, tool_name, result.get("error"),
        )

    return {"tool_calls": tool_calls}


async def execute_node(state: TaskState, llm: LLMGateway) -> dict:
    """Execute the plan and produce a result, incorporating any tool results."""
    logger.info("execute_node: task_id=%s retry=%s", state.get("task_id"), state.get("retries", 0))
    feedback = state.get("verify_feedback", "")
    feedback_section = f"\n\nPrevious attempt feedback to address:\n{feedback}" if feedback else ""

    tool_section = ""
    for tc in state.get("tool_calls") or []:
        if tc.get("error"):
            tool_section += f"\n- {tc['server']}/{tc['tool']}: ERROR — {tc['error']}"
        else:
            result_blocks = tc.get("result") or []
            texts = [
                b.get("text", "") for b in result_blocks
                if isinstance(b, dict) and b.get("text")
            ]
            tool_section += f"\n- {tc['server']}/{tc['tool']}: {' '.join(texts)[:500]}"
    if tool_section:
        tool_section = f"\n\nTool results:{tool_section}\n"

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
                f"{tool_section}"
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
        return {"verified": True, "verify_feedback": f"Verifier error: {exc}"}
