"""Tests for v1.0 Phase 1: Real Provider + SSE Streaming Chat."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.provider_errors import (
    ProviderConfigError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from app.llm.openai_provider import OpenAILLMProvider
from app.rag.embeddings import OpenAIEmbeddingProvider

# ── Provider Config Tests ──────────────────────────────────────────────


class TestProviderConfig:
    """Tests for provider configuration."""

    def test_default_provider_is_fake(self) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        assert settings.llm_provider == "fake"
        assert settings.embedding_provider == "fake"

    def test_openai_llm_without_api_key_raises_config_error(self) -> None:
        with pytest.raises(ProviderConfigError, match="OPENAI_API_KEY"):
            OpenAILLMProvider(api_key=None)

    def test_openai_llm_with_empty_api_key_raises_config_error(self) -> None:
        with pytest.raises(ProviderConfigError, match="OPENAI_API_KEY"):
            OpenAILLMProvider(api_key="")

    def test_openai_embedding_without_api_key_raises_config_error(self) -> None:
        with pytest.raises(ProviderConfigError, match="OPENAI_API_KEY"):
            OpenAIEmbeddingProvider(api_key=None)

    def test_openai_embedding_with_empty_api_key_raises_config_error(self) -> None:
        with pytest.raises(ProviderConfigError, match="OPENAI_API_KEY"):
            OpenAIEmbeddingProvider(api_key="")

    def test_openai_base_url_configurable(self) -> None:
        provider = OpenAILLMProvider(api_key="test-key", base_url="https://custom.api.com/v1")
        assert provider._base_url == "https://custom.api.com/v1"

    def test_provider_error_does_not_leak_api_key(self) -> None:
        try:
            raise ProviderConfigError("Missing API key", provider="openai")
        except ProviderConfigError as e:
            assert "sk-" not in str(e)
            assert "api_key" not in str(e).lower() or "required" in str(e).lower()


# ── OpenAI LLM Provider Tests ──────────────────────────────────────────


class TestOpenAILLMProvider:
    """Tests for OpenAI-compatible LLM provider with mock HTTP."""

    def test_mock_chat_completions_success(self) -> None:
        mock_response = httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "Hello! How can I help you?"}, "finish_reason": "stop"}
                ],
                "model": "gpt-4o-mini",
            },
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(return_value=mock_response)

        provider = OpenAILLMProvider(api_key="test-key", client=mock_client)
        result = provider.generate("Hello", "")
        assert result == "Hello! How can I help you?"

    def test_mock_response_format_error(self) -> None:
        mock_response = httpx.Response(200, json={"error": "bad format"})
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(return_value=mock_response)

        provider = OpenAILLMProvider(api_key="test-key", client=mock_client)
        with pytest.raises(ProviderResponseError, match="missing"):
            provider.generate("Hello", "")

    def test_mock_timeout_error(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(side_effect=httpx.TimeoutException("timeout"))

        provider = OpenAILLMProvider(api_key="test-key", client=mock_client)
        with pytest.raises(ProviderTimeoutError):
            provider.generate("Hello", "")

    def test_mock_5xx_retries(self) -> None:
        error_response = httpx.Response(500, text="Internal Server Error")
        success_response = httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]},
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(side_effect=[error_response, success_response])

        provider = OpenAILLMProvider(api_key="test-key", client=mock_client, max_retries=1)
        result = provider.generate("Hello", "")
        assert result == "OK"
        assert mock_client.post.call_count == 2

    def test_generate_does_not_access_real_network(self) -> None:
        """Verify that with mock client, no real network access occurs."""
        mock_response = httpx.Response(
            200,
            json={"choices": [{"message": {"content": "test"}, "finish_reason": "stop"}]},
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(return_value=mock_response)

        provider = OpenAILLMProvider(api_key="test-key", client=mock_client)
        provider.generate("test", "")
        # Verify the URL is correct
        call_args = mock_client.post.call_args
        assert "chat/completions" in str(call_args)


# ── OpenAI Embedding Provider Tests ────────────────────────────────────


class TestOpenAIEmbeddingProvider:
    """Tests for OpenAI-compatible Embedding provider with mock HTTP."""

    @pytest.mark.asyncio
    async def test_mock_embeddings_success(self) -> None:
        embedding = [0.1] * 1536
        mock_response = httpx.Response(
            200,
            json={"data": [{"embedding": embedding}]},
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = OpenAIEmbeddingProvider(api_key="test-key", client=mock_client, dimension=1536)
        result = await provider._async_embed("hello")
        assert len(result) == 1536
        assert result[0] == 0.1

    @pytest.mark.asyncio
    async def test_embedding_dimension_correct(self) -> None:
        embedding = [0.1] * 1536
        mock_response = httpx.Response(
            200,
            json={"data": [{"embedding": embedding}]},
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = OpenAIEmbeddingProvider(api_key="test-key", client=mock_client, dimension=1536)
        result = await provider._async_embed("hello")
        assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_embedding_dimension_mismatch_raises_error(self) -> None:
        embedding = [0.1] * 768  # Wrong dimension
        mock_response = httpx.Response(
            200,
            json={"data": [{"embedding": embedding}]},
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = OpenAIEmbeddingProvider(api_key="test-key", client=mock_client, dimension=1536)
        with pytest.raises(ProviderResponseError, match="dimension mismatch"):
            await provider._async_embed("hello")

    @pytest.mark.asyncio
    async def test_mock_response_format_error(self) -> None:
        mock_response = httpx.Response(200, json={"error": "bad"})
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = OpenAIEmbeddingProvider(api_key="test-key", client=mock_client)
        with pytest.raises(ProviderResponseError, match="missing"):
            await provider._async_embed("hello")

    @pytest.mark.asyncio
    async def test_mock_timeout_error(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        provider = OpenAIEmbeddingProvider(api_key="test-key", client=mock_client)
        with pytest.raises(ProviderTimeoutError):
            await provider._async_embed("hello")

    @pytest.mark.asyncio
    async def test_embed_does_not_access_real_network(self) -> None:
        embedding = [0.1] * 1536
        mock_response = httpx.Response(
            200,
            json={"data": [{"embedding": embedding}]},
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        provider = OpenAIEmbeddingProvider(api_key="test-key", client=mock_client, dimension=1536)
        await provider._async_embed("test")
        call_args = mock_client.post.call_args
        assert "embeddings" in str(call_args)


# ── SSE API Tests ──────────────────────────────────────────────────────


class TestSSEAPI:
    """Tests for SSE streaming Chat API."""

    def test_sse_rag_success(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "What is AI?"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        # Parse SSE events
        events = _parse_sse_events(resp.text)
        event_types = [e[0] for e in events]
        assert "trace" in event_types
        assert "user_message" in event_types
        assert "token" in event_types
        assert "assistant_message" in event_types
        assert "done" in event_types

    def test_sse_returns_trace_event(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "What is AI?"},
        )
        events = _parse_sse_events(resp.text)
        trace_events = [e for e in events if e[0] == "trace"]
        assert len(trace_events) >= 1
        assert "trace_id" in trace_events[0][1]

    def test_sse_returns_user_message_event(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "Hello"},
        )
        events = _parse_sse_events(resp.text)
        user_msg_events = [e for e in events if e[0] == "user_message"]
        assert len(user_msg_events) >= 1

    def test_sse_returns_token_events(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "Hello"},
        )
        events = _parse_sse_events(resp.text)
        token_events = [e for e in events if e[0] == "token"]
        assert len(token_events) >= 1

    def test_sse_returns_citations_event(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "What is AI?"},
        )
        events = _parse_sse_events(resp.text)
        # Citations may or may not appear depending on RAG results
        # Just verify the event format is correct if present
        citation_events = [e for e in events if e[0] == "citations"]
        if citation_events:
            assert isinstance(citation_events[0][1], list)

    def test_sse_returns_assistant_message_event(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "Hello"},
        )
        events = _parse_sse_events(resp.text)
        assistant_events = [e for e in events if e[0] == "assistant_message"]
        assert len(assistant_events) >= 1

    def test_sse_returns_done_event(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "Hello"},
        )
        events = _parse_sse_events(resp.text)
        done_events = [e for e in events if e[0] == "done"]
        assert len(done_events) >= 1
        assert done_events[0][1]["status"] == "ok"

    def test_sse_react_mode_returns_steps(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "计算 1+2", "mode": "react"},
        )
        events = _parse_sse_events(resp.text)
        steps_events = [e for e in events if e[0] == "steps"]
        assert len(steps_events) >= 1

    def test_sse_plan_execute_mode_returns_plan(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "计算 1+2", "mode": "plan_execute"},
        )
        events = _parse_sse_events(resp.text)
        plan_events = [e for e in events if e[0] == "plan"]
        assert len(plan_events) >= 1

    def test_sse_tool_command_returns_tool_calls(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": '/tool echo_tool {"text":"hello"}'},
        )
        events = _parse_sse_events(resp.text)
        tool_call_events = [e for e in events if e[0] == "tool_calls"]
        assert len(tool_call_events) >= 1

    def test_sse_session_not_found(self, client: TestClient) -> None:
        from uuid import uuid4

        fake_id = str(uuid4())
        resp = client.post(
            f"/api/chat/sessions/{fake_id}/messages/stream",
            json={"content": "Hello"},
        )
        # SSE endpoint returns 200 with error event
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error_events = [e for e in events if e[0] == "error"]
        assert len(error_events) >= 1

    def test_sse_empty_content_error(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "   "},
        )
        # Should return 422 for validation error
        assert resp.status_code == 422

    def test_non_streaming_endpoint_still_works(self, client: TestClient) -> None:
        session_resp = client.post("/api/chat/sessions", json={})
        session_id = session_resp.json()["id"]

        resp = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What is AI?"},
        )
        assert resp.status_code == 201


# ── Compatibility Tests ────────────────────────────────────────────────


class TestV1Phase1Compatibility:
    """Verify existing features still work."""

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

    def test_mcp_tools_still_work(self, client: TestClient) -> None:
        response = client.get("/api/tools")
        assert response.status_code == 200
        tool_names = [t["name"] for t in response.json()["tools"]]
        assert "mcp_echo" in tool_names


# ── Helpers ────────────────────────────────────────────────────────────


def _parse_sse_events(text: str) -> list[tuple[str, object]]:
    """Parse SSE event text into (event_type, data) tuples."""
    events: list[tuple[str, object]] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event_type = ""
        data_str = ""
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:]
        if event_type and data_str:
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = data_str
            events.append((event_type, data))
    return events
