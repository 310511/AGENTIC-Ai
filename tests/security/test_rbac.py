"""
Unit tests for RBAC helpers.

Tests cover role hierarchy, tenant isolation, and edge cases
that must not regress as the platform grows.
"""
from __future__ import annotations

import uuid

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

from auth.exceptions import InsufficientPermissionsError
from auth.rbac import require_admin, require_operator, require_role, require_same_tenant
from contracts.users import UserContext, UserRole


def _user(role: UserRole, active: bool = True) -> UserContext:
    return UserContext(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email=f"{role.value}@example.com",
        role=role,
        is_active=active,
    )


TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()


# ── Role hierarchy ────────────────────────────────────────────────────────────

@pytest.mark.security
def test_admin_passes_all_role_checks():
    admin = _user(UserRole.ADMIN)
    require_role(admin, UserRole.USER)
    require_role(admin, UserRole.OPERATOR)
    require_role(admin, UserRole.ADMIN)  # no exception


@pytest.mark.security
def test_operator_passes_user_and_operator_checks():
    op = _user(UserRole.OPERATOR)
    require_role(op, UserRole.USER)
    require_role(op, UserRole.OPERATOR)


@pytest.mark.security
def test_operator_fails_admin_check():
    op = _user(UserRole.OPERATOR)
    with pytest.raises(InsufficientPermissionsError):
        require_admin(op)


@pytest.mark.security
def test_user_fails_operator_check():
    user = _user(UserRole.USER)
    with pytest.raises(InsufficientPermissionsError):
        require_operator(user)


@pytest.mark.security
def test_user_fails_admin_check():
    user = _user(UserRole.USER)
    with pytest.raises(InsufficientPermissionsError):
        require_admin(user)


# ── Inactive account ──────────────────────────────────────────────────────────

@pytest.mark.security
def test_inactive_admin_is_rejected():
    """Even an admin cannot act if the account is inactive."""
    admin = _user(UserRole.ADMIN, active=False)
    with pytest.raises(InsufficientPermissionsError):
        require_role(admin, UserRole.USER)


# ── Tenant isolation ──────────────────────────────────────────────────────────

@pytest.mark.security
def test_same_tenant_passes():
    user = UserContext(
        user_id=uuid.uuid4(),
        tenant_id=TENANT_A,
        email="user@example.com",
        role=UserRole.USER,
        is_active=True,
    )
    require_same_tenant(user, TENANT_A)  # no exception


@pytest.mark.security
def test_different_tenant_raises():
    user = UserContext(
        user_id=uuid.uuid4(),
        tenant_id=TENANT_A,
        email="user@example.com",
        role=UserRole.USER,
        is_active=True,
    )
    with pytest.raises(InsufficientPermissionsError):
        require_same_tenant(user, TENANT_B)


@pytest.mark.security
def test_admin_cannot_cross_tenant_boundary():
    """
    Admins are NOT granted automatic cross-tenant access.
    Cross-tenant access requires an explicit bypass (document if added).
    """
    admin = UserContext(
        user_id=uuid.uuid4(),
        tenant_id=TENANT_A,
        email="admin@example.com",
        role=UserRole.ADMIN,
        is_active=True,
    )
    with pytest.raises(InsufficientPermissionsError):
        require_same_tenant(admin, TENANT_B)
