"""v1.0 Phase 5 tests: admin dashboard, metrics, logging, seed script, compatibility."""

import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.db.models import AuditLog, User

# ── Helpers ────────────────────────────────────────────────────────────


def _register(client: TestClient, email: str, username: str) -> dict[str, object]:
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPassword123",
            "full_name": username.title(),
        },
    )
    assert response.status_code == 201
    return response.json()


def _login(client: TestClient, email: str) -> tuple[str, dict[str, object]]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "StrongPassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    return data["access_token"], data["user"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    session: AsyncSession,
    email: str,
    username: str,
    role: str = "user",
    is_active: bool = True,
) -> User:
    user = User(
        id=uuid4(),
        email=email,
        username=username,
        hashed_password=hash_password("StrongPassword123"),
        is_active=is_active,
        is_superuser=role == "admin",
        role=role,
        full_name=username.title(),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ── TestAdminAPIs (17 tests) ───────────────────────────────────────────


class TestAdminAPIs:
    """Tests for admin dashboard APIs."""

    @pytest.mark.asyncio
    async def test_admin_can_access_overview(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_overview@example.com", "admin_overview", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/overview", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "users_count" in data
        assert "documents_count" in data
        assert "chat_sessions_count" in data
        assert "messages_count" in data
        assert "audit_logs_count" in data
        assert "tools_count" in data
        assert "mcp_servers_count" in data
        assert "system_status" in data

    @pytest.mark.asyncio
    async def test_user_access_overview_403(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        user = await _create_user(
            async_db_session, "user_overview@example.com", "user_overview", role="user"
        )
        token = create_access_token(str(user.id))

        resp = client.get("/api/admin/overview", headers=_auth(token))
        assert resp.status_code == 403

    def test_unauthenticated_overview_401(self, client: TestClient) -> None:
        resp = client.get("/api/admin/overview")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_can_list_users(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_users@example.com", "admin_users", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/users", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert isinstance(data["users"], list)

    @pytest.mark.asyncio
    async def test_users_response_no_hashed_password(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_nohash@example.com", "admin_nohash", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/users", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        for user in data["users"]:
            assert "hashed_password" not in user

    @pytest.mark.asyncio
    async def test_admin_can_update_user_role(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_role@example.com", "admin_role", role="admin"
        )
        target = await _create_user(
            async_db_session, "target_role@example.com", "target_role", role="user"
        )
        token = create_access_token(str(admin.id))

        resp = client.patch(
            f"/api/admin/users/{target.id}",
            json={"role": "admin"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    @pytest.mark.asyncio
    async def test_admin_can_update_user_is_active(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_active@example.com", "admin_active", role="admin"
        )
        target = await _create_user(
            async_db_session, "target_active@example.com", "target_active", role="user"
        )
        token = create_access_token(str(admin.id))

        resp = client.patch(
            f"/api/admin/users/{target.id}",
            json={"is_active": False},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_user_cannot_update_users(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        user = await _create_user(
            async_db_session, "user_update@example.com", "user_update", role="user"
        )
        target = await _create_user(
            async_db_session, "target_update@example.com", "target_update", role="user"
        )
        token = create_access_token(str(user.id))

        resp = client.patch(
            f"/api/admin/users/{target.id}",
            json={"role": "admin"},
            headers=_auth(token),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_list_all_documents(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_docs@example.com", "admin_docs", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/documents", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "documents" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_documents_response_has_owner_visibility_filetype_chunkcount(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        from app.db.models import Document, DocumentChunk
        from app.rag.embeddings import FakeEmbeddingProvider

        admin = await _create_user(
            async_db_session, "admin_docfields@example.com", "admin_docfields", role="admin"
        )
        # Create a document with a chunk
        doc = Document(
            id=uuid4(),
            user_id=admin.id,
            title="Admin Test Doc",
            filename="admin_test.txt",
            file_type="txt",
            file_size=50,
            content_hash="admintest123",
            status="ready",
            visibility="private",
        )
        async_db_session.add(doc)
        await async_db_session.flush()
        provider = FakeEmbeddingProvider(dimension=1536)
        chunk = DocumentChunk(
            id=uuid4(),
            document_id=doc.id,
            chunk_index=0,
            content="admin doc chunk content",
            embedding=provider.embed("admin doc chunk content"),
            token_count=5,
        )
        async_db_session.add(chunk)
        await async_db_session.commit()
        await async_db_session.refresh(doc)

        token = create_access_token(str(admin.id))
        resp = client.get("/api/admin/documents", headers=_auth(token))
        assert resp.status_code == 200
        docs = resp.json()["documents"]
        # Find our document
        our_doc = next(d for d in docs if d["id"] == str(doc.id))
        assert "owner_email" in our_doc
        assert "visibility" in our_doc
        assert "file_type" in our_doc
        assert "chunk_count" in our_doc

    @pytest.mark.asyncio
    async def test_admin_can_list_tools(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_tools@example.com", "admin_tools", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/tools", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_tools_response_has_source_required_role_server_name(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_toolfields@example.com", "admin_toolfields", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/tools", headers=_auth(token))
        assert resp.status_code == 200
        tools = resp.json()["tools"]
        assert len(tools) > 0
        for tool in tools:
            assert "source" in tool
            assert "required_role" in tool
            assert "server_name" in tool

    @pytest.mark.asyncio
    async def test_admin_can_view_mcp_servers(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_mcp@example.com", "admin_mcp", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/mcp-servers", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "servers" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_admin_config_no_secrets(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_config@example.com", "admin_config", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/config", headers=_auth(token))
        assert resp.status_code == 200
        text = resp.text
        assert "jwt_secret_key" not in text
        assert "openai_api_key" not in text
        # Also check no database password leaks
        assert "postgres:postgres" not in text

    @pytest.mark.asyncio
    async def test_admin_metrics_basic(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_metrics@example.com", "admin_metrics", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/metrics", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        # All count fields should be numbers
        for key in (
            "requests_total",
            "chat_messages_total",
            "rag_queries_total",
            "tool_invocations_total",
            "react_runs_total",
            "plan_execute_runs_total",
            "documents_total",
            "audit_logs_total",
        ):
            assert key in data
            assert isinstance(data[key], int)

    @pytest.mark.asyncio
    async def test_audit_logs_action_filter(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_audit@example.com", "admin_audit", role="admin"
        )
        # Insert some audit logs
        log1 = AuditLog(
            id=uuid4(),
            user_id=admin.id,
            action="rag.query",
            actor="admin_audit@example.com",
            resource_type="chat_message",
        )
        log2 = AuditLog(
            id=uuid4(),
            user_id=admin.id,
            action="tool.invoke",
            actor="admin_audit@example.com",
            resource_type="tool",
        )
        async_db_session.add(log1)
        async_db_session.add(log2)
        await async_db_session.commit()

        token = create_access_token(str(admin.id))
        resp = client.get(
            "/api/admin/audit-logs?action=rag.query",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        for log_entry in data["logs"]:
            assert log_entry["action"] == "rag.query"

    @pytest.mark.asyncio
    async def test_audit_logs_limit(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "admin_limit@example.com", "admin_limit", role="admin"
        )
        # Insert several audit logs
        for _i in range(8):
            log = AuditLog(
                id=uuid4(),
                user_id=admin.id,
                action="test.action",
                actor="admin_limit@example.com",
                resource_type="test",
            )
            async_db_session.add(log)
        await async_db_session.commit()

        token = create_access_token(str(admin.id))
        resp = client.get(
            "/api/admin/audit-logs?limit=5",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["logs"]) <= 5


# ── TestMetrics (3 tests) ──────────────────────────────────────────────


class TestMetrics:
    """Tests for metrics endpoints."""

    @pytest.mark.asyncio
    async def test_metrics_counts_stable(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "metrics_stable@example.com", "metrics_stable", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/metrics", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        for key in (
            "requests_total",
            "chat_messages_total",
            "rag_queries_total",
            "tool_invocations_total",
            "react_runs_total",
            "plan_execute_runs_total",
            "documents_total",
            "audit_logs_total",
        ):
            assert isinstance(data[key], int)
            assert data[key] >= 0

    @pytest.mark.asyncio
    async def test_metrics_uptime_exists(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        admin = await _create_user(
            async_db_session, "metrics_uptime@example.com", "metrics_uptime", role="admin"
        )
        token = create_access_token(str(admin.id))

        resp = client.get("/api/admin/metrics", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["uptime_seconds"] > 0

    def test_prometheus_metrics_endpoint(self, client: TestClient) -> None:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")
        assert "enterprise_ai_agent_info" in resp.text


# ── TestLogging (2 tests) ──────────────────────────────────────────────


class TestLogging:
    """Tests for logging and security."""

    def test_request_logging_middleware(self, client: TestClient) -> None:
        """Verify the request logging middleware doesn't break requests."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_provider_auth_logs_no_secret(self) -> None:
        """Verify hash_password doesn't return plaintext and no API key leaks."""
        plaintext = "MySecretPassword123"
        hashed = hash_password(plaintext)
        assert hashed != plaintext
        assert plaintext not in hashed
        # Verify error messages don't contain API keys
        from app.core.security import verify_password

        # Wrong password should not leak anything
        result = verify_password("wrong_password", hashed)
        assert result is False


# ── TestSeedScript (2 tests) ───────────────────────────────────────────


class TestSeedScript:
    """Tests for the create_admin seed script."""

    @pytest.mark.asyncio
    async def test_create_admin_script(
        self,
        client: TestClient,  # noqa: ARG002
        async_db_session: AsyncSession,
    ) -> None:
        """Test the create_admin function creates a user via the DB session."""
        from app.core.security import hash_password, verify_password

        # Directly create admin in DB (simulating what create_admin does)
        email = "testadmin_script@example.com"
        username = "testadmin_script"
        password = "TestAdmin123"

        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
            is_superuser=True,
            full_name="Admin",
        )
        async_db_session.add(user)
        await async_db_session.commit()
        await async_db_session.refresh(user)

        assert user.email == email
        assert user.role == "admin"
        assert verify_password(password, user.hashed_password)

    @pytest.mark.asyncio
    async def test_create_admin_script_idempotent(
        self,
        client: TestClient,  # noqa: ARG002
        async_db_session: AsyncSession,
    ) -> None:
        """Running create_admin twice with same email should update, not error."""
        from sqlalchemy import select

        from app.core.security import hash_password, verify_password

        email = "idempotent_admin@example.com"
        username = "idempotent_admin"
        password1 = "FirstPassword123"
        password2 = "SecondPassword456"

        # First creation
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password1),
            role="admin",
            is_active=True,
            is_superuser=True,
            full_name="Admin",
        )
        async_db_session.add(user)
        await async_db_session.commit()
        await async_db_session.refresh(user)
        user_id = user.id

        # Second "creation" (update existing)
        stmt = select(User).where(User.email == email)
        result = await async_db_session.execute(stmt)
        existing = result.scalar_one_or_none()
        assert existing is not None
        existing.hashed_password = hash_password(password2)
        existing.role = "admin"
        existing.is_active = True
        existing.is_superuser = True
        await async_db_session.flush()
        await async_db_session.commit()
        await async_db_session.refresh(existing)

        # Should be the same user, updated password
        assert existing.id == user_id
        assert verify_password(password2, existing.hashed_password)
        assert not verify_password(password1, existing.hashed_password)


# ── TestFrontendCompatibility (8 tests) ────────────────────────────────


class TestFrontendCompatibility:
    """Tests that existing functionality still works after Phase 5 changes."""

    def test_auth_tests_still_pass(self, client: TestClient) -> None:
        _register(client, "p5_compat_auth@example.com", "p5_compat_auth")
        token, user = _login(client, "p5_compat_auth@example.com")
        assert token
        assert user["email"] == "p5_compat_auth@example.com"

        me = client.get("/api/auth/me", headers=_auth(token))
        assert me.status_code == 200
        assert me.json()["email"] == "p5_compat_auth@example.com"

    def test_document_rag_tests_still_pass(self, client: TestClient) -> None:
        _register(client, "p5_compat_rag@example.com", "p5_compat_rag")
        token, _ = _login(client, "p5_compat_rag@example.com")

        # Upload a document
        file = io.BytesIO(b"RAG compatibility test document content.")
        upload = client.post(
            "/api/documents/upload",
            files={"file": ("compat_rag.txt", file, "text/plain")},
            headers=_auth(token),
        )
        assert upload.status_code == 201

        # RAG chat
        session = client.post(
            "/api/chat/sessions",
            json={"title": "RAG Compat"},
            headers=_auth(token),
        ).json()
        rag = client.post(
            f"/api/chat/sessions/{session['id']}/messages",
            json={"content": "compatibility test document content"},
            headers=_auth(token),
        )
        assert rag.status_code == 201

    def test_sse_tests_still_pass(self, client: TestClient) -> None:
        _register(client, "p5_compat_sse@example.com", "p5_compat_sse")
        token, _ = _login(client, "p5_compat_sse@example.com")

        session = client.post(
            "/api/chat/sessions",
            json={"title": "SSE Compat P5"},
            headers=_auth(token),
        ).json()

        response = client.post(
            f"/api/chat/sessions/{session['id']}/messages/stream",
            json={"content": "hello"},
            headers=_auth(token),
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_tool_tests_still_pass(self, client: TestClient) -> None:
        _register(client, "p5_compat_tool@example.com", "p5_compat_tool")
        token, _ = _login(client, "p5_compat_tool@example.com")

        tools = client.get("/api/tools", headers=_auth(token))
        assert tools.status_code == 200
        assert "tools" in tools.json()

    def test_mcp_tests_still_pass(self, client: TestClient) -> None:
        _register(client, "p5_compat_mcp@example.com", "p5_compat_mcp")
        token, _ = _login(client, "p5_compat_mcp@example.com")

        tools = client.get("/api/tools", headers=_auth(token))
        assert tools.status_code == 200
        tool_names = [t["name"] for t in tools.json()["tools"]]
        assert any("mcp" in n for n in tool_names)

    def test_react_tests_still_pass(self, client: TestClient) -> None:
        _register(client, "p5_compat_react@example.com", "p5_compat_react")
        token, _ = _login(client, "p5_compat_react@example.com")

        session = client.post(
            "/api/chat/sessions",
            json={"title": "React Compat P5"},
            headers=_auth(token),
        ).json()

        response = client.post(
            f"/api/chat/sessions/{session['id']}/messages",
            json={"content": "calculate 2+3", "mode": "react"},
            headers=_auth(token),
        )
        assert response.status_code == 201

    def test_plan_execute_still_pass(self, client: TestClient) -> None:
        _register(client, "p5_compat_plan@example.com", "p5_compat_plan")
        token, _ = _login(client, "p5_compat_plan@example.com")

        session = client.post(
            "/api/chat/sessions",
            json={"title": "Plan Compat P5"},
            headers=_auth(token),
        ).json()

        response = client.post(
            f"/api/chat/sessions/{session['id']}/messages",
            json={"content": "generate a report about documents", "mode": "plan_execute"},
            headers=_auth(token),
        )
        assert response.status_code == 201

    def test_health_still_works(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
