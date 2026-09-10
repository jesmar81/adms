"""Application factory: ADMS gateway + admin API + health/readiness."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.adms.router import router as adms_router
from app.api.v1.router import router as api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.debug)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ZKTeco ADMS Platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    origins = settings.frontend_origins()
    if origins:
        from fastapi.middleware.cors import CORSMiddleware

        # Explicit origins only — never "*" together with credentials (L-04).
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
            max_age=600,
        )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        # Baseline app-level headers (TLS-scoped ones live at the proxy).
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if settings.hsts_enabled:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        rid = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc), "request_id": rid}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Render every HTTP error in the §66 envelope (preserves headers)."""
        rid = getattr(request.state, "request_id", "")
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            error: dict[str, object] = dict(exc.detail["error"])
            if not error.get("request_id"):
                error["request_id"] = rid
            content: dict[str, object] = {"error": error}
        else:
            code = {
                401: "UNAUTHORIZED",
                403: "FORBIDDEN",
                404: "NOT_FOUND",
                422: "VALIDATION_ERROR",
            }.get(exc.status_code, "HTTP_ERROR")
            content = {"error": {"code": code, "message": str(exc.detail), "request_id": rid}}
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Sanitized (L-03): FastAPI 0.141 appends endpoint file/line context to
        # str(exc) — never expose it. Only type/loc/msg reach the client.
        rid = getattr(request.state, "request_id", "")
        details = [
            {"type": err.get("type"), "loc": list(err.get("loc", [])), "msg": err.get("msg")}
            for err in exc.errors()
            if isinstance(err, dict)
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "request_id": rid,
                    "details": details,
                }
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> JSONResponse:
        # Sanitized (L-03): booleans only, never exception strings.
        checks: dict[str, bool] = {}
        # PostgreSQL
        try:
            from sqlalchemy import text

            from app.core.database import get_engine

            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["postgres"] = True
        except Exception:
            checks["postgres"] = False
        # Redis
        try:
            from app.core.redis import get_redis

            await get_redis().ping()
            checks["redis"] = True
        except Exception:
            checks["redis"] = False
        ok = all(checks.values())
        return JSONResponse({"ready": ok, "checks": checks}, status_code=200 if ok else 503)

    app.include_router(adms_router, prefix="/iclock")
    app.include_router(api_router)
    return app


app = create_app()
