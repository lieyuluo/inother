"""Authentication API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    """Request schema for user registration."""

    email: str = Field(max_length=255)
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=256)
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normalize and lightly validate email."""
        email = value.strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("Invalid email")
        return email

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """Normalize username whitespace."""
        return value.strip()


class LoginRequest(BaseModel):
    """Request schema for user login."""

    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Normalize login email."""
        return value.strip().lower()


class UserResponse(BaseModel):
    """Public user response without password hash."""

    id: UUID
    email: str
    username: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime


class LoginResponse(BaseModel):
    """JWT login response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
