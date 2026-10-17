"""
Build trusted UserContext from verified JWT claims.

This module bridges the auth layer (JWT claims) and the contracts layer
(UserContext). It is the single place that maps raw claim values to the
typed identity object used by all downstream services.

Rules:
- Always build UserContext from verified JWTClaims, never from raw
  request data.
- If the JWT does not carry a tenant_id claim, fall back to treating
  the user's own sub (user_id) as the tenant scope. Update this
  strategy when multi-tenancy is fully defined.
- Map Supabase role strings to the platform UserRole enum here so the
  rest of the codebase works with typed roles.
"""
from __future__ import annotations

import logging
from uuid import UUID

# Import contracts from the sibling package.
# In a monorepo both packages are installed; adjust the import path if
# using a different layout.
from contracts.users import UserContext, UserRole

from .exceptions import InvalidTokenError
from .jwt import JWTClaims

logger = logging.getLogger(__name__)

# Mapping from Supabase/custom role strings to platform UserRole.
# Extend this map as new roles are introduced.
_ROLE_MAP: dict[str, UserRole] = {
    "admin": UserRole.ADMIN,
    "operator": UserRole.OPERATOR,
    "user": UserRole.USER,
    # Supabase default authenticated role falls back to USER.
    "authenticated": UserRole.USER,
    "anon": UserRole.USER,
}


def _resolve_role(raw_role: str) -> UserRole:
    """Map a raw JWT role string to a typed UserRole."""
    role = _ROLE_MAP.get(raw_role.lower())
    if role is None:
        logger.warning(
            "Unknown role claim '%s'; defaulting to UserRole.USER", raw_role
        )
        return UserRole.USER
    return role


def get_tenant_id(claims: JWTClaims) -> UUID:
    """
    Resolve the tenant UUID from JWT claims.

    Prefers the explicit 'tenant_id' custom claim. Falls back to the
    user's own UUID so single-user deployments work without additional
    JWT customisation.

    Update this function once the multi-tenant model is finalised
    (see context.md Section 12 — Open Decisions).
    """
    if claims.tenant_id is not None:
        return claims.tenant_id

    logger.debug(
        "No tenant_id claim present for user %s; falling back to user_id as tenant",
        claims.sub,
    )
    return claims.sub


def build_user_context(claims: JWTClaims) -> UserContext:
    """
    Construct a trusted UserContext from verified JWT claims.

    Args:
        claims: Verified JWTClaims returned by verify_jwt().

    Returns:
        UserContext — the identity object passed throughout the request.

    Raises:
        InvalidTokenError: If required fields cannot be resolved.
    """
    try:
        return UserContext(
            user_id=claims.sub,
            tenant_id=get_tenant_id(claims),
            email=claims.email,
            role=_resolve_role(claims.role),
            is_active=True,
        )
    except Exception as exc:
        logger.debug("Failed to build UserContext from claims: %s", exc)
        raise InvalidTokenError("Could not construct user context from token") from exc
