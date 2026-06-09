"""Health check API routes."""

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.schemas.health import HealthLiveResponse, HealthReadyResponse, HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])

settings = get_settings()


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description="Returns basic health status of the service.",
)
async def health_check() -> HealthResponse:
    """Basic health check endpoint."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get(
    "/ready",
    response_model=HealthReadyResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Checks if the service is ready to accept requests (database and redis connectivity).",
)
async def readiness_check() -> HealthReadyResponse:
    """Readiness check endpoint.

    In Phase 1, this returns a simple status without actual connectivity checks.
    Actual database and redis checks will be implemented in future phases.
    """
    return HealthReadyResponse(
        status="ok",
        database="not_checked",
        redis="not_checked",
    )


@router.get(
    "/live",
    response_model=HealthLiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Checks if the service is alive and running.",
)
async def liveness_check() -> HealthLiveResponse:
    """Liveness check endpoint."""
    return HealthLiveResponse(status="ok")
