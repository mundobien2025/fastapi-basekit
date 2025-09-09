from typing import Any, ClassVar, List, Optional, Type

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...controller.base import BaseController
from ..service.base import BaseService


class SQLAlchemyBaseController(BaseController):
    """BaseController para SQLAlchemy (AsyncSession).

    - Acepta `db: AsyncSession` en operaciones CRUD.
    - Construye y pasa parámetros específicos (joins, order_by, use_or).
    """

    service: BaseService = Depends()
    schema_class: ClassVar[Type[BaseModel]]

    async def list(
        self,
        db: AsyncSession,
        *,
        use_or: bool = False,
        joins: Optional[List[str]] = None,
        order_by: Optional[Any] = None,
    ):
        params = self._params()
        service_params = {
            "page": params.get("page"),
            "count": params.get("count"),
            "filters": params.get("filters"),
            "use_or": use_or,
            "joins": joins,
            "order_by": order_by,
        }
        items, total = await self.service.list(db, **service_params)
        pagination = {
            "page": params.get("page"),
            "count": params.get("count"),
            "total": total,
        }
        return self.format_response(data=items, pagination=pagination)

    async def retrieve(
        self, db: AsyncSession, id: str, *, joins: Optional[List[str]] = None
    ):
        item = await self.service.retrieve(db, id, joins=joins)
        return self.format_response(data=item)

    async def create(
        self,
        db: AsyncSession,
        validated_data: Any,
        *,
        check_fields: Optional[List[str]] = None,
    ):
        result = await self.service.create(db, validated_data, check_fields)
        return self.format_response(result, message="Creado exitosamente")

    async def update(self, db: AsyncSession, id: str, validated_data: Any):
        result = await self.service.update(db, id, validated_data)
        return self.format_response(result, message="Actualizado exitosamente")

    async def delete(self, db: AsyncSession, id: str):
        await self.service.delete(db, id)
        return self.format_response(None, message="Eliminado exitosamente")
