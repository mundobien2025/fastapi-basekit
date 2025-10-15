"""Controller con endpoints REST para Beanie."""

from typing import Optional
from fastapi import APIRouter, Query, Depends, Request
from fastapi_basekit.aio.beanie.controller.base import BeanieBaseController
from .schemas import (
    UserBeanieSchema,
    UserBeanieCreateSchema,
    UserBeanieUpdateSchema,
)
from .service import UserBeanieService
from .repository import UserBeanieRepository


router = APIRouter(prefix="/beanie-users", tags=["beanie-users"])


def get_user_beanie_service(request: Request) -> UserBeanieService:
    """Dependency para obtener el servicio de usuarios Beanie."""
    # En producción, esto obtendría la conexión MongoDB del request
    # Para tests, inyectaremos el mock directamente
    repository = UserBeanieRepository()
    return UserBeanieService(repository=repository)


@router.get("/")
class ListBeanieUsers(BeanieBaseController):
    """Lista usuarios con paginación y filtros usando Beanie."""

    schema_class = UserBeanieSchema
    service: UserBeanieService = Depends(get_user_beanie_service)

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
        age_min: Optional[int] = Query(None, ge=0, description="Edad mínima"),
    ):
        """
        Lista usuarios de MongoDB con soporte para:
        - Paginación (page, count)
        - Búsqueda por texto (search en name, email)
        - Filtro por estado (is_active)
        - Filtro por edad mínima (age_min)
        """
        await self.check_permissions_class()
        return await self.list()


@router.get("/{id}")
class GetBeanieUser(BeanieBaseController):
    """Obtiene un usuario por ID desde MongoDB."""

    schema_class = UserBeanieSchema
    service: UserBeanieService = Depends(get_user_beanie_service)

    async def __call__(self, id: str):
        """Obtiene un usuario específico por su ID."""
        await self.check_permissions_class()
        return await self.retrieve(id)


@router.post("/", status_code=201)
class CreateBeanieUser(BeanieBaseController):
    """Crea un nuevo usuario en MongoDB."""

    schema_class = UserBeanieSchema
    service: UserBeanieService = Depends(get_user_beanie_service)

    async def __call__(self, data: UserBeanieCreateSchema):
        """
        Crea un nuevo usuario en MongoDB.
        Valida que el email sea único.
        """
        await self.check_permissions_class()
        return await self.create(data)


@router.put("/{id}")
class UpdateBeanieUser(BeanieBaseController):
    """Actualiza un usuario existente en MongoDB."""

    schema_class = UserBeanieSchema
    service: UserBeanieService = Depends(get_user_beanie_service)

    async def __call__(self, id: str, data: UserBeanieUpdateSchema):
        """Actualiza un usuario existente por su ID."""
        await self.check_permissions_class()
        return await self.update(id, data)


@router.delete("/{id}")
class DeleteBeanieUser(BeanieBaseController):
    """Elimina un usuario en MongoDB."""

    schema_class = UserBeanieSchema
    service: UserBeanieService = Depends(get_user_beanie_service)

    async def __call__(self, id: str):
        """Elimina un usuario."""
        await self.check_permissions_class()
        return await self.delete(id)
