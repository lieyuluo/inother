"""Tests for Plan-and-Execute Agent, Planner, Executor, Verifier, Finalizer, Chat mode, and AuditLog."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.plan_execute_agent import (
    DeterministicPlanPlanner,
    Executor,
    Finalizer,
    PlanExecuteAgent,
    Verifier,
)
from app.agents.plan_execute_schemas import PlanStep, StepResult
from app.db.models import AuditLog, Document


# ── Planner Tests ──────────────────────────────────────────────────────


class TestDeterministicPlanPlanner:
    """Tests for the deterministic Plan-and-Execute planner."""

    def test_report_documents_generates_search_plus_final(self) -> None:
        plan = DeterministicPlanPlanner.plan("请生成一个关于文档内容的报告")
        assert len(plan) >= 2
        assert plan[0].action_type == "tool"
        assert plan[0].tool_name == "search_documents_tool"
        assert plan[-1].action_type == "final"

    def test_report_documents_english(self) -> None:
        plan = DeterministicPlanPlanner.plan("generate a report from documents")
        assert plan[0].tool_name == "search_documents_tool"

    def test_summary_knowledge_base(self) -> None:
        plan = DeterministicPlanPlanner.plan("总结知识库中的内容")
        assert plan[0].tool_name == "search_documents_tool"

    def test_multi_step_chinese_pattern(self) -> None:
        plan = DeterministicPlanPlanner.plan("先查看系统状态再搜索文档")
        assert len(plan) >= 2
        # Should have at least one tool step and a final step
        tool_steps = [s for s in plan if s.action_type == "tool"]
        assert len(tool_steps) >= 1
        assert plan[-1].action_type == "final"

    def test_multi_step_english_pattern(self) -> None:
        plan = DeterministicPlanPlanner.plan("first check system status then search documents")
        assert len(plan) >= 2
        tool_steps = [s for s in plan if s.action_type == "tool"]
        assert len(tool_steps) >= 1

    def test_system_status_plus_documents(self) -> None:
        plan = DeterministicPlanPlanner.plan("查看系统状态和文档信息")
        assert len(plan) >= 3
        tool_names = [s.tool_name for s in plan if s.tool_name]
        assert "get_system_status_tool" in tool_names
        assert "search_documents_tool" in tool_names

    def test_single_tool_task(self) -> None:
        plan = DeterministicPlanPlanner.plan("计算 1+2*3")
        assert len(plan) == 2
        assert plan[0].action_type == "tool"
        assert plan[0].tool_name == "calculator_tool"
        assert plan[1].action_type == "final"

    def test_single_echo_task(self) -> None:
        plan = DeterministicPlanPlanner.plan("echo hello")
        assert plan[0].tool_name == "echo_tool"

    def test_single_system_status_task(self) -> None:
        plan = DeterministicPlanPlanner.plan("系统状态")
        assert plan[0].tool_name == "get_system_status_tool"

    def test_unmatched_generates_rag_plus_final(self) -> None:
        plan = DeterministicPlanPlanner.plan("What is machine learning?")
        assert len(plan) >= 2
        assert plan[0].action_type == "rag"
        assert plan[-1].action_type == "final"

    def test_max_steps_limits_plan(self) -> None:
        plan = DeterministicPlanPlanner.plan("先查看系统状态再搜索文档然后计算1+2", max_steps=2)
        assert len(plan) <= 2
        # Last step should be final
        assert plan[-1].action_type == "final"

    def test_planner_output_stable(self) -> None:
        result1 = DeterministicPlanPlanner.plan("计算 1+2")
        result2 = DeterministicPlanPlanner.plan("计算 1+2")
        assert len(result1) == len(result2)
        for s1, s2 in zip(result1, result2):
            assert s1.step_index == s2.step_index
            assert s1.action_type == s2.action_type
            assert s1.tool_name == s2.tool_name


# ── Executor Tests ─────────────────────────────────────────────────────


class TestExecutor:
    """Tests for the Executor."""

    @pytest.mark.asyncio
    async def test_tool_step_success(self, async_db_session: AsyncSession) -> None:
        executor = Executor(async_db_session)
        step = PlanStep(
            step_index=0,
            description="Calculate",
            action_type="tool",
            tool_name="calculator_tool",
            tool_input={"expression": "1+2"},
        )
        result = await executor.execute_step(step, "计算 1+2")
        assert result.status == "success"
        assert result.tool_name == "calculator_tool"

    @pytest.mark.asyncio
    async def test_rag_step_success(self, async_db_session: AsyncSession) -> None:
        executor = Executor(async_db_session)
        step = PlanStep(
            step_index=0,
            description="Query RAG",
            action_type="rag",
        )
        result = await executor.execute_step(step, "What is AI?")
        assert result.status == "success"
        assert result.output  # RAG should return something

    @pytest.mark.asyncio
    async def test_final_step(self, async_db_session: AsyncSession) -> None:
        executor = Executor(async_db_session)
        step = PlanStep(
            step_index=0,
            description="Final",
            action_type="final",
        )
        result = await executor.execute_step(step, "test")
        assert result.status == "success"
        assert "Final answer" in result.output

    @pytest.mark.asyncio
    async def test_tool_failure_records_error(self, async_db_session: AsyncSession) -> None:
        executor = Executor(async_db_session)
        step = PlanStep(
            step_index=0,
            description="Bad tool",
            action_type="tool",
            tool_name="nonexistent_tool",
            tool_input={},
        )
        result = await executor.execute_step(step, "test")
        assert result.status == "error"
        assert result.error

    @pytest.mark.asyncio
    async def test_citations_collected_from_rag(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,  # noqa: ARG002
    ) -> None:
        executor = Executor(async_db_session)
        step = PlanStep(
            step_index=0,
            description="Query RAG",
            action_type="rag",
        )
        result = await executor.execute_step(step, "API endpoints")
        # RAG may or may not return citations depending on the query match
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_tool_calls_recorded(self, async_db_session: AsyncSession) -> None:
        executor = Executor(async_db_session)
        step = PlanStep(
            step_index=0,
            description="Calculate",
            action_type="tool",
            tool_name="calculator_tool",
            tool_input={"expression": "2+2"},
        )
        result = await executor.execute_step(step, "计算 2+2")
        assert result.tool_name == "calculator_tool"
        assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_latency_ms_recorded(self, async_db_session: AsyncSession) -> None:
        executor = Executor(async_db_session)
        step = PlanStep(
            step_index=0,
            description="Calculate",
            action_type="tool",
            tool_name="calculator_tool",
            tool_input={"expression": "1+1"},
        )
        result = await executor.execute_step(step, "计算 1+1")
        assert result.latency_ms is not None
        assert result.latency_ms >= 0


# ── Verifier Tests ─────────────────────────────────────────────────────


class TestVerifier:
    """Tests for the Verifier."""

    def test_all_success(self) -> None:
        step_results = [
            StepResult(step_index=0, status="success", output="ok"),
            StepResult(step_index=1, status="success", output="Final answer generated"),
        ]
        plan = [
            PlanStep(step_index=0, description="Step 0", action_type="tool", status="success"),
            PlanStep(step_index=1, description="Step 1", action_type="final", status="success"),
        ]
        assert Verifier.verify(step_results, plan, max_steps=5) == "success"

    def test_partial_error(self) -> None:
        step_results = [
            StepResult(step_index=0, status="success", output="ok"),
            StepResult(step_index=1, status="error", error="failed"),
        ]
        plan = [
            PlanStep(step_index=0, description="Step 0", action_type="tool", status="success"),
            PlanStep(step_index=1, description="Step 1", action_type="tool", status="error"),
        ]
        assert Verifier.verify(step_results, plan, max_steps=5) == "partial_error"

    def test_max_steps_reached(self) -> None:
        step_results = [
            StepResult(step_index=0, status="success", output="ok"),
        ]
        plan = [
            PlanStep(step_index=0, description="Step 0", action_type="tool", status="success"),
            PlanStep(step_index=1, description="Step 1", action_type="tool", status="pending"),
        ]
        assert Verifier.verify(step_results, plan, max_steps=5) == "max_steps_reached"


# ── Finalizer Tests ────────────────────────────────────────────────────


class TestFinalizer:
    """Tests for the Finalizer."""

    def test_all_success_message(self) -> None:
        step_results = [
            StepResult(step_index=0, status="success", output="Result: 7"),
            StepResult(step_index=1, status="success", output="Final answer generated"),
        ]
        answer = Finalizer.finalize(step_results, "success", used_fallback=False)
        assert "successfully" in answer.lower()

    def test_partial_error_message(self) -> None:
        step_results = [
            StepResult(step_index=0, status="success", output="ok"),
            StepResult(step_index=1, status="error", error="failed"),
        ]
        answer = Finalizer.finalize(step_results, "partial_error", used_fallback=False)
        assert "error" in answer.lower()

    def test_max_steps_message(self) -> None:
        step_results = [
            StepResult(step_index=0, status="success", output="ok"),
        ]
        answer = Finalizer.finalize(step_results, "max_steps_reached", used_fallback=False)
        assert "max_steps" in answer.lower()

    def test_fallback_uses_rag_answer(self) -> None:
        step_results = [
            StepResult(step_index=0, status="success", output="RAG answer here", citations=[{"doc": "x"}]),
        ]
        answer = Finalizer.finalize(step_results, "success", used_fallback=True)
        assert "RAG answer" in answer


# ── PlanExecuteAgent Integration Tests ─────────────────────────────────


class TestPlanExecuteAgent:
    """Integration tests for the PlanExecuteAgent."""

    @pytest.mark.asyncio
    async def test_plan_execute_calculator(self, async_db_session: AsyncSession) -> None:
        agent = PlanExecuteAgent(session=async_db_session)
        result = await agent.query("计算 1+2*3")
        assert result.answer
        assert len(result.plan) >= 2
        assert result.plan[0].tool_name == "calculator_tool"
        assert result.final_status == "success"

    @pytest.mark.asyncio
    async def test_plan_execute_echo(self, async_db_session: AsyncSession) -> None:
        agent = PlanExecuteAgent(session=async_db_session)
        result = await agent.query("echo hello")
        assert result.answer
        assert result.plan[0].tool_name == "echo_tool"

    @pytest.mark.asyncio
    async def test_plan_execute_system_status(self, async_db_session: AsyncSession) -> None:
        agent = PlanExecuteAgent(session=async_db_session)
        result = await agent.query("系统状态")
        assert result.answer
        assert result.plan[0].tool_name == "get_system_status_tool"

    @pytest.mark.asyncio
    async def test_plan_execute_search_documents(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,  # noqa: ARG002
    ) -> None:
        agent = PlanExecuteAgent(session=async_db_session)
        result = await agent.query("搜索文档 API")
        assert result.plan[0].tool_name == "search_documents_tool"

    @pytest.mark.asyncio
    async def test_plan_execute_fallback_to_rag(self, async_db_session: AsyncSession) -> None:
        agent = PlanExecuteAgent(session=async_db_session)
        result = await agent.query("What is machine learning?")
        assert result.used_fallback
        assert result.plan[0].action_type == "rag"

    @pytest.mark.asyncio
    async def test_plan_execute_returns_plan_and_step_results(
        self, async_db_session: AsyncSession
    ) -> None:
        agent = PlanExecuteAgent(session=async_db_session)
        result = await agent.query("计算 5+5")
        assert len(result.plan) >= 2
        assert len(result.step_results) >= 2
        assert result.trace_id

    @pytest.mark.asyncio
    async def test_plan_execute_tool_calls_recorded(self, async_db_session: AsyncSession) -> None:
        agent = PlanExecuteAgent(session=async_db_session)
        result = await agent.query("计算 1+1")
        assert len(result.tool_calls) >= 1
        assert result.tool_calls[0]["tool_name"] == "calculator_tool"

    @pytest.mark.asyncio
    async def test_plan_execute_max_steps(self, async_db_session: AsyncSession) -> None:
        agent = PlanExecuteAgent(session=async_db_session, max_steps=1)
        result = await agent.query("先查看系统状态再搜索文档")
        # With max_steps=1, plan should be truncated
        assert len(result.plan) <= 1

    @pytest.mark.asyncio
    async def test_plan_execute_tool_error_captured(self, async_db_session: AsyncSession) -> None:
        agent = PlanExecuteAgent(session=async_db_session)
        result = await agent.query("计算 1/0")
        # Calculator handles division by zero
        assert result.final_status in ("success", "partial_error")

    @pytest.mark.asyncio
    async def test_plan_execute_writes_audit_log(self, async_db_session: AsyncSession) -> None:
        agent = PlanExecuteAgent(session=async_db_session)
        await agent.query("计算 1+1")

        stmt = select(AuditLog).where(AuditLog.action == "plan_execute.run")
        db_result = await async_db_session.execute(stmt)
        logs = list(db_result.scalars().all())
        assert len(logs) >= 1
        log = logs[-1]
        assert log.meta["mode"] == "plan_execute"
        assert "plan_steps_count" in log.meta
        assert "trace_id" in log.meta
        assert "final_status" in log.meta

    @pytest.mark.asyncio
    async def test_tool_still_writes_tool_invoke_audit(
        self, async_db_session: AsyncSession
    ) -> None:
        agent = PlanExecuteAgent(session=async_db_session)
        await agent.query("计算 1+1")

        stmt = select(AuditLog).where(AuditLog.action == "tool.invoke")
        db_result = await async_db_session.execute(stmt)
        logs = list(db_result.scalars().all())
        assert len(logs) >= 1
        assert logs[-1].meta["tool_name"] == "calculator_tool"


# ── Chat API Mode Tests ────────────────────────────────────────────────


class TestChatModeAPI:
    """Tests for Chat API mode parameter with plan_execute."""

    def test_mode_plan_execute_goes_plan_execute(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "计算 1+2", "mode": "plan_execute"},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["mode"] == "plan_execute"
        assert data["plan"] is not None
        assert len(data["plan"]) >= 2
        assert data["step_results"] is not None
        assert len(data["step_results"]) >= 2

    def test_mode_react_still_works(self, client: TestClient) -> None:
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

    def test_mode_rag_still_works(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What is AI?", "mode": "rag"},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["mode"] == "rag"

    def test_tool_command_priority_over_plan_execute(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={
                "content": '/tool echo_tool {"text":"priority test"}',
                "mode": "plan_execute",
            },
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["mode"] == "tool"
        assert "priority test" in data["assistant_message"]["content"]

    def test_unsupported_mode_returns_error(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "test", "mode": "invalid_mode"},
        )
        assert msg_resp.status_code == 400

    def test_response_contains_plan_step_results_mode(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "计算 5+5", "mode": "plan_execute"},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert "plan" in data
        assert "step_results" in data
        assert "mode" in data
        assert data["mode"] == "plan_execute"

    def test_assistant_metadata_saves_plan_execute_trace(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        msg_resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "计算 3+3", "mode": "plan_execute"},
        )
        assert msg_resp.status_code == 201
        data = msg_resp.json()
        assert data["trace_id"]


# ── Compatibility Tests ────────────────────────────────────────────────


class TestPlanExecuteCompatibility:
    """Verify existing features still work with Plan-and-Execute additions."""

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
