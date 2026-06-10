"""JSON Lines stdio transport for local MCP demo servers."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from app.mcp.schemas import MCPToolCallResult, MCPToolDefinition
from app.mcp.transports.base import MCPTransportError


class StdioTransport:
    """Transport using subprocess stdin/stdout with one JSON object per line."""

    def __init__(self, command: Sequence[str], timeout_seconds: float = 5.0) -> None:
        self.command = list(command)
        self.timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[str] | None = None

    def connect(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        if not self.command:
            raise MCPTransportError("stdio transport command is required")
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def disconnect(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=1)
        self._process = None

    def list_tools(self) -> list[MCPToolDefinition]:
        response = self._request("list_tools", {})
        if response.get("status") != "success":
            raise MCPTransportError(str(response.get("error") or "stdio list_tools failed"))
        tools_raw = response.get("tools", [])
        if not isinstance(tools_raw, list):
            raise MCPTransportError("stdio list_tools returned invalid tools")
        return [MCPToolDefinition.model_validate(tool) for tool in tools_raw]

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> MCPToolCallResult:
        start = time.monotonic()
        try:
            response = self._request(
                "call_tool",
                {"tool_name": tool_name, "arguments": arguments},
            )
        except Exception as e:
            return MCPToolCallResult(
                tool_name=tool_name,
                status="error",
                error=f"stdio transport error: {e}",
                latency_ms=(time.monotonic() - start) * 1000,
            )

        latency_ms = (time.monotonic() - start) * 1000
        if response.get("status") == "success":
            output = response.get("output", {})
            return MCPToolCallResult(
                tool_name=str(response.get("tool_name", tool_name)),
                status="success",
                output=output if isinstance(output, dict) else {},
                latency_ms=latency_ms,
            )
        return MCPToolCallResult(
            tool_name=tool_name,
            status="error",
            error=str(response.get("error") or "stdio tool call failed"),
            latency_ms=latency_ms,
        )

    def health_check(self) -> MCPToolCallResult:
        start = time.monotonic()
        try:
            self.connect()
            return MCPToolCallResult(
                tool_name="health_check",
                status="success",
                output={"status": "connected", "transport": "stdio"},
                latency_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as e:
            return MCPToolCallResult(
                tool_name="health_check",
                status="error",
                error=str(e),
                latency_ms=(time.monotonic() - start) * 1000,
            )

    @classmethod
    def demo_command(cls) -> list[str]:
        """Return the command for the bundled demo stdio server."""
        return [sys.executable, "-m", "app.mcp.demo_stdio_server"]

    def _request(self, method: str, params: dict[str, object]) -> dict[str, object]:
        self.connect()
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise MCPTransportError("stdio process is not connected")
        if process.poll() is not None:
            raise MCPTransportError("stdio process exited")

        payload = json.dumps({"method": method, "params": params}, ensure_ascii=True)
        process.stdin.write(payload + "\n")
        process.stdin.flush()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(process.stdout.readline)
            try:
                line = future.result(timeout=self.timeout_seconds)
            except TimeoutError as e:
                self.disconnect()
                raise MCPTransportError("stdio request timed out") from e

        if not line:
            raise MCPTransportError("stdio process exited")

        try:
            response = json.loads(line)
        except json.JSONDecodeError as e:
            raise MCPTransportError(f"invalid stdio JSON response: {e}") from e
        if not isinstance(response, dict):
            raise MCPTransportError("stdio response must be an object")
        return response
