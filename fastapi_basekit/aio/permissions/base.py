from fastapi import Request


class BasePermission:
    message_exception: str = "Permiso denegado"
    """Clase base de permisos, para extender según lógica."""

    async def has_permission(self, request: Request) -> bool:
        """Sobreescribir con la lógica de permiso."""
        return True
