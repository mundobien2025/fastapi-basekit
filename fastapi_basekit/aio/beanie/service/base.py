from typing import Any, Dict, List, Optional, Union

from fastapi import Request
from pydantic import BaseModel


from ...beanie.repository.base import BaseRepository
from ....exceptions.api_exceptions import (
    NotFoundException,
    DatabaseIntegrityException,
)


class BaseService:
    """Servicio base específico para Beanie ODM (async)."""

    repository: BaseRepository
    search_fields: List[str] = []
    duplicate_check_fields: List[str] = []
    kwargs_query: Dict[str, Union[str, int]] = {}
    action: str = ""

    def __init__(
        self, repository: BaseRepository, request: Optional[Request] = None
    ):
        self.repository = repository
        self.request = request
        endpoint_func = (
            self.request.scope.get("endpoint") if self.request else None
        )
        self.action = endpoint_func.__name__ if endpoint_func else None

    async def _check_duplicate(self, data: Dict[str, Any], fields: List[str]):
        filters = {f: data[f] for f in fields if f in data}
        if not filters:
            return

        existing = await self.repository.get_by_fields(filters)
        if existing:
            raise DatabaseIntegrityException(
                message="Registro ya existe",
                data=filters,
            )

    def get_kwargs_query(self) -> Dict[str, Any]:
        return self.kwargs_query

    def get_filters(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        filters = filters or {}
        return filters

    async def retrieve(self, id: str):
        kwargs = self.get_kwargs_query()
        obj = await self.repository.get_by_id(id, **kwargs)
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
        kwargs = self.get_kwargs_query()
        applied_filters = self.get_filters(filters)
        query = self.repository.build_filter_query(
            search=search,
            search_fields=self.search_fields,
            filters=applied_filters,
            **kwargs,
        )
        return await self.repository.paginate(query, page, count)

    async def create(
        self, payload: BaseModel, check_fields: Optional[List[str]] = None
    ) -> Any:
        data = (
            payload.model_dump() if not isinstance(payload, dict) else payload
        )
        fields = (
            check_fields
            if check_fields is not None
            else self.duplicate_check_fields
        )
        if fields:
            await self._check_duplicate(data, fields)
        created = await self.repository.create(data)
        kwargs = self.get_kwargs_query()
        return (
            await self.repository.get_by_id(created.id, **kwargs)
            if kwargs
            else created
        )

    async def update(self, id: str, data: BaseModel) -> Any:
        kwargs = self.get_kwargs_query()
        obj = await self.repository.get_by_id(id, **kwargs)
        if not obj:
            raise NotFoundException(f"id={id} no encontrado")
        if isinstance(data, BaseModel):
            data = data.model_dump(exclude_unset=True)
        updated = await self.repository.update(obj, data)
        return updated

    async def delete(self, id: str) -> str:
        obj = await self.repository.get_by_id(id)
        if not obj:
            raise NotFoundException(f"id={id} no encontrado")
        await self.repository.delete(obj)
        return "deleted"
