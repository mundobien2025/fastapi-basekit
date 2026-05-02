from fastapi_basekit.aio.sqlmodel.repository.base import BaseRepository

from .models import User


class UserSQLModelRepository(BaseRepository):
    model = User
