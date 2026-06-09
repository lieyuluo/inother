"""Tool Registry for managing and invoking tools."""

from app.tools.base import BaseTool
from app.tools.schemas import ToolResult


class ToolRegistryError(Exception):
    """Error raised by ToolRegistry operations."""

    pass


class ToolNotFoundError(ToolRegistryError):
    """Error raised when a tool is not found in the registry."""

    pass


class DuplicateToolError(ToolRegistryError):
    """Error raised when attempting to register a tool with a duplicate name."""

    pass


class ToolRegistry:
    """Registry for managing and invoking tools.

    Features:
    - Register tools with unique names
    - List all registered tools
    - Get tool by name
    - Invoke tool by name with input validation
    - Duplicate registration raises error (no silent override)
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register.

        Raises:
            DuplicateToolError: If a tool with the same name already exists.
        """
        if tool.name in self._tools:
            raise DuplicateToolError(
                f"Tool '{tool.name}' is already registered. "
                f"Use a different name or unregister the existing tool first."
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """Get a tool by name.

        Args:
            name: Tool name.

        Returns:
            Tool instance.

        Raises:
            ToolNotFoundError: If tool is not found.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(
                f"Tool '{name}' not found. Available tools: {', '.join(sorted(self._tools.keys())) or '(none)'}"
            )
        return tool

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools.

        Returns:
            List of all registered tool instances, sorted by name.
        """
        return sorted(self._tools.values(), key=lambda t: t.name)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: Tool name.

        Returns:
            True if tool is registered.
        """
        return name in self._tools

    async def invoke(self, name: str, input_data: dict[str, object]) -> ToolResult:
        """Invoke a tool by name.

        Args:
            name: Tool name.
            input_data: Input data for the tool.

        Returns:
            ToolResult from the tool invocation.

        Raises:
            ToolNotFoundError: If tool is not found.
        """
        tool = self.get(name)
        return await tool.invoke(input_data)
