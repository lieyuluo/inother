"""MCP manager for multi-server discovery and invocation."""

from __future__ import annotations

from dataclasses import dataclass

from app.mcp.schemas import MCPToolCallResult, MCPToolDefinition
from app.mcp.server_config import MCPServerConfig, load_mcp_server_configs
from app.mcp.transports import HTTPTransport, InProcessTransport, MCPTransport, StdioTransport
from app.mcp.transports.base import MCPTransportError


@dataclass(frozen=True)
class MCPManagedTool:
    """Tool metadata produced by MCPManager discovery."""

    public_name: str
    server_tool_name: str
    definition: MCPToolDefinition
    server_name: str
    transport: str
    namespace: str
    required_role: str
    alias_for: str | None = None

    @property
    def is_alias(self) -> bool:
        return self.alias_for is not None


class MCPManager:
    """Load MCP servers, discover tools, and route tool calls."""

    def __init__(self, configs: list[MCPServerConfig] | None = None) -> None:
        self.configs = configs if configs is not None else load_mcp_server_configs()
        self._transports: dict[str, MCPTransport] = {}
        self._tools: dict[str, MCPManagedTool] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize enabled transports and discover tools."""
        if self._initialized:
            return
        for config in self.configs:
            if not config.enabled:
                continue
            transport = self._create_transport(config)
            self._transports[config.name] = transport
            try:
                transport.connect()
                for definition in transport.list_tools():
                    self._register_tool(config, definition)
            except Exception:
                # Unavailable servers should not prevent app startup.
                continue
        self._initialized = True

    def list_all_tools(self) -> list[MCPManagedTool]:
        """Return all discovered MCP tools, including compatibility aliases."""
        self.initialize()
        return sorted(self._tools.values(), key=lambda item: item.public_name)

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> MCPToolCallResult:
        """Call a server-local tool."""
        config = self._config_by_name(server_name)
        if config is None:
            return MCPToolCallResult(
                tool_name=tool_name,
                status="error",
                error=f"MCP server '{server_name}' not configured",
            )
        if not config.enabled:
            return MCPToolCallResult(
                tool_name=tool_name,
                status="error",
                error=f"MCP server '{server_name}' is disabled",
            )

        self.initialize()
        transport = self._transports.get(server_name)
        if transport is None:
            return MCPToolCallResult(
                tool_name=tool_name,
                status="error",
                error=f"MCP server '{server_name}' is unavailable",
            )
        return transport.call_tool(tool_name, arguments)

    def call_public_tool(
        self,
        public_name: str,
        arguments: dict[str, object],
    ) -> MCPToolCallResult:
        """Call a discovered namespaced or alias tool name."""
        self.initialize()
        tool = self._tools.get(public_name)
        if tool is None:
            return MCPToolCallResult(
                tool_name=public_name,
                status="error",
                error=f"MCP tool '{public_name}' not found",
            )
        result = self.call_tool(tool.server_name, tool.server_tool_name, arguments)
        result.tool_name = public_name
        return result

    def health_check(self) -> dict[str, MCPToolCallResult]:
        """Return health status for configured servers."""
        self.initialize()
        results: dict[str, MCPToolCallResult] = {}
        for config in self.configs:
            transport = self._transports.get(config.name)
            if not config.enabled:
                results[config.name] = MCPToolCallResult(
                    tool_name="health_check",
                    status="error",
                    error=f"MCP server '{config.name}' is disabled",
                )
            elif transport is None:
                results[config.name] = MCPToolCallResult(
                    tool_name="health_check",
                    status="error",
                    error=f"MCP server '{config.name}' is unavailable",
                )
            else:
                results[config.name] = transport.health_check()
        return results

    def disconnect(self) -> None:
        """Disconnect all transports."""
        for transport in self._transports.values():
            transport.disconnect()
        self._transports.clear()
        self._initialized = False

    def _register_tool(self, config: MCPServerConfig, definition: MCPToolDefinition) -> None:
        namespace = config.namespace or "mcp"
        short_name = _short_tool_name(definition.name)
        public_name = f"{namespace}.{config.name}.{short_name}"
        required_role = _effective_required_role(config.required_role, definition)
        namespaced_definition = definition.model_copy(
            update={
                "name": public_name,
                "required_role": required_role,
                "source_name": definition.name,
            }
        )
        managed = MCPManagedTool(
            public_name=public_name,
            server_tool_name=definition.name,
            definition=namespaced_definition,
            server_name=config.name,
            transport=config.transport,
            namespace=namespace,
            required_role=required_role,
        )
        self._tools[public_name] = managed

        # Backward-compatible aliases are retained for the demo server.
        if config.name == "demo" and definition.name not in self._tools:
            alias_definition = definition.model_copy(
                update={
                    "name": definition.name,
                    "required_role": required_role,
                    "source_name": definition.name,
                }
            )
            self._tools[definition.name] = MCPManagedTool(
                public_name=definition.name,
                server_tool_name=definition.name,
                definition=alias_definition,
                server_name=config.name,
                transport=config.transport,
                namespace=namespace,
                required_role=required_role,
                alias_for=public_name,
            )

    def _create_transport(self, config: MCPServerConfig) -> MCPTransport:
        if config.transport == "in_process":
            return InProcessTransport()
        if config.transport == "stdio":
            if config.command:
                return StdioTransport(config.command, timeout_seconds=config.timeout_seconds)
            return StdioTransport(
                StdioTransport.demo_command(), timeout_seconds=config.timeout_seconds
            )
        if config.transport == "http":
            return HTTPTransport(config.url or "", timeout_seconds=config.timeout_seconds)
        raise MCPTransportError(f"Unsupported MCP transport: {config.transport}")

    def _config_by_name(self, name: str) -> MCPServerConfig | None:
        for config in self.configs:
            if config.name == name:
                return config
        return None


def _short_tool_name(name: str) -> str:
    if name.startswith("mcp_"):
        return name.removeprefix("mcp_")
    if name.startswith("stdio_"):
        return name.removeprefix("stdio_")
    return name


def _effective_required_role(config_role: str, definition: MCPToolDefinition) -> str:
    if config_role == "admin" or definition.required_role == "admin":
        return "admin"
    if definition.name in {"mcp_create_ticket"}:
        return "admin"
    return "user"
