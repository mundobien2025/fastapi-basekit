"""Service con joins dinámicos para relaciones."""

from fastapi_basekit.aio.sqlalchemy.service.base import BaseService


class UserService(BaseService):
    """Service para usuarios con soporte de relaciones."""

    search_fields = ["name", "email"]
    duplicate_check_fields = ["email"]

    def get_kwargs_query(self) -> dict:
        """
        Define los joins según la acción.
        En 'list' y 'retrieve' carga automáticamente las relaciones.
        """
        if self.action in ["list", "retrieve"]:
            return {"joins": ["role", "roles"]}
        return {}

