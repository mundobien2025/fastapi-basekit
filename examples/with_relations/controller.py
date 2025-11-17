"""Controller con relaciones y joins."""

from typing import Optional
from fastapi import APIRouter, Query, Depends, Request
from fastapi_basekit.aio.sqlalchemy.controller.base import (
    SQLAlchemyBaseController,
)
from .schemas import UserSchema, UserCreateSchema
from .service import UserService
from .repository import UserRepository


router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(request: Request) -> UserService:
    """Dependency para obtener el servicio de usuarios."""
    repository = UserRepository(db=request.state.db)
    return UserService(repository=repository, request=request)


@router.get("/")
class ListUsers(SQLAlchemyBaseController):
    """
    Lista usuarios con relaciones cargadas automáticamente.
    
    Las relaciones 'role' y 'roles' se cargan mediante
    eager loading para evitar queries N+1.
    """

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
        role_id: Optional[int] = Query(None, description="Filtrar por rol"),
    ):
        """
        Lista usuarios con relaciones cargadas.
        Los joins se aplican automáticamente desde get_kwargs_query().
        """
        filters = {}
        if role_id is not None:
            filters["role_id"] = role_id

        return await self.list(search=search, filters=filters)


@router.get("/{id}")
class GetUser(SQLAlchemyBaseController):
    """Obtiene un usuario con sus relaciones."""

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, id: int):
        """
        Obtiene un usuario con sus relaciones cargadas.
        Los joins se aplican automáticamente.
        """
        return await self.retrieve(str(id))


@router.post("/", status_code=201)
class CreateUser(SQLAlchemyBaseController):
    """Crea un nuevo usuario."""

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, data: UserCreateSchema):
        """Crea un nuevo usuario."""
        return await self.create(data)

