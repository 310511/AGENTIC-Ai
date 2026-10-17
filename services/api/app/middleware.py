"""
Custom ASGI middleware for the API service.

RequestIDMiddleware  — attaches a unique request-id to every request and
                       response for distributed tracing correlation.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Ensure every request and response carries a unique X-Request-ID.

    If the caller supplies an X-Request-ID header we echo it back;
    otherwise we generate a new UUID. Downstream services should
    propagate this ID in their own outbound requests for end-to-end
    trace correlation.

    Security note: the incoming header value is used as-is but is
    not trusted for any identity or authorization purpose — it is
    purely for observability.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # Attach to request state so route handlers can access it.
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
