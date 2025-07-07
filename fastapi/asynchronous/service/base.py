# app/services/base.py
from typing import Any, Dict, List, Optional

from ..repository.base import BaseRepository
from ...exceptions.api_exceptions import NotFoundException
from pydantic import BaseModel


class BaseService:
    repository: BaseRepository
    search_fields: List[str] = []

    def __init__(self, repository: BaseRepository):
        self.repository = repository

    def get_filters(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Construye y retorna un diccionario con los filtros a aplicar.

        - Puede ser sobreescrito en servicios hijos para lógica específica.
        - Permite validar, limpiar o transformar filtros.
        """
        filters = filters or {}
        # Aquí puedes agregar lógica común o genérica para todos servicios

        return filters

    async def retrieve(self, id: str) -> Any:  # Retorna ODM
        obj = await self.repository.get_by_id(id, fetch_links=True)
        if not obj:
            raise NotFoundException(f"id={id} no encontrado")
        return obj

    async def list(
        self,
        search: Optional[str] = None,
        page: int = 1,
        count: int = 25,
        filters: Optional[Dict[str, Any]] = None,
    ):
        applied_filters = self.get_filters(filters)
        query = await self.repository.build_filter_query(
            search=search,
            search_fields=self.search_fields,
            filters=applied_filters,
        )
        return await self.repository.paginate(query, page, count)

    async def create(self, payload: BaseModel) -> Any:
        if isinstance(payload, dict):
            data = payload
        else:
            data = payload.model_dump()
        created = await self.repository.create(data)
        return created

    async def update(self, id: str, payload: BaseModel) -> Any:
        obj = await self.repository.get_by_id(id, fetch_links=True)
        if not obj:
            raise NotFoundException(f"id={id} no encontrado")
        data = payload.model_dump(exclude_unset=True)
        updated = await self.repository.update(obj, data)
        return updated

    async def delete(self, id: str) -> str:
        obj = await self.repository.get_by_id(id, fetch_links=True)
        if not obj:
            raise NotFoundException(f"id={id} no encontrado")
        await self.repository.delete(obj)
        return "deleted"
