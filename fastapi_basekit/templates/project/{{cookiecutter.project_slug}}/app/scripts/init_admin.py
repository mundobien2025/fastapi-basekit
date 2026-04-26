"""Seed default admin user."""

import asyncio
import os

{% if cookiecutter.orm == "sqlalchemy" -%}
from sqlalchemy import select

from app.config.database import AsyncSessionFactory
{%- elif cookiecutter.orm == "beanie" -%}
from app.config.database import init_db
{%- endif %}
from app.models.auth import Users
from app.models.enums import UserRoleEnum
from app.utils.security import get_password_hash

EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe2026!")
NAME = os.getenv("ADMIN_NAME", "Platform Admin")


async def init_admin() -> None:
{% if cookiecutter.orm == "sqlalchemy" %}
    async with AsyncSessionFactory() as session:
        existing = await session.execute(select(Users).where(Users.email == EMAIL))
        if existing.scalar_one_or_none():
            print(f"✓ Admin {EMAIL} already exists")
            return

        admin = Users(
            email=EMAIL,
            password_hash=get_password_hash(PASSWORD),
            full_name=NAME,
            role=UserRoleEnum.admin,
            is_platform_admin=True,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
{% elif cookiecutter.orm == "beanie" %}
    await init_db()
    existing = await Users.find_one(Users.email == EMAIL)
    if existing:
        print(f"✓ Admin {EMAIL} already exists")
        return

    admin = Users(
        email=EMAIL,
        password_hash=get_password_hash(PASSWORD),
        full_name=NAME,
        role=UserRoleEnum.admin,
        is_platform_admin=True,
        is_active=True,
    )
    await admin.insert()
{% endif %}
    print(f"✓ Admin created: {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(init_admin())
