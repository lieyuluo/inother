"""MCP Tool Adapter for integrating MCP tools into the Tool Registry.

This adapter wraps MCP tools as BaseTool instances, allowing them to be
registered in the existing Tool Registry and invoked through ToolService.
"""

from __future__ import annotations

import time
from uuid import uuid4

from app.mcp.client import MCPClient
from app.mcp.schemas import MCPToolDefinition
from app.tools.base import BaseTool
from app.tools.schemas import ToolResult


class MCPToolAdapter(BaseTool):
    """Adapter that wraps an MCP tool as a BaseTool.

    This allows MCP tools to be registered in the Tool Registry and
    invoked through ToolService, maintaining full compatibility with
    the existing tool infrastructure.
    """

    def __init__(self, definition: MCPToolDefinition, client: MCPClient) -> None:
        self._definition = definition
        self._client = client

    @property
    def name(self) -> str:
        return self._definition.name

    @property
    def description(self) -> str:
        return self._definition.description

    @property
    def input_schema(self) -> dict[str, object]:
        return self._definition.input_schema

    @property
    def output_schema(self) -> dict[str, object] | None:
        return self._definition.output_schema

    @property
    def required_role(self) -> str:
        if self._definition.name == "mcp_create_ticket":
            return "admin"
        return "user"

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:
        """Invoke the MCP tool through the MCP client.

        Args:
            input_data: Input data matching the tool's input_schema.

        Returns:
            ToolResult with status, output, and metadata.
        """
        start = time.monotonic()
        trace_id = str(uuid4())

        mcp_result = self._client.call_tool(self._definition.name, input_data)
        latency_ms = (time.monotonic() - start) * 1000

        if mcp_result.status == "success":
            output = dict(mcp_result.output)
            output["source"] = "mcp"
            return ToolResult(
                tool_name=self.name,
                status="success",
                output=output,
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
        else:
            return ToolResult(
                tool_name=self.name,
                status="error",
                error=mcp_result.error,
                latency_ms=latency_ms,
                trace_id=trace_id,
            )


def create_mcp_tools(client: MCPClient | None = None) -> list[BaseTool]:
    """Create MCP tool adapters for all demo MCP tools.

    Args:
        client: Optional MCPClient instance. If None, a new one is created.

    Returns:
        List of MCPToolAdapter instances.
    """
    if client is None:
        client = MCPClient()

    tools: list[BaseTool] = []
    for definition in client.list_tools():
        tools.append(MCPToolAdapter(definition, client))

    return tools
