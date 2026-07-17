"""Regresión: cbv NO debe exponer `action` como query param.

`BaseController.action` es una `@property` (no un campo anotado) precisamente
para que fastapi-restful (cbv) no lo promueva a parámetro de query en cada ruta
montada. Antes de 0.4.0 aparecía un `?action=` espurio en toda mutación.
"""

from fastapi import FastAPI

from tests.example_crud.controller import router


def _spec():
    app = FastAPI()
    app.include_router(router)
    return app.openapi()


def test_no_spurious_action_query_param_on_any_route():
    spec = _spec()
    offending = []
    for path, item in spec["paths"].items():
        for method, op in item.items():
            for param in op.get("parameters", []):
                if param.get("name") == "action" and param.get("in") == "query":
                    offending.append(f"{method.upper()} {path}")
    assert offending == [], f"`action` leaked as query param on: {offending}"


def test_declared_query_filters_still_present():
    # Sanidad: los filtros declarados explícitamente sí deben seguir ahí.
    spec = _spec()
    get_list = spec["paths"]["/users/"]["get"]
    names = {p["name"] for p in get_list.get("parameters", [])}
    assert {"page", "count", "search", "is_active", "age_min"} <= names


def test_action_is_filterable_not_excluded():
    """Regresión inversa: `action` NO debe estar en `_params_excluded_fields`.

    El ClassVar ya evita el `?action=` espurio (test de arriba); excluir
    `action` del set de filtros rompía filtrar por una columna `action`
    declarada como query param (ej. audit-logs `?action=...`). v0.4.1.
    """
    from fastapi_basekit.aio.sqlalchemy.controller.base import (
        SQLAlchemyBaseController,
    )
    from fastapi_basekit.aio.controller.base import BaseController

    assert "action" not in SQLAlchemyBaseController._params_excluded_fields
    assert "action" not in BaseController._params_excluded_fields


def test_action_falls_back_to_endpoint_name():
    """`action` resuelve al nombre de la función de endpoint cuando el endpoint
    custom NO llamó `prepare_action`.

    Antes `action` era un ClassVar que quedaba en None → `get_schema_class`
    devolvía el schema por defecto (de lista) y la validación del `response_model`
    de detalle fallaba. Ahora es una property con fallback a
    `request.scope["endpoint"].__name__`. Sigue sin filtrarse como query param
    (test de arriba) porque una property no es un campo anotado.
    """
    from fastapi_basekit.aio.controller.base import BaseController

    class C(BaseController):
        pass

    # Sin request ni prepare_action → None (no rompe).
    assert C().action is None

    # `prepare_action` (vía backing attr) gana sobre el fallback.
    c = C()
    c._basekit_prepared_action = "list"
    assert c.action == "list"

    # Fallback: lee el nombre de la función de endpoint activa.
    def create():  # nombre = acción canónica
        ...

    class _Req:
        scope = {"endpoint": create}

    c2 = C()
    c2.request = _Req()
    assert c2.action == "create"

    # Setter de compat: `self.action = "x"` sigue funcionando.
    c2.action = "update"
    assert c2.action == "update"
