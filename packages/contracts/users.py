"""
User and identity schemas shared across services.

These schemas represent the *trusted* context extracted from a validated
JWT — never accept raw user/tenant IDs from request bodies as trusted.
"""
from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """Platform roles used for RBAC checks."""

    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"


class UserContext(BaseModel):
    """
    Trusted user identity extracted from a validated Supabase JWT.

    Populated by the auth middleware after signature verification.
    Do NOT construct from untrusted request data.
    """

    user_id: UUID = Field(..., description="Supabase user UUID (sub claim)")
    tenant_id: UUID = Field(..., description="Tenant the user belongs to")
    email: EmailStr = Field(..., description="User's verified email address")
    role: UserRole = Field(..., description="User's platform role")
    is_active: bool = Field(True, description="Whether the account is active")

    model_config = {"populate_by_name": True}
