"""Prometheus-style metrics endpoint."""

from fastapi import APIRouter, Response

from app.core.config import get_settings

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Return metrics in Prometheus text format.

    This is a lightweight implementation for development/demo purposes.
    For production monitoring, integrate with a proper Prometheus exporter.
    """
    settings = get_settings()
    lines = [
        "# HELP enterprise_ai_agent_info Application info",
        "# TYPE enterprise_ai_agent_info gauge",
        f'enterprise_ai_agent_info{{version="{settings.app_version}",env="{settings.app_env}"}} 1',
        "",
    ]
    return Response(content="\n".join(lines), media_type="text/plain")
