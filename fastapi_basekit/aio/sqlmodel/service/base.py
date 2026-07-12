from typing import Any, Dict, Generic, List, Optional, Tuple

from fastapi import Request
from pydantic import BaseModel

from ..repository.base import BaseRepository, ModelT
from ....exceptions.api_exceptions import (
    NotFoundException,
    DatabaseIntegrityException,
)


class BaseService(Generic[ModelT]):
    """Servicio base para SQLModel AsyncSession, parametrizado por el modelo.

    Idéntico en contrato al servicio de SQLAlchemy pero referencia el
    repositorio SQLModel.  Proporciona CRUD, paginación, búsqueda y
    verificación de duplicados. Declara el modelo vía el genérico::

        class UserService(BaseService[User]):
            repository: UserRepository
    """

    repository: BaseRepository[ModelT]
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

        # Copia por instancia de los defaults mutables (heredados como
        # atributos de CLASE, compartidos por el proceso). Sin esto, mutar
        # `self.search_fields.append(...)` en runtime contamina la clase y
        # otras requests. Respeta el override del subclass.
        self.search_fields = list(self.search_fields)
        self.duplicate_check_fields = list(self.duplicate_check_fields)
        self.kwargs_query = dict(self.kwargs_query)

        if self.repository:
            self.repository.service = self

        for name, value in kwargs.items():
            if isinstance(value, BaseRepository):
                value.service = self
            setattr(self, name, value)

        endpoint_func = (
            self.request.scope.get("endpoint") if self.request else None
        )
        self.action = endpoint_func.__name__ if endpoint_func else None

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
        """Sobrescribe para validar/transformar filtros antes de consultar."""
        return filters or {}

    def get_kwargs_query(self) -> Dict[str, Any]:
        """Sobrescribe para retornar kwargs de consulta para el repositorio.

        Ejemplo::

            def get_kwargs_query(self):
                if self.action in ["retrieve", "list"]:
                    return {"joins": ["team"]}
                return super().get_kwargs_query()
        """
        return self.kwargs_query or {}

    async def retrieve(
        self, id: str, joins: Optional[List[str]] = None
    ) -> ModelT:
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
    ) -> Tuple[List[ModelT], int]:
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

        applied_filters = self.get_filters(self.params["filters"])
        kwargs = self.get_kwargs_query()

        final_joins = self.params["joins"]
        if final_joins is None:
            final_joins = kwargs.get("joins")

        final_order_by = self.params["order_by"]
        if order_by is None:
            final_order_by = kwargs.get("order_by", self.params["order_by"])

        items, total = await self.repository.list_paginated(
            page=self.params["page"],
            count=self.params["count"],
            filters=applied_filters,
            use_or=self.params["use_or"],
            joins=final_joins,
            order_by=final_order_by,
            search=self.params["search"],
            search_fields=self.params["search_fields"],
        )
        items = await self.post_process_list(items)
        return items, total

    async def post_process_list(self, items: List[ModelT]) -> List[ModelT]:
        """Hook: transforma/enriquece los items DE UNA PÁGINA ya paginada.

        El método para "hacer algo custom con los resultados" SIN reescribir la
        paginación ni overridear `list()`. Corre después de `list_paginated`,
        sobre los items de la página actual. Default: sin cambios. NO cambies
        `total` ni filtres items acá (usa `get_filters`/`build_list_queryset`).
        """
        return items

    async def create(
        self,
        payload: BaseModel | Dict[str, Any],
        check_fields: Optional[List[str]] = None,
    ) -> ModelT:
        data = (
            payload.model_dump() if isinstance(payload, BaseModel) else payload
        )
        fields = (
            check_fields
            if check_fields is not None
            else self.duplicate_check_fields
        )
        if fields:
            field_filters = {f: data[f] for f in fields if f in data}
            if field_filters:
                existing = await self.repository.get_by_filters(field_filters)
                if existing:
                    raise DatabaseIntegrityException(
                        message="Registro ya existe", data=field_filters
                    )
        return await self.repository.create(data)

    async def update(
        self, id: str, data: BaseModel | Dict[str, Any]
    ) -> ModelT:
        update_data = (
            data.model_dump(exclude_unset=True)
            if isinstance(data, BaseModel)
            else data
        )
        return await self.repository.update(id, update_data)

    async def delete(self, id: str) -> bool:
        return await self.repository.delete(id)
