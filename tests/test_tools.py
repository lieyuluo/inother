"""Tests for Tool Registry, Builtin Tools, Tool API, and Chat /tool calling."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Document
from app.tools.base import BaseTool
from app.tools.builtin import CalculatorTool, EchoTool, GetSystemStatusTool
from app.tools.registry import DuplicateToolError, ToolNotFoundError, ToolRegistry
from app.tools.schemas import ToolResult

# ── Tool Abstraction / Registry Tests ──────────────────────────────────


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_tool_success(self) -> None:
        registry = ToolRegistry()
        tool = EchoTool()
        registry.register(tool)
        assert registry.has_tool("echo_tool")

    def test_list_tools_success(self) -> None:
        registry = ToolRegistry()
        tool = EchoTool()
        registry.register(tool)
        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "echo_tool"

    def test_get_tool_success(self) -> None:
        registry = ToolRegistry()
        tool = EchoTool()
        registry.register(tool)
        retrieved = registry.get("echo_tool")
        assert retrieved.name == "echo_tool"

    def test_duplicate_registration_raises_error(self) -> None:
        registry = ToolRegistry()
        tool = EchoTool()
        registry.register(tool)
        with pytest.raises(DuplicateToolError):
            registry.register(EchoTool())

    def test_not_found_tool_raises_error(self) -> None:
        registry = ToolRegistry()
        with pytest.raises(ToolNotFoundError):
            registry.get("nonexistent_tool")

    @pytest.mark.asyncio
    async def test_invoke_tool_success(self) -> None:
        registry = ToolRegistry()
        tool = EchoTool()
        registry.register(tool)
        result = await registry.invoke("echo_tool", {"text": "hello"})
        assert result.status == "success"
        assert result.output == {"text": "hello"}

    @pytest.mark.asyncio
    async def test_invoke_nonexistent_tool_raises_error(self) -> None:
        registry = ToolRegistry()
        with pytest.raises(ToolNotFoundError):
            await registry.invoke("nonexistent_tool", {})


class FakeFailingTool(BaseTool):
    """A tool that always raises an exception."""

    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "Always fails"

    @property
    def input_schema(self) -> dict[str, object]:
        return {"type": "object", "properties": {}}

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:  # noqa: ARG002
        raise RuntimeError("Tool failed unexpectedly")


class TestToolExceptionHandling:
    """Tests that tool exceptions are properly handled."""

    @pytest.mark.asyncio
    async def test_tool_exception_not_caught_by_registry(self) -> None:
        """Tool exceptions propagate up - the service layer catches them."""
        registry = ToolRegistry()
        tool = FakeFailingTool()
        registry.register(tool)
        with pytest.raises(RuntimeError, match="Tool failed unexpectedly"):
            await registry.invoke("failing_tool", {})


# ── Builtin Tools Tests ─────────────────────────────────────────────────


class TestEchoTool:
    """Tests for EchoTool."""

    @pytest.mark.asyncio
    async def test_echo_returns_input(self) -> None:
        tool = EchoTool()
        result = await tool.invoke({"text": "hello"})
        assert result.status == "success"
        assert result.output == {"text": "hello"}

    @pytest.mark.asyncio
    async def test_echo_has_name(self) -> None:
        tool = EchoTool()
        assert tool.name == "echo_tool"

    @pytest.mark.asyncio
    async def test_echo_has_description(self) -> None:
        tool = EchoTool()
        assert tool.description


class TestCalculatorTool:
    """Tests for CalculatorTool."""

    @pytest.mark.asyncio
    async def test_basic_addition(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "1+2"})
        assert result.status == "success"
        assert result.output["result"] == 3

    @pytest.mark.asyncio
    async def test_basic_multiplication(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "2*3"})
        assert result.status == "success"
        assert result.output["result"] == 6

    @pytest.mark.asyncio
    async def test_complex_expression(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "1+2*3"})
        assert result.status == "success"
        assert result.output["result"] == 7

    @pytest.mark.asyncio
    async def test_power_expression(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "2**3"})
        assert result.status == "success"
        assert result.output["result"] == 8

    @pytest.mark.asyncio
    async def test_rejects_import(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "__import__('os')"})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_rejects_function_call(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "print(1)"})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_rejects_attribute_access(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "1 .__class__"})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_rejects_name_access(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "x + 1"})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_rejects_long_expression(self) -> None:
        tool = CalculatorTool()
        long_expr = "1" + "+1" * 150  # > 200 chars
        result = await tool.invoke({"expression": long_expr})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_division_by_zero(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "1/0"})
        assert result.status == "error"
        assert "zero" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_expression(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": ""})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_modulo(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "10%3"})
        assert result.status == "success"
        assert result.output["result"] == 1

    @pytest.mark.asyncio
    async def test_negative_number(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "-5+3"})
        assert result.status == "success"
        assert result.output["result"] == -2

    @pytest.mark.asyncio
    async def test_float_division(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "7/2"})
        assert result.status == "success"
        assert result.output["result"] == 3.5


class TestGetSystemStatusTool:
    """Tests for GetSystemStatusTool."""

    @pytest.mark.asyncio
    async def test_returns_service_info(self) -> None:
        tool = GetSystemStatusTool()
        result = await tool.invoke({})
        assert result.status == "success"
        assert result.output["service"] == "enterprise-ai-agent"
        assert "version" in result.output
        assert result.output["status"] == "ok"

    @pytest.mark.asyncio
    async def test_returns_environment(self) -> None:
        tool = GetSystemStatusTool()
        result = await tool.invoke({})
        assert "environment" in result.output


class TestSearchDocumentsTool:
    """Tests for SearchDocumentsTool."""

    @pytest.mark.asyncio
    async def test_returns_ready_documents(
        self, async_db_session: AsyncSession, ready_document: Document  # noqa: ARG002
    ) -> None:
        from app.tools.builtin import SearchDocumentsTool

        tool = SearchDocumentsTool(async_db_session)
        result = await tool.invoke({"query": "API endpoints"})
        assert result.status == "success"
        assert result.output["count"] >= 1

    @pytest.mark.asyncio
    async def test_excludes_deleted_documents(
        self, async_db_session: AsyncSession, deleted_document: Document  # noqa: ARG002
    ) -> None:
        from app.tools.builtin import SearchDocumentsTool

        tool = SearchDocumentsTool(async_db_session)
        result = await tool.invoke({"query": "deleted content"})
        assert result.status == "success"
        # Deleted document should not appear in results
        for r in result.output.get("results", []):
            assert r["document_id"] != str(deleted_document.id)


# ── Tool API Tests ──────────────────────────────────────────────────────


class TestToolAPI:
    """Tests for Tool API endpoints."""

    def test_list_tools(self, client: TestClient) -> None:
        response = client.get("/api/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "total" in data
        assert data["total"] >= 4
        tool_names = [t["name"] for t in data["tools"]]
        assert "echo_tool" in tool_names
        assert "calculator_tool" in tool_names
        assert "get_system_status_tool" in tool_names
        assert "search_documents_tool" in tool_names

    def test_invoke_echo_tool(self, client: TestClient) -> None:
        response = client.post(
            "/api/tools/echo_tool/invoke",
            json={"input": {"text": "hello"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["output"]["text"] == "hello"
        assert data["tool_name"] == "echo_tool"
        assert data["trace_id"]

    def test_invoke_calculator_tool(self, client: TestClient) -> None:
        response = client.post(
            "/api/tools/calculator_tool/invoke",
            json={"input": {"expression": "1+2"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["output"]["result"] == 3

    def test_invoke_nonexistent_tool_returns_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/tools/nonexistent_tool/invoke",
            json={"input": {}},
        )
        assert response.status_code == 404

    def test_invoke_tool_missing_required_field(self, client: TestClient) -> None:
        """Missing required field returns error status (not 422)."""
        response = client.post(
            "/api/tools/echo_tool/invoke",
            json={"input": {}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "text" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_tool_invoke_writes_audit_log(
        self, async_db_session: AsyncSession, client: TestClient
    ) -> None:
        from sqlalchemy import select

        response = client.post(
            "/api/tools/echo_tool/invoke",
            json={"input": {"text": "audit test"}},
        )
        assert response.status_code == 200

        # Check audit log using async session
        stmt = select(AuditLog).where(AuditLog.action == "tool.invoke")
        result = await async_db_session.execute(stmt)
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        log = logs[-1]
        assert log.resource_type == "tool"
        assert log.meta["tool_name"] == "echo_tool"
        assert log.meta["status"] == "success"


# ── Chat /tool Calling Tests ────────────────────────────────────────────


class TestChatToolCalling:
    """Tests for /tool command in chat."""

    def test_tool_echo_in_chat(self, client: TestClient) -> None:
        # Create session (returns 201)
        session_resp = client.post("/api/chat/sessions", json={})
        assert session_resp.status_code == 201
        session_id = session_resp.json()["id"]

        # Send /tool command (returns 201)
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": '/tool echo_tool {"text":"hello"}'},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert "hello" in data["assistant_message"]["content"]
        assert data["citations"] == []
        assert data["trace_id"]

    def test_tool_calculator_in_chat(self, client: TestClient) -> None:
        # Create session
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        # Send /tool command
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": '/tool calculator_tool {"expression":"1+2"}'},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert "3" in data["assistant_message"]["content"]
        assert data["citations"] == []

    def test_normal_message_still_uses_rag(self, client: TestClient) -> None:
        # Create session
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        # Send normal message
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What is AI?"},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        # Should have RAG response (fallback since no documents)
        assert data["assistant_message"]["content"]

    def test_tool_call_saves_metadata(self, client: TestClient) -> None:
        # Create session
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        # Send /tool command
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": '/tool echo_tool {"text":"test"}'},
        )
        assert msg_resp.status_code == 201

    def test_tool_call_citations_empty(self, client: TestClient) -> None:
        # Create session
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        # Send /tool command
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": '/tool get_system_status_tool {}'},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["citations"] == []

    def test_invalid_tool_format_returns_rag(self, client: TestClient) -> None:
        """If /tool format is invalid, it falls through to RAG."""
        # Create session
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        # Send malformed /tool command (no JSON)
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "/tool echo_tool not_json"},
        )
        # Should still get a response (falls through to RAG)
        assert msg_resp.status_code == 201


# ── Compatibility Tests ─────────────────────────────────────────────────


class TestToolCompatibility:
    """Verify existing features still work with tool additions."""

    def test_health_still_works(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_chat_session_still_works(self, client: TestClient) -> None:
        response = client.post("/api/chat/sessions", json={})
        assert response.status_code == 201

    def test_documents_still_works(self, client: TestClient) -> None:
        response = client.get("/api/documents")
        assert response.status_code == 200
