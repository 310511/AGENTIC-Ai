# MCP Client Manager

**Status:** Placeholder — Phase 5

## Responsibility

Connects to both third-party and custom MCP servers using the **official MCP
Python SDK**. Discovers available tools, validates invocation requests against
allowlists and policy, invokes tools, and returns normalised results to the
Orchestrator.

## Planned components

```
mcp-client-manager/
├── app/
│   ├── main.py                  # Internal FastAPI app
│   ├── config.py
│   ├── client/
│   │   ├── manager.py           # Server discovery, connection pooling
│   │   └── invoker.py           # Tool invocation with timeout + retries
│   ├── policy/
│   │   └── allowlist.py         # Per-user/per-tenant tool allowlists
│   └── audit.py                 # Tool invocation audit log
├── requirements.txt
└── Dockerfile
```

## Key design rules (from context.md)

- Use the official MCP Python SDK (`mcp`).
- Treat MCP tool descriptions and results as **untrusted data**.
- Tool availability does not imply permission to invoke — always check
  the Policy Service before every tool call.
- Enforce allowlists, per-user/per-tenant permissions, timeouts, argument
  validation, output limits, and audit logging.
- Require explicit human approval for high-impact or irreversible actions.
- Keep MCP server credentials in server-side secret management, never in
  the frontend or logs.

## Phase 5 dependencies

- `mcp` (official MCP Python SDK)
- `httpx==0.27.0`
- `pydantic==2.7.1`
- `pydantic-settings==2.2.1`
