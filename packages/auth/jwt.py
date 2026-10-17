"""
JWT verification helpers for Supabase-issued tokens.

Supabase signs JWTs with HS256 using the project's JWT secret.
This module validates the signature, expiry, and required claims,
then returns a typed claims object — never raw dict data.

Usage:
    claims = verify_jwt(token, jwt_secret)
    user_ctx = build_user_context(claims)

Security notes:
- The jwt_secret MUST come from server-side config, never from the
  request or frontend.
- Always verify the token before trusting any claim it contains.
- 'sub' is the authoritative user identity — do not accept a user_id
  from the request body as a substitute.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import jwt as pyjwt
from pydantic import BaseModel, Field

from .exceptions import ExpiredTokenError, InvalidTokenError

logger = logging.getLogger(__name__)

# Supabase uses HS256 for project JWTs.
_ALGORITHM = "HS256"

# Expected audience for Supabase authenticated users.
_EXPECTED_AUDIENCE = "authenticated"


class JWTClaims(BaseModel):
    """
    Typed representation of the claims extracted from a valid Supabase JWT.

    Only fields explicitly listed here are surfaced — extra claims are
    silently dropped to prevent accidental trust in arbitrary payloads.
    """

    sub: UUID = Field(..., description="User UUID (subject)")
    email: str = Field(..., description="Verified user email")
    role: str = Field(..., description="Supabase/app role claim")
    aud: str = Field(..., description="Token audience")
    exp: int = Field(..., description="Expiry timestamp (Unix epoch)")
    iat: int = Field(..., description="Issued-at timestamp (Unix epoch)")

    # Custom claim injected by Supabase custom JWT hooks or user metadata.
    # If absent, the middleware falls back to a default tenant strategy.
    tenant_id: UUID | None = Field(
        None,
        alias="tenant_id",
        description="Tenant UUID, expected as a custom JWT claim",
    )

    model_config = {"populate_by_name": True}

    @property
    def is_expired(self) -> bool:
        return datetime.now(tz=timezone.utc).timestamp() > self.exp


def verify_jwt(token: str, jwt_secret: str) -> JWTClaims:
    """
    Decode and verify a Supabase JWT.

    Args:
        token:      Raw Bearer token string (without 'Bearer ' prefix).
        jwt_secret: The Supabase project JWT secret from server config.

    Returns:
        JWTClaims — typed, verified claims.

    Raises:
        ExpiredTokenError:  Token signature is valid but the token has expired.
        InvalidTokenError:  Token is malformed, signature is wrong, or
                            required claims are missing.
    """
    if not token or not token.strip():
        raise InvalidTokenError("Token must not be empty")

    try:
        raw: dict[str, Any] = pyjwt.decode(
            token,
            jwt_secret,
            algorithms=[_ALGORITHM],
            audience=_EXPECTED_AUDIENCE,
            options={"require": ["sub", "email", "exp", "iat", "aud"]},
        )
    except pyjwt.ExpiredSignatureError as exc:
        logger.debug("JWT expired: %s", exc)
        raise ExpiredTokenError() from exc
    except pyjwt.InvalidAudienceError as exc:
        logger.debug("JWT audience mismatch: %s", exc)
        raise InvalidTokenError("Token audience is invalid") from exc
    except pyjwt.PyJWTError as exc:
        # Log at debug to avoid leaking token details into logs.
        logger.debug("JWT decode failed: %s", exc)
        raise InvalidTokenError() from exc

    try:
        claims = JWTClaims.model_validate(raw)
    except Exception as exc:
        logger.debug("JWT claims validation failed: %s", exc)
        raise InvalidTokenError("Token is missing required claims") from exc

    return claims
