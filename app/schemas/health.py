"""Health check response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: str
    service: str
    version: str


class HealthReadyResponse(BaseModel):
    """Response schema for readiness check endpoint."""

    status: str
    database: str
    redis: str


class HealthLiveResponse(BaseModel):
    """Response schema for liveness check endpoint."""

    status: str
