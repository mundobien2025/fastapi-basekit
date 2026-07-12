"""Coerción de tipos ricos en `_params` (date/datetime/UUID/Decimal/Enum).

Regresión encontrada probando sereno_block_backend: un query param
`date: Optional[date]` o `region_id: Optional[UUID]` quedaba como STRING (mi
`_params` solo coaccionaba bool/int/float), así que el filtro contra una columna
DATE/UUID en Postgres reventaba (500). Fix: los tipos no-simples se coaccionan
con pydantic TypeAdapter (mismo motor que FastAPI). Este test lo clava.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

import pytest

from fastapi_basekit.aio.controller.base import BaseController

coerce = BaseController._coerce_param


class Color(str, Enum):
    RED = "red"
    BLUE = "blue"


@pytest.mark.parametrize("ann", [date, Optional[date]])
def test_date_coercion(ann):
    out = coerce("2024-03-15", ann)
    assert out == date(2024, 3, 15)
    assert isinstance(out, date)


@pytest.mark.parametrize("ann", [datetime, Optional[datetime]])
def test_datetime_coercion(ann):
    out = coerce("2024-03-15T10:30:00", ann)
    assert isinstance(out, datetime)
    assert out.year == 2024 and out.hour == 10


@pytest.mark.parametrize("ann", [uuid.UUID, Optional[uuid.UUID]])
def test_uuid_coercion(ann):
    u = uuid.uuid4()
    out = coerce(str(u), ann)
    assert out == u
    assert isinstance(out, uuid.UUID)


@pytest.mark.parametrize("ann", [Decimal, Optional[Decimal]])
def test_decimal_coercion(ann):
    out = coerce("19.99", ann)
    assert out == Decimal("19.99")
    assert isinstance(out, Decimal)


def test_enum_coercion():
    assert coerce("red", Color) is Color.RED


def test_invalid_date_falls_back_to_string():
    # No revienta: valor no parseable → string original (FastAPI ya filtra 422).
    assert coerce("not-a-date", date) == "not-a-date"


def test_invalid_uuid_falls_back():
    assert coerce("xyz", uuid.UUID) == "xyz"


def test_bool_int_float_unchanged():
    # El path hand-rolled sigue igual (no lo tocó el fix).
    assert coerce("true", bool) is True
    assert coerce("false", bool) is False
    assert coerce("42", int) == 42
    assert coerce("3.14", float) == 3.14


def test_str_passthrough():
    assert coerce("2024-03-15", str) == "2024-03-15"
