# v1.0 Phase 2 Auth, User Isolation, and Basic RBAC Design

## Goal

Implement enterprise-ai-agent v1.0 Phase 2: basic authentication, JWT access tokens, user-owned Chat and Document data, actor-aware audit logging, basic `user`/`admin` RBAC, tool permissions, and frontend login/register support while preserving the existing demo and test workflows.

## Current Project Context

The project already has a FastAPI backend, SQLAlchemy async models, Alembic, SQLite-based tests, PostgreSQL/pgvector production paths, a Tool Registry and Tool Service, ReAct and Plan-and-Execute agents, MCP demo tools, and a Vite/React frontend.

Important existing facts:

- `User`, `ChatSession.user_id`, `Document.user_id`, and `AuditLog.user_id` already exist.
- `User.role` does not exist yet and needs a model change plus Alembic migration.
- `ChatService` and `DocumentService` currently create or load the demo user internally.
- RAG retrieval currently searches all ready documents.
- `search_documents_tool` and `list_documents_tool` currently do not filter by current user.
- Tool calls flow through `ToolService` for direct Tool API, Chat `/tool`, ReAct, and Plan-and-Execute.
- The frontend has one working application shell and no auth panel.
- Local Docker is not available. Docker and Docker Compose verification is a GitHub Codespaces acceptance step.

## Scope

Phase 2 includes:

- Register, login, and `/api/auth/me`.
- Password hashing and verification.
- JWT access-token creation and decoding.
- Auth dependencies and role dependencies.
- `AUTH_REQUIRED=false` compatibility mode by default.
- User isolation for Chat sessions, Chat messages, Documents, Document chunks, RAG retrieval, and document-search tools.
- `GET /api/admin/audit-logs` guarded by admin role.
- Tool metadata with `required_role`.
- Tool invocation RBAC.
- Frontend auth panel, token persistence, bearer headers, current-user display, logout, and 401/403 error surfacing.
- README and REPORT updates.
- Backend tests for auth, isolation, RBAC, compatibility, and tool permissions.
- Frontend lint/build verification.

Phase 2 excludes:

- OAuth2 third-party login.
- Enterprise SSO.
- Complex multi-tenancy.
- Full admin dashboard.
- Complex approval workflows.
- Requiring real external services in tests.
- Requiring local Docker Desktop.

## Architecture

### Auth Model

`User` gains a `role` field:

- Type: string.
- Allowed values: `user`, `admin`.
- Default: `user`.
- Main RBAC field: `role`.
- `is_superuser` remains for compatibility but is not the primary authorization field.

Alembic migration `002_add_user_role.py` will add `users.role` with a server default of `user`, backfill existing rows, make the column non-null, and create a check constraint where supported. SQLite tests use `Base.metadata.create_all`, so the model field is enough for test DB creation.

### Auth API

Add `app/api/routes_auth.py` with:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

Add auth schemas in `app/schemas/auth.py`:

- `UserResponse`
- `RegisterRequest`
- `LoginRequest`
- `TokenResponse`

Behavior:

- Duplicate email returns 409.
- Duplicate username returns 409.
- Wrong password returns 401.
- Unknown user returns 401.
- Missing or invalid token for `/me` returns 401.
- Inactive user returns 403.
- Responses never include `hashed_password`.

Register creates a normal active user with `role="user"`. Admin users are created by tests, fixtures, or seed/demo data, not by public registration.

### Security Module

Add `app/core/security.py`:

- `hash_password(password: str) -> str`
- `verify_password(password: str, hashed_password: str) -> bool`
- `create_access_token(subject: str, expires_delta: timedelta | None = None) -> str`
- `decode_access_token(token: str) -> dict[str, object]`
- `get_current_user(...) -> User`
- `get_current_active_user(...) -> User`
- `require_admin(...) -> User`
- `get_optional_current_user(...) -> User | None`
- `get_current_user_or_demo(...) -> User`

Preferred dependencies:

- Use `pwdlib` for password hashing because it has a small modern API.
- Use `PyJWT` for JWT encode/decode.

Configuration additions in `app/core/config.py`:

- `jwt_secret_key: str`
- `access_token_expire_minutes: int = 60`
- `auth_required: bool = False`

`.env.example` additions:

- `JWT_SECRET_KEY=dev-only-change-me`
- `ACCESS_TOKEN_EXPIRE_MINUTES=60`
- `AUTH_REQUIRED=false`

`SECRET_KEY` can remain for compatibility, but JWT code uses `JWT_SECRET_KEY`.

### Compatibility Auth Dependency

Existing Chat, Document, and Tool APIs will use a compatibility dependency:

- If a valid `Authorization: Bearer <token>` is present, use that real active user.
- If no token is present and `AUTH_REQUIRED=false`, fall back to `UserRepository.get_or_create_demo_user()`.
- If no token is present and `AUTH_REQUIRED=true`, return 401.
- If token is present but invalid or expired, return 401.
- If token user is inactive, return 403.

This keeps historical demo tests usable while making production strict when configured.

### Chat User Isolation

`ChatService` will accept `current_user: User`.

Behavior:

- Create session binds `current_user.id`.
- List sessions filters by `current_user.id`.
- Get session checks owner.
- Get messages checks owner through the session.
- Send message checks owner before creating the user message.
- Streaming checks owner before generating events.
- Cross-user session/message access returns stable 404.

The route layer will pass the resolved user into the service. Service methods will not call `get_or_create_demo_user()` except through the compatibility dependency path.

### Document User Isolation

`DocumentService` will accept `current_user: User`.

Behavior:

- Upload binds `current_user.id`.
- List filters by `current_user.id`.
- Get document checks owner.
- Get chunks checks document owner.
- Delete checks owner.
- Cross-user document/chunk/delete access returns stable 404.

Repository helpers can be added for owner-filtered reads, such as:

- `DocumentRepository.get_by_id_for_user(document_id, user_id, include_deleted=False)`
- `ChatSessionRepository.get_by_id_for_user(session_id, user_id)`

### RAG Retrieval Isolation

`Retriever` gains optional `user_id`.

Behavior:

- Default searches only ready documents for the provided user.
- If `user_id` is omitted, current historical behavior is preserved for direct unit tests and low-level uses.
- Chat RAG, ReAct, Plan-and-Execute, `search_documents_tool`, and `list_documents_tool` pass the current user's id.
- PostgreSQL raw SQL and SQLite Python-cosine paths both filter by `documents.user_id` when present.

### Tool RBAC

`BaseTool` gains:

- `required_role: str = "user"`

`ToolInfo` and frontend `ToolInfo` gain:

- `required_role: "user" | "admin"`

Tool rules:

- User tools: `echo_tool`, `calculator_tool`, `search_documents_tool`, `get_system_status_tool`, `list_documents_tool`, `mcp_echo`, `mcp_get_business_metric`.
- Admin tool: `mcp_create_ticket`.

Implementation:

- `MCPToolAdapter.required_role` returns `admin` for `mcp_create_ticket`, otherwise `user`.
- `ToolService.invoke_tool(...)` accepts `current_user: User | None`.
- Role checks happen after tool lookup and before input validation.
- Insufficient role returns `ToolResult(status="error", error="Permission denied: admin role required")`.
- Direct HTTP Tool API can return the same stable error body with HTTP 200, except missing tools still return 404. This preserves current Tool API behavior.
- Chat `/tool`, ReAct, and Plan-and-Execute keep going through `ToolService`, so the same permission check applies everywhere.

### Audit Logging

Audit logs already support `user_id`, `actor`, `action`, `resource_type`, `resource_id`, and `metadata`.

Phase 2 changes:

- Tool audit logs record `user_id` when a current user is available.
- RAG audit logs record `user_id`.
- ReAct and Plan-and-Execute audit logs record `user_id`.
- Auth register/login may write audit logs; if implemented, they must not include raw password or access token.
- Actor uses the current user's email or username for authenticated users and `demo@example.com` for demo fallback.
- Tokens are never written to logs.

### Admin API

Add `app/api/routes_admin.py`:

- `GET /api/admin/audit-logs?limit=50`

Behavior:

- Requires a real authenticated active admin.
- User role returns 403.
- Missing token returns 401.
- Returns recent logs ordered by `created_at` descending.
- Limit defaults to 50 and is bounded, for example `1 <= limit <= 200`.

This admin API does not expose all users' Chat/Document data. Admin data access beyond audit logs remains out of scope until a later phase.

### Frontend Auth

Add `frontend/src/components/AuthPanel.tsx`.

Update:

- `frontend/src/api/client.ts`
- `frontend/src/types.ts`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`

Behavior:

- Register form: email, username, password, full name.
- Login form: email, password.
- Store token in `localStorage`.
- API client automatically attaches `Authorization: Bearer <token>`.
- `/api/auth/me` loads current user on app start when a token exists.
- Header displays current username or email when logged in.
- Logout clears token and current user.
- API helper throws useful errors for non-2xx responses, especially 401/403.
- Demo mode remains usable when no token is present and backend `AUTH_REQUIRED=false`.
- If backend returns 401/403, the app shows a visible error banner.

The frontend remains a work-focused app shell. No landing page or full admin dashboard is added.

## Data Flow

### Register/Login

1. Frontend posts credentials.
2. Backend validates uniqueness or password.
3. Password hash is stored on register.
4. Login returns JWT and public user object.
5. Frontend stores token and reloads authenticated resources.

### Authenticated Chat

1. Request includes bearer token.
2. Compatibility dependency resolves active user.
3. Route creates `ChatService(session, current_user)`.
4. Service reads and writes only rows owned by `current_user.id`.
5. RAG/Tool/Agent calls receive the same user context.

### Demo Chat

1. Request omits bearer token.
2. If `AUTH_REQUIRED=false`, dependency loads the demo user.
3. Existing demo flows continue using demo-owned data.
4. If `AUTH_REQUIRED=true`, dependency returns 401.

### Tool Invocation

1. Route or agent calls `ToolService.invoke_tool(...)` with current user context.
2. ToolService finds the tool.
3. ToolService checks `current_user.role` against `tool.required_role`.
4. Permission failures return stable `ToolResult(status="error")`.
5. Successful invocations write audit logs with user context.

## Error Handling

Stable status behavior:

- Auth duplicate email: 409.
- Auth duplicate username: 409.
- Auth bad credentials: 401.
- Auth missing/invalid/expired token: 401.
- Inactive user: 403.
- Cross-user Chat/Document access: 404.
- User accessing admin API: 403.
- Missing auth for admin API: 401.
- Missing tool: 404 at HTTP route level.
- Tool permission denied: stable tool error result.

No response exposes `hashed_password`. No logs include passwords or JWTs.

## Testing Strategy

Use test-first implementation for new behavior.

Backend tests:

- Auth register success.
- Duplicate email returns 409.
- Duplicate username returns 409.
- Stored password is hashed and not plaintext.
- Login success returns bearer token and user object.
- Wrong password returns 401.
- `/me` with token succeeds.
- `/me` without token returns 401.
- Inactive user returns 403.
- Invalid or expired token returns 401.
- Auth responses do not include `hashed_password`.
- User A only lists own sessions.
- User B cannot access User A session.
- User B cannot access User A messages.
- User A only lists own documents.
- User B cannot access User A document.
- RAG searches only current user's documents.
- `search_documents_tool` searches only current user's documents.
- Admin can access `/api/admin/audit-logs`.
- User gets 403 for `/api/admin/audit-logs`.
- Missing auth gets 401 for admin API.
- User can invoke user tool.
- User cannot invoke admin-only tool.
- Admin can invoke admin-only tool.
- `AUTH_REQUIRED=false` preserves existing demo Chat, Document, Tool, ReAct, Plan-and-Execute, MCP, SSE, Provider, and Health tests.

Frontend verification:

- `npm ci`
- `npm run lint`
- `npm run build`

Repository verification:

- `uv sync`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy app`
- `uv run pytest -q`
- `docker compose config`

Docker and `docker compose up -d --build` are Codespaces validation steps because local Docker is unavailable.

## Documentation Updates

`README.md` will describe:

- v1.0 Phase 2 features.
- Auth API examples.
- JWT settings.
- `AUTH_REQUIRED=false/true` behavior.
- RBAC roles.
- User data isolation.
- Admin audit logs API.
- Tool permissions.
- Frontend login/register usage.
- Current limitations: no OAuth/SSO, no complex multi-tenancy, no admin dashboard, and `AUTH_REQUIRED=false` is demo/dev only.
- GitHub Codespaces as the acceptance environment.

`REPORT.md` will include:

- Phase 2 completion checklist.
- Changed file list.
- Auth architecture.
- JWT and password hashing details.
- Compatibility strategy.
- User isolation design.
- RBAC and tool permission design.
- Admin audit log API.
- Frontend auth summary.
- Test cases and results.
- Codespaces automated and manual acceptance commands/results.
- Impact assessment for v0.1, v0.2, and v1.0 Phase 1.
- Known issues.
- Next Phase suggestions.

## Known Baseline Issue

On the current Windows local environment, running pytest through `.venv` produced `334 passed / 1 failed`. The failure is `UnicodeDecodeError` in `tests/test_providers.py::TestDatetimeUtcnowFix::test_no_utcnow_in_project`, caused by reading source files with the platform default GBK codec. This is not a business logic failure. The implementation may fix the test by reading files with `encoding="utf-8"` if it is still present when verification runs.

The global `uv` command is not installed locally. Codespaces remains the required environment for `uv` and Docker verification.

## Acceptance Criteria

Phase 2 is complete when:

- Auth APIs behave as specified.
- JWT and password hashing are implemented with config-driven secrets and expiry.
- `AUTH_REQUIRED=false` preserves demo compatibility.
- `AUTH_REQUIRED=true` requires login for protected Chat/Document/Tool paths.
- Chat, Document, RAG, and document tools are user-isolated.
- Audit logs include actor/user context for Phase 2 flows.
- Admin audit log API is admin-only.
- Tool RBAC is enforced, with `mcp_create_ticket` admin-only.
- Frontend supports register, login, current-user display, bearer headers, logout, and 401/403 errors.
- Backend tests, lint, formatting, mypy, frontend lint/build, and Codespaces Docker validation are documented in REPORT.md.
