"""Controller con sistema de permisos."""

from typing import List, Type, Optional
from fastapi import APIRouter, Query, Depends, Request
from fastapi_basekit.aio.sqlalchemy.controller.base import (
    SQLAlchemyBaseController,
)
from fastapi_basekit.aio.permissions.base import BasePermission
from .schemas import UserSchema, UserCreateSchema
from .service import UserService
from .repository import UserRepository
from .permissions import IsAdmin, IsActive, IsOwnerOrAdmin


router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(request: Request) -> UserService:
    """Dependency para obtener el servicio de usuarios."""
    repository = UserRepository(db=request.state.db)
    return UserService(repository=repository, request=request)


@router.get("/")
class ListUsers(SQLAlchemyBaseController):
    """
    Lista usuarios.
    Requiere que el usuario esté activo.
    """

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    def check_permissions(self) -> List[Type[BasePermission]]:
        """Define los permisos requeridos para listar."""
        return [IsActive]

    async def __call__(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
    ):
        """Lista usuarios (requiere usuario activo)."""
        return await self.list(search=search)


@router.get("/{id}")
class GetUser(SQLAlchemyBaseController):
    """
    Obtiene un usuario.
    Requiere ser el propietario o administrador.
    """

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    def check_permissions(self) -> List[Type[BasePermission]]:
        """Define los permisos requeridos para obtener."""
        return [IsOwnerOrAdmin]

    async def __call__(self, id: int):
        """Obtiene un usuario (requiere ser propietario o admin)."""
        return await self.retrieve(str(id))


@router.post("/", status_code=201)
class CreateUser(SQLAlchemyBaseController):
    """
    Crea un usuario.
    Requiere ser administrador.
    """

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    def check_permissions(self) -> List[Type[BasePermission]]:
        """Define los permisos requeridos para crear."""
        return [IsAdmin]

    async def __call__(self, data: UserCreateSchema):
        """Crea un usuario (requiere ser admin)."""
        return await self.create(data)


@router.put("/{id}")
class UpdateUser(SQLAlchemyBaseController):
    """
    Actualiza un usuario.
    Requiere ser el propietario o administrador.
    """

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    def check_permissions(self) -> List[Type[BasePermission]]:
        """Define los permisos requeridos para actualizar."""
        return [IsOwnerOrAdmin]

    async def __call__(self, id: int, data: UserCreateSchema):
        """Actualiza un usuario (requiere ser propietario o admin)."""
        return await self.update(str(id), data)


@router.delete("/{id}")
class DeleteUser(SQLAlchemyBaseController):
    """
    Elimina un usuario.
    Requiere ser administrador.
    """

    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    def check_permissions(self) -> List[Type[BasePermission]]:
        """Define los permisos requeridos para eliminar."""
        return [IsAdmin]

    async def __call__(self, id: int):
        """Elimina un usuario (requiere ser admin)."""
        return await self.delete(str(id))

