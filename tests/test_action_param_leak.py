"""Regresión: cbv NO debe exponer `action` como query param.

`BaseController.action` se declara `ClassVar` precisamente para que
fastapi-restful (cbv) no lo promueva a parámetro de query en cada ruta
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
