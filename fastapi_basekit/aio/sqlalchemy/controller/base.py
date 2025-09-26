from typing import Any, ClassVar, List, Optional, Type

from fastapi import Depends
from pydantic import BaseModel
from ...controller.base import BaseController
from ..service.base import BaseService


class SQLAlchemyBaseController(BaseController):
    """BaseController para SQLAlchemy (AsyncSession).

    Espera que el servicio ya esté construido con un repositorio que tenga
    la sesión asignada, de modo que aquí solo se construyan los kwargs
    adicionales (joins, order_by, use_or).
    """

    service: BaseService = Depends()
    schema_class: ClassVar[Type[BaseModel]]

    async def list(
        self,
        *,
        use_or: bool = False,
        joins: Optional[List[str]] = None,
        order_by: Optional[Any] = None,
    ):
        params = self._params()
        service_params = {
            **params,
            "use_or": use_or,
            "joins": joins,
            "order_by": order_by,
        }
        items, total = await self.service.list(**service_params)
        count = params.get("count") or 0
        total_pages = (total + count - 1) // count if count > 0 else 0
        pagination = {
            "page": params.get("page"),
            "count": count,
            "total": total,
            "total_pages": total_pages,
        }
        return self.format_response(data=items, pagination=pagination)

    async def retrieve(
        self, id: str, *, joins: Optional[List[str]] = None
    ):
        item = await self.service.retrieve(id, joins=joins)
        return self.format_response(data=item)

    async def create(
        self,
        validated_data: Any,
        *,
        check_fields: Optional[List[str]] = None,
    ):
        result = await self.service.create(validated_data, check_fields)
        return self.format_response(result, message="Creado exitosamente")

    async def update(self, id: str, validated_data: Any):
        result = await self.service.update(id, validated_data)
        return self.format_response(result, message="Actualizado exitosamente")

    async def delete(self, id: str):
        await self.service.delete(id)
        return self.format_response(None, message="Eliminado exitosamente")
