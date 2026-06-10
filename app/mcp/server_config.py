"""MCP server configuration models."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings

TransportName = Literal["in_process", "stdio", "http"]


class MCPServerConfig(BaseModel):
    """Configuration for one MCP server."""

    name: str
    transport: TransportName = "in_process"
    enabled: bool = True
    command: list[str] | None = None
    url: str | None = None
    timeout_seconds: float = Field(default=5.0, gt=0)
    required_role: str = "user"
    namespace: str | None = "mcp"

    @field_validator("required_role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in {"user", "admin"}:
            raise ValueError("required_role must be user or admin")
        return value


def load_mcp_server_configs() -> list[MCPServerConfig]:
    """Load MCP server configs from defaults plus optional JSON env config."""
    settings = get_settings()
    configs = [
        MCPServerConfig(
            name="demo",
            transport="in_process",
            enabled=settings.mcp_demo_enabled,
            namespace="mcp",
            required_role="user",
        )
    ]

    raw = settings.mcp_server_configs.strip()
    if raw:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("MCP_SERVER_CONFIGS must be a JSON array")
        configs.extend(MCPServerConfig.model_validate(item) for item in data)

    return configs
