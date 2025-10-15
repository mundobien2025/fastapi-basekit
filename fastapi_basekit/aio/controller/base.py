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
        "self",
        "page",
        "count",
        "search",
        "__class__",
        "args",
        "kwargs",
        "id",
        "payload",
        "data",
        "validated_data",
    }

    def __init__(self) -> None:
        endpoint_func = (
            self.request.scope.get("endpoint")
            if hasattr(self, "request") and self.request
            else None
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
        response_status: str = "success",
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
                status=response_status,
            )
        else:
            return BaseResponse(
                data=data_parsed,
                message=message or "Operación exitosa",
                status=response_status,
            )

    def _params(self, skip_frames: int = 1) -> Dict[str, Any]:
        """
        Extrae parámetros automáticamente usando introspección.

        Usa query_params como fuente de verdad para determinar QUÉ parámetros
        existen, y luego intenta obtener sus VALORES validados desde el frame
        del método llamador (con tipos ya convertidos por FastAPI).

        Args:
            skip_frames: Número de frames a saltar (1 por defecto para
                llamadas directas, 2 para controllers heredados)
        """
        # Obtener query_params como fuente de verdad
        query_params = self.request.query_params if self.request else {}

        # Parámetros especiales de paginación y búsqueda
        standard_params = {"page", "count", "search"}

        # Valores por defecto
        page = 1
        count = 10
        search = None
        filters = {}

        # Intentar obtener valores validados del frame local
        frame = inspect.currentframe()
        caller_locals = {}

        if frame:
            # Navegar hacia atrás en la pila según skip_frames
            caller_frame = frame
            for _ in range(skip_frames):
                if caller_frame and caller_frame.f_back:
                    caller_frame = caller_frame.f_back
                else:
                    break

            if caller_frame:
                caller_locals = caller_frame.f_locals

        # Procesar cada parámetro de query_params
        for param_name, param_value in query_params.items():
            # Intentar obtener valor validado del frame local
            validated_value = caller_locals.get(param_name)

            # Si no existe en locals, usar el valor del query_param
            final_value = (
                validated_value if validated_value is not None else param_value
            )

            # Clasificar el parámetro
            if param_name == "page":
                page = (
                    int(final_value)
                    if not isinstance(final_value, int)
                    else final_value
                )
            elif param_name == "count":
                count = (
                    int(final_value)
                    if not isinstance(final_value, int)
                    else final_value
                )
            elif param_name == "search":
                search = final_value
            elif param_name not in standard_params:
                # Es un filtro
                filters[param_name] = final_value

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
