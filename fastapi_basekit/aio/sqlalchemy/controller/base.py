from typing import Any, ClassVar, List, Optional, Set
from fastapi import Depends

from ....aio.controller.base import BaseController
from ..service.base import BaseService


class SQLAlchemyBaseController(BaseController):
    """BaseController para SQLAlchemy (AsyncSession).

    Controlador base específico para proyectos que usan SQLAlchemy con
    async/await. Incluye soporte para joins, ordenamiento personalizado
    y operadores OR en filtros, características específicas de SQL.
    """

    service: BaseService = Depends()

    # Campos adicionales a excluir específicos de SQLAlchemy
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
        """
        Lista registros con paginación usando SQLAlchemy.

        Args:
            use_or: Si True, usa OR en lugar de AND para los filtros
            joins: Lista de relaciones a hacer JOIN eager loading
            order_by: Expresión de ordenamiento (ej: User.created_at.desc())
        """
        params = self._params(skip_frames=2)
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

    async def retrieve(self, id: str, *, joins: Optional[List[str]] = None):
        """
        Obtiene un registro por ID.

        Args:
            id: ID del registro
            joins: Lista de relaciones a hacer JOIN eager loading
        """
        item = await self.service.retrieve(id, joins=joins)
        return self.format_response(data=item)

    async def create(
        self,
        validated_data: Any,
        *,
        check_fields: Optional[List[str]] = None,
    ):
        """
        Crea un nuevo registro.

        Args:
            validated_data: Datos validados para crear
            check_fields: Campos a verificar por duplicados antes de crear
        """
        result = await self.service.create(validated_data, check_fields)
        return self.format_response(result, message="Creado exitosamente")

    def to_dict(self, obj: Any):
        """Convierte un modelo SQLAlchemy a dict."""
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        # Para modelos SQLAlchemy que usan __dict__
        if hasattr(obj, "__dict__"):
            return {
                k: v for k, v in obj.__dict__.items() if not k.startswith("_")
            }
        return obj
