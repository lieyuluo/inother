"""v1.0 Phase 2 tests for auth, user isolation, and RBAC."""

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import clear_settings_cache
from app.core.security import create_access_token, hash_password
from app.db.models import Document, DocumentChunk, User
from app.rag.embeddings import FakeEmbeddingProvider


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


async def _create_ready_document(
    session: AsyncSession,
    user: User,
    title: str,
    content: str,
) -> Document:
    provider = FakeEmbeddingProvider(dimension=1536)
    document = Document(
        id=uuid4(),
        user_id=user.id,
        title=title,
        filename=f"{title}.txt",
        file_type="txt",
        file_size=len(content),
        content_hash=title,
        status="ready",
    )
    session.add(document)
    await session.flush()
    session.add(
        DocumentChunk(
            id=uuid4(),
            document_id=document.id,
            chunk_index=0,
            content=content,
            embedding=provider.embed(content),
            token_count=10,
        )
    )
    await session.commit()
    await session.refresh(document)
    return document


class TestAuthAPI:
    def test_register_success_and_no_password_hash(self, client: TestClient) -> None:
        data = _register(client, "user@example.com", "user1")

        assert data["email"] == "user@example.com"
        assert data["username"] == "user1"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "hashed_password" not in data

    def test_register_duplicate_email_returns_409(self, client: TestClient) -> None:
        _register(client, "dupe@example.com", "dupe1")
        response = client.post(
            "/api/auth/register",
            json={
                "email": "dupe@example.com",
                "username": "dupe2",
                "password": "StrongPassword123",
            },
        )
        assert response.status_code == 409

    def test_register_duplicate_username_returns_409(self, client: TestClient) -> None:
        _register(client, "one@example.com", "sameuser")
        response = client.post(
            "/api/auth/register",
            json={
                "email": "two@example.com",
                "username": "sameuser",
                "password": "StrongPassword123",
            },
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_password_is_hashed(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        _register(client, "hash@example.com", "hashuser")
        user = await _get_user_by_email(async_db_session, "hash@example.com")
        assert user is not None
        assert user.hashed_password != "StrongPassword123"
        assert user.hashed_password.startswith("pbkdf2_sha256$")

    def test_login_success_and_me(self, client: TestClient) -> None:
        _register(client, "login@example.com", "loginuser")
        token, user = _login(client, "login@example.com")

        assert token
        assert user["email"] == "login@example.com"

        response = client.get("/api/auth/me", headers=_auth(token))
        assert response.status_code == 200
        assert response.json()["email"] == "login@example.com"
        assert "hashed_password" not in response.json()

    def test_login_wrong_password_returns_401(self, client: TestClient) -> None:
        _register(client, "wrong@example.com", "wronguser")
        response = client.post(
            "/api/auth/login",
            json={"email": "wrong@example.com", "password": "bad"},
        )
        assert response.status_code == 401

    def test_login_missing_user_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "bad"},
        )
        assert response.status_code == 401

    def test_me_without_token_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_user_returns_403(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        user = await _create_user(
            async_db_session,
            "inactive@example.com",
            "inactive",
            is_active=False,
        )
        token = create_access_token(str(user.id))

        login_response = client.post(
            "/api/auth/login",
            json={"email": "inactive@example.com", "password": "StrongPassword123"},
        )
        assert login_response.status_code == 403

        me_response = client.get("/api/auth/me", headers=_auth(token))
        assert me_response.status_code == 403

    def test_invalid_or_expired_token_returns_401(self, client: TestClient) -> None:
        invalid = client.get("/api/auth/me", headers=_auth("not-a-token"))
        assert invalid.status_code == 401

        expired = create_access_token("00000000-0000-0000-0000-000000000000", timedelta(minutes=-1))
        expired_response = client.get("/api/auth/me", headers=_auth(expired))
        assert expired_response.status_code == 401


class TestDataIsolation:
    def test_auth_required_true_rejects_unauthenticated_chat(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AUTH_REQUIRED", "true")
        clear_settings_cache()
        try:
            response = client.get("/api/chat/sessions")
            assert response.status_code == 401
        finally:
            clear_settings_cache()

    def test_chat_session_and_messages_are_user_isolated(self, client: TestClient) -> None:
        _register(client, "a@example.com", "usera")
        token_a, _ = _login(client, "a@example.com")
        _register(client, "b@example.com", "userb")
        token_b, _ = _login(client, "b@example.com")

        session_a = client.post(
            "/api/chat/sessions",
            json={"title": "A session"},
            headers=_auth(token_a),
        ).json()
        client.post(
            f"/api/chat/sessions/{session_a['id']}/messages",
            json={"content": "hello from A"},
            headers=_auth(token_a),
        )

        list_a = client.get("/api/chat/sessions", headers=_auth(token_a)).json()
        list_b = client.get("/api/chat/sessions", headers=_auth(token_b)).json()
        assert list_a["total"] == 1
        assert list_b["total"] == 0

        assert (
            client.get(
                f"/api/chat/sessions/{session_a['id']}",
                headers=_auth(token_b),
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/chat/sessions/{session_a['id']}/messages",
                headers=_auth(token_b),
            ).status_code
            == 404
        )

    def test_documents_are_user_isolated(self, client: TestClient) -> None:
        import io

        _register(client, "doca@example.com", "doca")
        token_a, _ = _login(client, "doca@example.com")
        _register(client, "docb@example.com", "docb")
        token_b, _ = _login(client, "docb@example.com")

        upload = client.post(
            "/api/documents/upload",
            files={"file": ("a.txt", io.BytesIO(b"alpha document"), "text/plain")},
            headers=_auth(token_a),
        )
        assert upload.status_code == 201
        document_id = upload.json()["document"]["id"]

        assert client.get("/api/documents", headers=_auth(token_a)).json()["total"] == 1
        assert client.get("/api/documents", headers=_auth(token_b)).json()["total"] == 0
        assert (
            client.get(f"/api/documents/{document_id}", headers=_auth(token_b)).status_code == 404
        )
        assert (
            client.get(f"/api/documents/{document_id}/chunks", headers=_auth(token_b)).status_code
            == 404
        )
        assert (
            client.delete(f"/api/documents/{document_id}", headers=_auth(token_b)).status_code
            == 404
        )

    @pytest.mark.asyncio
    async def test_rag_and_search_tool_only_use_current_user_documents(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        user_a = await _create_user(async_db_session, "raga@example.com", "raga")
        user_b = await _create_user(async_db_session, "ragb@example.com", "ragb")
        doc_a = await _create_ready_document(
            async_db_session,
            user_a,
            "Private A",
            "alpha private owner A content",
        )
        doc_b = await _create_ready_document(
            async_db_session,
            user_b,
            "Private B",
            "beta private owner B content",
        )
        token_b = create_access_token(str(user_b.id))

        session_b = client.post("/api/chat/sessions", json={}, headers=_auth(token_b)).json()
        rag = client.post(
            f"/api/chat/sessions/{session_b['id']}/messages",
            json={"content": "private content"},
            headers=_auth(token_b),
        )
        assert rag.status_code == 201
        citation_ids = {c["document_id"] for c in rag.json()["citations"]}
        assert str(doc_a.id) not in citation_ids
        assert str(doc_b.id) in citation_ids

        search = client.post(
            "/api/tools/search_documents_tool/invoke",
            json={"input": {"query": "private content", "top_k": 10}},
            headers=_auth(token_b),
        )
        assert search.status_code == 200
        result_ids = {r["document_id"] for r in search.json()["output"]["results"]}
        assert str(doc_a.id) not in result_ids
        assert str(doc_b.id) in result_ids


class TestRBAC:
    @pytest.mark.asyncio
    async def test_admin_audit_logs_rbac(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        user = await _create_user(async_db_session, "plain@example.com", "plain")
        admin = await _create_user(async_db_session, "admin@example.com", "admin", role="admin")

        user_token = create_access_token(str(user.id))
        admin_token = create_access_token(str(admin.id))

        assert client.get("/api/admin/audit-logs").status_code == 401
        assert client.get("/api/admin/audit-logs", headers=_auth(user_token)).status_code == 403
        admin_response = client.get("/api/admin/audit-logs?limit=10", headers=_auth(admin_token))
        assert admin_response.status_code == 200
        assert "logs" in admin_response.json()

    @pytest.mark.asyncio
    async def test_tool_permissions(
        self,
        client: TestClient,
        async_db_session: AsyncSession,
    ) -> None:
        user = await _create_user(async_db_session, "tooluser@example.com", "tooluser")
        admin = await _create_user(
            async_db_session, "tooladmin@example.com", "tooladmin", role="admin"
        )
        user_token = create_access_token(str(user.id))
        admin_token = create_access_token(str(admin.id))

        user_tool = client.post(
            "/api/tools/echo_tool/invoke",
            json={"input": {"text": "hello"}},
            headers=_auth(user_token),
        )
        assert user_tool.status_code == 200
        assert user_tool.json()["status"] == "success"

        denied = client.post(
            "/api/tools/mcp_create_ticket/invoke",
            json={"input": {"title": "Need help", "description": "Demo"}},
            headers=_auth(user_token),
        )
        assert denied.status_code == 200
        assert denied.json()["status"] == "error"
        assert "requires role 'admin'" in denied.json()["error"]

        allowed = client.post(
            "/api/tools/mcp_create_ticket/invoke",
            json={"input": {"title": "Need help", "description": "Demo"}},
            headers=_auth(admin_token),
        )
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "success"


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    from sqlalchemy import select

    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
