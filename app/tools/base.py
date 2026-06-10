"""Tool base class and abstract interface."""

from abc import ABC, abstractmethod

from app.tools.schemas import ToolPolicy, ToolResult


class BaseTool(ABC):
    """Abstract base class for all tools.

    Every tool must implement:
    - name: unique identifier
    - description: human-readable description
    - input_schema: JSON schema for input validation
    - invoke: execute the tool with validated input

    Tools must NOT:
    - Directly depend on FastAPI request/response
    - Use eval() or execute arbitrary code
    - Access external network (in v0.2)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable tool description."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, object]:
        """JSON Schema for tool input validation."""
        pass

    @property
    def output_schema(self) -> dict[str, object] | None:
        """Optional JSON Schema for tool output."""
        return None

    @property
    def requires_confirmation(self) -> bool:
        """Whether this tool requires user confirmation before execution."""
        return False

    @property
    def required_role(self) -> str:
        """Minimum role required to invoke this tool."""
        return "user"

    @property
    def enabled(self) -> bool:
        """Whether this tool is enabled."""
        return True

    @property
    def allowed_modes(self) -> list[str]:
        """Invocation modes where this tool can be used."""
        return ["direct", "chat_tool", "react", "plan_execute"]

    @property
    def source(self) -> str:
        """Tool source."""
        return "builtin"

    @property
    def server_name(self) -> str | None:
        """MCP server name when source is mcp."""
        return None

    @property
    def transport(self) -> str | None:
        """MCP transport name when source is mcp."""
        return None

    @property
    def namespaced_tool_name(self) -> str | None:
        """Canonical namespaced tool name for aliases."""
        return None

    @property
    def policy(self) -> ToolPolicy:
        """Runtime policy for this tool."""
        return ToolPolicy(
            required_role=self.required_role,
            enabled=self.enabled,
            requires_confirmation=self.requires_confirmation,
            allowed_modes=self.allowed_modes,
            description=self.description,
        )

    @abstractmethod
    async def invoke(self, input_data: dict[str, object]) -> ToolResult:
        """Execute the tool with validated input.

        Args:
            input_data: Validated input matching input_schema.

        Returns:
            ToolResult with status, output, and metadata.
        """
        pass
