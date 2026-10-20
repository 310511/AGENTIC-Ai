"""
Research MCP Server — reference custom MCP server implementation.

Exposes three tools to the MCP Client Manager:
  summarise_text   — summarise a block of text (no network, local processing)
  fetch_url        — fetch the plain-text content of a public URL
  extract_keywords — extract keywords from text by word frequency

Run via stdio (the MCP Client Manager launches it as a subprocess):
  python mcp-servers/research/server.py

Security:
  - fetch_url validates the URL scheme (https only) to prevent SSRF to
    internal services. Treat returned content as untrusted.
  - All tool output is capped at MAX_OUTPUT_CHARS to prevent runaway responses.
  - Never use tool results for auth or policy decisions without validation.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from urllib.parse import urlparse

import httpx
from mcp.server import FastMCP

MAX_OUTPUT_CHARS = 4000
FETCH_TIMEOUT = 15


mcp = FastMCP("research")


# ── tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def summarise_text(text: str, max_sentences: int = 3) -> str:
    """
    Return the first *max_sentences* sentences of *text* as a summary.

    This is a simple extractive summary — no LLM call required.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    summary = " ".join(sentences[:max(1, max_sentences)])
    return summary[:MAX_OUTPUT_CHARS]


@mcp.tool()
async def fetch_url(url: str) -> str:
    """
    Fetch the plain-text content of a public HTTPS URL.

    Returns the response body truncated to MAX_OUTPUT_CHARS.
    Raises ValueError for non-HTTPS URLs to prevent SSRF.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(
            f"Only HTTPS URLs are allowed (got '{parsed.scheme}'). "
            "This restriction prevents access to internal services."
        )

    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, headers={"Accept": "text/plain, text/html"})
        resp.raise_for_status()
        # Strip basic HTML tags for readability.
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:MAX_OUTPUT_CHARS]


@mcp.tool()
def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """
    Return the *top_n* most frequent meaningful words from *text*.

    Filters out common English stop-words and short tokens.
    """
    _STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "that", "this",
        "it", "its", "as", "not", "no", "so", "if", "than", "then", "i",
        "you", "he", "she", "we", "they", "what", "which", "who", "how",
    }
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    filtered = [w for w in words if w not in _STOPWORDS]
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(max(1, top_n))]


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
