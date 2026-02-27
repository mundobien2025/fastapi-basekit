from typing import Any, ClassVar, List, Optional, Set
from fastapi import Depends

from ....aio.controller.base import BaseController
from ..service.base import BaseService


class SQLModelBaseController(BaseController):
    """BaseController para SQLModel (AsyncSession).

    Controlador base específico para proyectos que usan SQLModel con
    async/await.  Incluye soporte para joins, ordenamiento personalizado
    y operadores OR en filtros.

    Dado que los modelos SQLModel son también modelos Pydantic, la
    serialización es directa a través de ``model_dump()``.
    """

    service: BaseService = Depends()

    _params_excluded_fields: ClassVar[Set[str]] = {
        "self",
        "page",
        "count",
        "search",
        "use_or",
        "joins",
        "order_by",
        "__class__",
        "args",
        "kwargs",
        "id",
        "payload",
        "data",
        "validated_data",
    }

    async def list(
        self,
        *,
        use_or: bool = False,
        joins: Optional[List[str]] = None,
        order_by: Optional[Any] = None,
    ):
        """Lista registros con paginación usando SQLModel.

        Args:
            use_or: Si True, usa OR en lugar de AND para los filtros.
            joins: Lista de relaciones para eager loading.
            order_by: Expresión de ordenamiento (ej: ``"-created_at"``).
        """
        params = self._params(skip_frames=2)
        service_params = {
            **params,
            "use_or": use_or,
            "joins": joins,
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

    async def retrieve(self, id: str, *, joins: Optional[List[str]] = None):
        """Obtiene un registro por ID.

        Args:
            id: ID del registro.
            joins: Lista de relaciones para eager loading.
        """
        item = await self.service.retrieve(id, joins=joins)
        return self.format_response(data=item)

    async def create(
        self,
        validated_data: Any,
        *,
        check_fields: Optional[List[str]] = None,
    ):
        """Crea un nuevo registro.

        Args:
            validated_data: Datos validados para crear.
            check_fields: Campos a verificar por duplicados antes de crear.
        """
        result = await self.service.create(validated_data, check_fields)
        return self.format_response(result, message="Creado exitosamente")

    def to_dict(self, obj: Any) -> Any:
        """Convierte un modelo SQLModel a dict.

        Los modelos SQLModel son modelos Pydantic, por lo que ``model_dump()``
        está siempre disponible.  Se mantiene el fallback a ``__dict__`` para
        compatibilidad con subclases o decoradores inesperados.
        """
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "__dict__"):
            return {
                k: v for k, v in obj.__dict__.items() if not k.startswith("_")
            }
        return obj
