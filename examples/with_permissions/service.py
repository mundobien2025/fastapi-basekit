"""Service para usuarios."""

from fastapi_basekit.aio.sqlalchemy.service.base import BaseService


class UserService(BaseService):
    """Service para usuarios."""

    search_fields = ["name", "email"]
    duplicate_check_fields = ["email"]

