"""SQLAlchemy CRUD controller fixture using the canonical `@cbv` pattern.

Endpoints live as methods on a single CBV class. This is the pattern the
fastapi-basekit skill documents (see `.claude/skills/fastapi-basekit-crud/SKILL.md`)
and the only way FastAPI properly resolves class-based handlers — the
previous ``@router.get`` decoration of bare classes never produced a
working handler (it returned an empty body).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi_restful.cbv import cbv

from fastapi_basekit.aio.sqlalchemy.controller.base import (
    SQLAlchemyBaseController,
)

from .repository import UserRepository
from .schemas import UserCreateSchema, UserSchema, UserUpdateSchema
from .service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(request: Request) -> UserService:
    """Dependency factory; tests override this via ``app.dependency_overrides``
    to inject a session-bound repository.
    """
    repository = UserRepository(db=request.state.db)
    return UserService(repository=repository)


@cbv(router)
class UserController(SQLAlchemyBaseController):
    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    @router.get("/")
    async def list_users(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
        is_active: Optional[bool] = Query(None),
        age_min: Optional[int] = Query(None, ge=0),
    ):
        return await self.list()

    @router.get("/{id}")
    async def retrieve_user(self, id: int):
        return await self.retrieve(str(id))

    @router.post("/", status_code=201)
    async def create_user(self, data: UserCreateSchema):
        return await self.create(data)

    @router.put("/{id}")
    async def update_user(self, id: int, data: UserUpdateSchema):
        return await self.update(str(id), data)

    @router.delete("/{id}")
    async def delete_user(self, id: int):
        return await self.delete(str(id))
