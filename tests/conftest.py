"""
Shared pytest fixtures for the AI Agent Platform test suite.

Fixtures defined here are available to all tests under tests/.
Service-specific fixtures should live in the relevant sub-package's
own conftest.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ── Token / auth helpers ──────────────────────────────────────────────────────

def _make_jwt_claims(
    user_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    role: str = "user",
) -> dict:
    """Return a minimal dict that looks like decoded Supabase JWT claims."""
    now = int(datetime.now(tz=timezone.utc).timestamp())
    return {
        "sub": str(user_id or uuid.uuid4()),
        "email": email,
        "role": role,
        "aud": "authenticated",
        "iat": now,
        "exp": now + 3600,
        "tenant_id": str(tenant_id or uuid.uuid4()),
    }


@pytest.fixture()
def user_claims() -> dict:
    return _make_jwt_claims(role="user")


@pytest.fixture()
def operator_claims() -> dict:
    return _make_jwt_claims(role="operator")


@pytest.fixture()
def admin_claims() -> dict:
    return _make_jwt_claims(role="admin")


@pytest.fixture()
def another_tenant_claims() -> dict:
    """Claims for a user in a completely different tenant."""
    return _make_jwt_claims(role="user", tenant_id=uuid.uuid4())
