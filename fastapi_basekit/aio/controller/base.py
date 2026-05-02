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

    # DRF Style: Permisos globales por defecto
    permission_classes: ClassVar[List[Type[BasePermission]]] = []

    action: Optional[str] = None
    request: Request
    _params_excluded_fields: ClassVar[Set[str]] = {
        "self",
        "page",
        "count",
        "search",
        "order_by",
        "__class__",
        "args",
        "kwargs",
        "id",
        "payload",
        "data",
        "validated_data",
    }

    def __init__(self) -> None:
        """Inicializa el controller."""
        pass

    def get_permissions(self) -> List[Type[BasePermission]]:
        """
        Instancia y retorna la lista de permisos que esta vista requiere.

        Sobrescribir esto permite lógica tipo DRF:

        if self.action == 'list':
            return [AllowAny]
        return [IsAuthenticated]
        """
        return self.permission_classes

    async def prepare_action(self, action_name: str) -> None:
        """Set the current action and run permission checks.

        Auto-called by ``ControllerMeta`` for every public async method on
        the controller. Idempotent within one invocation: if the same
        ``action_name`` has already been prepared on this instance,
        subsequent calls are no-ops. This lets custom methods opt into
        calling ``await self.prepare_action(...)`` explicitly without
        double-firing permission checks (when the metaclass already ran
        before entering the method body).
        """
        if getattr(self, "_basekit_prepared_action", None) == action_name:
            return
        self.action = action_name
        self._basekit_prepared_action = action_name
        await self.check_permissions()

    async def check_permissions(self):
        """Run each declared permission. Raises ``PermissionException``
        on the first denial.
        """
        for permission_class in self.get_permissions():
            permission = permission_class()
            has_perm = await permission.has_permission(self.request)
            if not has_perm:
                message = getattr(
                    permission,
                    "message_exception",
                    "No tienes permiso para realizar esta acción.",
                )
                raise PermissionException(message)

    async def check_permissions_class(self):
        """Backward-compat alias for ``check_permissions``.

        Pre-0.3.2 controllers called this manually inside endpoint methods.
        Keep working for users who haven't migrated to ``permission_classes``
        + auto-wrapping yet. New code should declare ``permission_classes``
        on the controller and let the metaclass run permissions.
        """
        await self.check_permissions()

    def get_schema_class(self) -> Type[BaseModel]:
        assert self.schema_class is not None, (
            "'%s' should either include a `schema_class` attribute, "
            "or override the `get_schema_class()` method."
            % self.__class__.__name__
        )
        return self.schema_class

    async def list(self):
        await self.prepare_action("list")
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
        await self.prepare_action("retrieve")
        item = await self.service.retrieve(id)
        return self.format_response(data=item)

    async def create(self, validated_data: Any):
        await self.prepare_action("create")
        result = await self.service.create(validated_data)
        return self.format_response(result, message="Creado exitosamente")

    async def update(self, id: str, validated_data: Any):
        await self.prepare_action("update")
        result = await self.service.update(id, validated_data)
        return self.format_response(result, message="Actualizado exitosamente")

    async def delete(self, id: str):
        await self.prepare_action("delete")
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

        # Robust Pydantic v2 validation. Each branch falls back to the
        # raw value when the schema doesn't fit (custom-action endpoints
        # often return ad-hoc dicts that don't match the controller's
        # default schema_class — those should pass through untouched).
        if isinstance(data, list):
            data_dicts = [self.to_dict(item) for item in data]
            try:
                adapter = TypeAdapter(List[schema])
                data_parsed = adapter.validate_python(data_dicts)
            except Exception:
                data_parsed = data_dicts

        elif isinstance(data, dict):
            try:
                data_parsed = schema.model_validate(data)
            except Exception:
                data_parsed = data

        elif hasattr(data, "__dict__"):
            data_dict = self.to_dict(data)
            try:
                data_parsed = schema.model_validate(data_dict)
            except Exception:
                data_parsed = data_dict

        elif data is None:
            data_parsed = None
        else:
            data_parsed = data

        response_cls = BasePaginationResponse if pagination else BaseResponse

        # Construcción dinámica de argumentos
        kwargs = {
            "data": data_parsed,
            "message": message or "Operación exitosa",
            "status": response_status,
        }
        if pagination:
            kwargs["pagination"] = pagination

        return response_cls(**kwargs)

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
        standard_params = {"page", "count", "search", "order_by"}

        # Valores por defecto
        page = 1
        count = 10
        search = None
        order_by = None
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
            elif param_name == "order_by":
                order_by = final_value
            elif param_name not in standard_params:
                # Es un filtro
                filters[param_name] = final_value

        return {
            "page": page,
            "count": count,
            "search": search,
            "order_by": order_by,
            "filters": filters,
        }

    def to_dict(self, obj: Any):
        """Helper para convertir modelos ORM/Pydantic a dict."""
        if hasattr(obj, "model_dump"):  # Pydantic v2
            return obj.model_dump()
        if hasattr(obj, "dict"):  # Pydantic v1
            return obj.dict()
        if hasattr(obj, "__dict__"):  # SQLAlchemy models (basic)
            # Filtramos atributos privados de SQLAlchemy
            return {
                k: v for k, v in obj.__dict__.items() if not k.startswith("_")
            }
        return obj
