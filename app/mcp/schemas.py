"""MCP (Model Context Protocol) demo integration schemas.

This is a demo MCP integration for the Enterprise AI Agent platform.
It does NOT implement the full MCP protocol specification, but provides
a compatible interface that can be replaced with a standard MCP SDK
in the future.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    """Definition of an MCP tool."""

    name: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object] | None = None


class MCPToolCallRequest(BaseModel):
    """Request to call an MCP tool."""

    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class MCPToolCallResult(BaseModel):
    """Result from calling an MCP tool."""

    tool_name: str
    status: str = "success"  # success / error
    output: dict[str, object] = Field(default_factory=dict)
    error: str | None = None
    latency_ms: float = 0.0
