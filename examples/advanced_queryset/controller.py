"""Controller avanzado con queryset personalizado."""

from typing import Optional
from fastapi import APIRouter, Query, Depends, Request
from fastapi_basekit.aio.sqlalchemy.controller.base import (
    SQLAlchemyBaseController,
)
from .schemas import UserWithStatsSchema, UserCreateSchema
from .service import UserService
from .repository import UserRepository


router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(request: Request) -> UserService:
    """Dependency para obtener el servicio de usuarios."""
    repository = UserRepository(db=request.state.db)
    return UserService(repository=repository, request=request)


@router.get("/")
class ListUsersWithStats(SQLAlchemyBaseController):
    """
    Lista usuarios con estadísticas agregadas.
    
    Incluye automáticamente:
    - Número de referidos por usuario
    - Total de órdenes por usuario
    - Total gastado por usuario
    """

    schema_class = UserWithStatsSchema
    service: UserService = Depends(get_user_service)

    async def __call__(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
        min_referidos: Optional[int] = Query(
            None, ge=0, description="Mínimo número de referidos"
        ),
    ):
        """
        Lista usuarios con estadísticas.
        
        El queryset personalizado se aplica automáticamente
        sin necesidad de reescribir el método list().
        """
        filters = {}
        if min_referidos is not None:
            # Nota: Los filtros en agregaciones requieren HAVING
            # Esto se manejaría en build_queryset() si fuera necesario
            pass

        return await self.list(search=search, filters=filters)


@router.post("/", status_code=201)
class CreateUser(SQLAlchemyBaseController):
    """Crea un nuevo usuario."""

    schema_class = UserWithStatsSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, data: UserCreateSchema):
        """Crea un nuevo usuario."""
        return await self.create(data)

