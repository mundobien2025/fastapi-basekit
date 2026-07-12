"""Cobertura de `BaseController._params()` — clasificación page/count/search/
order_by/filters + coerción por firma del endpoint, SIN HTTP.

Construimos un controller con un `request` falso (query_params dict + scope con
un endpoint de firma conocida) y verificamos el dict resultante. Cubre el
comportamiento que pulbot depende: filtros tipados coaccionados, no-declarados
como string, campos estándar/excluidos fuera de `filters`, defaults robustos.
"""

from typing import Optional

import pytest
from fastapi import Query

from fastapi_basekit.aio.controller.base import BaseController
from fastapi_basekit.aio.sqlalchemy.controller.base import (
    SQLAlchemyBaseController,
)


class _FakeRequest:
    def __init__(self, query_params: dict, endpoint=None):
        self.query_params = query_params
        self.scope = {"endpoint": endpoint} if endpoint is not None else {}


def _make(query_params: dict, endpoint=None, cls=BaseController):
    ctrl = cls.__new__(cls)  # sin pasar por Depends()
    ctrl.request = _FakeRequest(query_params, endpoint)
    return ctrl


# Endpoints de referencia con firmas típicas -------------------------------

async def ep_typed(
    self,
    page: int = Query(1),
    count: int = Query(10),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    age_min: Optional[int] = Query(None),
    ratio: Optional[float] = Query(None),
    name: Optional[str] = Query(None),
):
    ...


async def ep_none(self):
    ...


# ---------------------------------------------------------------------------
# page / count
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "qp,exp_page,exp_count",
    [
        ({}, 1, 10),
        ({"page": "3"}, 3, 10),
        ({"count": "50"}, 1, 50),
        ({"page": "2", "count": "25"}, 2, 25),
        ({"page": "abc"}, 1, 10),          # inválido → default
        ({"count": ""}, 1, 10),            # vacío → default
        ({"page": "0"}, 0, 10),            # 0 permitido a nivel _params
        ({"page": "-1"}, -1, 10),
        ({"page": "999999"}, 999999, 10),
    ],
)
def test_page_count(qp, exp_page, exp_count):
    p = _make(qp, ep_typed)._params()
    assert p["page"] == exp_page
    assert p["count"] == exp_count


# ---------------------------------------------------------------------------
# search / order_by
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "qp,key,expected",
    [
        ({"search": "juan"}, "search", "juan"),
        ({"search": ""}, "search", ""),
        ({"order_by": "-created_at"}, "order_by", "-created_at"),
        ({"order_by": "name"}, "order_by", "name"),
        ({}, "search", None),
        ({}, "order_by", None),
    ],
)
def test_search_order(qp, key, expected):
    assert _make(qp, ep_typed)._params()[key] == expected


# ---------------------------------------------------------------------------
# filtros tipados: coerción
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "qp,expected_filters",
    [
        ({"is_active": "true"}, {"is_active": True}),
        ({"is_active": "false"}, {"is_active": False}),
        ({"is_active": "0"}, {"is_active": False}),
        ({"age_min": "18"}, {"age_min": 18}),
        ({"age_min": "abc"}, {"age_min": "abc"}),        # inválido → string
        ({"ratio": "1.5"}, {"ratio": 1.5}),
        ({"name": "Ana"}, {"name": "Ana"}),
        (
            {"is_active": "true", "age_min": "21", "name": "Bob"},
            {"is_active": True, "age_min": 21, "name": "Bob"},
        ),
    ],
)
def test_typed_filters(qp, expected_filters):
    assert _make(qp, ep_typed)._params()["filters"] == expected_filters


# ---------------------------------------------------------------------------
# sin endpoint en scope → sin coerción (todo string)
# ---------------------------------------------------------------------------

def test_no_endpoint_no_coercion():
    p = _make({"is_active": "false", "age_min": "18"}, endpoint=None)._params()
    assert p["filters"] == {"is_active": "false", "age_min": "18"}


def test_endpoint_without_declared_param_stays_string():
    # `foo` no está en la firma ep_typed → se queda string.
    p = _make({"foo": "123", "is_active": "true"}, ep_typed)._params()
    assert p["filters"]["foo"] == "123"
    assert p["filters"]["is_active"] is True


# ---------------------------------------------------------------------------
# campos estándar y excluidos NO entran a filters
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field", ["page", "count", "search", "order_by", "id"])
def test_standard_and_excluded_not_in_filters(field):
    p = _make({field: "x"}, ep_none)._params()
    assert field not in p["filters"]


@pytest.mark.parametrize("field", ["use_or", "joins", "id", "payload", "data"])
def test_sqlalchemy_excluded_not_in_filters(field):
    p = _make({field: "x"}, ep_none, cls=SQLAlchemyBaseController)._params()
    assert field not in p["filters"]


# ---------------------------------------------------------------------------
# request ausente → defaults, no revienta
# ---------------------------------------------------------------------------

def test_no_request_defaults():
    ctrl = BaseController.__new__(BaseController)
    ctrl.request = None
    p = ctrl._params()
    assert p == {
        "page": 1,
        "count": 10,
        "search": None,
        "order_by": None,
        "filters": {},
    }


# ---------------------------------------------------------------------------
# combinación completa realista
# ---------------------------------------------------------------------------

def test_full_realistic_query():
    qp = {
        "page": "2",
        "count": "15",
        "search": "smith",
        "order_by": "-age",
        "is_active": "true",
        "age_min": "30",
        "name": "S",
        "unknown_flag": "yes",
    }
    p = _make(qp, ep_typed)._params()
    assert p["page"] == 2
    assert p["count"] == 15
    assert p["search"] == "smith"
    assert p["order_by"] == "-age"
    assert p["filters"] == {
        "is_active": True,
        "age_min": 30,
        "name": "S",
        "unknown_flag": "yes",  # no declarado → string
    }
