"""Regresión: format_response no debe re-castear modelos Pydantic específicos
a ``schema_class`` cuando un endpoint custom devuelve otro schema."""

import pytest
from pydantic import BaseModel

from fastapi_basekit.aio.controller.base import BaseController


class _DefaultSchema(BaseModel):
    id: int
    name: str


class _OtherSchema(BaseModel):
    ok: bool
    status: str


class _Controller(BaseController):
    schema_class = _DefaultSchema


@pytest.fixture
def controller():
    return _Controller()


def test_format_response_respects_other_pydantic_model(controller):
    """Un endpoint custom que devuelve otro schema no debe romperse al forzar
    ``schema_class`` (GatewayCheckoutResponseSchema vs GatewayChargeResponseSchema)."""
    other = _OtherSchema(ok=True, status="paid")
    resp = controller.format_response(other, message="OK")

    # Se convierte a dict limpio y se deja pasar; FastAPI validará contra
    # el response_model declarado en la ruta.
    assert resp.data == {"ok": True, "status": "paid"}
    assert isinstance(resp.data, dict)
    assert resp.message == "OK"


def test_format_response_keeps_default_model_instance(controller):
    """Si ``data`` ya es instancia de ``schema_class``, se usa tal cual."""
    item = _DefaultSchema(id=1, name="foo")
    resp = controller.format_response(item)

    assert resp.data is item


def test_format_response_validates_plain_dict(controller):
    """Los dicts planos siguen validándose contra ``schema_class``."""
    resp = controller.format_response({"id": 2, "name": "bar"})

    assert isinstance(resp.data, _DefaultSchema)
    assert resp.data.id == 2
    assert resp.data.name == "bar"


def test_format_response_list_of_other_models(controller):
    """Una lista de modelos Pydantic distintos a ``schema_class`` se respeta."""
    items = [
        _OtherSchema(ok=True, status="paid"),
        _OtherSchema(ok=False, status="failed"),
    ]
    resp = controller.format_response(items)

    assert resp.data == [
        {"ok": True, "status": "paid"},
        {"ok": False, "status": "failed"},
    ]


def test_format_response_list_of_dicts_still_validates(controller):
    """Una lista de dicts sigue validándose contra ``List[schema_class]``."""
    resp = controller.format_response([{"id": 3, "name": "baz"}])

    assert isinstance(resp.data, list)
    assert isinstance(resp.data[0], _DefaultSchema)
    assert resp.data[0].id == 3
