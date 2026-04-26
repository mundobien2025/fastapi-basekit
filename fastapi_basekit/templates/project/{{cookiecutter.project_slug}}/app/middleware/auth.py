"""JWT auth middleware — sets request.state.user."""

from typing import Callable

from fastapi import Request
from fastapi_basekit.exceptions.api_exceptions import JWTAuthenticationException
from fastapi_basekit.servicios import JWTService
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

{% if cookiecutter.orm == "sqlalchemy" -%}
from app.config import database
from app.repositories.user.repository import UserRepository
{%- elif cookiecutter.orm == "beanie" -%}
from app.models.auth import Users
{%- endif %}


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        excluded_paths: list[str] | None = None,
        excluded_path_prefixes: list[str] | None = None,
    ):
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/api/v1/auth/login/",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh/",
            "/api/v1/auth/refresh",
        ]
        self.excluded_path_prefixes = excluded_path_prefixes or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/uploads",
        ]

    def _is_excluded(self, path: str) -> bool:
        if path in self.excluded_paths:
            return True
        return any(path.startswith(p) for p in self.excluded_path_prefixes)

    def _extract_token(self, request: Request) -> str | None:
        auth = request.headers.get("Authorization")
        if not auth:
            return None
        parts = auth.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        return parts[1]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._is_excluded(request.url.path):
            return await call_next(request)

        token = self._extract_token(request)
        if token:
            try:
                user_id = JWTService().decode_token(token).sub
{% if cookiecutter.orm == "sqlalchemy" %}
                async with database.AsyncSessionFactory() as session:
                    user = await UserRepository(session).get(user_id)
                    if user and user.is_active:
                        request.state.user = user
{% elif cookiecutter.orm == "beanie" %}
                user = await Users.get(user_id)
                if user and user.is_active:
                    request.state.user = user
{% endif %}
            except JWTAuthenticationException:
                pass
            except Exception:
                pass

        return await call_next(request)
