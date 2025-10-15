from typing import Any, List, Optional
from fastapi import Depends
from bson import ObjectId

from ....aio.controller.base import BaseController
from ..service.base import BaseService


class BeanieBaseController(BaseController):
    """BaseController para Beanie ODM (async).

    Controlador base específico para proyectos que usan Beanie (MongoDB).
    Incluye manejo completo de CRUD, paginación, permisos y formato de
    respuestas optimizado para documentos de Beanie.
    """

    service: BaseService = Depends()

    async def list(self):
        """Lista documentos con paginación usando Beanie."""
        params = self._params(skip_frames=2)
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

    async def create(
        self,
        validated_data: Any,
        *,
        check_fields: Optional[List[str]] = None,
    ):
        """Crea un nuevo documento con validación de campos únicos."""
        result = await self.service.create(validated_data, check_fields)
        return self.format_response(result, message="Creado exitosamente")

    def to_dict(self, obj: Any):
        """Convierte un documento Beanie a dict, convirtiendo ObjectId a str."""
        if hasattr(obj, "model_dump"):
            data = obj.model_dump()
            # Convertir ObjectId a string
            if "id" in data and isinstance(data["id"], ObjectId):
                data["id"] = str(data["id"])
            return data
        return obj
