"""Controller for SQLModel CRUD tests (mirrors the SQLAlchemy fixture style)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from fastapi_basekit.aio.sqlmodel.controller.base import SQLModelBaseController

from .repository import UserSQLModelRepository
from .schemas import UserCreateSchema, UserSchema, UserUpdateSchema
from .service import UserSQLModelService


router = APIRouter(prefix="/users-sqlmodel", tags=["users-sqlmodel"])


def get_user_service(request: Request) -> UserSQLModelService:
    repository = UserSQLModelRepository(db=request.state.db)
    return UserSQLModelService(repository=repository)


@router.get("/")
class ListUsers(SQLModelBaseController):
    schema_class = UserSchema
    service: UserSQLModelService = Depends(get_user_service)

    async def __call__(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
        is_active: Optional[bool] = Query(None),
        age_min: Optional[int] = Query(None, ge=0),
    ):
        return await self.list()


@router.get("/{id}")
class GetUser(SQLModelBaseController):
    schema_class = UserSchema
    service: UserSQLModelService = Depends(get_user_service)

    async def __call__(self, id: int):
        return await self.retrieve(str(id))


@router.post("/", status_code=201)
class CreateUser(SQLModelBaseController):
    schema_class = UserSchema
    service: UserSQLModelService = Depends(get_user_service)

    async def __call__(self, data: UserCreateSchema):
        return await self.create(data)


@router.put("/{id}")
class UpdateUser(SQLModelBaseController):
    schema_class = UserSchema
    service: UserSQLModelService = Depends(get_user_service)

    async def __call__(self, id: int, data: UserUpdateSchema):
        return await self.update(str(id), data)


@router.delete("/{id}")
class DeleteUser(SQLModelBaseController):
    schema_class = UserSchema
    service: UserSQLModelService = Depends(get_user_service)

    async def __call__(self, id: int):
        return await self.delete(str(id))
