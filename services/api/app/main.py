"""
AI Agent Platform — FastAPI application entry point.

Startup sequence:
  1. Load and validate configuration (fails fast on missing env vars).
  2. Register middleware (CORS, request-id).
  3. Mount routers.
  4. Connect to the database on startup; disconnect on shutdown.

All protected routes require a valid Supabase JWT.
"""
from __future__ import annotations

import logging
import sys

import httpx
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth.exceptions import AuthError

from .config import get_settings
from .database import close_engine, get_engine
from .dependencies import set_http_client
from .middleware import RequestIDMiddleware
from .routers import health, tasks

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── App factory ───────────────────────────────────────────────────────────────

settings = get_settings()

# shortcut: http_client lifecycle lives in dependencies.py; kept here for startup/shutdown wiring


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Agent Platform API",
        description=(
            "Secure API gateway for the AI Agent Platform. "
            "All endpoints require a valid Supabase JWT unless noted."
        ),
        version="0.1.0",
        # Disable automatic docs in production to reduce attack surface.
        docs_url="/docs" if settings.api_debug else None,
        redoc_url="/redoc" if settings.api_debug else None,
        openapi_url="/openapi.json" if settings.api_debug else None,
    )

    # ── Middleware (applied in reverse registration order) ────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIDMiddleware)

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(tasks.router, prefix="/api/v1")

    # ── Global exception handlers ─────────────────────────────────────────

    @app.exception_handler(AuthError)
    async def auth_error_handler(request: Request, exc: AuthError) -> JSONResponse:
        """Catch any AuthError that escaped route-level handling."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": {"code": "auth_error", "message": exc.message}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Last-resort handler for unhandled exceptions.

        Returns a generic 500 without internal details to avoid leaking
        stack traces or system information to callers.
        """
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred",
                },
            },
        )

    # ── Lifecycle events ──────────────────────────────────────────────────

    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info("Starting AI Agent Platform API (debug=%s)", settings.api_debug)
        get_engine()
        set_http_client(httpx.AsyncClient(timeout=10.0))
        logger.info("Startup complete")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        from .dependencies import _http_client
        logger.info("Shutting down AI Agent Platform API")
        await close_engine()
        if _http_client:
            await _http_client.aclose()
        set_http_client(None)

    return app


app = create_app()
