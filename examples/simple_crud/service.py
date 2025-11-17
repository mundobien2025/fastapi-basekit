"""Service para usuarios con lógica de negocio."""

from fastapi_basekit.aio.sqlalchemy.service.base import BaseService


class UserService(BaseService):
    """Service para lógica de negocio de usuarios."""

    # Campos por los que se puede buscar
    search_fields = ["name", "email"]

    # Campos que deben ser únicos al crear
    duplicate_check_fields = ["email"]

