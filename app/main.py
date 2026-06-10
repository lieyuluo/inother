"""FastAPI main application entry point."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes_admin import router as admin_router
from app.api.routes_auth import router as auth_router
from app.api.routes_chat import router as chat_router
from app.api.routes_documents import router as documents_router
from app.api.routes_health import router as health_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_tools import router as tools_router
from app.core.config import get_settings
from app.core.errors import AppException, app_exception_handler, http_exception_handler
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.app_env}")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Enterprise AI Agent - A production-ready AI agent backend",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    cors_origins = settings.get_cors_origins()
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Request logging middleware
    @app.middleware("http")
    async def request_logging_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        import time

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        # Skip health check noise
        if request.url.path != "/health":
            logger.info(
                f"{request.method} {request.url.path} {response.status_code} {duration_ms:.1f}ms"
            )
        return response

    # Register exception handlers
    exception_handler = cast(
        Callable[[Request, Exception], Response | Awaitable[Response]],
        app_exception_handler,
    )
    http_handler = cast(
        Callable[[Request, Exception], Response | Awaitable[Response]],
        http_exception_handler,
    )

    app.add_exception_handler(AppException, exception_handler)
    app.add_exception_handler(HTTPException, http_handler)

    # Include routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
    app.include_router(tools_router)
    app.include_router(metrics_router)

    return app


# Create the application instance
app = create_app()
