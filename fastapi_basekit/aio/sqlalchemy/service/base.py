from typing import Any, Dict, List, Optional

from fastapi import Request
from pydantic import BaseModel
from ..repository.base import BaseRepository
from ....exceptions.api_exceptions import (
    NotFoundException,
    DatabaseIntegrityException,
)


class BaseService:
    """Servicio base para SQLAlchemy AsyncSession."""

    repository: BaseRepository
    search_fields: List[str] = []
    duplicate_check_fields: List[str] = []
    action: str | None = None
    kwargs_query: Dict[str, Any] = {}

    def __init__(
        self,
        repository: BaseRepository,
        request: Optional[Request] = None,
    ):
        self.repository = repository
        self.request = request
        endpoint_func = (
            self.request.scope.get("endpoint") if self.request else None
        )
        self.action = endpoint_func.__name__ if endpoint_func else None

    def get_filters(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Sobrescribe para validar/transformar filtros entrantes
        antes de consultar."""
        return filters or {}

    def get_kwargs_query(self) -> Dict[str, Any]:
        """Sobrescribe para retornar kwargs de consulta para el repositorio.

        Ejemplo de uso en un servicio:

            def get_kwargs_query(self):
                if self.action in ["retrieve", "list"]:
                    return {"joins": ["role"]}
                return super().get_kwargs_query()

        """
        return self.kwargs_query or {}

    async def retrieve(
        self, id: str, joins: Optional[List[str]] = None
    ) -> Any:
        # Permite que el servicio defina joins u otros kwargs por acción
        kwargs = self.get_kwargs_query()
        if joins is None:
            joins = kwargs.get("joins")

        obj = await self.repository.get_with_joins(id, joins=joins)
        if not obj:
            obj = await self.repository.get(id)
        if not obj:
            raise NotFoundException(f"id={id} no encontrado")
        return obj

    async def list(
        self,
        search: Optional[str] = None,
        page: int = 1,
        count: int = 25,
        filters: Optional[Dict[str, Any]] = None,
        use_or: bool = False,
        joins: Optional[List[str]] = None,
        order_by: Optional[Any] = None,
    ) -> tuple[List[Any], int]:
        # Aplica filtros y kwargs de consulta definidos por el servicio
        applied = self.get_filters(filters)
        kwargs = self.get_kwargs_query()
        if joins is None:
            joins = kwargs.get("joins")
        if order_by is None:
            order_by = kwargs.get("order_by")
        return await self.repository.list_paginated(
            page=page,
            count=count,
            filters=applied,
            use_or=use_or,
            joins=joins,
            order_by=order_by,
            search=search,
            search_fields=self.search_fields,
        )

    async def create(
        self,
        payload: BaseModel | Dict[str, Any],
        check_fields: Optional[List[str]] = None,
    ) -> Any:
        data = (
            payload.model_dump() if isinstance(payload, BaseModel) else payload
        )
        fields = (
            check_fields
            if check_fields is not None
            else self.duplicate_check_fields
        )
        if fields:
            filters = {f: data[f] for f in fields if f in data}
            if filters:
                existing = await self.repository.get_by_filters(filters)
                if existing:
                    raise DatabaseIntegrityException(
                        message="Registro ya existe", data=filters
                    )
        created = await self.repository.create(data)
        return created

    async def update(
        self, id: str, data: BaseModel | Dict[str, Any]
    ) -> Any:
        update_data = (
            data.model_dump(exclude_unset=True)
            if isinstance(data, BaseModel)
            else data
        )
        updated = await self.repository.update(id, update_data)
        return updated

    async def delete(self, id: str) -> bool:
        return await self.repository.delete(id)
