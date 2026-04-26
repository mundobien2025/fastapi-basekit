"""Auth service: login + refresh + change password."""

import os
import time
from datetime import datetime{% if cookiecutter.orm == "sqlalchemy" %}, timezone{% endif %}
from typing import Optional

import jwt as pyjwt
from fastapi import Request
{% if cookiecutter.orm == "sqlalchemy" -%}
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
{%- elif cookiecutter.orm == "beanie" -%}
from fastapi_basekit.aio.beanie.service.base import BaseService
{%- endif %}
from fastapi_basekit.exceptions.api_exceptions import (
    JWTAuthenticationException,
    ValidationException,
)
from fastapi_basekit.servicios import JWTService
{% if cookiecutter.orm == "sqlalchemy" -%}
from sqlalchemy.ext.asyncio import AsyncSession
{%- endif %}

from app.config.settings import get_settings
from app.models.auth import Users
from app.repositories.user.repository import UserRepository
from app.utils.security import get_password_hash, verify_password


class AuthService(BaseService):
    def __init__(
        self,
        user_repository: UserRepository,
        request: Optional[Request] = None,
        {% if cookiecutter.orm == "sqlalchemy" %}session: Optional[AsyncSession] = None,{% endif %}
    ):
        super().__init__(user_repository, request=request)
        self.user_repository = user_repository
        {% if cookiecutter.orm == "sqlalchemy" %}self.session = session{% endif %}
        self.jwt_service = JWTService()

    async def login(self, email: str, password: str) -> dict:
        user = await self.user_repository.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise JWTAuthenticationException(message="Invalid credentials")
        if not user.is_active:
            raise JWTAuthenticationException(message="Inactive user")

        {% if cookiecutter.orm == "sqlalchemy" -%}
        # last_login could be added here if you store it on the model
        await self.session.flush()
        {%- elif cookiecutter.orm == "beanie" -%}
        await user.save()
        {%- endif %}

        return self._build_token_pair(user)

    async def refresh(self, refresh_token: str) -> dict:
        try:
            payload = self.jwt_service.decode_token(refresh_token)
        except Exception as exc:
            raise JWTAuthenticationException(message="Invalid refresh token") from exc

        user = await self.user_repository.get(payload.sub)
        if not user or not user.is_active:
            raise JWTAuthenticationException(message="User not found or inactive")

        return self._build_token_pair(user)

    async def change_password(
        self, user: Users, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise ValidationException(message="Current password is incorrect")
        user.password_hash = get_password_hash(new_password)
        {% if cookiecutter.orm == "sqlalchemy" -%}
        await self.session.flush()
        {%- elif cookiecutter.orm == "beanie" -%}
        await user.save()
        {%- endif %}

    def _build_token_pair(self, user: Users) -> dict:
        settings = get_settings()
        secret = os.getenv("JWT_SECRET") or settings.SECRET_KEY
        algorithm = os.getenv("JWT_ALGORITHM", settings.ALGORITHM)
        now = int(time.time())

        access_payload = {
            "sub": str(user.id),
            "exp": now + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
        refresh_payload = {
            "sub": str(user.id),
            "exp": now + settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "type": "refresh",
        }

        return {
            "access_token": pyjwt.encode(access_payload, secret, algorithm=algorithm),
            "refresh_token": pyjwt.encode(refresh_payload, secret, algorithm=algorithm),
            "token_type": "bearer",
        }
