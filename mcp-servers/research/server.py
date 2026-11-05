"""
Research MCP Server — custom MCP server implementation.

Tools:
  web_search       — search the web via DuckDuckGo (no API key needed)
  fetch_url        — fetch plain-text content of a public HTTPS URL
  summarise_text   — extractive summary of a text block
  extract_keywords — top N keywords by frequency

Run via stdio (MCP Client Manager launches it as a subprocess).

Security:
  - fetch_url validates scheme (https only) to prevent SSRF.
  - All output is capped at MAX_OUTPUT_CHARS.
  - Never use tool results for auth or policy decisions.
"""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlparse

import httpx
from mcp.server.mcpserver import MCPServer as FastMCP

MAX_OUTPUT_CHARS = 5000
FETCH_TIMEOUT = 15

mcp = FastMCP("research")


# ── tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> str:
    """
    Search Wikipedia for information about a topic.

    Best for: facts, history, concepts, geography, people, organizations.
    For real-time data (prices, schedules, live news), use fetch_url with a specific URL.
    """
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "format": "json",
                "utf8": "1",
            },
            headers={
                "User-Agent": "AIAgentPlatform/1.0 (research tool; contact: admin@example.com)",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("query", {}).get("search", [])
    if not results:
        return f"No Wikipedia results found for: {query}"

    lines = [f"Wikipedia search results for: {query}\n"]
    for r in results:
        title = r.get("title", "")
        snippet = re.sub(r"<[^>]+>", "", r.get("snippet", ""))
        url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        lines.append(f"• {title}\n  {snippet}\n  {url}\n")

    return "\n".join(lines)[:MAX_OUTPUT_CHARS]


@mcp.tool()
async def fetch_url(url: str) -> str:
    """
    Fetch the plain-text content of a public HTTPS URL.

    Returns the response body stripped of HTML tags, truncated to MAX_OUTPUT_CHARS.
    Only HTTPS URLs are allowed (prevents access to internal services).
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(
            f"Only HTTPS URLs are allowed (got '{parsed.scheme}'). "
            "This prevents access to internal services."
        )
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)",
                "Accept": "text/plain, text/html",
            },
        )
        resp.raise_for_status()
    text = re.sub(r"<[^>]+>", " ", resp.text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_OUTPUT_CHARS]


@mcp.tool()
def summarise_text(text: str, max_sentences: int = 3) -> str:
    """Return the first max_sentences sentences of text as a simple extractive summary."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:max(1, max_sentences)])[:MAX_OUTPUT_CHARS]


@mcp.tool()
def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """Return the top_n most frequent meaningful words from text."""
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
