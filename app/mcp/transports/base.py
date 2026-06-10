"""Base protocol for MCP transports."""

from __future__ import annotations

from typing import Protocol

from app.mcp.schemas import MCPToolCallResult, MCPToolDefinition


class MCPTransportError(Exception):
    """Raised when an MCP transport fails."""


class MCPTransport(Protocol):
    """Protocol implemented by all MCP transports."""

    def connect(self) -> None:
        """Open the transport connection."""

    def disconnect(self) -> None:
        """Close the transport connection."""

    def list_tools(self) -> list[MCPToolDefinition]:
        """List tools exposed by this server."""

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> MCPToolCallResult:
        """Call a tool by its server-local name."""

    def health_check(self) -> MCPToolCallResult:
        """Return transport health status."""
