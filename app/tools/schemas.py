"""Tool schemas for input/output and API contracts."""

from pydantic import BaseModel, Field


class ToolPolicy(BaseModel):
    """Runtime policy for invoking a tool."""

    required_role: str = "user"
    enabled: bool = True
    requires_confirmation: bool = False
    allowed_modes: list[str] = Field(
        default_factory=lambda: ["direct", "chat_tool", "react", "plan_execute"]
    )
    description: str = ""


class ToolResult(BaseModel):
    """Result from a tool invocation."""

    tool_name: str
    status: str = Field(description="success or error")
    output: dict[str, object] | None = None
    error: str | None = None
    latency_ms: float = 0.0
    trace_id: str = ""


class ToolInfo(BaseModel):
    """Public info about a registered tool."""

    name: str
    description: str
    input_schema: dict[str, object]
    requires_confirmation: bool = False
    required_role: str = "user"
    source: str = "builtin"
    server_name: str | None = None
    enabled: bool = True
    available: bool = True
    allowed_modes: list[str] = Field(default_factory=list)
    namespaced_tool_name: str | None = None


class ToolListResponse(BaseModel):
    """Response for GET /api/tools."""

    tools: list[ToolInfo]
    total: int


class ToolInvokeRequest(BaseModel):
    """Request for POST /api/tools/{tool_name}/invoke."""

    input: dict[str, object] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    """Response for POST /api/tools/{tool_name}/invoke."""

    tool_name: str
    status: str
    output: dict[str, object] | None = None
    error: str | None = None
    latency_ms: float = 0.0
    trace_id: str = ""
