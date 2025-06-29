# app/controllers/base.py
from typing import Any, ClassVar, Dict, List, Optional, Type
from fastapi import Depends, Request

from app.schemas.response import BasePaginationResponse, BaseResponse
from ..service.base import BaseService
from pydantic import BaseModel, TypeAdapter


class BaseController:
    """
    Monta rutas CRUD genéricas y captura errores de negocio.
    Define métodos que pueden heredarse sin repetir try/except.
      GET    /          → list
      GET    /{id}      → retrieve
      POST   /          → create
      PATCH  /{id}      → update
      DELETE /{id}      → delete
    """

    service: BaseService = Depends()
    schema_class: ClassVar[Type[BaseModel]]
    action: ClassVar[Type[str]] = None
    request: Request

    def __init__(self):
        """
        Al instanciarse (por cada petición), el atributo `self.request`
        ya existe porque FastAPI lo inyectó como dependencia.
        Aquí fijamos `self.action` al nombre del método (endpoint) actual.
        """
        # La clave es `scope["endpoint"]`: FastAPI llena esta clave con
        # la función Python que está sirviendo esta ruta.
        endpoint_func = self.request.scope.get("endpoint")
        if endpoint_func:
            # El nombre del endpoint será, por ejemplo:
            # "create_invoice", "list_business_types", etc.
            self.action = endpoint_func.__name__
        else:
            self.action = None

    def get_schema_class(self):

        assert self.schema_class is not None, (
            "'%s' should either include a `schema_class` attribute, "
            "or override the `get_serializer_class()` method."
            % self.__class__.__name__
        )

        return self.schema_class

    async def check_permissions(self):
        """
        Método para validar permisos basado en `self.action` y `self.request`.
        Por defecto no hace nada (permite todo).
        Debe ser sobreescrito en controladores hijos para lógica específica.
        """
        pass

    async def list(self):
        params = self._params()
        items, total = await self.service.list(**params)

        pagination = {
            "page": params.get("page"),
            "count": params.get("count"),
            "total": total,
        }
        return self.format_response(data=items, pagination=pagination)

    async def retrieve(self, id: str):
        item = await self.service.retrieve(id)
        return self.format_response(data=item)

    async def create(self, validated_data: Any):
        result = await self.service.create(validated_data)
        return self.format_response(result, message="Creado exitosamente")

    async def update(self, id: str, validated_data: Any):
        result = await self.service.update(id, validated_data)
        return self.format_response(result, message="Actualizado exitosamente")

    async def delete(self, id: str):
        await self.service.delete(id)
        return self.format_response(None, message="Eliminado exitosamente")

    def format_response(
        self,
        data: Any,
        pagination: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
        status: str = "success",
    ) -> BaseModel:
        """
        Centraliza la creación de respuestas estándar.

        - Si `pagination` es None, devuelve BaseResponse.
        - Si `pagination` es dict, devuelve BasePaginationResponse.
        """
        schema = self.get_schema_class()

        # Si es lista, parseamos con pydantic
        if isinstance(data, list):
            data_dicts = [self.to_dict(item) for item in data]
            adapter = TypeAdapter(List[schema])
            data_parsed = adapter.validate_python(data_dicts)
        elif isinstance(data, self.service.repository.model):
            data_parsed = self.to_dict(data)
            data_parsed = schema.model_validate(data_parsed)
        elif isinstance(data, dict):
            data_parsed = schema.model_validate(data)
        else:
            data_parsed = data

        if pagination:
            return BasePaginationResponse(
                data=data_parsed,
                pagination=pagination,
                message=message or "Operación exitosa",
                status=status,
            )
        else:
            return BaseResponse(
                data=data_parsed,
                message=message or "Operación exitosa",
                status=status,
            )

    def _params(self):
        query_params = self.request.query_params

        page = int(query_params.get("page", 1))
        count = int(query_params.get("count", 10))
        search = query_params.get("search")

        # Extrae los filtros (todo menos paginación y búsqueda)
        filters = {
            k: v
            for k, v in query_params.items()
            if k not in ["page", "count", "search"]
        }

        return {
            "page": page,
            "count": count,
            "search": search,
            "filters": filters,
        }

    def to_dict(self, obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return obj
