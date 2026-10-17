# Policy Service

**Status:** Partial — Phase 1 (basic RBAC helpers exist in `packages/auth`)

## Responsibility

Central authority for all authorization decisions: role checks, tenant scope,
tool allowlists, sensitive operation guards, and human approval requirements.
Every tool call and sensitive write goes through this service before execution.
All decisions are recorded in the audit trail.

## Current state

Basic RBAC logic (`require_role`, `require_same_tenant`) lives in
`packages/auth/rbac.py` and is used directly by the API service in Phase 1.

A standalone Policy Service process will be introduced when the Orchestrator
and MCP Client Manager need to make policy calls at runtime (Phase 5+).

## Planned components

```
policy/
├── app/
│   ├── main.py              # Internal FastAPI app
│   ├── config.py
│   ├── engine.py            # Policy evaluation engine
│   ├── rules/
│   │   ├── rbac.py          # Role-based rules
│   │   ├── tenant.py        # Tenant isolation rules
│   │   └── tool_allowlist.py # Per-user/tenant MCP tool allowlists
│   └── audit.py             # Decision and outcome logging
├── requirements.txt
└── Dockerfile
```

## Key design rules (from context.md)

- Check policy **before** every tool call and sensitive write/action.
- Record the decision, relevant policy, and action outcome in the audit trail.
- Never rely on an LLM's claim that an action is permitted.
- Authentication is not authorization — a valid JWT identifies a user;
  policy determines what that user may do.
