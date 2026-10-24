"""
FastAPI dependency functions for auth, RBAC, and request context.

These are injected via Depends() into route handlers. They keep
route logic clean and make it easy to swap implementations in tests.

Security contract:
- `get_current_user` is the single authoritative source of trusted
  identity for all protected endpoints.
- Never bypass it. Never accept a user_id from the request body as
  a substitute for authenticated identity.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.context import build_user_context
from auth.exceptions import AuthError, ExpiredTokenError, InvalidTokenError
from auth.jwt import verify_jwt
from auth.rbac import require_admin, require_operator, require_role
from contracts.users import UserContext, UserRole

from .config import Settings, get_settings

logger = logging.getLogger(__name__)

# HTTPBearer extracts the token from the Authorization: Bearer <token> header.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserContext:
    """
    Validate the Bearer JWT and return a trusted UserContext.

    Raises HTTP 401 if the token is absent, expired, or invalid.
    Raises HTTP 403 if the account is inactive (handled downstream).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        claims = verify_jwt(token, settings.supabase_jwt_secret)
        user_ctx = build_user_context(claims)
    except ExpiredTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (InvalidTokenError, AuthError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_ctx.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user_ctx


# ── Pre-built role-gated dependencies ────────────────────────────────────────

async def require_user_role(
    user: Annotated[UserContext, Depends(get_current_user)],
) -> UserContext:
    """Allow any active authenticated user."""
    return user


async def require_operator_role(
    user: Annotated[UserContext, Depends(get_current_user)],
) -> UserContext:
    """Allow operators and admins."""
    try:
        require_operator(user)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return user


async def require_admin_role(
    user: Annotated[UserContext, Depends(get_current_user)],
) -> UserContext:
    """Allow admins only."""
    try:
        require_admin(user)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return user


# Convenience type aliases for use in route signatures.
CurrentUser = Annotated[UserContext, Depends(get_current_user)]
OperatorUser = Annotated[UserContext, Depends(require_operator_role)]
AdminUser = Annotated[UserContext, Depends(require_admin_role)]


# ── Shared HTTP client dependency ─────────────────────────────────────────────

import httpx as _httpx  # local import to avoid circular at module level

_http_client: "_httpx.AsyncClient | None" = None


def set_http_client(client: "_httpx.AsyncClient | None") -> None:
    """Called from main.py startup/shutdown to set the shared client."""
    global _http_client
    _http_client = client


def get_http_client() -> "_httpx.AsyncClient":
    if _http_client is None:
        raise RuntimeError("HTTP client not initialised")
    return _http_client
