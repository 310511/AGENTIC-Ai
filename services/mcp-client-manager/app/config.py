"""
MCP Client Manager configuration.

MCP_SERVERS is a JSON-encoded list of server definitions, e.g.:
  [{"name":"research","command":"python","args":["-m","mcp_servers.research"]}]

Each entry:
  name    — unique server identifier used in tool calls
  command — executable to launch (stdio transport)
  args    — argument list

SSE (HTTP) servers can be added later via an "url" field instead of command/args.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    mcp_manager_host: str = Field("0.0.0.0")
    mcp_manager_port: int = Field(8004)
    mcp_manager_debug: bool = Field(False)

    # JSON list of {name, command, args[]} or {name, url} server definitions.
    # shortcut: stdio only; add SSE transport when needed.
    mcp_servers: str = Field("[]", description="JSON-encoded MCP server list")

    # Per-tool invocation timeout in seconds.
    tool_timeout: int = Field(30)

    # Global tool allowlist — "*" means allow all (dev default).
    # In production, replace with a per-tenant config store.
    tool_allowlist: str = Field("*", description="Comma-separated allowed tool names or *")

    @field_validator("mcp_servers", mode="before")
    @classmethod
    def validate_json(cls, v: Any) -> str:
        if isinstance(v, list):
            return json.dumps(v)
        json.loads(v)  # raises ValueError if invalid JSON
        return v

    def parsed_servers(self) -> list[dict]:
        return json.loads(self.mcp_servers)

    def allowed_tools(self) -> set[str] | None:
        """Return None for allow-all, or a set of permitted tool names."""
        if self.tool_allowlist.strip() == "*":
            return None
        return {t.strip() for t in self.tool_allowlist.split(",") if t.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
