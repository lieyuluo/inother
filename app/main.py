"""FastAPI main application entry point."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes_health import router as health_router
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

    return app


# Create the application instance
app = create_app()
