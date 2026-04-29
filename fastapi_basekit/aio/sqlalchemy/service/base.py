from typing import Any, Dict, List, Optional

from fastapi import Request
from pydantic import BaseModel
from ..repository.base import BaseRepository
from ....exceptions.api_exceptions import (
    NotFoundException,
    DatabaseIntegrityException,
)


class BaseService:
    """Servicio base para SQLAlchemy AsyncSession.

    Regla del proyecto: los servicios NO deben llamar `session.flush()`,
    `session.commit()` ni `session.refresh()`. El flush vive en
    `BaseRepository.create / update`; el commit/rollback único por
    request lo gestiona el lifecycle creado con
    `fastapi_basekit.aio.sqlalchemy.make_session_lifecycle`.
    """

    repository: BaseRepository
    search_fields: List[str] = []
    duplicate_check_fields: List[str] = []
    order_by: Optional[str] = None
    action: str | None = None
    kwargs_query: Dict[str, Any] = {}

    def __init__(
        self,
        repository: BaseRepository,
        request: Optional[Request] = None,
        **kwargs,
    ):
        self.repository = repository
        self.request = request

        # Vincular el servicio al repositorio principal
        if self.repository:
            self.repository.service = self

        # Procesar kwargs adicionales para vincular otros repositorios
        for name, value in kwargs.items():
            if isinstance(value, BaseRepository):
                value.service = self
            setattr(self, name, value)
        endpoint_func = (
            self.request.scope.get("endpoint") if self.request else None
        )
        self.action = endpoint_func.__name__ if endpoint_func else None

        # Parámetros compartidos para consultas (especialmente list)
        self.params: Dict[str, Any] = {
            "search": None,
            "page": 1,
            "count": 25,
            "filters": {},
            "use_or": False,
            "joins": None,
            "order_by": self.order_by,
            "search_fields": self.search_fields,
            "meta": {},
        }

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
        page: Optional[int] = None,
        count: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        use_or: Optional[bool] = None,
        joins: Optional[List[str]] = None,
        order_by: Optional[Any] = None,
    ) -> tuple[List[Any], int]:
        # Actualiza self.params con los argumentos
        # proporcionados (si no son None)
        if search is not None:
            self.params["search"] = search
        if page is not None:
            self.params["page"] = page
        if count is not None:
            self.params["count"] = count
        if filters is not None:
            self.params["filters"] = filters
        if use_or is not None:
            self.params["use_or"] = use_or
        if joins is not None:
            self.params["joins"] = joins
        if order_by is not None:
            self.params["order_by"] = order_by

        # Aplica filtros y kwargs de consulta definidos por el servicio
        applied_filters = self.get_filters(self.params["filters"])
        kwargs = self.get_kwargs_query()

        # Prioridad de joins: argumento explícito >
        # kwargs del servicio (por acción)
        final_joins = self.params["joins"]
        if final_joins is None:
            final_joins = kwargs.get("joins")

        # Prioridad de order_by: argumento explícito >
        # kwargs del servicio > default del servicio
        final_order_by = self.params["order_by"]
        if order_by is None:
            final_order_by = kwargs.get("order_by", self.params["order_by"])

        return await self.repository.list_paginated(
            page=self.params["page"],
            count=self.params["count"],
            filters=applied_filters,
            use_or=self.params["use_or"],
            joins=final_joins,
            order_by=final_order_by,
            search=self.params["search"],
            search_fields=self.params["search_fields"],
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

    async def update(self, id: str, data: BaseModel | Dict[str, Any]) -> Any:
        update_data = (
            data.model_dump(exclude_unset=True)
            if isinstance(data, BaseModel)
            else data
        )
        updated = await self.repository.update(id, update_data)
        return updated

    async def delete(self, id: str) -> bool:
        return await self.repository.delete(id)
