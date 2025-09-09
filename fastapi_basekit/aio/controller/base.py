from typing import Any, ClassVar, Dict, List, Optional, Type
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
