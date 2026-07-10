"""Helpers para limpiar el esquema OpenAPI generado.

Con controllers `@cbv`, FastAPI genera ``operationId`` largos y ruidosos
(p. ej. ``UserController_list_users_users__get``) y, según la versión de
fastapi-restful, summaries con prefijo de clase (``UserController.list_users``).
``simplify_openapi`` normaliza ambos sin acoplarse a nombres de recurso de un
proyecto concreto: el ``operationId`` pasa a ser el nombre del método de ruta
(``list_users``) y el ``summary`` se vuelve legible.
"""

import re
from typing import Any, Callable, Dict, Optional

from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

# Prefijo de clase cbv en summaries con punto: "UserController.list_users".
_CBV_DOT_PREFIX = re.compile(r"^[A-Za-z0-9_]+\.(.+)$")

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def _clean_label(value: str) -> str:
    """Quita el prefijo de clase cbv (forma con punto) y formatea legible."""
    match = _CBV_DOT_PREFIX.match(value)
    tail = match.group(1) if match else value
    return tail.replace("_", " ").strip().capitalize()


def simplify_openapi(
    app,
    *,
    title: Optional[str] = None,
    version: Optional[str] = None,
    description: Optional[str] = None,
    summary_overrides: Optional[Dict[str, str]] = None,
) -> Callable[[], Dict[str, Any]]:
    """Instala un ``app.openapi`` con operationIds/summaries limpios.

    El ``operationId`` de cada ruta pasa a ser su ``name`` (el nombre del
    método, p. ej. ``list_users``), de modo que ``summary_overrides`` se
    indexa por ese nombre simple.

    Args:
        app: instancia FastAPI.
        title/version/description: overrides opcionales de metadatos.
        summary_overrides: mapa ``operationId -> summary`` (clave = nombre de
            método de ruta). Lo específico del proyecto vive aquí, no en la
            librería.

    Returns:
        La función ``custom_openapi`` instalada.
    """
    overrides = summary_overrides or {}

    def _method_name(route: APIRoute) -> str:
        """Nombre real del método de ruta ("list_users"), independiente de la
        versión de fastapi-restful — que emite el prefijo de clase cbv ya como
        punto ("UserController.list_users") ya como guión bajo
        ("UserController_list_users"). `endpoint.__name__` no depende de ese
        formato; fallback al parseo del prefijo con punto si no hay endpoint."""
        name = getattr(getattr(route, "endpoint", None), "__name__", None)
        if name:
            return name
        match = _CBV_DOT_PREFIX.match(route.name)
        return match.group(1) if match else route.name

    # (path, http_method) → nombre de método limpio. Reescribimos el operationId
    # directamente en el schema GENERADO en vez de setear `route.operation_id`:
    # las versiones nuevas de FastAPI ignoran ese atributo seteado post-hoc y
    # regeneran el operationId largo por defecto, dejando `summary_overrides`
    # sin matchear. Reescribir el dict final es robusto entre versiones.
    route_method: Dict[tuple, str] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            clean = _method_name(route)
            route.operation_id = clean  # best-effort para consumidores que lo lean
            path_key = getattr(route, "path_format", route.path)
            for http_method in (route.methods or set()):
                route_method[(path_key, http_method.lower())] = clean

    def custom_openapi() -> Dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=title or app.title,
            version=version or app.version,
            description=description or app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )

        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if method not in _HTTP_METHODS:
                    continue
                clean = route_method.get((path, method))
                if clean:
                    operation["operationId"] = clean
                op_key = clean or operation.get("operationId", "")
                if op_key in overrides:
                    operation["summary"] = overrides[op_key]
                elif operation.get("summary"):
                    operation["summary"] = _clean_label(operation["summary"])

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
    return custom_openapi
