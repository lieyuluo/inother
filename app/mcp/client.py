"""MCP Client for communicating with MCP servers.

This client uses an in-process DemoMCPServer. In the future, it can be
replaced with a standard MCP client using stdio or HTTP transport.
"""

from __future__ import annotations

from app.mcp.demo_server import DemoMCPServer
from app.mcp.schemas import MCPToolCallResult, MCPToolDefinition


class MCPClient:
    """Client for communicating with MCP servers.

    Currently uses an in-process DemoMCPServer. The connect/disconnect
    methods are no-ops for the demo, but provide extension points for
    future transport implementations.
    """

    def __init__(self, server: DemoMCPServer | None = None) -> None:
        self._server = server or DemoMCPServer()
        self._connected = False

    async def connect(self) -> None:
        """Connect to the MCP server.

        For the demo, this is a no-op. In the future, this would
        establish a transport connection (stdio/HTTP).
        """
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        self._connected = False

    def list_tools(self) -> list[MCPToolDefinition]:
        """List available MCP tools.

        Returns:
            List of MCPToolDefinition objects.
        """
        return self._server.list_tools()

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> MCPToolCallResult:
        """Call an MCP tool.

        Args:
            tool_name: Name of the tool to call.
            arguments: Input arguments.

        Returns:
            MCPToolCallResult with status, output, and metadata.
        """
        try:
            return self._server.call_tool(tool_name, arguments)
        except Exception as e:
            return MCPToolCallResult(
                tool_name=tool_name,
                status="error",
                error=f"MCP client error: {e}",
            )
