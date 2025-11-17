"""Permisos personalizados para usuarios."""

from typing import List, Type
from fastapi import Request
from fastapi_basekit.aio.permissions.base import BasePermission
from fastapi_basekit.exceptions.api_exceptions import PermissionException


class IsAdmin(BasePermission):
    """Permiso: Solo administradores."""

    message_exception = "Solo los administradores pueden realizar esta acción"

    async def has_permission(self, request: Request) -> bool:
        """Verifica si el usuario es administrador."""
        user = getattr(request.state, "user", None)
        if not user:
            return False
        return getattr(user, "is_admin", False)


class IsActive(BasePermission):
    """Permiso: Usuario activo."""

    message_exception = "Solo usuarios activos pueden realizar esta acción"

    async def has_permission(self, request: Request) -> bool:
        """Verifica si el usuario está activo."""
        user = getattr(request.state, "user", None)
        if not user:
            return False
        return getattr(user, "is_active", False)


class IsOwnerOrAdmin(BasePermission):
    """Permiso: Propietario o administrador."""

    message_exception = "Solo el propietario o un administrador puede realizar esta acción"

    async def has_permission(self, request: Request) -> bool:
        """Verifica si el usuario es el propietario o administrador."""
        user = getattr(request.state, "user", None)
        if not user:
            return False

        # Obtener el ID del recurso desde la ruta
        resource_id = request.path_params.get("id")
        if not resource_id:
            return False

        # Si es admin, tiene permiso
        if getattr(user, "is_admin", False):
            return True

        # Si es el propietario, tiene permiso
        return str(user.id) == str(resource_id)

