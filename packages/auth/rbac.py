"""
Role-Based Access Control (RBAC) helpers.

Use these functions in FastAPI dependencies and service-layer guards to
enforce the principle of least privilege.

Design notes:
- Roles are ordered by privilege level: ADMIN > OPERATOR > USER.
- A check for OPERATOR also grants access to ADMIN holders.
- Authorization is always server-side — never trust role claims sent by
  the client directly.
"""
from __future__ import annotations

from contracts.users import UserContext, UserRole

from .exceptions import InsufficientPermissionsError

# Privilege ordering: higher index = higher privilege.
_ROLE_HIERARCHY: list[UserRole] = [
    UserRole.USER,
    UserRole.OPERATOR,
    UserRole.ADMIN,
]


def _role_level(role: UserRole) -> int:
    """Return the numeric privilege level of a role (higher = more privileged)."""
    try:
        return _ROLE_HIERARCHY.index(role)
    except ValueError:
        return -1


def require_role(user: UserContext, minimum_role: UserRole) -> None:
    """
    Assert that the user holds at least the specified role.

    Args:
        user:         Trusted UserContext from a verified JWT.
        minimum_role: The lowest role that is permitted.

    Raises:
        InsufficientPermissionsError: If the user's role is below the minimum.
    """
    if not user.is_active:
        raise InsufficientPermissionsError("User account is inactive")

    if _role_level(user.role) < _role_level(minimum_role):
        raise InsufficientPermissionsError(
            f"Role '{user.role}' does not meet the required minimum '{minimum_role}'"
        )


def require_admin(user: UserContext) -> None:
    """Shorthand: assert the user is an admin."""
    require_role(user, UserRole.ADMIN)


def require_operator(user: UserContext) -> None:
    """Shorthand: assert the user is at least an operator."""
    require_role(user, UserRole.OPERATOR)


def require_same_tenant(user: UserContext, resource_tenant_id: object) -> None:
    """
    Assert that the user belongs to the same tenant as the resource.

    Args:
        user:               Trusted UserContext.
        resource_tenant_id: The tenant_id stored on the resource.

    Raises:
        InsufficientPermissionsError: On tenant mismatch.

    Note:
        Admins currently still get a tenant check. If cross-tenant admin
        access is required in future, add an explicit bypass here and
        document the decision.
    """
    if str(user.tenant_id) != str(resource_tenant_id):
        raise InsufficientPermissionsError(
            "Access denied: resource belongs to a different tenant"
        )
