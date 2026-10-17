"""
Common response envelopes and shared primitives used across all services.
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error detail returned in API error responses."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    field: str | None = Field(None, description="Field name if the error is field-specific")


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response envelope.

    All service endpoints should wrap their payloads in this schema so
    clients have a consistent shape to parse.
    """

    success: bool = Field(..., description="Whether the request succeeded")
    data: T | None = Field(None, description="Response payload on success")
    error: ErrorDetail | None = Field(None, description="Error detail on failure")
    request_id: str | None = Field(None, description="Correlation ID for tracing")

    model_config = {"populate_by_name": True}


class PaginationParams(BaseModel):
    """Common query parameters for paginated list endpoints."""

    page: int = Field(1, ge=1, description="1-indexed page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page (max 100)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
