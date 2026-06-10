"""Tool schemas for input/output and API contracts."""

from pydantic import BaseModel, Field


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
