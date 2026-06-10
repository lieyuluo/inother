"""MCP Tool Adapter for integrating MCP tools into the Tool Registry.

This adapter wraps MCP tools as BaseTool instances, allowing them to be
registered in the existing Tool Registry and invoked through ToolService.
"""

from __future__ import annotations

import time
from uuid import uuid4

from app.mcp.client import MCPClient
from app.mcp.manager import MCPManagedTool, MCPManager
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


class MCPManagerToolAdapter(BaseTool):
    """Adapter for tools discovered by MCPManager."""

    def __init__(self, managed_tool: MCPManagedTool, manager: MCPManager) -> None:
        self._managed_tool = managed_tool
        self._manager = manager

    @property
    def name(self) -> str:
        return self._managed_tool.public_name

    @property
    def description(self) -> str:
        return self._managed_tool.definition.description

    @property
    def input_schema(self) -> dict[str, object]:
        return self._managed_tool.definition.input_schema

    @property
    def output_schema(self) -> dict[str, object] | None:
        return self._managed_tool.definition.output_schema

    @property
    def required_role(self) -> str:
        return self._managed_tool.required_role

    @property
    def source(self) -> str:
        return "mcp"

    @property
    def server_name(self) -> str | None:
        return self._managed_tool.server_name

    @property
    def transport(self) -> str | None:
        return self._managed_tool.transport

    @property
    def namespaced_tool_name(self) -> str | None:
        if self._managed_tool.is_alias:
            return self._managed_tool.alias_for
        return self._managed_tool.public_name

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:
        start = time.monotonic()
        trace_id = str(uuid4())
        mcp_result = self._manager.call_public_tool(self.name, input_data)
        latency_ms = (time.monotonic() - start) * 1000

        if mcp_result.status == "success":
            output = dict(mcp_result.output)
            output["source"] = "mcp"
            output["server_name"] = self._managed_tool.server_name
            output["transport"] = self._managed_tool.transport
            return ToolResult(
                tool_name=self.name,
                status="success",
                output=output,
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
        return ToolResult(
            tool_name=self.name,
            status="error",
            error=mcp_result.error,
            latency_ms=latency_ms,
            trace_id=trace_id,
        )


def create_mcp_tools(
    client: MCPClient | None = None,
    manager: MCPManager | None = None,
) -> list[BaseTool]:
    """Create MCP tool adapters for all demo MCP tools.

    Args:
        client: Optional MCPClient instance. If None, a new one is created.

    Returns:
        List of MCPToolAdapter instances.
    """
    if client is not None:
        return [MCPToolAdapter(definition, client) for definition in client.list_tools()]

    manager = manager or MCPManager()
    tools: list[BaseTool] = [
        MCPManagerToolAdapter(managed_tool, manager) for managed_tool in manager.list_all_tools()
    ]

    return tools
