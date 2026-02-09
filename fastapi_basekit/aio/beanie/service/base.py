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
    order_by: Optional[List[tuple]] = None

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

    def get_order(self) -> Optional[List[tuple]]:
        """Override this method to define custom ordering.
        
        Returns:
            List of tuples with (field_name, direction) where direction is 1 for ascending or -1 for descending.
            Example: [("created_at", -1)] for newest first
        """
        return self.order_by

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
        order_by: Optional[str] = None,  # NEW: Dynamic ordering (e.g., "-created_at" or "tool__name")
    ):
        kwargs = self.get_kwargs_query()
        applied_filters = self.get_filters(filters)
        
        # Determine which ordering to use
        if order_by:
            # Dynamic ordering from parameter (takes precedence)
            order_str = order_by
        else:
            # Fall back to service-level ordering
            default_order = self.get_order()
            if default_order:
                # Convert list of tuples to string format
                # e.g., [("created_at", -1)] -> "-created_at"
                field, direction = default_order[0]
                order_str = f"{'-' if direction == -1 else ''}{field}"
            else:
                order_str = None
        
        # Check if we need aggregation (nested field with __ or .)
        if order_str and ("__" in order_str or "." in order_str):
            # Use aggregation pipeline for nested ordering
            return await self.repository.list_with_aggregation(
                search=search,
                search_fields=self.search_fields,
                filters=applied_filters,
                order_by=order_str,
                page=page,
                count=count,
                **kwargs,
            )
        else:
            # Use standard query for simple ordering
            order_list = None
            if order_str:
                # Parse the order string
                direction = -1 if order_str.startswith("-") else 1
                field = order_str.lstrip("-")
                order_list = [(field, direction)]
            
            query = self.repository.build_filter_query(
                search=search,
                search_fields=self.search_fields,
                filters=applied_filters,
                order_by=order_list,
                **kwargs,
            )
            return await self.repository.paginate(query, page, count, order_by=order_list)

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
