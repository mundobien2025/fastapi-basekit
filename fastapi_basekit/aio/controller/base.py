import inspect
from typing import Any, ClassVar, Dict, List, Optional, Type, Set
from fastapi import Depends, Request
from pydantic import BaseModel, TypeAdapter

from ..permissions.base import BasePermission

from ...schema.base import BasePaginationResponse, BaseResponse
from ...exceptions.api_exceptions import PermissionException


class BaseController:
    """Montar rutas CRUD genericas y captura errores de negocio."""

    service = Depends()
    schema_class: ClassVar[Type[BaseModel]]
    action: ClassVar[Optional[str]] = None
    request: Request
    _params_excluded_fields: ClassVar[Set[str]] = {
        "self", "page", "count", "search",
        "__class__", "args", "kwargs", "id",
        "payload", "data", "validated_data",
    }

    def __init__(self) -> None:
        endpoint_func = (
            self.request.scope.get("endpoint") if self.request else None
        )
        self.action = endpoint_func.__name__ if endpoint_func else None

    def get_schema_class(self) -> Type[BaseModel]:
        assert self.schema_class is not None, (
            "'%s' should either include a `schema_class` attribute, "
            "or override the `get_serializer_class()` method."
            % self.__class__.__name__
        )
        return self.schema_class

    async def check_permissions_class(self):
        permissions = self.check_permissions()
        if permissions:
            for permission in permissions:
                obj = permission()
                check = await obj.has_permission(self.request)
                if not check:
                    raise PermissionException(obj.message_exception)

    def check_permissions(self) -> List[Type[BasePermission]]:
        pass

    async def list(self):
        params = self._params()
        items, total = await self.service.list(**params)
        count = params.get("count") or 0
        page = params.get("page") or 1

        total_pages = (total + count - 1) // count if count > 0 else 0
        pagination = {
            "page": page,
            "count": count,
            "total": total,
            "total_pages": total_pages,
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
        schema = self.get_schema_class()

        if isinstance(data, list):
            data_dicts = [self.to_dict(item) for item in data]
            adapter = TypeAdapter(List[schema])
            data_parsed = adapter.validate_python(data_dicts)
        elif self.service.repository and isinstance(
            data, self.service.repository.model
        ):
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

    def _params(self) -> Dict[str, Any]:
        """
        Extrae parámetros automáticamente usando introspección.

        Primero intenta obtener parámetros validados por FastAPI desde
        el frame del método llamador (con tipos ya convertidos).
        Si falla, usa el método legacy de request.query_params.
        """
        # Intentar usar introspección para obtener valores validados
        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_locals = frame.f_back.f_locals

            # Extraer page, count, search de los parámetros validados
            page = caller_locals.get("page")
            count = caller_locals.get("count")
            search = caller_locals.get("search")

            # Si encontramos al menos page o count, usamos introspección
            if page is not None or count is not None:
                # Variables estándar a excluir de los filtros
                
                excluded = self._params_excluded_fields
                # Construir filtros con todos los demás parámetros
                # que no empiecen con _ y no sean None
                filters = {
                    k: v
                    for k, v in caller_locals.items()
                    if k not in excluded
                    and not k.startswith("_")
                    and v is not None
                    and not callable(v)
                }

                return {
                    "page": page if page is not None else 1,
                    "count": count if count is not None else 10,
                    "search": search,
                    "filters": filters,
                }

        # Fallback: Método legacy usando request.query_params
        query_params = self.request.query_params if self.request else {}

        page = int(query_params.get("page", 1))
        count = int(query_params.get("count", 10))
        search = query_params.get("search")

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

    def to_dict(self, obj: Any):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return obj
