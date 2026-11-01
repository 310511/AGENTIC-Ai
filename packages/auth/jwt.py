"""
JWT verification helpers for Supabase-issued tokens.

Supabase signs JWTs with HS256 (older projects) or ES256 (newer projects).
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
from jwt.algorithms import ECAlgorithm
from pydantic import BaseModel, Field

from .exceptions import ExpiredTokenError, InvalidTokenError

logger = logging.getLogger(__name__)

# Supabase uses HS256 for older projects and ES256 for newer ones.
_ALGORITHMS = ["HS256", "ES256"]

# Expected audience for Supabase authenticated users.
_EXPECTED_AUDIENCE = "authenticated"

# Supabase ES256 public key (JWKS) — fetched once at import time.
# Stored as a JWK dict; converted to a key object on first use.
_SUPABASE_JWKS: dict[str, Any] | None = None


def _get_es256_key(kid: str | None = None) -> Any:
    """Return the EC public key for verifying ES256 tokens."""
    global _SUPABASE_JWKS
    if _SUPABASE_JWKS is None:
        # shortcut: key is hardcoded from JWKS; refresh on key rotation
        _SUPABASE_JWKS = {
            "alg": "ES256", "crv": "P-256", "kty": "EC", "use": "sig",
            "x": "v44G_tfzH2sJ9jetKTUetyngexSh819ZBQBjxbthmlg",
            "y": "6xLShAyMOQlRfRfoZQbob01SGnlY3NJ0epgxXJCer8I",
        }
    return ECAlgorithm.from_jwk(_SUPABASE_JWKS)


class JWTClaims(BaseModel):
    """
    Typed representation of the claims extracted from a valid Supabase JWT.

    Only fields explicitly listed here are surfaced — extra claims are
    silently dropped to prevent accidental trust in arbitrary payloads.
    """

    sub: UUID = Field(..., description="User UUID (subject)")
    # email may be top-level or inside user_metadata depending on Supabase version
    email: str = Field("", description="Verified user email")
    role: str = Field("authenticated", description="Supabase/app role claim")
    aud: str | list[str] = Field("authenticated", description="Token audience")
    exp: int = Field(..., description="Expiry timestamp (Unix epoch)")
    iat: int = Field(..., description="Issued-at timestamp (Unix epoch)")

    # Custom claim injected by Supabase custom JWT hooks or user metadata.
    # If absent, the middleware falls back to a default tenant strategy.
    tenant_id: UUID | None = Field(
        None,
        alias="tenant_id",
        description="Tenant UUID, expected as a custom JWT claim",
    )

    # Supabase stores email in user_metadata in newer versions
    user_metadata: dict | None = Field(None)

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @property
    def is_expired(self) -> bool:
        return datetime.now(tz=timezone.utc).timestamp() > self.exp

    def get_email(self) -> str:
        """Return email from top-level claim or user_metadata fallback."""
        if self.email:
            return self.email
        if self.user_metadata and self.user_metadata.get("email"):
            return self.user_metadata["email"]
        return str(self.sub)  # last resort: use UUID as identifier


def verify_jwt(token: str, jwt_secret: str) -> JWTClaims:
    """
    Decode and verify a Supabase JWT (HS256 or ES256).

    For ES256 tokens, uses the hardcoded JWKS public key.
    For HS256 tokens, uses the provided jwt_secret.
    """
    if not token or not token.strip():
        raise InvalidTokenError("Token must not be empty")

    # Peek at the algorithm without verifying, to choose the right key.
    try:
        header = pyjwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
    except pyjwt.PyJWTError as exc:
        raise InvalidTokenError("Malformed token header") from exc

    key: Any = _get_es256_key() if alg == "ES256" else jwt_secret

    try:
        raw: dict[str, Any] = pyjwt.decode(
            token,
            key,
            algorithms=[alg],
            options={
                "verify_aud": False,
                "require": ["sub", "exp", "iat"],
            },
        )
    except pyjwt.ExpiredSignatureError as exc:
        logger.debug("JWT expired: %s", exc)
        raise ExpiredTokenError() from exc
    except pyjwt.PyJWTError as exc:
        logger.warning("JWT decode failed: %s | token_prefix=%s", exc, token[:20] if token else "")
        raise InvalidTokenError() from exc

    try:
        claims = JWTClaims.model_validate(raw)
    except Exception as exc:
        logger.debug("JWT claims validation failed: %s", exc)
        raise InvalidTokenError("Token is missing required claims") from exc

    return claims
