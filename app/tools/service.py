"""Tool service for business logic operations."""

import time
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.repositories import AuditLogRepository
from app.mcp.tool_adapter import create_mcp_tools
from app.tools.base import BaseTool
from app.tools.builtin import create_builtin_tools
from app.tools.registry import ToolNotFoundError, ToolRegistry
from app.tools.schemas import ToolInfo, ToolListResponse, ToolResult


class ToolService:
    """Service for tool management and invocation.

    Responsibilities:
    - List available tools
    - Invoke tools by name
    - Write AuditLog for each invocation
    - Validate tool input against schema
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit_repo = AuditLogRepository(session)
        self.registry = ToolRegistry()
        # Register all builtin tools
        for tool in create_builtin_tools(session):
            self.registry.register(tool)
        # Register MCP demo tools if enabled
        settings = get_settings()
        if settings.mcp_demo_enabled:
            for tool in create_mcp_tools():
                self.registry.register(tool)

    def list_tools(self) -> ToolListResponse:
        """List all registered tools.

        Returns:
            ToolListResponse with tool info list.
        """
        tools = self.registry.list_tools()
        tool_infos = [
            ToolInfo(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                requires_confirmation=tool.requires_confirmation,
            )
            for tool in tools
        ]
        return ToolListResponse(tools=tool_infos, total=len(tool_infos))

    async def invoke_tool(
        self,
        tool_name: str,
        input_data: dict[str, object],
        actor: str = "system",
        session_id: UUID | None = None,
    ) -> ToolResult:
        """Invoke a tool by name and write AuditLog.

        Args:
            tool_name: Name of the tool to invoke.
            input_data: Input data for the tool.
            actor: Actor identifier for audit log.
            session_id: Optional chat session ID for audit log.

        Returns:
            ToolResult from the tool invocation.
        """
        trace_id = str(uuid4())
        start = time.monotonic()

        try:
            tool = self.registry.get(tool_name)
        except ToolNotFoundError:
            latency_ms = (time.monotonic() - start) * 1000
            result = ToolResult(
                tool_name=tool_name,
                status="error",
                error=f"Tool '{tool_name}' not found",
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
            await self._write_audit_log(
                tool_name=tool_name,
                input_data=input_data,
                result=result,
                actor=actor,
                session_id=session_id,
            )
            return result

        # Validate input against tool schema
        validation_error = self._validate_input(tool, input_data)
        if validation_error:
            latency_ms = (time.monotonic() - start) * 1000
            result = ToolResult(
                tool_name=tool_name,
                status="error",
                error=validation_error,
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
            await self._write_audit_log(
                tool_name=tool_name,
                input_data=input_data,
                result=result,
                actor=actor,
                session_id=session_id,
            )
            return result

        # Invoke the tool
        result = await tool.invoke(input_data)
        # Override trace_id with the one we generated for consistency
        result.trace_id = trace_id

        # Write AuditLog
        await self._write_audit_log(
            tool_name=tool_name,
            input_data=input_data,
            result=result,
            actor=actor,
            session_id=session_id,
        )

        return result

    def _validate_input(self, tool: BaseTool, input_data: dict[str, object]) -> str | None:
        """Validate input data against tool schema.

        Args:
            tool: Tool instance.
            input_data: Input data to validate.

        Returns:
            Error message if validation fails, None if valid.
        """
        schema = tool.input_schema
        required_fields: list[str] = schema.get("required", [])  # type: ignore[assignment]
        properties: dict[str, object] = schema.get("properties", {})  # type: ignore[assignment]

        # Check required fields
        for field_name in required_fields:
            if field_name not in input_data or input_data[field_name] is None:
                return f"Missing required field: '{field_name}'"

        # Check that all provided fields are in the schema
        for key in input_data:
            if key not in properties:
                return f"Unknown field: '{key}'"

        return None

    async def _write_audit_log(
        self,
        tool_name: str,
        input_data: dict[str, object],
        result: ToolResult,
        actor: str,
        session_id: UUID | None,  # noqa: ARG002
    ) -> None:
        """Write an audit log entry for a tool invocation.

        Args:
            tool_name: Name of the invoked tool.
            input_data: Input data for the tool.
            result: ToolResult from the invocation.
            actor: Actor identifier.
            session_id: Optional chat session ID.
        """
        metadata = {
            "trace_id": result.trace_id,
            "tool_name": tool_name,
            "input_summary": str(input_data)[:500],
            "status": result.status,
            "latency_ms": result.latency_ms,
        }
        if result.error:
            metadata["error"] = result.error

        await self.audit_repo.create(
            action="tool.invoke",
            actor=actor,
            resource_type="tool",
            resource_id=None,
            metadata=metadata,
            user_id=None,
        )
