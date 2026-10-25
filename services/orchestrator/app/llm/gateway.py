"""
LLM Gateway — provider-neutral interface backed by Ollama.

All LLM calls go through here so the orchestrator never knows which
provider is underneath. To swap providers, change this file only.

Security: treat every string returned by the LLM as untrusted input.
Never use LLM output to bypass auth or policy checks.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from ..config import Settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMGateway:
    """Calls Ollama /api/chat and returns a normalised LLMResponse."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.default_llm_model
        self._timeout = settings.llm_timeout

    async def chat(self, system: str, user: str) -> LLMResponse:
        """
        Send a system + user message pair and return the assistant reply.

        Raises httpx.HTTPError on network/server failure — callers should
        catch and handle retries at the graph level.
        """
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()

        data = resp.json()
        content = data["message"]["content"]
        usage = data.get("usage", {})

        logger.debug("LLM response: model=%s tokens=%s", self._model, usage)
        return LLMResponse(
            content=content,
            model=self._model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
