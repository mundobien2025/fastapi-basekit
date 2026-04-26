"""Auth controller."""

from fastapi import APIRouter, Depends, status
{% if cookiecutter.orm == "sqlalchemy" -%}
from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
{%- elif cookiecutter.orm == "beanie" -%}
from fastapi_basekit.aio.beanie.controller.base import BeanieBaseController
{%- endif %}
from fastapi_basekit.schema.base import BaseResponse
from fastapi_restful.cbv import cbv

from app.models.auth import Users
from app.schemas.auth import LoginSchema, RefreshSchema, TokenResponseSchema
from app.schemas.user import UserResponseSchema
from app.services.auth_service import AuthService
from app.services.dependency import get_auth_service, get_dependency_service

router = APIRouter()


@cbv(router)
class AuthController({% if cookiecutter.orm == "sqlalchemy" %}SQLAlchemyBaseController{% else %}BeanieBaseController{% endif %}):
    service: AuthService = Depends(get_auth_service)
    schema_class = TokenResponseSchema

    @router.post(
        "/login/",
        response_model=BaseResponse[TokenResponseSchema],
        status_code=status.HTTP_200_OK,
    )
    async def login(self, data: LoginSchema):
        tokens = await self.service.login(data.email, data.password)
        return self.format_response(TokenResponseSchema(**tokens), message="Login OK")

    @router.post("/refresh/", response_model=BaseResponse[TokenResponseSchema])
    async def refresh(self, data: RefreshSchema):
        tokens = await self.service.refresh(data.refresh_token)
        return self.format_response(TokenResponseSchema(**tokens), message="Refreshed")

    @router.get("/me", response_model=BaseResponse[UserResponseSchema])
    async def me(self, user: Users = Depends(get_dependency_service)):
        return self.format_response(UserResponseSchema.model_validate(user), message="OK")
