"""Cobertura exhaustiva de la coerción de `_params` (refactor sin frames).

`BaseController._params` ahora coacciona `request.query_params` (strings) al
tipo declarado en la firma del endpoint. Estos tests martillan las piezas puras
de esa coerción — `_unwrap_optional`, `_coerce_param`, `_as_int` — sobre tablas
grandes, porque un fallo aquí filtra datos MAL en pulbot (filtros booleanos que
se invierten, ints que quedan string, etc.).
"""

from typing import List, Optional, Union

import pytest

from fastapi_basekit.aio.controller.base import (
    BaseController,
    _unwrap_optional,
)


coerce = BaseController._coerce_param
as_int = BaseController._as_int


# ---------------------------------------------------------------------------
# _unwrap_optional
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "annotation,expected",
    [
        (Optional[int], int),
        (Optional[bool], bool),
        (Optional[str], str),
        (Optional[float], float),
        (Union[int, None], int),
        (Union[None, int], int),
        (int, int),
        (bool, bool),
        (str, str),
        (float, float),
        # Uniones con >1 tipo no-None: se dejan intactas
        (Union[int, str], Union[int, str]),
        (Union[int, str, None], Union[int, str, None]),
        # Genéricos no-opcionales: intactos
        (List[int], List[int]),
        (Optional[List[int]], List[int]),
    ],
)
def test_unwrap_optional(annotation, expected):
    assert _unwrap_optional(annotation) == expected


def test_unwrap_optional_pep604():
    # `int | None` (PEP 604, Python 3.10+) → int. Sintaxis nativa, sin eval.
    assert _unwrap_optional(int | None) is int
    assert _unwrap_optional(bool | None) is bool
    # `int | str` (2 no-None) → intacto
    assert _unwrap_optional(int | str) == (int | str)


# ---------------------------------------------------------------------------
# _coerce_param — BOOL (el riesgo #1: 'false' es truthy si queda string)
# ---------------------------------------------------------------------------

TRUE_STRINGS = ["1", "true", "True", "TRUE", "t", "T", "yes", "YES", "on", "ON", " true "]
FALSE_STRINGS = ["0", "false", "False", "FALSE", "f", "no", "off", "", " ", "2", "random", "null", "None"]


@pytest.mark.parametrize("annotation", [bool, Optional[bool], Union[bool, None]])
@pytest.mark.parametrize("raw", TRUE_STRINGS)
def test_coerce_bool_truthy(annotation, raw):
    assert coerce(raw, annotation) is True


@pytest.mark.parametrize("annotation", [bool, Optional[bool], Union[bool, None]])
@pytest.mark.parametrize("raw", FALSE_STRINGS)
def test_coerce_bool_falsy(annotation, raw):
    assert coerce(raw, annotation) is False


# ---------------------------------------------------------------------------
# _coerce_param — INT
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("annotation", [int, Optional[int]])
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0", 0),
        ("5", 5),
        ("-3", -3),
        ("  7  ", 7),
        ("000", 0),
        ("2147483648", 2147483648),
    ],
)
def test_coerce_int_valid(annotation, raw, expected):
    assert coerce(raw, annotation) == expected


@pytest.mark.parametrize("annotation", [int, Optional[int]])
@pytest.mark.parametrize("raw", ["abc", "3.5", "1e3", "0x10", "", "  ", "5,000", "one"])
def test_coerce_int_invalid_stays_string(annotation, raw):
    # No debe reventar: valor inválido para int se devuelve tal cual (string).
    assert coerce(raw, annotation) == raw


# ---------------------------------------------------------------------------
# _coerce_param — FLOAT
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("annotation", [float, Optional[float]])
@pytest.mark.parametrize(
    "raw,expected",
    [("3.14", 3.14), ("-0.5", -0.5), ("1e3", 1000.0), ("0", 0.0), ("10", 10.0)],
)
def test_coerce_float_valid(annotation, raw, expected):
    assert coerce(raw, annotation) == expected


@pytest.mark.parametrize("annotation", [float, Optional[float]])
@pytest.mark.parametrize("raw", ["abc", "", "1,5", "3.4.5"])
def test_coerce_float_invalid_stays_string(annotation, raw):
    assert coerce(raw, annotation) == raw


# ---------------------------------------------------------------------------
# _coerce_param — STR / sin anotación / no-string
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("annotation", [str, Optional[str], None])
@pytest.mark.parametrize("raw", ["hola", "false", "123", "", "true", "3.14"])
def test_coerce_str_or_none_annotation_passthrough(annotation, raw):
    # String annotation (o sin anotación): el valor NO se toca.
    assert coerce(raw, annotation) == raw


@pytest.mark.parametrize("annotation", [bool, int, float, str, None])
@pytest.mark.parametrize("raw", [True, False, 5, 3.14, ["a"], {"k": 1}, None])
def test_coerce_non_string_passthrough(annotation, raw):
    # Si el valor ya NO es string (raro, pero defensivo), se devuelve igual.
    assert coerce(raw, annotation) is raw


# ---------------------------------------------------------------------------
# _as_int
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,default,expected",
    [
        ("5", 1, 5),
        (5, 1, 5),
        ("0", 1, 0),
        ("-2", 1, -2),
        (3.9, 1, 3),
        ("abc", 7, 7),
        ("", 7, 7),
        (None, 9, 9),
        ("3.5", 10, 10),
        ([], 4, 4),
    ],
)
def test_as_int(value, default, expected):
    assert as_int(value, default) == expected
