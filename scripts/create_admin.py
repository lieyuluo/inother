"""Create an admin user for the Enterprise AI Agent.

Usage:
    uv run python scripts/create_admin.py --email admin@example.com --username admin --password Admin123456
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select


async def create_admin(email: str, username: str, password: str) -> None:
    """Create or update an admin user."""
    from app.core.security import hash_password
    from app.db.models import User
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        # Check if user exists by email
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing user
            existing.hashed_password = hash_password(password)
            existing.role = "admin"
            existing.is_active = True
            existing.is_superuser = True
            await session.flush()
            print(f"Admin user '{username}' updated successfully (email: {email})")
        else:
            # Create new admin user
            user = User(
                email=email,
                username=username,
                hashed_password=hash_password(password),
                role="admin",
                is_active=True,
                is_superuser=True,
                full_name="Admin",
            )
            session.add(user)
            await session.flush()
            print(f"Admin user '{username}' created successfully (email: {email})")

        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password")
    args = parser.parse_args()

    asyncio.run(create_admin(args.email, args.username, args.password))


if __name__ == "__main__":
    main()
