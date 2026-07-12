import functools
import inspect
import types
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    Set,
    Union,
    get_args,
    get_origin,
)
from fastapi import Depends, Request
from pydantic import BaseModel, TypeAdapter


@functools.lru_cache(maxsize=512)
def _type_adapter_for(target: Any) -> Any:
    """Devuelve un ``TypeAdapter`` cacheado para coaccionar un valor de query a
    ``target`` con el MISMO motor que usa FastAPI (pydantic). Cubre date,
    datetime, UUID, Decimal, Enum, etc. — todo lo que no sea bool/int/float/str.
    ``None`` si el tipo no es adaptable."""
    try:
        return TypeAdapter(target)
    except Exception:
        return None


@functools.lru_cache(maxsize=1024)
def _endpoint_param_types_cached(endpoint: Any) -> Dict[str, Any]:
    """Mapea {nombre_param: anotación} desde la firma del endpoint, CACHEADO.

    El endpoint (`request.scope["endpoint"]`) es el MISMO objeto callable en cada
    request (se crea una vez al montar la ruta), así que su firma se computa una
    sola vez por endpoint — no en cada request de listado. Antes cada listado
    pagaba un `inspect.signature`; ahora es O(1) tras el primer hit.

    El dict devuelto es compartido (cacheado): tratar como SOLO-LECTURA.
    """
    try:
        parameters = inspect.signature(endpoint).parameters
    except (TypeError, ValueError):
        return {}
    return {
        name: param.annotation
        for name, param in parameters.items()
        if param.annotation is not inspect.Parameter.empty
    }


def _unwrap_optional(annotation: Any) -> Any:
    """Strip ``Optional[X]`` / ``Union[X, None]`` / ``X | None`` → ``X``.

    Returns the annotation unchanged when it is not an optional/union, or when
    the union has no single non-``None`` member.
    """
    origin = get_origin(annotation)
    if origin is Union or origin is getattr(types, "UnionType", ()):  # X | None
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return annotation

from ..permissions.base import BasePermission

from ...schema.base import BasePaginationResponse, BaseResponse
from ...exceptions.api_exceptions import PermissionException


class BaseController:
    """Montar rutas CRUD genericas y captura errores de negocio."""

    service = Depends()
    schema_class: ClassVar[Type[BaseModel]]

    # DRF Style: Permisos globales por defecto
    permission_classes: ClassVar[List[Type[BasePermission]]] = []

    # ClassVar so cbv (fastapi-restful) does NOT promote it to a query param.
    # A plain `Optional[str]` annotation here leaks a spurious `action` query
    # parameter onto every mounted endpoint. `prepare_action` still assigns
    # `self.action` (instance attr) at runtime, which works fine.
    action: ClassVar[Optional[str]] = None
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

        NO metaclass or auto-wrapping exists. This is called EXPLICITLY:

        - The base CRUD methods (``list``/``retrieve``/``create``/``update``/
          ``delete``) call it for you — if your endpoint just does
          ``return await super().list()`` you are covered.
        - A CUSTOM endpoint (any method you write yourself, e.g.
          ``async def approve(self, id: str)``) runs with NO permission check
          unless you add ``await self.prepare_action("approve")`` as its first
          line. Forgetting this silently skips ``permission_classes``.

        Idempotent within one instance: if the same ``action_name`` is already
        prepared, subsequent calls are no-ops, so calling it in a custom method
        that also delegates to ``super().<crud>()`` won't double-fire.
        """
        if getattr(self, "_basekit_prepared_action", None) == action_name:
            return
        self.action = action_name
        self._basekit_prepared_action = action_name
        # Propagate the canonical CRUD action ("list"/"retrieve"/...) to the
        # service so `get_kwargs_query` / `get_filters` can branch on it. The
        # service's own constructor derives `action` from the endpoint
        # function name (e.g. "list_users"), which is unreliable for that
        # purpose; the controller knows the canonical action.
        service = getattr(self, "service", None)
        if service is not None:
            try:
                service.action = action_name
            except Exception:
                pass
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
        Kept working for code that hasn't migrated. New code should declare
        ``permission_classes`` on the controller and call
        ``await self.prepare_action("<action>")`` at the top of each custom
        endpoint (there is no metaclass that does this automatically).
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
        """Extrae page/count/search/order_by/filters de ``request.query_params``.

        Los valores llegan como strings; se coaccionan a los tipos DECLARADOS
        en la firma del endpoint (leída de ``request.scope["endpoint"]``), de
        forma DETERMINISTA — sin introspección de stack-frames. Un query param
        que no está declarado en la firma se deja como string (idéntico a lo
        que haría FastAPI si no lo tipara), evitando coacciones-adivinanza que
        romperían columnas string con valores numéricos.

        Reemplaza el viejo mecanismo basado en ``inspect.currentframe()`` +
        ``skip_frames`` (un número mágico distinto por capa de herencia, fuente
        de listados vacíos difíciles de diagnosticar).

        ``skip_frames``: DEPRECADO e IGNORADO. Se conserva solo por
        retro-compatibilidad — algunos consumidores overridean ``_params`` y
        llaman ``super()._params(skip_frames + 1)`` (p.ej. mixins de path
        params). Ya no se usa: la coerción no depende de frames. No lo pases en
        código nuevo.
        """
        query_params = (
            dict(self.request.query_params) if self.request else {}
        )
        declared = self._endpoint_param_types()

        standard_params = {"page", "count", "search", "order_by"}
        page = 1
        count = 10
        search = None
        order_by = None
        filters: Dict[str, Any] = {}

        for param_name, raw_value in query_params.items():
            value = self._coerce_param(raw_value, declared.get(param_name))

            if param_name == "page":
                page = self._as_int(value, 1)
            elif param_name == "count":
                count = self._as_int(value, 10)
            elif param_name == "search":
                search = value
            elif param_name == "order_by":
                order_by = value
            elif (
                param_name not in standard_params
                and param_name not in self._params_excluded_fields
            ):
                filters[param_name] = value

        return {
            "page": page,
            "count": count,
            "search": search,
            "order_by": order_by,
            "filters": filters,
        }

    def _endpoint_param_types(self) -> Dict[str, Any]:
        """Mapea {nombre_param: anotación} desde la firma del endpoint activo.

        Lee ``request.scope["endpoint"]`` (la función de ruta que FastAPI está
        ejecutando) y delega en el cache por-endpoint. Devuelve ``{}`` si no hay
        endpoint o su firma no es introspectable (los valores quedan como string).
        """
        request = getattr(self, "request", None)
        scope = getattr(request, "scope", None) if request is not None else None
        endpoint = scope.get("endpoint") if isinstance(scope, dict) else None
        if endpoint is None:
            return {}
        try:
            return _endpoint_param_types_cached(endpoint)
        except TypeError:
            # endpoint no hasheable (raro) → sin coerción, valores string.
            return {}

    @staticmethod
    def _coerce_param(raw: Any, annotation: Any) -> Any:
        """Coacciona un valor de query (string) al tipo declarado en la firma.

        bool/int/float a mano; el RESTO (date, datetime, UUID, Decimal, Enum…)
        vía pydantic ``TypeAdapter`` — el MISMO motor que usa FastAPI, para que
        el filtro reciba el objeto tipado (ej. un `date` real que compara contra
        una columna DATE) y no el string. Sin anotación, str, o si la coacción
        falla → se devuelve el valor original sin romper.

        Nota: FastAPI ya rechaza (422) un query param tipado con valor inválido
        antes de llegar acá, así que en la práctica la coacción siempre aplica.
        """
        if annotation is None or not isinstance(raw, str):
            return raw
        target = _unwrap_optional(annotation)
        if target is bool:
            return raw.strip().lower() in {"1", "true", "t", "yes", "on"}
        if target is int:
            try:
                return int(raw)
            except (TypeError, ValueError):
                return raw
        if target is float:
            try:
                return float(raw)
            except (TypeError, ValueError):
                return raw
        if target is str or target is Any:
            return raw
        # date / datetime / UUID / Decimal / Enum / etc. → pydantic (FastAPI-parity)
        adapter = _type_adapter_for(target)
        if adapter is None:
            return raw
        try:
            return adapter.validate_python(raw)
        except Exception:
            return raw

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

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
