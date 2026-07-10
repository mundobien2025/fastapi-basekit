"""simplify_openapi: quita el prefijo de clase cbv de summaries/operationIds."""

from fastapi import FastAPI

from fastapi_basekit.openapi import simplify_openapi
from tests.example_crud.controller import router


def test_strips_cbv_class_prefix():
    app = FastAPI()
    app.include_router(router)
    simplify_openapi(app)
    spec = app.openapi()

    for path, item in spec["paths"].items():
        for method, op in item.items():
            op_id = op.get("operationId", "")
            assert "." not in op_id, f"operationId sin limpiar: {op_id}"
            summary = op.get("summary", "")
            # El prefijo "UserController." no debe sobrevivir en el summary.
            assert "Controller." not in summary


def test_summary_override_applies():
    app = FastAPI()
    app.include_router(router)
    # operationId base (ya sin prefijo tras limpiar) para list_users.
    simplify_openapi(app, summary_overrides={"list_users": "Listar usuarios"})
    spec = app.openapi()
    summaries = {
        op.get("operationId"): op.get("summary")
        for item in spec["paths"].values()
        for op in item.values()
    }
    # El override se aplica por operationId original (con prefijo cbv).
    assert "Listar usuarios" in summaries.values() or any(
        s == "Listar usuarios" for s in summaries.values()
    )


def test_operation_ids_are_clean_method_names():
    """operationId == nombre del método de ruta, sin prefijo de clase cbv —
    independiente de si fastapi-restful lo emite con punto o guión bajo. Blinda
    contra la regresión donde el prefijo `Clase_metodo` (versiones nuevas)
    dejaba `summary_overrides` sin matchear."""
    app = FastAPI()
    app.include_router(router)
    simplify_openapi(app)
    spec = app.openapi()
    op_ids = {
        op.get("operationId")
        for item in spec["paths"].values()
        for op in item.values()
        if isinstance(op, dict) and "operationId" in op
    }
    expected = {
        "list_users",
        "retrieve_user",
        "create_user",
        "update_user",
        "delete_user",
    }
    assert expected.issubset(op_ids), op_ids
