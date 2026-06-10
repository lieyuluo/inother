"""Bundled deterministic JSON Lines MCP demo server."""

from __future__ import annotations

import json
import sys
import time

from app.mcp.schemas import MCPToolDefinition


def _tools() -> list[MCPToolDefinition]:
    return [
        MCPToolDefinition(
            name="stdio_echo",
            description="Echo back input text from the stdio demo MCP server.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            output_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        ),
        MCPToolDefinition(
            name="stdio_get_status",
            description="Return deterministic status from the stdio demo MCP server.",
            input_schema={"type": "object", "properties": {}},
            output_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "server": {"type": "string"},
                },
            },
        ),
    ]


def _call_tool(tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
    if tool_name == "stdio_echo":
        return {"text": str(arguments.get("text", ""))}
    if tool_name == "stdio_get_status":
        return {"status": "ok", "server": "demo_stdio"}
    raise ValueError(f"Tool '{tool_name}' not found")


def _handle(request: dict[str, object]) -> dict[str, object]:
    method = request.get("method")
    params = request.get("params", {})
    if not isinstance(params, dict):
        params = {}

    if method == "list_tools":
        return {"status": "success", "tools": [tool.model_dump() for tool in _tools()]}

    if method == "call_tool":
        tool_name = str(params.get("tool_name", ""))
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}
        try:
            output = _call_tool(tool_name, arguments)
            return {"status": "success", "tool_name": tool_name, "output": output}
        except Exception as e:
            return {"status": "error", "tool_name": tool_name, "error": str(e)}

    if method == "health_check":
        return {"status": "success", "output": {"status": "ok", "transport": "stdio"}}

    return {"status": "error", "error": f"Unknown method: {method}"}


def main() -> None:
    """Run the JSON Lines server until stdin closes."""
    for line in sys.stdin:
        start = time.monotonic()
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Request must be an object")
            response = _handle(request)
        except Exception as e:
            response = {"status": "error", "error": str(e)}
        response["latency_ms"] = (time.monotonic() - start) * 1000
        sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
