"""Controller con endpoints REST para usuarios."""

from typing import Optional
from fastapi import APIRouter, Query, Depends, Request
from fastapi_basekit.aio.sqlalchemy.controller.base import (
    SQLAlchemyBaseController,
)
from .schemas import UserSchema, UserCreateSchema, UserUpdateSchema
from .service import UserService
from .repository import UserRepository


router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(request: Request) -> UserService:
    """Dependency para obtener el servicio de usuarios."""
    # En producción, esto obtendría la sesión de DB del request
    repository = UserRepository(db=request.state.db)
    return UserService(repository=repository, request=request)


@router.get("/")
class ListUsers(SQLAlchemyBaseController):
    """Lista usuarios con paginación y filtros."""

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(
        self,
        page: int = Query(1, ge=1, description="Número de página"),
        count: int = Query(10, ge=1, le=100, description="Items por página"),
        search: Optional[str] = Query(
            None, description="Buscar en nombre o email"
        ),
        is_active: Optional[bool] = Query(
            None, description="Filtrar por estado activo"
        ),
    ):
        """
        Lista usuarios con soporte para:
        - Paginación (page, count)
        - Búsqueda por texto (search en name, email)
        - Filtro por estado (is_active)
        """
        return await self.list()


@router.get("/{id}")
class GetUser(SQLAlchemyBaseController):
    """Obtiene un usuario por ID."""

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, id: int):
        """Obtiene un usuario específico por su ID."""
        return await self.retrieve(str(id))


@router.post("/", status_code=201)
class CreateUser(SQLAlchemyBaseController):
    """Crea un nuevo usuario."""

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, data: UserCreateSchema):
        """
        Crea un nuevo usuario.
        Valida que el email sea único.
        """
        return await self.create(data)


@router.put("/{id}")
class UpdateUser(SQLAlchemyBaseController):
    """Actualiza un usuario existente."""

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, id: int, data: UserUpdateSchema):
        """Actualiza un usuario existente por su ID."""
        return await self.update(str(id), data)


@router.delete("/{id}")
class DeleteUser(SQLAlchemyBaseController):
    """Elimina un usuario."""

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, id: int):
        """Elimina un usuario por su ID."""
        return await self.delete(str(id))

