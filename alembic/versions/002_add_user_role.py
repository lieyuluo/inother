"""Add role column to users for Phase 2 RBAC.

Revision ID: 002_add_user_role
Revises: 001_initial
Create Date: 2026-06-10 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_add_user_role"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
    )
    op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin')")
    op.alter_column("users", "role", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
