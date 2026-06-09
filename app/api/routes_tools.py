"""Tool API routes for listing and invoking tools."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.tools.schemas import ToolInvokeRequest, ToolInvokeResponse, ToolListResponse
from app.tools.service import ToolService

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("", response_model=ToolListResponse)
async def list_tools(
    db_session: AsyncSession = Depends(get_db_session),
) -> ToolListResponse:
    """List all available tools."""
    service = ToolService(db_session)
    return service.list_tools()


@router.post("/{tool_name}/invoke", response_model=ToolInvokeResponse)
async def invoke_tool(
    tool_name: str,
    request: ToolInvokeRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> ToolInvokeResponse:
    """Invoke a tool by name.

    Returns 404 if tool not found.
    Returns 200 with status="error" if tool execution fails.
    """
    service = ToolService(db_session)
    result = await service.invoke_tool(tool_name, request.input)

    # If tool not found, return 404
    if result.status == "error" and "not found" in (result.error or "").lower():
        raise HTTPException(status_code=404, detail=result.error)

    return ToolInvokeResponse(
        tool_name=result.tool_name,
        status=result.status,
        output=result.output,
        error=result.error,
        latency_ms=result.latency_ms,
        trace_id=result.trace_id,
    )
