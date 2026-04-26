"""User controller."""

{% if cookiecutter.orm == "sqlalchemy" -%}
import uuid
{%- endif %}
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
{% if cookiecutter.orm == "sqlalchemy" -%}
from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
{%- elif cookiecutter.orm == "beanie" -%}
from fastapi_basekit.aio.beanie.controller.base import BeanieBaseController
{%- endif %}
from fastapi_basekit.schema.base import BasePaginationResponse, BaseResponse
from fastapi_restful.cbv import cbv

from app.models.auth import Users
from app.permissions.user import AdminPermission
from app.schemas.user import UserCreateSchema, UserResponseSchema, UserUpdateSchema
from app.services.dependency import get_dependency_service, get_user_service
from app.services.user_service import UserService

router = APIRouter(prefix="/users")


@cbv(router)
class UserController({% if cookiecutter.orm == "sqlalchemy" %}SQLAlchemyBaseController{% else %}BeanieBaseController{% endif %}):
    service: UserService = Depends(get_user_service)
    schema_class = UserResponseSchema
    user: Users = Depends(get_dependency_service)

    def check_permissions(self):
        if self.action in ("create_user", "update_user", "delete_user"):
            return [AdminPermission]
        return []

    @router.get("/", response_model=BasePaginationResponse[UserResponseSchema])
    async def list_users(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
    ):
        return await self.list()

    @router.post(
        "/",
        response_model=BaseResponse[UserResponseSchema],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_user(self, data: UserCreateSchema):
        await self.check_permissions_class()
        created = await self.service.create(data)
        return self.format_response(UserResponseSchema.model_validate(created), message="Created")

    @router.get("/me", response_model=BaseResponse[UserResponseSchema])
    async def me(self):
        return self.format_response(UserResponseSchema.model_validate(self.user))

    @router.get("/{user_id}", response_model=BaseResponse[UserResponseSchema])
    async def get_user(self, user_id: {% if cookiecutter.orm == "sqlalchemy" %}uuid.UUID{% else %}str{% endif %}):
        return await self.retrieve(user_id)

    @router.put("/{user_id}", response_model=BaseResponse[UserResponseSchema])
    async def update_user(self, user_id: {% if cookiecutter.orm == "sqlalchemy" %}uuid.UUID{% else %}str{% endif %}, data: UserUpdateSchema):
        await self.check_permissions_class()
        updated = await self.service.update(str(user_id), data.model_dump(exclude_unset=True))
        return self.format_response(UserResponseSchema.model_validate(updated), message="Updated")

    @router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_user(self, user_id: {% if cookiecutter.orm == "sqlalchemy" %}uuid.UUID{% else %}str{% endif %}):
        await self.check_permissions_class()
        return await self.delete(user_id)
