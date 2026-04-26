"""Dependency factory layer."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi_basekit.exceptions.api_exceptions import JWTAuthenticationException
{% if cookiecutter.orm == "sqlalchemy" -%}
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
{%- endif %}
from app.models.auth import Users

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login/")


async def get_dependency_service(
    request: Request,
    token: str = Depends(oauth2_scheme),
) -> Users:
    user = getattr(request.state, "user", None)
    if not user:
        raise JWTAuthenticationException(
            message="Not authenticated. Valid token required."
        )
    return user


CurrentUser = Annotated[Users, Depends(get_dependency_service)]


def get_auth_service(
    request: Request{% if cookiecutter.orm == "sqlalchemy" %}, session: AsyncSession = Depends(get_db){% endif %}
):
    from app.repositories.user.repository import UserRepository
    from app.services.auth_service import AuthService

    {% if cookiecutter.orm == "sqlalchemy" -%}
    return AuthService(
        user_repository=UserRepository(session),
        request=request,
        session=session,
    )
    {%- else -%}
    return AuthService(
        user_repository=UserRepository(),
        request=request,
    )
    {%- endif %}


def get_user_service(
    request: Request{% if cookiecutter.orm == "sqlalchemy" %}, session: AsyncSession = Depends(get_db){% endif %}
):
    from app.repositories.user.repository import UserRepository
    from app.services.user_service import UserService

    {% if cookiecutter.orm == "sqlalchemy" -%}
    return UserService(
        repository=UserRepository(session),
        request=request,
        session=session,
    )
    {%- else -%}
    return UserService(
        repository=UserRepository(),
        request=request,
    )
    {%- endif %}
