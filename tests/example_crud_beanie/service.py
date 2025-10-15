"""Service con lógica de negocio para Beanie."""

from fastapi_basekit.aio.beanie.service.base import BaseService


class UserBeanieService(BaseService):
    """Service para lógica de negocio de usuarios en MongoDB."""

    # Campos por los que se puede buscar
    search_fields = ["name", "email"]

    # Campos que deben ser únicos al crear
    duplicate_check_fields = ["email"]
