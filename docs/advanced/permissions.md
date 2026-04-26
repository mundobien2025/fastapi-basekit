# Permisos personalizados

## `BasePermission` class

```python
from fastapi import Request
from fastapi_basekit.aio.permissions.base import BasePermission

from app.models.enums import UserRoleEnum


class AdminPermission(BasePermission):
    message_exception: str = "Se requiere rol admin"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if not user:
            return False
        return user.role == UserRoleEnum.admin
```

`request.state.user` lo setea `AuthenticationMiddleware` por request.

## Por acción del controller

```python
def check_permissions(self):
    if self.action in ("delete_thing", "update_thing"):
        return [AdminPermission]
    if self.action == "publish_thing":
        return [AdminPermission, PublisherPermission]   # AND
    return []

@router.delete("/{thing_id}")
async def delete_thing(self, thing_id: uuid.UUID):
    await self.check_permissions_class()    # dispara verificación
    return await self.delete(thing_id)
```

`check_permissions_class()` itera la lista y lanza `PermissionException` (HTTP 403) si alguna `has_permission()` falla.

## Permisos compuestos

```python
class WriterPermission(BasePermission):
    """admin OR manager OR seller (no readonly)."""
    message_exception = "Solo lectura: no puede modificar"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if not user:
            return False
        return user.role in (UserRoleEnum.admin, UserRoleEnum.manager, UserRoleEnum.seller)
```

## Platform admin

```python
class PlatformAdminPermission(BasePermission):
    message_exception = "Se requiere ser administrador de plataforma"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return bool(user and getattr(user, "is_platform_admin", False))
```

## Object-level permissions

`BasePermission.has_permission()` recibe solo `request`. Para verificar ownership de objetos:

```python
class ThingOwnerPermission(BasePermission):
    message_exception = "Solo el dueño puede modificar este recurso"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if not user:
            return False
        thing_id = request.path_params.get("thing_id")
        if not thing_id:
            return False
        # OPCIÓN A: query directo (rompe abstraction)
        # OPCIÓN B: setear flag en service.retrieve y verificar request.state
        thing_owner_id = getattr(request.state, "_thing_owner_id", None)
        return thing_owner_id == user.id
```

Más limpio: hacer el check en el service directo, no en `BasePermission`.

## RBAC con tablas

Para permission system DB-driven (Roles/Permissions/Modules tables + `EndpointPermission` middleware), ver el ejemplo en `axion_accounter_backend` o `fluxio_core_backend` — usan `PermissionMiddleware` que consulta DB en cada request.

Para apps simples, role-enum + `BasePermission` subclasses es más liviano.
