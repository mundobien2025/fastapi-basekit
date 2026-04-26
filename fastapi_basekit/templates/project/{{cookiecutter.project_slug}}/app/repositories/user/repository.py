{% if cookiecutter.orm == "sqlalchemy" -%}
"""User repository."""

from typing import Any

from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from sqlalchemy import select

from app.models.auth import Users


class UserRepository(BaseRepository):
    model = Users

    def build_list_queryset(self, **kwargs: Any):
        return select(self.model).where(self.model.deleted_at.is_(None))

    async def get_by_email(self, email: str) -> Users | None:
        result = await self.session.execute(
            select(Users).where(Users.email == email, Users.deleted_at.is_(None))
        )
        return result.scalars().first()
{%- elif cookiecutter.orm == "beanie" -%}
"""User repository."""

from fastapi_basekit.aio.beanie.repository.base import BeanieBaseRepository

from app.models.auth import Users


class UserRepository(BeanieBaseRepository):
    model = Users

    async def get_by_email(self, email: str) -> Users | None:
        return await Users.find_one(Users.email == email, Users.deleted_at == None)  # noqa: E711
{%- endif %}
