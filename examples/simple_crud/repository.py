"""Repository para usuarios."""

from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from .models import User


class UserRepository(BaseRepository):
    """Repository para el modelo User."""

    model = User

