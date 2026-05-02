from fastapi_basekit.aio.sqlmodel.service.base import BaseService


class UserSQLModelService(BaseService):
    search_fields = ["name", "email"]
    duplicate_check_fields = ["email"]
