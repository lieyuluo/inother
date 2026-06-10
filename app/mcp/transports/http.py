"""HTTP MCP transport placeholder.

Phase 3 defines the shape of the HTTP transport but does not connect to a real
third-party MCP service. Tests can subclass or mock this transport.
"""

from __future__ import annotations

import time

from app.mcp.schemas import MCPToolCallResult, MCPToolDefinition


class HTTPTransport:
    """Stable placeholder for future HTTP MCP transport support."""

    def __init__(self, url: str, timeout_seconds: float = 5.0) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def list_tools(self) -> list[MCPToolDefinition]:
        return []

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> MCPToolCallResult:
        _ = arguments
        start = time.monotonic()
        return MCPToolCallResult(
            tool_name=tool_name,
            status="error",
            error="HTTP MCP transport is not implemented in v1.0 Phase 3.",
            latency_ms=(time.monotonic() - start) * 1000,
        )

    def health_check(self) -> MCPToolCallResult:
        start = time.monotonic()
        return MCPToolCallResult(
            tool_name="health_check",
            status="success",
            output={
                "status": "placeholder",
                "transport": "http",
                "url_configured": bool(self.url),
            },
            latency_ms=(time.monotonic() - start) * 1000,
        )
