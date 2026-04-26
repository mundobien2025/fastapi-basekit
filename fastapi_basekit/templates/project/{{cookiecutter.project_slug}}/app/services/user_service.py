"""User CRUD service."""

from typing import Any, Optional

from fastapi import Request
{% if cookiecutter.orm == "sqlalchemy" -%}
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
{%- elif cookiecutter.orm == "beanie" -%}
from fastapi_basekit.aio.beanie.service.base import BaseService
{%- endif %}
from fastapi_basekit.exceptions.api_exceptions import DatabaseIntegrityException
{% if cookiecutter.orm == "sqlalchemy" -%}
from sqlalchemy.ext.asyncio import AsyncSession
{%- endif %}

from app.repositories.user.repository import UserRepository
from app.utils.security import get_password_hash


class UserService(BaseService):
    repository: UserRepository
    search_fields = ["email", "full_name"]
    duplicate_check_fields = ["email"]

    def __init__(
        self,
        repository: UserRepository,
        request: Optional[Request] = None,
        {% if cookiecutter.orm == "sqlalchemy" %}session: Optional[AsyncSession] = None,{% endif %}
    ):
        super().__init__(repository, request=request)
        self.repository = repository
        {% if cookiecutter.orm == "sqlalchemy" %}self.session = session{% endif %}

    async def create(self, payload, check_fields=None) -> Any:
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        password = data.pop("password", None)
        if not password:
            raise DatabaseIntegrityException(message="Password required")

        existing = await self.repository.get_by_email(data["email"])
        if existing:
            raise DatabaseIntegrityException(message="Email already registered")

        data["password_hash"] = get_password_hash(password)
        return await self.repository.create(data)
