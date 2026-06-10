"""Authentication, password hashing, JWT, and RBAC dependencies."""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import User
from app.db.repositories import UserRepository
from app.db.session import get_db_session

_PASSWORD_ALGORITHM = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 390000
_JWT_ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a plaintext password with PBKDF2-SHA256."""
    salt = secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PASSWORD_ITERATIONS,
    )
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{_PASSWORD_ALGORITHM}${_PASSWORD_ITERATIONS}${salt}${encoded}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    try:
        algorithm, iterations_raw, salt, expected = hashed_password.split("$", 3)
        iterations = int(iterations_raw)
    except ValueError:
        return False

    if algorithm != _PASSWORD_ALGORITHM:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    actual = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return hmac.compare_digest(actual, expected)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create an HS256 JWT access token."""
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "type": "access",
    }
    return _encode_jwt(payload, settings.jwt_secret_key)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an HS256 JWT access token."""
    settings = get_settings()
    payload = _decode_jwt(token, settings.jwt_secret_key)
    if payload.get("type") != "access":
        raise _credentials_exception()
    exp = payload.get("exp")
    if not isinstance(exp, int) or datetime.now(UTC).timestamp() >= exp:
        raise _credentials_exception()
    if not isinstance(payload.get("sub"), str):
        raise _credentials_exception()
    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Return the authenticated user or raise 401."""
    if credentials is None:
        raise _credentials_exception()
    return await _get_user_from_token(credentials.credentials, session)


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the authenticated active user or raise 403."""
    _ensure_active(current_user)
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Require an active admin user."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


async def get_request_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Return token user, or demo user when AUTH_REQUIRED=false and no token exists."""
    if credentials is not None:
        user = await _get_user_from_token(credentials.credentials, session)
        _ensure_active(user)
        return user

    settings = get_settings()
    if settings.auth_required:
        raise _credentials_exception()
    if settings.is_production():
        raise _credentials_exception()

    return await UserRepository(session).get_or_create_demo_user()


async def _get_user_from_token(token: str, session: AsyncSession) -> User:
    payload = decode_access_token(token)
    try:
        user_id = UUID(payload["sub"])
    except (TypeError, ValueError):
        raise _credentials_exception()

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise _credentials_exception()
    return user


def _ensure_active(user: User) -> None:
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _encode_jwt(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": _JWT_ALGORITHM, "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64_json(header),
            _b64_json(payload),
        ]
    )
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64_bytes(signature)}"


def _decode_jwt(token: str, secret: str) -> dict[str, Any]:
    try:
        header_raw, payload_raw, signature_raw = token.split(".")
    except ValueError:
        raise _credentials_exception()

    signing_input = f"{header_raw}.{payload_raw}"
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()

    try:
        actual_signature = _b64_decode(signature_raw)
    except ValueError:
        raise _credentials_exception()

    if not hmac.compare_digest(actual_signature, expected_signature):
        raise _credentials_exception()

    try:
        header = json.loads(_b64_decode(header_raw))
        payload = json.loads(_b64_decode(payload_raw))
    except (json.JSONDecodeError, ValueError):
        raise _credentials_exception()

    if not isinstance(header, dict) or header.get("alg") != _JWT_ALGORITHM:
        raise _credentials_exception()
    if not isinstance(payload, dict):
        raise _credentials_exception()

    return payload


def _b64_json(value: dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64_bytes(raw)


def _b64_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
