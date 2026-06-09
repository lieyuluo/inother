"""Tests for MCP integration: server, client, adapter, registry, Chat, ReAct, Plan-Execute."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.plan_execute_agent import DeterministicPlanPlanner
from app.agents.react_agent import DeterministicPlanner
from app.db.models import AuditLog
from app.mcp.client import MCPClient
from app.mcp.demo_server import DemoMCPServer
from app.mcp.tool_adapter import create_mcp_tools
from app.tools.service import ToolService

# ── MCP Server Tests ───────────────────────────────────────────────────


class TestDemoMCPServer:
    """Tests for the DemoMCPServer."""

    def test_list_tools_returns_demo_tools(self) -> None:
        server = DemoMCPServer()
        tools = server.list_tools()
        assert len(tools) >= 3
        names = [t.name for t in tools]
        assert "mcp_echo" in names
        assert "mcp_get_business_metric" in names
        assert "mcp_create_ticket" in names

    def test_mcp_echo_success(self) -> None:
        server = DemoMCPServer()
        result = server.call_tool("mcp_echo", {"text": "hello"})
        assert result.status == "success"
        assert result.output["text"] == "hello"

    def test_mcp_get_business_metric_revenue(self) -> None:
        server = DemoMCPServer()
        result = server.call_tool("mcp_get_business_metric", {"metric": "revenue"})
        assert result.status == "success"
        assert result.output["metric"] == "revenue"
        assert result.output["value"] == 1250000.00

    def test_mcp_get_business_metric_active_users(self) -> None:
        server = DemoMCPServer()
        result = server.call_tool("mcp_get_business_metric", {"metric": "active_users"})
        assert result.status == "success"
        assert result.output["metric"] == "active_users"
        assert result.output["value"] == 8432

    def test_mcp_get_business_metric_unsupported_returns_error(self) -> None:
        server = DemoMCPServer()
        result = server.call_tool("mcp_get_business_metric", {"metric": "unknown_metric"})
        assert result.status == "error"
        assert "unsupported" in result.error.lower() or "not found" in result.error.lower() or "unsupported" in result.error.lower()

    def test_mcp_create_ticket_success(self) -> None:
        server = DemoMCPServer()
        result = server.call_tool("mcp_create_ticket", {"title": "Test", "description": "Test desc"})
        assert result.status == "success"
        assert "ticket_id" in result.output
        assert result.output["title"] == "Test"
        assert result.output["status"] == "created"

    def test_nonexistent_tool_returns_error(self) -> None:
        server = DemoMCPServer()
        result = server.call_tool("nonexistent_tool", {})
        assert result.status == "error"
        assert "not found" in result.error.lower()

    def test_invalid_schema_returns_error(self) -> None:
        server = DemoMCPServer()
        result = server.call_tool("mcp_echo", {})
        assert result.status == "error"
        assert "missing" in result.error.lower()


# ── MCP Client Tests ───────────────────────────────────────────────────


class TestMCPClient:
    """Tests for the MCPClient."""

    def test_list_tools_success(self) -> None:
        client = MCPClient()
        tools = client.list_tools()
        assert len(tools) >= 3

    def test_call_tool_success(self) -> None:
        client = MCPClient()
        result = client.call_tool("mcp_echo", {"text": "hello"})
        assert result.status == "success"

    def test_call_tool_captures_server_error(self) -> None:
        client = MCPClient()
        result = client.call_tool("nonexistent_tool", {})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_connect_disconnect(self) -> None:
        client = MCPClient()
        await client.connect()
        await client.disconnect()


# ── MCP Adapter / Tool Registry Tests ──────────────────────────────────


class TestMCPAdapterAndRegistry:
    """Tests for MCPToolAdapter and Tool Registry integration."""

    def test_mcp_adapter_exposes_name_description_schema(self) -> None:
        client = MCPClient()
        tools = create_mcp_tools(client)
        mcp_echo = next(t for t in tools if t.name == "mcp_echo")
        assert mcp_echo.name == "mcp_echo"
        assert mcp_echo.description
        assert mcp_echo.input_schema

    @pytest.mark.asyncio
    async def test_mcp_adapter_invoke_success(self) -> None:
        client = MCPClient()
        tools = create_mcp_tools(client)
        mcp_echo = next(t for t in tools if t.name == "mcp_echo")
        result = await mcp_echo.invoke({"text": "hello"})
        assert result.status == "success"
        assert result.output is not None
        assert result.output.get("text") == "hello"
        assert result.output.get("source") == "mcp"

    def test_tool_registry_contains_mcp_tools(self, async_db_session: AsyncSession) -> None:
        service = ToolService(async_db_session)
        tool_names = [t.name for t in service.registry.list_tools()]
        assert "mcp_echo" in tool_names
        assert "mcp_get_business_metric" in tool_names
        assert "mcp_create_ticket" in tool_names

    def test_get_api_tools_returns_mcp_tools(self, client: TestClient) -> None:
        response = client.get("/api/tools")
        assert response.status_code == 200
        data = response.json()
        tool_names = [t["name"] for t in data["tools"]]
        assert "mcp_echo" in tool_names
        assert "mcp_get_business_metric" in tool_names
        assert "mcp_create_ticket" in tool_names

    def test_post_mcp_echo_invoke(self, client: TestClient) -> None:
        response = client.post(
            "/api/tools/mcp_echo/invoke",
            json={"input": {"text": "hello mcp"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["output"]["text"] == "hello mcp"

    def test_post_mcp_get_business_metric_invoke(self, client: TestClient) -> None:
        response = client.post(
            "/api/tools/mcp_get_business_metric/invoke",
            json={"input": {"metric": "revenue"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["output"]["metric"] == "revenue"

    def test_post_mcp_create_ticket_invoke(self, client: TestClient) -> None:
        response = client.post(
            "/api/tools/mcp_create_ticket/invoke",
            json={"input": {"title": "Test ticket", "description": "Test description"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "ticket_id" in data["output"]

    @pytest.mark.asyncio
    async def test_mcp_tool_invoke_writes_audit_log(self, async_db_session: AsyncSession) -> None:
        service = ToolService(async_db_session)
        await service.invoke_tool("mcp_echo", {"text": "audit test"}, actor="test")

        stmt = select(AuditLog).where(AuditLog.action == "tool.invoke")
        result = await async_db_session.execute(stmt)
        logs = list(result.scalars().all())
        mcp_logs = [log for log in logs if log.meta.get("tool_name") == "mcp_echo"]
        assert len(mcp_logs) >= 1


# ── Chat /tool Tests ───────────────────────────────────────────────────


class TestChatMCPTool:
    """Tests for Chat /tool with MCP tools."""

    def test_tool_mcp_echo(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": '/tool mcp_echo {"text":"hello"}'},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert "hello" in data["assistant_message"]["content"]

    def test_tool_mcp_get_business_metric(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": '/tool mcp_get_business_metric {"metric":"revenue"}'},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert "revenue" in data["assistant_message"]["content"].lower()

    def test_tool_mcp_create_ticket(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": '/tool mcp_create_ticket {"title":"Bug","description":"Fix it"}'},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert "ticket" in data["assistant_message"]["content"].lower() or "created" in data["assistant_message"]["content"].lower()

    def test_assistant_metadata_saves_tool_call(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": '/tool mcp_echo {"text":"meta test"}'},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["trace_id"]


# ── ReAct MCP Tests ────────────────────────────────────────────────────


class TestReActMCP:
    """Tests for ReAct planner with MCP tools."""

    def test_react_business_metric_calls_mcp(self) -> None:
        tool_name, action_input, thought = DeterministicPlanner.plan("查询 revenue 业务指标")
        assert tool_name == "mcp_get_business_metric"
        assert action_input["metric"] == "revenue"

    def test_react_create_ticket_calls_mcp(self) -> None:
        tool_name, action_input, thought = DeterministicPlanner.plan("创建工单")
        assert tool_name == "mcp_create_ticket"

    def test_react_mcp_echo(self) -> None:
        tool_name, action_input, thought = DeterministicPlanner.plan("mcp echo hello")
        assert tool_name == "mcp_echo"
        assert action_input["text"] == "hello"


# ── Plan-and-Execute MCP Tests ─────────────────────────────────────────


class TestPlanExecuteMCP:
    """Tests for Plan-and-Execute planner with MCP tools."""

    def test_metric_then_ticket_plan(self) -> None:
        plan = DeterministicPlanPlanner.plan("请先查看业务指标，再创建工单")
        tool_names = [s.tool_name for s in plan if s.tool_name]
        assert "mcp_get_business_metric" in tool_names
        assert "mcp_create_ticket" in tool_names
        assert plan[-1].action_type == "final"

    def test_business_metric_report_plan(self) -> None:
        plan = DeterministicPlanPlanner.plan("生成业务指标报告")
        tool_names = [s.tool_name for s in plan if s.tool_name]
        assert "mcp_get_business_metric" in tool_names
        assert plan[-1].action_type == "final"

    def test_plan_step_results_contain_mcp_tool_names(self) -> None:
        plan = DeterministicPlanPlanner.plan("请先查看业务指标，再创建工单")
        tool_names = [s.tool_name for s in plan if s.tool_name]
        assert any("mcp_" in name for name in tool_names if name)


# ── Compatibility Tests ────────────────────────────────────────────────


class TestMCPCompatibility:
    """Verify existing features still work with MCP additions."""

    def test_health_still_works(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_rag_chat_still_works(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What is AI?"},
        )
        assert msg_resp.status_code == 201

    def test_builtin_tools_still_work(self, client: TestClient) -> None:
        response = client.get("/api/tools")
        assert response.status_code == 200
        tool_names = [t["name"] for t in response.json()["tools"]]
        assert "echo_tool" in tool_names
        assert "calculator_tool" in tool_names

    def test_react_still_works(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "计算 1+2", "mode": "react"},
        )
        assert msg_resp.status_code == 201

    def test_plan_execute_still_works(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "计算 1+2", "mode": "plan_execute"},
        )
        assert msg_resp.status_code == 201
