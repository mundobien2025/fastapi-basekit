"""Repository para operaciones con Beanie (MongoDB)."""

from fastapi_basekit.aio.beanie.repository.base import BaseRepository
from .models import UserDocument


class UserBeanieRepository(BaseRepository):
    """Repository para el modelo UserDocument."""

    model = UserDocument
