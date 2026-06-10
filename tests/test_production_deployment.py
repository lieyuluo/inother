"""Tests for production deployment hardening and LLM planning features."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.agents.llm_planner import LLMPlanner, LLMPlannerError
from app.agents.plan_execute_agent import PlanExecuteAgent
from app.agents.react_agent import ReActAgent
from app.core.config import Settings, clear_settings_cache
from app.llm.base import BaseLLMProvider
from app.rag.reranker import LLMReranker
from app.rag.retrieval_pipeline import RetrievalPipeline
from app.rag.retriever import RetrievalResult
from app.tools.schemas import ToolInfo


@pytest.fixture(autouse=True)
def clear_settings_between_tests() -> None:
    clear_settings_cache()
    yield
    clear_settings_cache()


class StaticLLMProvider(BaseLLMProvider):
    """Test LLM provider that returns a fixed response."""

    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, query: str, context: str) -> str:  # noqa: ARG002
        return self.response


def _tool(name: str) -> ToolInfo:
    return ToolInfo(
        name=name,
        description=f"{name} description",
        input_schema={"type": "object", "properties": {}, "required": []},
        allowed_modes=["react", "plan_execute"],
    )


def _results() -> list[RetrievalResult]:
    return [
        RetrievalResult("chunk-a", "doc-a", "Doc A", 0, "less relevant", 0.2),
        RetrievalResult("chunk-b", "doc-b", "Doc B", 0, "more relevant", 0.8),
    ]


class TestProductionSettings:
    def teardown_method(self) -> None:
        clear_settings_cache()

    def test_production_requires_auth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("AUTH_REQUIRED", "false")
        monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
        monkeypatch.setenv("MCP_DEMO_ENABLED", "false")
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AGENT_PLANNER_PROVIDER", "llm")
        clear_settings_cache()

        with pytest.raises(ValueError, match="AUTH_REQUIRED"):
            Settings()

    def test_production_requires_strong_jwt_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("AUTH_REQUIRED", "true")
        monkeypatch.setenv("JWT_SECRET_KEY", "short")
        monkeypatch.setenv("MCP_DEMO_ENABLED", "false")
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AGENT_PLANNER_PROVIDER", "llm")
        clear_settings_cache()

        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            Settings()

    def test_production_requires_mcp_demo_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("AUTH_REQUIRED", "true")
        monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
        monkeypatch.setenv("MCP_DEMO_ENABLED", "true")
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AGENT_PLANNER_PROVIDER", "llm")
        clear_settings_cache()

        with pytest.raises(ValueError, match="MCP_DEMO_ENABLED"):
            Settings()


class TestLLMPlanner:
    def test_react_llm_planner_valid_json(self) -> None:
        planner = LLMPlanner(
            StaticLLMProvider(
                '{"tool_name":"echo_tool","action_input":{"text":"hello"},"thought":"echo it"}'
            )
        )

        decision = planner.plan_react("echo hello", [_tool("echo_tool")])

        assert decision.tool_name == "echo_tool"
        assert decision.action_input == {"text": "hello"}
        assert decision.thought == "echo it"

    def test_react_llm_planner_rejects_unknown_tool(self) -> None:
        planner = LLMPlanner(
            StaticLLMProvider('{"tool_name":"missing_tool","action_input":{},"thought":"bad"}')
        )

        with pytest.raises(LLMPlannerError, match="unknown tool"):
            planner.plan_react("use a tool", [_tool("echo_tool")])

    def test_plan_execute_llm_planner_valid_json(self) -> None:
        planner = LLMPlanner(
            StaticLLMProvider(
                '{"steps":[{"description":"Echo","action_type":"tool",'
                '"tool_name":"echo_tool","tool_input":{"text":"hello"}},'
                '{"description":"Finish","action_type":"final"}]}'
            )
        )

        plan = planner.plan_execute("echo hello", [_tool("echo_tool")], max_steps=5)

        assert plan[0].tool_name == "echo_tool"
        assert plan[0].tool_input == {"text": "hello"}
        assert plan[-1].action_type == "final"

    @pytest.mark.asyncio
    async def test_react_agent_llm_failure_falls_back(
        self,
        async_db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AGENT_PLANNER_PROVIDER", "llm")
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        clear_settings_cache()

        result = await ReActAgent(async_db_session).query("echo hello")

        assert result.planner_provider == "deterministic"
        assert result.fallback_reason
        assert result.steps[0].tool_name == "echo_tool"

    @pytest.mark.asyncio
    async def test_plan_execute_agent_llm_failure_falls_back(
        self,
        async_db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AGENT_PLANNER_PROVIDER", "llm")
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        clear_settings_cache()

        result = await PlanExecuteAgent(async_db_session).query("echo hello")

        assert result.planner_provider == "deterministic"
        assert result.fallback_reason
        assert result.plan[0].tool_name == "echo_tool"


class TestLLMReranker:
    def test_llm_reranker_reorders_valid_chunks(self) -> None:
        reranker = LLMReranker(
            StaticLLMProvider(
                '{"results":[{"chunk_id":"chunk-b","score":0.99},'
                '{"chunk_id":"chunk-a","score":0.4}]}'
            )
        )

        reranked = reranker.rerank("query", _results())

        assert [r.chunk_id for r in reranked] == ["chunk-b", "chunk-a"]
        assert reranked[0].score == 0.99

    def test_llm_reranker_appends_missing_chunks(self) -> None:
        reranker = LLMReranker(StaticLLMProvider('{"results":[{"chunk_id":"chunk-b"}]}'))

        reranked = reranker.rerank("query", _results())

        assert [r.chunk_id for r in reranked] == ["chunk-b", "chunk-a"]

    @pytest.mark.asyncio
    async def test_pipeline_reranker_failure_falls_back(
        self,
        async_db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("RAG_RERANKER_PROVIDER", "llm")
        monkeypatch.setenv("LLM_PROVIDER", "fake")
        clear_settings_cache()

        pipeline = RetrievalPipeline(async_db_session)
        reranked, fallback_reason = pipeline._rerank("query", _results())

        assert [r.chunk_id for r in reranked] == ["chunk-a", "chunk-b"]
        assert fallback_reason


@pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Postgres migration integration test is opt-in",
)
def test_empty_postgres_migration_and_core_api() -> None:
    """Run Alembic on an empty Postgres DB and call core APIs."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql+asyncpg://"):
        pytest.skip("DATABASE_URL is not async PostgreSQL")

    async def reset_schema() -> None:
        engine = create_async_engine(database_url)
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    asyncio.run(reset_schema())
    clear_settings_cache()
    alembic_exe = Path(sys.executable).with_name("alembic.exe" if os.name == "nt" else "alembic")
    subprocess.run([str(alembic_exe), "upgrade", "head"], check=True)

    from app.main import app

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        register = client.post(
            "/api/auth/register",
            json={
                "email": "pg-user@example.com",
                "username": "pg_user",
                "password": "Password12345",
            },
        )
        assert register.status_code == 201

        login = client.post(
            "/api/auth/login",
            json={"email": "pg-user@example.com", "password": "Password12345"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        upload = client.post(
            "/api/documents/upload",
            data={"visibility": "private"},
            files={"file": ("test.txt", b"Postgres migration document content", "text/plain")},
            headers=headers,
        )
        assert upload.status_code == 201

        assert client.get("/api/documents", headers=headers).status_code == 200
        session = client.post("/api/chat/sessions", json={}, headers=headers)
        assert session.status_code == 201
        message = client.post(
            f"/api/chat/sessions/{session.json()['id']}/messages",
            json={"content": "What is in the document?"},
            headers=headers,
        )
        assert message.status_code == 201
        assert client.get("/api/tools", headers=headers).status_code == 200
