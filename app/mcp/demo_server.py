"""Demo MCP Server with deterministic demo tools.

This server provides 3 demo MCP tools for testing and development:
1. mcp_echo - Echo back input text
2. mcp_get_business_metric - Return demo business metrics
3. mcp_create_ticket - Create a demo ticket

All data is deterministic and does not access external services.
"""

from __future__ import annotations

import hashlib
import time

from app.mcp.schemas import MCPToolCallResult, MCPToolDefinition

# Demo business metrics data (deterministic, no external access)
_DEMO_METRICS: dict[str, dict[str, object]] = {
    "revenue": {"metric": "revenue", "value": 1250000.00, "unit": "USD"},
    "active_users": {"metric": "active_users", "value": 8432, "unit": "users"},
    "tickets": {"metric": "tickets", "value": 156, "unit": "tickets"},
}

# Ticket counter for deterministic ticket IDs
_ticket_counter = 0


class DemoMCPServer:
    """Demo MCP Server with deterministic tools.

    This is an in-process demo server. It does NOT implement MCP transport
    protocol (stdio/HTTP). It can be replaced with a standard MCP server
    in the future.
    """

    def __init__(self) -> None:
        self._tools: dict[str, MCPToolDefinition] = {}
        self._register_demo_tools()

    def _register_demo_tools(self) -> None:
        """Register all demo MCP tools."""
        self._tools["mcp_echo"] = MCPToolDefinition(
            name="mcp_echo",
            description="Echo back the input text. MCP demo tool for testing.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to echo back",
                    },
                },
                "required": ["text"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
            },
        )

        self._tools["mcp_get_business_metric"] = MCPToolDefinition(
            name="mcp_get_business_metric",
            description=(
                "Get a business metric value. "
                "Supported metrics: revenue, active_users, tickets. "
                "MCP demo tool."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "description": "Metric name: revenue, active_users, or tickets",
                    },
                },
                "required": ["metric"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "metric": {"type": "string"},
                    "value": {"type": "number"},
                    "unit": {"type": "string"},
                },
            },
        )

        self._tools["mcp_create_ticket"] = MCPToolDefinition(
            name="mcp_create_ticket",
            description="Create a demo support ticket. MCP demo tool.",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Ticket title",
                    },
                    "description": {
                        "type": "string",
                        "description": "Ticket description",
                    },
                },
                "required": ["title", "description"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "title": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
        )

    def list_tools(self) -> list[MCPToolDefinition]:
        """List all available MCP tools.

        Returns:
            List of MCPToolDefinition objects.
        """
        return list(self._tools.values())

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> MCPToolCallResult:
        """Call an MCP tool by name.

        Args:
            tool_name: Name of the tool to call.
            arguments: Input arguments for the tool.

        Returns:
            MCPToolCallResult with status, output, and metadata.
        """
        start = time.monotonic()

        if tool_name not in self._tools:
            latency_ms = (time.monotonic() - start) * 1000
            return MCPToolCallResult(
                tool_name=tool_name,
                status="error",
                error=f"MCP tool '{tool_name}' not found. Available: {', '.join(sorted(self._tools.keys()))}",
                latency_ms=latency_ms,
            )

        handler = {
            "mcp_echo": self._handle_echo,
            "mcp_get_business_metric": self._handle_get_business_metric,
            "mcp_create_ticket": self._handle_create_ticket,
        }.get(tool_name)

        if handler is None:
            latency_ms = (time.monotonic() - start) * 1000
            return MCPToolCallResult(
                tool_name=tool_name,
                status="error",
                error=f"No handler for MCP tool '{tool_name}'",
                latency_ms=latency_ms,
            )

        try:
            output = handler(arguments)
            latency_ms = (time.monotonic() - start) * 1000
            return MCPToolCallResult(
                tool_name=tool_name,
                status="success",
                output=output,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return MCPToolCallResult(
                tool_name=tool_name,
                status="error",
                error=str(e),
                latency_ms=latency_ms,
            )

    def _handle_echo(self, arguments: dict[str, object]) -> dict[str, object]:
        """Handle mcp_echo tool call."""
        text = arguments.get("text")
        if text is None:
            raise ValueError("Missing required argument: 'text'")
        return {"text": str(text)}

    def _handle_get_business_metric(self, arguments: dict[str, object]) -> dict[str, object]:
        """Handle mcp_get_business_metric tool call."""
        metric = arguments.get("metric")
        if metric is None:
            raise ValueError("Missing required argument: 'metric'")
        metric_key = str(metric).lower().strip()
        if metric_key not in _DEMO_METRICS:
            raise ValueError(
                f"Unsupported metric: '{metric_key}'. "
                f"Supported metrics: {', '.join(sorted(_DEMO_METRICS.keys()))}"
            )
        return dict(_DEMO_METRICS[metric_key])

    def _handle_create_ticket(self, arguments: dict[str, object]) -> dict[str, object]:
        """Handle mcp_create_ticket tool call."""
        title = arguments.get("title")
        description = arguments.get("description")
        if title is None:
            raise ValueError("Missing required argument: 'title'")
        if description is None:
            raise ValueError("Missing required argument: 'description'")

        global _ticket_counter  # noqa: PLW0603
        _ticket_counter += 1
        ticket_id = f"DEMO-TICKET-{_ticket_counter:04d}"

        # Alternative: hash-based deterministic ID
        hash_input = f"{title}:{description}"
        hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:6].upper()
        ticket_id = f"DEMO-{hash_suffix}-{_ticket_counter:04d}"

        return {
            "ticket_id": ticket_id,
            "title": str(title),
            "status": "created",
        }
