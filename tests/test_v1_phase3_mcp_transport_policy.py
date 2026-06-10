"""v1.0 Phase 3 tests for MCP transports, manager, namespace, and tool policy."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.db.models import User
from app.db.repositories import AuditLogRepository
from app.mcp.manager import MCPManager
from app.mcp.server_config import MCPServerConfig
from app.mcp.transports.http import HTTPTransport
from app.mcp.transports.in_process import InProcessTransport
from app.mcp.transports.stdio import StdioTransport
from app.tools.base import BaseTool
from app.tools.schemas import ToolResult
from app.tools.service import ToolService


async def _create_user(session: AsyncSession, role: str = "user") -> User:
    user = User(
        id=uuid4(),
        email=f"{role}-{uuid4()}@example.com",
        username=f"{role}_{uuid4().hex[:8]}",
        hashed_password=hash_password("StrongPassword123"),
        is_active=True,
        is_superuser=role == "admin",
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


class DisabledTool(BaseTool):
    @property
    def name(self) -> str:
        return "disabled_demo_tool"

    @property
    def description(self) -> str:
        return "Disabled demo tool"

    @property
    def input_schema(self) -> dict[str, object]:
        return {"type": "object", "properties": {}}

    @property
    def enabled(self) -> bool:
        return False

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:
        _ = input_data
        return ToolResult(tool_name=self.name, status="success", output={})


class ReactOnlyTool(BaseTool):
    @property
    def name(self) -> str:
        return "react_only_demo_tool"

    @property
    def description(self) -> str:
        return "React only demo tool"

    @property
    def input_schema(self) -> dict[str, object]:
        return {"type": "object", "properties": {}}

    @property
    def allowed_modes(self) -> list[str]:
        return ["react"]

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:
        _ = input_data
        return ToolResult(tool_name=self.name, status="success", output={})


class ConfirmationTool(BaseTool):
    @property
    def name(self) -> str:
        return "confirmation_demo_tool"

    @property
    def description(self) -> str:
        return "Confirmation demo tool"

    @property
    def input_schema(self) -> dict[str, object]:
        return {"type": "object", "properties": {}}

    @property
    def requires_confirmation(self) -> bool:
        return True

    async def invoke(self, input_data: dict[str, object]) -> ToolResult:
        _ = input_data
        return ToolResult(tool_name=self.name, status="success", output={})


class TestTransports:
    def test_in_process_transport_list_and_call(self) -> None:
        transport = InProcessTransport()
        tools = transport.list_tools()
        assert any(tool.name == "mcp_echo" for tool in tools)

        result = transport.call_tool("mcp_echo", {"text": "hello"})
        assert result.status == "success"
        assert result.output["text"] == "hello"

    def test_stdio_demo_server_list_and_call(self) -> None:
        transport = StdioTransport(StdioTransport.demo_command(), timeout_seconds=5)
        try:
            tools = transport.list_tools()
            assert any(tool.name == "stdio_echo" for tool in tools)

            result = transport.call_tool("stdio_echo", {"text": "hello"})
            assert result.status == "success"
            assert result.output["text"] == "hello"
        finally:
            transport.disconnect()

    def test_stdio_missing_tool_returns_error(self) -> None:
        transport = StdioTransport(StdioTransport.demo_command(), timeout_seconds=5)
        try:
            result = transport.call_tool("missing_tool", {})
            assert result.status == "error"
            assert "not found" in (result.error or "").lower()
        finally:
            transport.disconnect()

    def test_stdio_timeout_returns_stable_error(self) -> None:
        transport = StdioTransport(
            ["python", "-c", "import time; time.sleep(5)"], timeout_seconds=0.1
        )
        result = transport.call_tool("anything", {})
        assert result.status == "error"
        assert "timed out" in (result.error or "")

    def test_http_transport_placeholder(self) -> None:
        transport = HTTPTransport("http://example.invalid")
        assert transport.list_tools() == []
        result = transport.call_tool("demo", {})
        assert result.status == "error"
        assert "not implemented" in (result.error or "")
        assert transport.health_check().status == "success"


class TestMCPManager:
    def test_manager_loads_demo_and_namespaced_tools(self) -> None:
        manager = MCPManager()
        tools = manager.list_all_tools()
        names = {tool.public_name for tool in tools}
        assert "mcp.demo.echo" in names
        assert "mcp.demo.get_business_metric" in names
        assert "mcp.demo.create_ticket" in names
        assert "mcp_echo" in names

    def test_manager_calls_namespaced_and_alias_tools(self) -> None:
        manager = MCPManager()
        namespaced = manager.call_public_tool("mcp.demo.echo", {"text": "hello"})
        alias = manager.call_public_tool("mcp_echo", {"text": "hello"})
        assert namespaced.status == "success"
        assert alias.status == "success"
        assert namespaced.output["text"] == "hello"

    def test_disabled_server_returns_stable_error(self) -> None:
        manager = MCPManager(
            configs=[
                MCPServerConfig(
                    name="disabled",
                    transport="in_process",
                    enabled=False,
                    namespace="mcp",
                )
            ]
        )
        result = manager.call_tool("disabled", "mcp_echo", {"text": "hello"})
        assert result.status == "error"
        assert "disabled" in (result.error or "")

    def test_stdio_server_metadata(self) -> None:
        manager = MCPManager(
            configs=[
                MCPServerConfig(
                    name="stdio_demo",
                    transport="stdio",
                    enabled=True,
                    namespace="mcp",
                    command=StdioTransport.demo_command(),
                )
            ]
        )
        try:
            tools = manager.list_all_tools()
            stdio_tool = next(tool for tool in tools if tool.public_name == "mcp.stdio_demo.echo")
            assert stdio_tool.server_name == "stdio_demo"
            assert stdio_tool.transport == "stdio"
        finally:
            manager.disconnect()


class TestToolPolicyAndAPI:
    def test_api_tools_include_phase3_metadata(self, client: TestClient) -> None:
        response = client.get("/api/tools")
        assert response.status_code == 200
        tool = next(item for item in response.json()["tools"] if item["name"] == "mcp.demo.echo")
        assert tool["source"] == "mcp"
        assert tool["server_name"] == "demo"
        assert tool["required_role"] == "user"
        assert tool["enabled"] is True

    @pytest.mark.asyncio
    async def test_tool_service_policy_checks(self, async_db_session: AsyncSession) -> None:
        service = ToolService(async_db_session)
        service.registry.register(DisabledTool())
        service.registry.register(ReactOnlyTool())
        service.registry.register(ConfirmationTool())

        disabled = await service.invoke_tool("disabled_demo_tool", {})
        assert disabled.status == "error"
        assert "disabled" in (disabled.error or "")

        wrong_mode = await service.invoke_tool("react_only_demo_tool", {}, mode="direct")
        assert wrong_mode.status == "error"
        assert "not allowed" in (wrong_mode.error or "")

        confirmation = await service.invoke_tool("confirmation_demo_tool", {})
        assert confirmation.status == "error"
        assert "requires confirmation" in (confirmation.error or "")

    @pytest.mark.asyncio
    async def test_mcp_permissions_and_audit_metadata(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
        audit_repo: AuditLogRepository,
    ) -> None:
        user = await _create_user(async_db_session, "user")
        admin = await _create_user(async_db_session, "admin")

        user_result = client.post(
            "/api/tools/mcp.demo.get_business_metric/invoke",
            json={"input": {"metric": "revenue"}},
            headers=_auth(user),
        )
        assert user_result.status_code == 200
        assert user_result.json()["status"] == "success"

        denied = client.post(
            "/api/tools/mcp.demo.create_ticket/invoke",
            json={"input": {"title": "Need help", "description": "Demo"}},
            headers=_auth(user),
        )
        assert denied.status_code == 200
        assert denied.json()["status"] == "error"

        allowed = client.post(
            "/api/tools/mcp.demo.create_ticket/invoke",
            json={"input": {"title": "Need help", "description": "Demo"}},
            headers=_auth(admin),
        )
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "success"

        logs = await audit_repo.list_recent(limit=20)
        matching = [
            log
            for log in logs
            if log.meta
            and log.meta.get("tool_name") == "mcp.demo.get_business_metric"
            and log.meta.get("source") == "mcp"
        ]
        assert matching
        assert matching[0].meta["server_name"] == "demo"
        assert matching[0].meta["transport"] == "in_process"
        assert matching[0].meta["namespaced_tool_name"] == "mcp.demo.get_business_metric"


class TestChatAgentNamespacedMCP:
    def test_chat_tool_namespaced_and_alias_work(self, client: TestClient) -> None:
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        namespaced = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": '/tool mcp.demo.echo {"text":"hello"}'},
        )
        assert namespaced.status_code == 201
        assert "hello" in namespaced.json()["assistant_message"]["content"]

        alias = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": '/tool mcp_echo {"text":"hello"}'},
        )
        assert alias.status_code == 201
        assert "hello" in alias.json()["assistant_message"]["content"]

    def test_plan_execute_namespaced_mcp_tool(self, client: TestClient) -> None:
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={
                "content": '/tool mcp.demo.get_business_metric {"metric":"revenue"}',
                "mode": "plan_execute",
            },
        )
        assert response.status_code == 201
        assert response.json()["tool_calls"][0]["status"] == "success"
