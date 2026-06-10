"""In-process MCP transport wrapping the demo MCP server."""

from __future__ import annotations

import time

from app.mcp.demo_server import DemoMCPServer
from app.mcp.schemas import MCPToolCallResult, MCPToolDefinition


class InProcessTransport:
    """Transport that calls an in-process demo server directly."""

    def __init__(self, server: DemoMCPServer | None = None) -> None:
        self._server = server or DemoMCPServer()
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def list_tools(self) -> list[MCPToolDefinition]:
        self._ensure_connected()
        return self._server.list_tools()

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> MCPToolCallResult:
        self._ensure_connected()
        return self._server.call_tool(tool_name, arguments)

    def health_check(self) -> MCPToolCallResult:
        start = time.monotonic()
        status = "connected" if self._connected else "disconnected"
        return MCPToolCallResult(
            tool_name="health_check",
            status="success",
            output={"status": status, "transport": "in_process"},
            latency_ms=(time.monotonic() - start) * 1000,
        )

    def _ensure_connected(self) -> None:
        if not self._connected:
            self.connect()
