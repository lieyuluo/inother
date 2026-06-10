# v1.0 Phase 2 Auth RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add basic auth, JWTs, user-owned data isolation, `user`/`admin` RBAC, tool permissions, frontend auth, and Phase 2 documentation without breaking demo compatibility.

**Architecture:** Implement config-driven JWT authentication and a compatibility dependency that resolves a bearer-token user when present and falls back to the demo user only when `AUTH_REQUIRED=false`. Pass the resolved user through Chat, Document, RAG, Tool, ReAct, and Plan-Execute paths so data isolation and tool RBAC are enforced in one place. Keep admin scope limited to audit-log access and admin-only tools.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Pydantic v2, pytest, SQLite test DB, PostgreSQL/pgvector production path, React 18, Vite, TypeScript.

---

## File Structure

Create:

- `app/core/security.py` - password hashing, JWT encode/decode, auth dependencies, compatibility user dependency.
- `app/schemas/auth.py` - register, login, token, and public user schemas.
- `app/schemas/admin.py` - audit-log response schemas.
- `app/api/routes_auth.py` - register, login, and current-user endpoints.
- `app/api/routes_admin.py` - admin audit-log endpoint.
- `alembic/versions/002_add_user_role.py` - add `users.role`.
- `tests/test_auth.py` - auth API and token behavior.
- `tests/test_data_isolation.py` - Chat, Document, RAG, and document-tool isolation.
- `tests/test_rbac.py` - admin audit API and tool role permissions.
- `frontend/src/components/AuthPanel.tsx` - login/register/logout/current-user UI.

Modify:

- `pyproject.toml` - add JWT/password hashing dependencies.
- `app/core/config.py` - add JWT and auth-required settings.
- `.env.example` - add Phase 2 auth configuration.
- `app/db/models.py` - add `User.role`.
- `app/db/repositories.py` - add user lookup, owner-filtered reads, recent audit logs, demo user role.
- `app/main.py` - include auth/admin routers.
- `app/api/routes_chat.py` - resolve current user and pass it into `ChatService`.
- `app/api/routes_documents.py` - resolve current user and pass it into `DocumentService`.
- `app/api/routes_tools.py` - resolve current user and pass it into `ToolService`.
- `app/services/chat_service.py` - accept current user and enforce session ownership.
- `app/services/document_service.py` - accept current user and enforce document ownership.
- `app/rag/retriever.py` - optional `user_id` filtering in SQLite and pgvector paths.
- `app/agents/rag_agent.py` - accept optional user id for retrieval.
- `app/agents/react_agent.py` - accept optional current user and pass to ToolService/RAG/audit.
- `app/agents/plan_execute_agent.py` - accept optional current user and pass to ToolService/RAG/audit.
- `app/tools/base.py` - add default `required_role`.
- `app/tools/schemas.py` - expose `required_role`.
- `app/tools/builtin.py` - pass user id into document tools.
- `app/mcp/tool_adapter.py` - mark `mcp_create_ticket` as admin.
- `app/tools/service.py` - enforce tool RBAC and audit user context.
- `frontend/src/api/client.ts` - token storage, auth methods, auth headers, HTTP error handling.
- `frontend/src/types.ts` - user/auth/tool role types.
- `frontend/src/App.tsx` - render AuthPanel and reload protected data after auth changes.
- `frontend/src/styles.css` - style compact auth controls.
- `tests/conftest.py` - fixed auth env defaults and role-aware fixtures.
- `tests/test_providers.py` - read app source with UTF-8 to fix the Windows baseline decode failure.
- `README.md` - Phase 2 user docs.
- `REPORT.md` - Phase 2 completion report.

---

## Task 1: Dependencies, Settings, and User Role

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/core/config.py`
- Modify: `.env.example`
- Modify: `app/db/models.py`
- Modify: `app/db/repositories.py`
- Modify: `tests/conftest.py`
- Create: `alembic/versions/002_add_user_role.py`

- [ ] **Step 1: Write failing model/config tests**

Add these tests to `tests/test_auth.py`:

```python
"""Tests for Phase 2 authentication."""

from app.core.config import Settings
from app.db.models import User


def test_settings_include_phase2_auth_defaults() -> None:
    settings = Settings()

    assert settings.auth_required is False
    assert settings.access_token_expire_minutes == 60
    assert settings.jwt_secret_key


def test_user_role_defaults_to_user() -> None:
    user = User(
        email="role-default@example.com",
        username="role_default",
        hashed_password="hash",
    )

    assert user.role == "user"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py::test_settings_include_phase2_auth_defaults tests/test_auth.py::test_user_role_defaults_to_user -q
```

Expected: tests fail because `Settings.auth_required`, `Settings.jwt_secret_key`, `Settings.access_token_expire_minutes`, and `User.role` do not exist.

- [ ] **Step 3: Add dependencies**

Modify `pyproject.toml` dependencies:

```toml
"pwdlib[argon2]>=0.2.1",
"PyJWT>=2.10.0",
```

Then run:

```powershell
.\.venv\Scripts\python.exe -m pip install "pwdlib[argon2]>=0.2.1" "PyJWT>=2.10.0"
```

If using Codespaces or a machine with `uv`, also run:

```bash
uv sync
```

- [ ] **Step 4: Add settings**

In `app/core/config.py`, replace the future-phase security block with:

```python
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    jwt_secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60
    auth_required: bool = False
```

- [ ] **Step 5: Add env example values**

In `.env.example`, replace the security block with:

```dotenv
# Security
# JWT_SECRET_KEY default is for development/demo only. Replace it in production.
SECRET_KEY=your-secret-key-change-in-production
JWT_SECRET_KEY=dev-only-change-me
ACCESS_TOKEN_EXPIRE_MINUTES=60
AUTH_REQUIRED=false
```

- [ ] **Step 6: Add User.role**

In `app/db/models.py`, add after `is_superuser`:

```python
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
```

- [ ] **Step 7: Make demo/test users role-aware**

In `app/db/repositories.py`, add `role="user"` to the demo user constructor:

```python
            role="user",
```

In `tests/conftest.py`, add `role="user"` to every direct `User(...)` fixture.

- [ ] **Step 8: Add Alembic migration**

Create `alembic/versions/002_add_user_role.py`:

```python
"""Add role to users.

Revision ID: 002_add_user_role
Revises: 001_initial
Create Date: 2026-06-10 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_add_user_role"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
    )
    op.create_check_constraint(
        "ck_users_role_valid",
        "users",
        "role IN ('user', 'admin')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role_valid", "users", type_="check")
    op.drop_column("users", "role")
```

If SQLite migration smoke tests complain about check constraints, guard the constraint by dialect in Alembic. Keep PostgreSQL behavior intact.

- [ ] **Step 9: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py::test_settings_include_phase2_auth_defaults tests/test_auth.py::test_user_role_defaults_to_user -q
```

Expected: both tests pass.

---

## Task 2: Security Helpers and Auth Schemas

**Files:**
- Create: `app/core/security.py`
- Create: `app/schemas/auth.py`
- Modify: `app/db/repositories.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write failing security tests**

Append to `tests/test_auth.py`:

```python
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    password = "StrongPassword123"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False


def test_access_token_contains_subject() -> None:
    user_id = str(uuid4())

    token = create_access_token(subject=user_id)
    payload = decode_access_token(token)

    assert payload["sub"] == user_id
    assert "exp" in payload


def test_expired_access_token_raises_401() -> None:
    token = create_access_token(subject=str(uuid4()), expires_delta=timedelta(seconds=-1))

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)

    assert exc_info.value.status_code == 401


def test_invalid_access_token_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("not-a-valid-token")

    assert exc_info.value.status_code == 401
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py::test_password_hash_is_not_plaintext_and_verifies tests/test_auth.py::test_access_token_contains_subject tests/test_auth.py::test_expired_access_token_raises_401 tests/test_auth.py::test_invalid_access_token_raises_401 -q
```

Expected: import failure because `app.core.security` does not exist.

- [ ] **Step 3: Add auth schemas**

Create `app/schemas/auth.py`:

```python
"""Authentication API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    username: str
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
```

- [ ] **Step 4: Add user repository lookup helpers**

In `app/db/repositories.py`, add methods to `UserRepository`:

```python
    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        username: str,
        hashed_password: str,
        full_name: str | None = None,
        role: str = "user",
        is_active: bool = True,
        is_superuser: bool = False,
    ) -> User:
        user = User(
            id=uuid4(),
            email=email,
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_active=is_active,
            is_superuser=is_superuser,
        )
        self.session.add(user)
        await self.session.flush()
        return user
```

- [ ] **Step 5: Add security helpers**

Create `app/core/security.py`:

```python
"""Authentication, password hashing, and JWT helpers."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import User
from app.db.repositories import UserRepository
from app.db.session import get_db_session

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(password, hashed_password)
    except Exception:
        return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expire_delta = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    expire_at = datetime.now(UTC) + expire_delta
    payload: dict[str, Any] = {"sub": subject, "exp": expire_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    return dict(payload)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db_session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = await UserRepository(db_session).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user


async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


async def get_current_user_or_demo(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db_session: AsyncSession = Depends(get_db_session),
) -> User:
    settings = get_settings()
    repo = UserRepository(db_session)

    if credentials is not None:
        user = await get_current_user(credentials, db_session)
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
        return user

    if settings.auth_required:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    return await repo.get_or_create_demo_user()
```

Remove the `request` argument if ruff flags it as unused; it is only needed if later code inspects request metadata.

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py::test_password_hash_is_not_plaintext_and_verifies tests/test_auth.py::test_access_token_contains_subject tests/test_auth.py::test_expired_access_token_raises_401 tests/test_auth.py::test_invalid_access_token_raises_401 -q
```

Expected: all four tests pass.

---

## Task 3: Auth API

**Files:**
- Create: `app/api/routes_auth.py`
- Modify: `app/main.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write failing API tests**

Append to `tests/test_auth.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _register_payload(email: str = "user@example.com", username: str = "user1") -> dict[str, str]:
    return {
        "email": email,
        "username": username,
        "password": "StrongPassword123",
        "full_name": "User One",
    }


def test_register_success(client: TestClient) -> None:
    response = client.post("/api/auth/register", json=_register_payload())

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "user@example.com"
    assert data["username"] == "user1"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert "hashed_password" not in data


def test_register_duplicate_email_returns_409(client: TestClient) -> None:
    client.post("/api/auth/register", json=_register_payload())

    response = client.post(
        "/api/auth/register",
        json=_register_payload(username="another_user"),
    )

    assert response.status_code == 409


def test_register_duplicate_username_returns_409(client: TestClient) -> None:
    client.post("/api/auth/register", json=_register_payload())

    response = client.post(
        "/api/auth/register",
        json=_register_payload(email="another@example.com"),
    )

    assert response.status_code == 409


async def test_register_stores_hashed_password(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    response = client.post("/api/auth/register", json=_register_payload())
    assert response.status_code == 201

    stmt = select(User).where(User.email == "user@example.com")
    result = await async_db_session.execute(stmt)
    user = result.scalar_one()
    assert user.hashed_password != "StrongPassword123"
    assert verify_password("StrongPassword123", user.hashed_password)


def test_login_success_returns_token(client: TestClient) -> None:
    client.post("/api/auth/register", json=_register_payload())

    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "StrongPassword123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600
    assert data["user"]["email"] == "user@example.com"
    assert "hashed_password" not in data["user"]


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    client.post("/api/auth/register", json=_register_payload())

    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "WrongPassword123"},
    )

    assert response.status_code == 401


def test_login_unknown_user_returns_401(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "StrongPassword123"},
    )

    assert response.status_code == 401


def test_me_with_token_success(client: TestClient) -> None:
    client.post("/api/auth/register", json=_register_payload())
    login = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "StrongPassword123"},
    ).json()

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_me_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py -q
```

Expected: route tests fail with 404 for `/api/auth/*`.

- [ ] **Step 3: Implement auth routes**

Create `app/api/routes_auth.py`:

```python
"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    get_current_active_user,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.db.repositories import AuditLogRepository, UserRepository
from app.db.session import get_db_session
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    repo = UserRepository(db_session)
    if await repo.get_by_email(request.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if await repo.get_by_username(request.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already registered")

    user = await repo.create(
        email=request.email,
        username=request.username,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        role="user",
    )
    await AuditLogRepository(db_session).create(
        action="auth.register",
        actor=user.email,
        resource_type="user",
        resource_id=user.id,
        user_id=user.id,
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    repo = UserRepository(db_session)
    user = await repo.get_by_email(request.email)
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    settings = get_settings()
    token = create_access_token(subject=str(user.id))
    await AuditLogRepository(db_session).create(
        action="auth.login",
        actor=user.email,
        resource_type="user",
        resource_id=user.id,
        user_id=user.id,
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_active_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
```

- [ ] **Step 4: Register router**

In `app/main.py`, import and include:

```python
from app.api.routes_auth import router as auth_router
```

```python
    app.include_router(auth_router)
```

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py -q
```

Expected: auth tests pass.

---

## Task 4: Inactive Users and Token Edge Cases

**Files:**
- Modify: `tests/test_auth.py`
- Modify: `app/core/security.py`
- Modify: `app/api/routes_auth.py`

- [ ] **Step 1: Write failing edge-case tests**

Append:

```python
from uuid import uuid4


async def test_me_inactive_user_returns_403(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    user = User(
        id=uuid4(),
        email="inactive@example.com",
        username="inactive",
        hashed_password=hash_password("StrongPassword123"),
        full_name="Inactive User",
        is_active=False,
        is_superuser=False,
        role="user",
    )
    async_db_session.add(user)
    await async_db_session.commit()

    token = create_access_token(subject=str(user.id))
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_me_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})

    assert response.status_code == 401
```

- [ ] **Step 2: Run tests and verify RED or confirm coverage**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py::test_me_inactive_user_returns_403 tests/test_auth.py::test_me_invalid_token_returns_401 -q
```

Expected: tests should pass if Task 2 and 3 already implemented correctly. If they fail, fix `get_current_active_user` or JWT decode error handling.

- [ ] **Step 3: Keep implementation minimal**

No production change is needed if the tests pass. If not, adjust only the exact failing branch:

```python
if not current_user.is_active:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py -q
```

Expected: all auth tests pass.

---

## Task 5: Chat Ownership and Compatibility Auth

**Files:**
- Modify: `app/api/routes_chat.py`
- Modify: `app/services/chat_service.py`
- Modify: `app/db/repositories.py`
- Test: `tests/test_data_isolation.py`

- [ ] **Step 1: Write failing chat isolation tests**

Create `tests/test_data_isolation.py`:

```python
"""Tests for user-owned data isolation."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.db.models import ChatSession, User


async def _create_user(
    session: AsyncSession,
    email: str,
    username: str,
    role: str = "user",
) -> User:
    user = User(
        id=uuid4(),
        email=email,
        username=username,
        hashed_password=hash_password("StrongPassword123"),
        full_name=username,
        is_active=True,
        is_superuser=role == "admin",
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


async def test_user_only_lists_own_sessions(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    user_a = await _create_user(async_db_session, "a@example.com", "user_a")
    user_b = await _create_user(async_db_session, "b@example.com", "user_b")

    a_response = client.post(
        "/api/chat/sessions",
        json={"title": "A Session"},
        headers=_auth_headers(user_a),
    )
    b_response = client.post(
        "/api/chat/sessions",
        json={"title": "B Session"},
        headers=_auth_headers(user_b),
    )
    assert a_response.status_code == 201
    assert b_response.status_code == 201

    response = client.get("/api/chat/sessions", headers=_auth_headers(user_a))

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert [s["title"] for s in sessions] == ["A Session"]


async def test_user_cannot_get_another_users_session(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    user_a = await _create_user(async_db_session, "a2@example.com", "user_a2")
    user_b = await _create_user(async_db_session, "b2@example.com", "user_b2")
    session_resp = client.post(
        "/api/chat/sessions",
        json={"title": "Private"},
        headers=_auth_headers(user_a),
    )
    session_id = session_resp.json()["id"]

    response = client.get(f"/api/chat/sessions/{session_id}", headers=_auth_headers(user_b))

    assert response.status_code == 404


async def test_user_cannot_get_another_users_messages(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    user_a = await _create_user(async_db_session, "a3@example.com", "user_a3")
    user_b = await _create_user(async_db_session, "b3@example.com", "user_b3")
    session_resp = client.post("/api/chat/sessions", json={}, headers=_auth_headers(user_a))
    session_id = session_resp.json()["id"]
    client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content": "hello"},
        headers=_auth_headers(user_a),
    )

    response = client.get(
        f"/api/chat/sessions/{session_id}/messages",
        headers=_auth_headers(user_b),
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_data_isolation.py::test_user_only_lists_own_sessions tests/test_data_isolation.py::test_user_cannot_get_another_users_session tests/test_data_isolation.py::test_user_cannot_get_another_users_messages -q
```

Expected: isolation tests fail because routes/services still use demo user or unowned reads.

- [ ] **Step 3: Add repository owner helper**

In `ChatSessionRepository`, add:

```python
    async def get_by_id_for_user(self, session_id: UUID, user_id: UUID) -> ChatSession | None:
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
```

- [ ] **Step 4: Make ChatService user-aware**

Change `ChatService.__init__`:

```python
    def __init__(self, session: AsyncSession, current_user: User) -> None:
        self.session = session
        self.current_user = current_user
```

Import `User` from `app.db.models`.

Replace demo user usage:

```python
chat_session = await self.session_repo.create(user_id=self.current_user.id, title=title)
```

```python
sessions = await self.session_repo.get_all_by_user(
    user_id=self.current_user.id, limit=limit, offset=offset
)
total = await self.session_repo.count_by_user(self.current_user.id)
```

Replace direct session reads in `get_session`, `get_messages`, and `process_message`:

```python
chat_session = await self.session_repo.get_by_id_for_user(session_id, self.current_user.id)
```

- [ ] **Step 5: Pass user from routes**

In `app/api/routes_chat.py`, import:

```python
from app.core.security import get_current_user_or_demo
from app.db.models import User
```

Add a dependency to every Chat route:

```python
current_user: User = Depends(get_current_user_or_demo),
```

Instantiate:

```python
service = ChatService(session, current_user)
```

In streaming route, also pass user to `ChatService`. When saving the assistant message at the end, owner has already been checked by `service.process_message`.

- [ ] **Step 6: Pass actor/user into ChatService internals**

When calling `ToolService`, `RAGAgent`, `ReActAgent`, and `PlanExecuteAgent`, pass the current user:

```python
tool_service = ToolService(self.session, current_user=self.current_user)
```

```python
agent = RAGAgent(session=self.session, user_id=self.current_user.id)
agent = ReActAgent(session=self.session, current_user=self.current_user)
agent = PlanExecuteAgent(session=self.session, current_user=self.current_user)
```

Set audit actor to `self.current_user.email` and `user_id=self.current_user.id`.

- [ ] **Step 7: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_data_isolation.py::test_user_only_lists_own_sessions tests/test_data_isolation.py::test_user_cannot_get_another_users_session tests/test_data_isolation.py::test_user_cannot_get_another_users_messages -q
```

Expected: chat isolation tests pass.

---

## Task 6: Document and RAG Isolation

**Files:**
- Modify: `app/api/routes_documents.py`
- Modify: `app/services/document_service.py`
- Modify: `app/db/repositories.py`
- Modify: `app/rag/retriever.py`
- Modify: `app/agents/rag_agent.py`
- Test: `tests/test_data_isolation.py`

- [ ] **Step 1: Write failing document/RAG tests**

Append to `tests/test_data_isolation.py`:

```python
import io


async def test_user_only_lists_own_documents(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    user_a = await _create_user(async_db_session, "doca@example.com", "doc_a")
    user_b = await _create_user(async_db_session, "docb@example.com", "doc_b")

    client.post(
        "/api/documents/upload",
        files={"file": ("a.txt", io.BytesIO(b"alpha private document"), "text/plain")},
        headers=_auth_headers(user_a),
    )
    client.post(
        "/api/documents/upload",
        files={"file": ("b.txt", io.BytesIO(b"beta private document"), "text/plain")},
        headers=_auth_headers(user_b),
    )

    response = client.get("/api/documents", headers=_auth_headers(user_a))

    assert response.status_code == 200
    docs = response.json()["documents"]
    assert [d["filename"] for d in docs] == ["a.txt"]


async def test_user_cannot_get_another_users_document(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    user_a = await _create_user(async_db_session, "doca2@example.com", "doc_a2")
    user_b = await _create_user(async_db_session, "docb2@example.com", "doc_b2")
    upload = client.post(
        "/api/documents/upload",
        files={"file": ("private.txt", io.BytesIO(b"private document"), "text/plain")},
        headers=_auth_headers(user_a),
    )
    doc_id = upload.json()["document"]["id"]

    response = client.get(f"/api/documents/{doc_id}", headers=_auth_headers(user_b))

    assert response.status_code == 404


async def test_rag_only_searches_current_users_documents(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    user_a = await _create_user(async_db_session, "raga@example.com", "rag_a")
    user_b = await _create_user(async_db_session, "ragb@example.com", "rag_b")
    client.post(
        "/api/documents/upload",
        files={"file": ("a.txt", io.BytesIO(b"alpha project endpoint details"), "text/plain")},
        headers=_auth_headers(user_a),
    )
    client.post(
        "/api/documents/upload",
        files={"file": ("b.txt", io.BytesIO(b"beta finance policy details"), "text/plain")},
        headers=_auth_headers(user_b),
    )
    session_resp = client.post("/api/chat/sessions", json={}, headers=_auth_headers(user_b))
    session_id = session_resp.json()["id"]

    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content": "alpha project endpoint details"},
        headers=_auth_headers(user_b),
    )

    assert response.status_code == 201
    citations = response.json()["citations"]
    assert all(c["document_title"] != "a.txt" for c in citations)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_data_isolation.py::test_user_only_lists_own_documents tests/test_data_isolation.py::test_user_cannot_get_another_users_document tests/test_data_isolation.py::test_rag_only_searches_current_users_documents -q
```

Expected: tests fail because documents and retriever are not user-filtered.

- [ ] **Step 3: Add document repository helper**

In `DocumentRepository`, add:

```python
    async def get_by_id_for_user(
        self,
        document_id: UUID,
        user_id: UUID,
        include_deleted: bool = False,
    ) -> Document | None:
        stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(Document.status != "deleted")
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
```

- [ ] **Step 4: Make DocumentService user-aware**

Change constructor:

```python
    def __init__(self, session: AsyncSession, current_user: User) -> None:
        self.session = session
        self.current_user = current_user
```

Use `self.current_user.id` in upload/list/get/chunks/delete. Replace direct `get_by_id` calls with `get_by_id_for_user`.

- [ ] **Step 5: Pass user from document routes**

In `app/api/routes_documents.py`, add:

```python
from app.core.security import get_current_user_or_demo
from app.db.models import User
```

Add route dependency:

```python
current_user: User = Depends(get_current_user_or_demo),
```

Instantiate:

```python
service = DocumentService(session, current_user)
```

- [ ] **Step 6: Add Retriever user filtering**

In `Retriever.__init__`, add:

```python
        user_id: UUID | None = None,
```

Store:

```python
        self.user_id = user_id
```

Import `UUID`.

In `_pgvector_search`, add conditional SQL:

```python
        user_filter = "AND d.user_id = :user_id" if self.user_id else ""
        query_sql = text(f"""
            SELECT ...
            WHERE d.status = 'ready'
              AND dc.embedding IS NOT NULL
              {user_filter}
            ORDER BY dc.embedding <=> :query_embedding::vector
            LIMIT :limit
        """)
        params = {"query_embedding": embedding_str, "limit": self.top_k}
        if self.user_id:
            params["user_id"] = str(self.user_id)
```

Keep the rest of row mapping unchanged.

In `_fetch_ready_chunks`, add:

```python
        if self.user_id is not None:
            stmt = stmt.where(Document.user_id == self.user_id)
```

- [ ] **Step 7: Pass user into RAGAgent**

In `app/agents/rag_agent.py`, change constructor:

```python
    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        self.session = session
        self.user_id = user_id
        self.retriever = Retriever(session=session, user_id=user_id)
```

Import `UUID`.

- [ ] **Step 8: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_data_isolation.py -q
```

Expected: all isolation tests pass.

---

## Task 7: Tool RBAC and Document Tool Isolation

**Files:**
- Modify: `app/tools/base.py`
- Modify: `app/tools/schemas.py`
- Modify: `app/tools/builtin.py`
- Modify: `app/tools/service.py`
- Modify: `app/mcp/tool_adapter.py`
- Modify: `app/api/routes_tools.py`
- Modify: `app/agents/react_agent.py`
- Modify: `app/agents/plan_execute_agent.py`
- Test: `tests/test_rbac.py`

- [ ] **Step 1: Write failing RBAC tests**

Create `tests/test_rbac.py`:

```python
"""Tests for Phase 2 RBAC."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.db.models import User
from app.tools.service import ToolService


async def _create_rbac_user(session: AsyncSession, email: str, username: str, role: str) -> User:
    user = User(
        id=uuid4(),
        email=email,
        username=username,
        hashed_password=hash_password("StrongPassword123"),
        full_name=username,
        is_active=True,
        is_superuser=role == "admin",
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


async def test_tool_info_exposes_required_role(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    response = client.get("/api/tools")

    assert response.status_code == 200
    tools = {tool["name"]: tool for tool in response.json()["tools"]}
    assert tools["echo_tool"]["required_role"] == "user"
    assert tools["mcp_create_ticket"]["required_role"] == "admin"


async def test_user_invokes_user_tool_success(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    user = await _create_rbac_user(async_db_session, "user@example.com", "rbac_user", "user")

    response = client.post(
        "/api/tools/echo_tool/invoke",
        json={"input": {"text": "ok"}},
        headers=_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


async def test_user_invokes_admin_tool_returns_permission_error(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    user = await _create_rbac_user(async_db_session, "user2@example.com", "rbac_user2", "user")

    response = client.post(
        "/api/tools/mcp_create_ticket/invoke",
        json={"input": {"title": "T", "description": "D"}},
        headers=_headers(user),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "admin" in data["error"].lower()


async def test_admin_invokes_admin_tool_success(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    admin = await _create_rbac_user(async_db_session, "admin@example.com", "rbac_admin", "admin")

    response = client.post(
        "/api/tools/mcp_create_ticket/invoke",
        json={"input": {"title": "T", "description": "D"}},
        headers=_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rbac.py::test_tool_info_exposes_required_role tests/test_rbac.py::test_user_invokes_user_tool_success tests/test_rbac.py::test_user_invokes_admin_tool_returns_permission_error tests/test_rbac.py::test_admin_invokes_admin_tool_success -q
```

Expected: tests fail because `required_role` does not exist and tool service does not check roles.

- [ ] **Step 3: Add role metadata to tools**

In `app/tools/base.py`, add:

```python
    @property
    def required_role(self) -> str:
        """Minimum role required to invoke this tool."""
        return "user"
```

In `app/tools/schemas.py`, add to `ToolInfo`:

```python
    required_role: str = "user"
```

- [ ] **Step 4: Mark MCP ticket admin-only**

In `app/mcp/tool_adapter.py`, add:

```python
    @property
    def required_role(self) -> str:
        if self._definition.name == "mcp_create_ticket":
            return "admin"
        return "user"
```

- [ ] **Step 5: Make ToolService user-aware**

Change constructor:

```python
    def __init__(self, session: AsyncSession, current_user: User | None = None) -> None:
        self.session = session
        self.current_user = current_user
```

Import `User`.

In `list_tools`, include:

```python
                required_role=tool.required_role,
```

In `invoke_tool`, after getting the tool:

```python
        permission_error = self._check_permission(tool)
        if permission_error:
            latency_ms = (time.monotonic() - start) * 1000
            result = ToolResult(
                tool_name=tool_name,
                status="error",
                error=permission_error,
                latency_ms=latency_ms,
                trace_id=trace_id,
            )
            await self._write_audit_log(...)
            return result
```

Add:

```python
    def _check_permission(self, tool: BaseTool) -> str | None:
        if tool.required_role == "admin":
            if self.current_user is None or self.current_user.role != "admin":
                return "Permission denied: admin role required"
        return None
```

In `_write_audit_log`, set:

```python
            user_id=self.current_user.id if self.current_user else None,
```

Use actor fallback:

```python
actor = actor or (self.current_user.email if self.current_user else "system")
```

- [ ] **Step 6: Pass current user from Tool API**

In `routes_tools.py`, add:

```python
from app.core.security import get_current_user_or_demo
from app.db.models import User
```

Add dependency to list and invoke routes:

```python
current_user: User = Depends(get_current_user_or_demo),
```

Instantiate:

```python
service = ToolService(db_session, current_user=current_user)
```

- [ ] **Step 7: Make document tools user-filtered**

Change `SearchDocumentsTool` and `ListDocumentsTool` constructors:

```python
    def __init__(self, db_session: AsyncSession, user_id: UUID | None = None) -> None:
        self._db_session = db_session
        self._user_id = user_id
```

Use `Retriever(..., user_id=self._user_id)` in search.

Add to list documents query:

```python
            if self._user_id is not None:
                stmt = stmt.where(Document.user_id == self._user_id)
```

Change `create_builtin_tools`:

```python
def create_builtin_tools(db_session: AsyncSession, user_id: UUID | None = None) -> list[BaseTool]:
```

Pass `user_id` into the two document tools.

In `ToolService.__init__`, call:

```python
for tool in create_builtin_tools(session, user_id=current_user.id if current_user else None):
```

- [ ] **Step 8: Pass current user through agents**

In `ReActAgent.__init__`, accept and store `current_user: User | None = None`, then instantiate:

```python
self.tool_service = ToolService(session, current_user=current_user)
```

When falling back to RAG:

```python
rag_agent = RAGAgent(session=self.session, user_id=self.current_user.id if self.current_user else None)
```

In audit log, actor/user:

```python
actor=self.current_user.email if self.current_user else "react_agent"
user_id=self.current_user.id if self.current_user else None
```

In `PlanExecuteAgent`, pass `current_user` into `Executor`, and let `Executor` instantiate ToolService/RAG with that user.

- [ ] **Step 9: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rbac.py::test_tool_info_exposes_required_role tests/test_rbac.py::test_user_invokes_user_tool_success tests/test_rbac.py::test_user_invokes_admin_tool_returns_permission_error tests/test_rbac.py::test_admin_invokes_admin_tool_success -q
```

Expected: tool RBAC tests pass.

---

## Task 8: Admin Audit Logs API

**Files:**
- Create: `app/schemas/admin.py`
- Create: `app/api/routes_admin.py`
- Modify: `app/db/repositories.py`
- Modify: `app/main.py`
- Test: `tests/test_rbac.py`

- [ ] **Step 1: Write failing admin API tests**

Append to `tests/test_rbac.py`:

```python
async def test_admin_can_access_audit_logs(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    admin = await _create_rbac_user(async_db_session, "admin2@example.com", "admin2", "admin")
    client.post(
        "/api/tools/echo_tool/invoke",
        json={"input": {"text": "audit"}},
        headers=_headers(admin),
    )

    response = client.get("/api/admin/audit-logs", headers=_headers(admin))

    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
    assert data["total"] >= 1


async def test_user_cannot_access_audit_logs(
    async_db_session: AsyncSession,
    client: TestClient,
) -> None:
    user = await _create_rbac_user(async_db_session, "user3@example.com", "user3", "user")

    response = client.get("/api/admin/audit-logs", headers=_headers(user))

    assert response.status_code == 403


def test_unauthenticated_cannot_access_audit_logs(client: TestClient) -> None:
    response = client.get("/api/admin/audit-logs")

    assert response.status_code == 401
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rbac.py::test_admin_can_access_audit_logs tests/test_rbac.py::test_user_cannot_access_audit_logs tests/test_rbac.py::test_unauthenticated_cannot_access_audit_logs -q
```

Expected: 404 because `/api/admin/audit-logs` does not exist.

- [ ] **Step 3: Add audit log repository list helper**

In `AuditLogRepository`, add:

```python
    async def list_recent(self, limit: int = 50) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

Ensure `desc` is already imported at the top.

- [ ] **Step 4: Add admin schemas**

Create `app/schemas/admin.py`:

```python
"""Admin API schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    action: str
    actor: str
    resource_type: str | None
    resource_id: UUID | None
    meta: dict[str, Any] | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
```

- [ ] **Step 5: Add admin route**

Create `app/api/routes_admin.py`:

```python
"""Admin-only API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.models import User
from app.db.repositories import AuditLogRepository
from app.db.session import get_db_session
from app.schemas.admin import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    current_user: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditLogListResponse:
    logs = await AuditLogRepository(db_session).list_recent(limit=limit)
    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=len(logs),
    )
```

If ruff flags `current_user` as unused, rename it to `_current_user`.

- [ ] **Step 6: Register admin router**

In `app/main.py`, import/include:

```python
from app.api.routes_admin import router as admin_router
```

```python
    app.include_router(admin_router)
```

- [ ] **Step 7: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rbac.py -q
```

Expected: all RBAC tests pass.

---

## Task 9: AUTH_REQUIRED=true Compatibility Tests

**Files:**
- Modify: `tests/test_auth.py`
- Modify: `tests/conftest.py`
- Modify: `app/core/security.py`

- [ ] **Step 1: Write failing auth-required tests**

Append:

```python
import os

from app.core.config import clear_settings_cache


def test_auth_required_true_rejects_chat_without_token(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    clear_settings_cache()
    try:
        response = client.get("/api/chat/sessions")
        assert response.status_code == 401
    finally:
        monkeypatch.setenv("AUTH_REQUIRED", "false")
        clear_settings_cache()


def test_auth_required_false_allows_demo_without_token(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    clear_settings_cache()

    response = client.get("/api/chat/sessions")

    assert response.status_code == 200
```

- [ ] **Step 2: Run tests and verify behavior**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py::test_auth_required_true_rejects_chat_without_token tests/test_auth.py::test_auth_required_false_allows_demo_without_token -q
```

Expected: tests pass if compatibility dependency reads settings at request time. If they fail, ensure `get_current_user_or_demo` calls `get_settings()` inside the function body and no route stores settings at import time.

- [ ] **Step 3: Reset test env defaults**

In `tests/conftest.py`, add:

```python
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("AUTH_REQUIRED", "false")
```

- [ ] **Step 4: Verify existing compatibility**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py tests/test_documents.py tests/test_tools.py tests/test_mcp.py tests/test_react.py tests/test_plan_execute.py -q
```

Expected: existing demo-mode tests pass.

---

## Task 10: Fix Windows UTF-8 Baseline Test

**Files:**
- Modify: `tests/test_providers.py`

- [ ] **Step 1: Confirm failing baseline**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_providers.py::TestDatetimeUtcnowFix::test_no_utcnow_in_project -q
```

Expected on current Windows local environment: `UnicodeDecodeError` from platform default GBK decoding.

- [ ] **Step 2: Apply minimal test fix**

Change:

```python
with open(fpath) as f:
```

to:

```python
with open(fpath, encoding="utf-8") as f:
```

- [ ] **Step 3: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_providers.py::TestDatetimeUtcnowFix::test_no_utcnow_in_project -q
```

Expected: test passes.

---

## Task 11: Frontend Auth UI and API Client

**Files:**
- Create: `frontend/src/components/AuthPanel.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add frontend types**

In `frontend/src/types.ts`, add:

```typescript
export type UserRole = 'user' | 'admin'

export interface User {
  id: string
  email: string
  username: string
  full_name: string | null
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}
```

Update `ToolInfo`:

```typescript
  required_role: UserRole
```

- [ ] **Step 2: Add API client auth helpers**

In `frontend/src/api/client.ts`, define:

```typescript
const TOKEN_KEY = 'enterprise_ai_agent_token'

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getAuthToken()
  return {
    ...(extra || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function parseJson<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data && typeof data === 'object' && 'detail' in data ? String(data.detail) : `HTTP ${res.status}`
    throw new Error(detail)
  }
  return data as T
}
```

Use `authHeaders()` for every protected request and `parseJson` for every JSON response. Add:

```typescript
  async register(payload: { email: string; username: string; password: string; full_name?: string }): Promise<User> {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return parseJson<User>(res)
  },

  async login(payload: { email: string; password: string }): Promise<LoginResponse> {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return parseJson<LoginResponse>(res)
  },

  async me(): Promise<User> {
    const res = await fetch(`${API_BASE}/api/auth/me`, { headers: authHeaders() })
    return parseJson<User>(res)
  },
```

For SSE, include:

```typescript
headers: authHeaders({ 'Content-Type': 'application/json' }),
```

- [ ] **Step 3: Add AuthPanel**

Create `frontend/src/components/AuthPanel.tsx`:

```tsx
import { useState } from 'react'
import { api, clearAuthToken, setAuthToken } from '../api/client'
import type { User } from '../types'

interface Props {
  user: User | null
  onUserChange: (user: User | null) => void
  onError: (message: string) => void
}

export function AuthPanel({ user, onUserChange, onError }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)

  const reset = () => {
    setPassword('')
  }

  const submit = async () => {
    setLoading(true)
    try {
      if (mode === 'register') {
        await api.register({
          email,
          username,
          password,
          full_name: fullName || undefined,
        })
      }
      const login = await api.login({ email, password })
      setAuthToken(login.access_token)
      onUserChange(login.user)
      reset()
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  const logout = () => {
    clearAuthToken()
    onUserChange(null)
  }

  if (user) {
    return (
      <section className="auth-panel">
        <div>
          <strong>{user.username}</strong>
          <span>{user.email}</span>
        </div>
        <button type="button" onClick={logout}>Logout</button>
      </section>
    )
  }

  return (
    <section className="auth-panel">
      <div className="auth-tabs">
        <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Login</button>
        <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Register</button>
      </div>
      <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
      {mode === 'register' && (
        <>
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Username" />
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Full name" />
        </>
      )}
      <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" type="password" />
      <button type="button" onClick={submit} disabled={loading}>{loading ? 'Working...' : mode === 'login' ? 'Login' : 'Register'}</button>
    </section>
  )
}
```

- [ ] **Step 4: Integrate into App**

In `App.tsx`, import `AuthPanel`, `getAuthToken`, and `User`.

Add state:

```typescript
const [currentUser, setCurrentUser] = useState<User | null>(null)
```

On mount, if a token exists:

```typescript
useEffect(() => {
  if (!getAuthToken()) return
  api.me()
    .then(setCurrentUser)
    .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load current user'))
}, [])
```

Render `AuthPanel` in the header or top of sidebar:

```tsx
<AuthPanel
  user={currentUser}
  onUserChange={(user) => {
    setCurrentUser(user)
    setMessages(null)
    setMessageList([])
    setSelectedSessionId(null)
    loadDocuments()
    loadSessions()
  }}
  onError={(msg) => setError(msg)}
/>
```

- [ ] **Step 5: Add CSS**

In `frontend/src/styles.css`, add compact styles:

```css
.auth-panel {
  display: grid;
  gap: 8px;
  align-items: center;
}

.auth-panel input {
  width: 100%;
}

.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.auth-tabs button.active {
  border-color: #2563eb;
  color: #1d4ed8;
}
```

Adjust to match existing button/input styles and avoid nested cards.

- [ ] **Step 6: Verify frontend**

Run:

```powershell
cd frontend
npm run lint
npm run build
```

Expected: lint and build pass.

---

## Task 12: Documentation and Report

**Files:**
- Modify: `README.md`
- Modify: `REPORT.md`

- [ ] **Step 1: Update README**

Add a `v1.0 Phase 2 - Auth, User Isolation, and Basic RBAC` section covering:

- Register/login/me examples.
- JWT settings and production replacement warning.
- `AUTH_REQUIRED=false` demo/dev mode.
- `AUTH_REQUIRED=true` protected mode.
- RBAC roles.
- User data isolation.
- Admin audit logs API.
- Tool permission table.
- Frontend login/register usage.
- Current limitations: no OAuth/SSO, no complex multi-tenancy, no admin dashboard, `AUTH_REQUIRED=false` demo/dev only.
- GitHub Codespaces is the acceptance environment.

- [ ] **Step 2: Update REPORT**

Rewrite or extend `REPORT.md` with:

- v1.0 Phase 2 completion checklist.
- Changed files.
- Auth architecture.
- JWT/password hashing.
- `AUTH_REQUIRED` compatibility strategy.
- User isolation.
- RBAC.
- Tool permissions.
- Admin audit logs.
- Frontend auth.
- Test case list and results.
- Codespaces automated commands and results.
- Codespaces manual acceptance flow and results.
- Impact on v0.1, v0.2, v1.0 Phase 1.
- Known issues.
- Next Phase suggestions.

- [ ] **Step 3: Include exact verification commands**

In `REPORT.md`, list:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q
docker compose config

cd frontend
npm ci
npm run lint
npm run build
```

Codespaces Docker:

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```

State that local Docker is unavailable and Docker verification is performed in GitHub Codespaces.

---

## Task 13: Full Verification

**Files:**
- All changed files

- [ ] **Step 1: Backend local verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all pass locally. If `ruff` or `mypy` is unavailable in `.venv`, use Codespaces `uv run ...` equivalents.

- [ ] **Step 2: Frontend verification**

Run:

```powershell
cd frontend
npm run lint
npm run build
```

Expected: both pass.

- [ ] **Step 3: Codespaces verification**

Run in GitHub Codespaces:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q
docker compose config
cd frontend
npm ci
npm run lint
npm run build
```

Expected: all pass.

- [ ] **Step 4: Codespaces manual acceptance**

Run the manual flow from the user request:

1. Open frontend forwarded port.
2. Register user A.
3. Login user A.
4. Upload document A.
5. Create chat session A.
6. Confirm user A can use RAG Chat.
7. Logout.
8. Register user B.
9. Login user B.
10. Confirm user B cannot see user A documents or sessions.
11. Upload user B document and chat.
12. Test `/api/auth/me`.
13. Confirm normal user cannot access `/api/admin/audit-logs`.
14. Login with admin test account or fixture.
15. Confirm admin can access `/api/admin/audit-logs`.
16. Confirm normal user invoking admin-only tool is denied.
17. Confirm Streaming Chat works.
18. Confirm ReAct, Plan-Execute, and MCP tools still work.

Record results in `REPORT.md`.

---

## Self-Review Checklist

- Auth API requirements are covered by Tasks 2-4.
- User role and migration are covered by Task 1.
- Compatibility mode is covered by Tasks 5 and 9.
- Chat isolation is covered by Task 5.
- Document and RAG isolation are covered by Task 6.
- Tool RBAC is covered by Task 7.
- Admin audit logs are covered by Task 8.
- Frontend auth is covered by Task 11.
- README and REPORT are covered by Task 12.
- Verification and Codespaces acceptance are covered by Task 13.
- No OAuth, SSO, complex multi-tenancy, admin dashboard, or approval workflow is included.
