"""Permission classes (role-enum based)."""

from fastapi import Request
from fastapi_basekit.aio.permissions.base import BasePermission

from app.models.enums import UserRoleEnum


class AdminPermission(BasePermission):
    message_exception: str = "Admin role required"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if not user:
            return False
        return user.role == UserRoleEnum.admin


class PlatformAdminPermission(BasePermission):
    message_exception: str = "Platform admin required"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if not user:
            return False
        return bool(getattr(user, "is_platform_admin", False))
