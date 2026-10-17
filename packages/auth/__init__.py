# packages/auth
# Shared JWT validation and trusted user/tenant context helpers.
from .jwt import verify_jwt, JWTClaims
from .context import build_user_context, get_tenant_id
from .exceptions import (
    AuthError,
    InvalidTokenError,
    ExpiredTokenError,
    InsufficientPermissionsError,
)

__all__ = [
    "verify_jwt",
    "JWTClaims",
    "build_user_context",
    "get_tenant_id",
    "AuthError",
    "InvalidTokenError",
    "ExpiredTokenError",
    "InsufficientPermissionsError",
]
