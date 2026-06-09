"""Tests for ReAct Agent, Deterministic Planner, Chat mode, and AuditLog."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.react_agent import DeterministicPlanner, ReActAgent
from app.db.models import AuditLog, Document

# ── Deterministic Planner Tests ────────────────────────────────────────


class TestDeterministicPlanner:
    """Tests for the deterministic ReAct planner."""

    def test_arithmetic_selects_calculator(self) -> None:
        tool_name, action_input, thought = DeterministicPlanner.plan("计算 1+2*3")
        assert tool_name == "calculator_tool"
        assert action_input["expression"] == "1+2*3"
        assert "arithmetic" in thought.lower()

    def test_calculate_keyword_selects_calculator(self) -> None:
        tool_name, action_input, _ = DeterministicPlanner.plan("calculate 10/2")
        assert tool_name == "calculator_tool"

    def test_what_is_arithmetic_selects_calculator(self) -> None:
        tool_name, action_input, _ = DeterministicPlanner.plan("what is 5+3")
        assert tool_name == "calculator_tool"

    def test_echo_prefix_selects_echo(self) -> None:
        tool_name, action_input, _ = DeterministicPlanner.plan("echo hello world")
        assert tool_name == "echo_tool"
        assert action_input["text"] == "hello world"

    def test_echo_chinese_prefix_selects_echo(self) -> None:
        tool_name, action_input, _ = DeterministicPlanner.plan("回显 测试文本")
        assert tool_name == "echo_tool"
        assert action_input["text"] == "测试文本"

    def test_system_status_selects_status_tool(self) -> None:
        tool_name, _, _ = DeterministicPlanner.plan("系统状态")
        assert tool_name == "get_system_status_tool"

    def test_system_status_english(self) -> None:
        tool_name, _, _ = DeterministicPlanner.plan("system status")
        assert tool_name == "get_system_status_tool"

    def test_health_keyword(self) -> None:
        tool_name, _, _ = DeterministicPlanner.plan("health check")
        assert tool_name == "get_system_status_tool"

    def test_search_documents_selects_search_tool(self) -> None:
        tool_name, _, _ = DeterministicPlanner.plan("搜索文档 API")
        assert tool_name == "search_documents_tool"

    def test_search_documents_english(self) -> None:
        tool_name, _, _ = DeterministicPlanner.plan("search documents for AI")
        assert tool_name == "search_documents_tool"

    def test_unmatched_falls_back_to_rag(self) -> None:
        tool_name, _, thought = DeterministicPlanner.plan("What is machine learning?")
        assert tool_name is None
        assert "fallback" in thought.lower() or "rag" in thought.lower()

    def test_planner_output_stable(self) -> None:
        """Same input always produces same output."""
        result1 = DeterministicPlanner.plan("计算 1+2")
        result2 = DeterministicPlanner.plan("计算 1+2")
        assert result1 == result2

    def test_invalid_arithmetic_expression_still_selects_calculator(self) -> None:
        """Planner selects calculator, but calculator will handle the error."""
        tool_name, _, _ = DeterministicPlanner.plan("计算 xyz")
        # The planner detects the keyword, calculator handles invalid input
        assert tool_name == "calculator_tool"

    def test_pure_arithmetic_expression(self) -> None:
        """Pure arithmetic expression without keyword prefix."""
        tool_name, _, _ = DeterministicPlanner.plan("2+3*4")
        assert tool_name == "calculator_tool"


# ── ReAct Agent Tests ──────────────────────────────────────────────────


class TestReActAgent:
    """Tests for the ReAct Agent."""

    @pytest.mark.asyncio
    async def test_react_calculator_success(self, async_db_session: AsyncSession) -> None:
        agent = ReActAgent(session=async_db_session)
        result = await agent.query("计算 1+2*3")
        assert result.answer
        assert "7" in result.answer
        assert len(result.steps) >= 1
        assert result.steps[0].tool_name == "calculator_tool"
        assert result.steps[0].status == "success"
        assert not result.used_fallback

    @pytest.mark.asyncio
    async def test_react_echo_success(self, async_db_session: AsyncSession) -> None:
        agent = ReActAgent(session=async_db_session)
        result = await agent.query("echo hello")
        assert "hello" in result.answer
        assert result.steps[0].tool_name == "echo_tool"

    @pytest.mark.asyncio
    async def test_react_system_status_success(self, async_db_session: AsyncSession) -> None:
        agent = ReActAgent(session=async_db_session)
        result = await agent.query("系统状态")
        assert "enterprise-ai-agent" in result.answer
        assert result.steps[0].tool_name == "get_system_status_tool"

    @pytest.mark.asyncio
    async def test_react_search_documents(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,  # noqa: ARG002
    ) -> None:
        agent = ReActAgent(session=async_db_session)
        result = await agent.query("搜索文档 API")
        assert result.steps[0].tool_name == "search_documents_tool"

    @pytest.mark.asyncio
    async def test_react_fallback_to_rag(self, async_db_session: AsyncSession) -> None:
        agent = ReActAgent(session=async_db_session)
        result = await agent.query("What is machine learning?")
        assert result.used_fallback
        assert len(result.steps) >= 1
        assert result.steps[0].action == "fallback_to_rag"

    @pytest.mark.asyncio
    async def test_react_returns_steps(self, async_db_session: AsyncSession) -> None:
        agent = ReActAgent(session=async_db_session)
        result = await agent.query("计算 5+5")
        assert len(result.steps) >= 1
        step = result.steps[0]
        assert step.thought
        assert step.action
        assert step.observation is not None

    @pytest.mark.asyncio
    async def test_steps_contain_thought_action_observation_status(
        self, async_db_session: AsyncSession
    ) -> None:
        agent = ReActAgent(session=async_db_session)
        result = await agent.query("计算 3+4")
        step = result.steps[0]
        assert step.thought
        assert step.action
        assert step.observation is not None
        assert step.status in ("success", "error", "skipped")

    @pytest.mark.asyncio
    async def test_tool_calls_recorded(self, async_db_session: AsyncSession) -> None:
        agent = ReActAgent(session=async_db_session)
        result = await agent.query("计算 1+1")
        assert len(result.tool_calls) >= 1
        assert result.tool_calls[0]["tool_name"] == "calculator_tool"

    @pytest.mark.asyncio
    async def test_trace_id_exists(self, async_db_session: AsyncSession) -> None:
        agent = ReActAgent(session=async_db_session)
        result = await agent.query("计算 2+2")
        assert result.trace_id

    @pytest.mark.asyncio
    async def test_max_steps_effect(self, async_db_session: AsyncSession) -> None:
        agent = ReActAgent(session=async_db_session, max_steps=1)
        result = await agent.query("计算 1+1")
        # With max_steps=1, single tool call should still work
        assert result.answer

    @pytest.mark.asyncio
    async def test_tool_error_captured(self, async_db_session: AsyncSession) -> None:
        agent = ReActAgent(session=async_db_session)
        result = await agent.query("计算 1/0")
        # Calculator should handle division by zero
        assert result.steps[0].status == "error"

    @pytest.mark.asyncio
    async def test_react_writes_audit_log(self, async_db_session: AsyncSession) -> None:
        agent = ReActAgent(session=async_db_session)
        await agent.query("计算 1+1")

        stmt = select(AuditLog).where(AuditLog.action == "react.run")
        db_result = await async_db_session.execute(stmt)
        logs = list(db_result.scalars().all())
        assert len(logs) >= 1
        log = logs[-1]
        assert log.meta["mode"] == "react"
        assert "steps_count" in log.meta
        assert "trace_id" in log.meta

    @pytest.mark.asyncio
    async def test_tool_still_writes_tool_invoke_audit(
        self, async_db_session: AsyncSession
    ) -> None:
        agent = ReActAgent(session=async_db_session)
        await agent.query("计算 1+1")

        stmt = select(AuditLog).where(AuditLog.action == "tool.invoke")
        db_result = await async_db_session.execute(stmt)
        logs = list(db_result.scalars().all())
        assert len(logs) >= 1
        assert logs[-1].meta["tool_name"] == "calculator_tool"


# ── Chat API Mode Tests ────────────────────────────────────────────────


class TestChatModeAPI:
    """Tests for Chat API mode parameter."""

    def test_mode_react_goes_react(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "计算 1+2", "mode": "react"},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["mode"] == "react"
        assert data["steps"] is not None
        assert len(data["steps"]) >= 1
        assert "3" in data["assistant_message"]["content"]

    def test_mode_missing_goes_rag(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What is AI?"},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["mode"] == "rag"
        assert data["steps"] is None

    def test_mode_rag_goes_rag(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What is AI?", "mode": "rag"},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["mode"] == "rag"

    def test_tool_command_priority_over_react(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={
                "content": '/tool echo_tool {"text":"priority test"}',
                "mode": "react",
            },
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        # /tool takes priority over react mode
        assert data["mode"] == "tool"
        assert "priority test" in data["assistant_message"]["content"]

    def test_unsupported_mode_returns_error(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "test", "mode": "invalid_mode"},
        )
        # Should return 400 or 422
        assert msg_resp.status_code in (400, 422)

    def test_response_contains_steps_tool_calls_mode(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "计算 5+5", "mode": "react"},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert "steps" in data
        assert "tool_calls" in data
        assert "mode" in data
        assert data["mode"] == "react"

    def test_assistant_message_metadata_saves_react_trace(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "计算 3+3", "mode": "react"},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["trace_id"]


# ── Compatibility Tests ────────────────────────────────────────────────


class TestReActCompatibility:
    """Verify existing features still work with ReAct additions."""

    def test_health_still_works(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_tool_api_still_works(self, client: TestClient) -> None:
        response = client.get("/api/tools")
        assert response.status_code == 200

    def test_documents_still_works(self, client: TestClient) -> None:
        response = client.get("/api/documents")
        assert response.status_code == 200

    def test_rag_chat_still_works(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]
        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What is AI?"},
        )
        assert msg_resp.status_code == 201
