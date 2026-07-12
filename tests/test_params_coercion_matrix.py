"""Matriz cartesiana de invariantes de coerción de `_params`.

Cruza muchos valores crudos × muchas anotaciones y verifica INVARIANTES
(seguridad de tipo, no-revienta, correctitud en válidos) en vez de reimplementar
la lógica. Es la superficie exacta del refactor: un fallo aquí corrompe filtros
de pulbot en silencio, así que se martilla ancho.
"""

from typing import Optional, Union

import pytest

from fastapi_basekit.aio.controller.base import BaseController, _unwrap_optional

coerce = BaseController._coerce_param

# Valores crudos representativos (como llegan de query_params: siempre string).
RAWS = [
    "true", "True", "TRUE", "false", "False", "1", "0", "t", "f", "yes", "no",
    "on", "off", "", " ", "  true  ", "5", "-3", "0", "42", "999999999",
    "3.14", "-0.5", "1e3", "abc", "3.5", "one", "null", "None", "áéí", "🚀",
    "12,345", "0x10", "  ", "TrUe", "FALSE",
]

# Anotaciones que declara un endpoint típico.
BOOL_ANNOTS = [bool, Optional[bool], Union[bool, None], bool | None]
INT_ANNOTS = [int, Optional[int], int | None]
FLOAT_ANNOTS = [float, Optional[float], float | None]
STR_ANNOTS = [str, Optional[str], str | None, None]

TRUE_SET = {"1", "true", "t", "yes", "on"}


# ---------------------------------------------------------------------------
# BOOL: siempre devuelve un bool nativo; True sólo para el set canónico.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("annotation", BOOL_ANNOTS)
@pytest.mark.parametrize("raw", RAWS)
def test_bool_invariants(annotation, raw):
    result = coerce(raw, annotation)
    assert isinstance(result, bool)
    assert result == (raw.strip().lower() in TRUE_SET)


# ---------------------------------------------------------------------------
# INT: válido → int(raw); inválido → raw sin reventar.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("annotation", INT_ANNOTS)
@pytest.mark.parametrize("raw", RAWS)
def test_int_invariants(annotation, raw):
    result = coerce(raw, annotation)
    try:
        expected = int(raw)
        assert result == expected
        assert isinstance(result, int)
    except (TypeError, ValueError):
        assert result == raw  # inválido → intacto


# ---------------------------------------------------------------------------
# FLOAT: válido → float(raw); inválido → raw.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("annotation", FLOAT_ANNOTS)
@pytest.mark.parametrize("raw", RAWS)
def test_float_invariants(annotation, raw):
    result = coerce(raw, annotation)
    try:
        expected = float(raw)
        assert result == expected
        assert isinstance(result, float)
    except (TypeError, ValueError):
        assert result == raw


# ---------------------------------------------------------------------------
# STR / None annotation: passthrough exacto, jamás coacciona.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("annotation", STR_ANNOTS)
@pytest.mark.parametrize("raw", RAWS)
def test_str_passthrough_invariants(annotation, raw):
    assert coerce(raw, annotation) == raw
    assert isinstance(coerce(raw, annotation), str)


# ---------------------------------------------------------------------------
# Nunca revienta, para CUALQUIER combinación raw × annotation.
# ---------------------------------------------------------------------------

ALL_ANNOTS = BOOL_ANNOTS + INT_ANNOTS + FLOAT_ANNOTS + STR_ANNOTS


@pytest.mark.parametrize("annotation", ALL_ANNOTS)
@pytest.mark.parametrize("raw", RAWS)
def test_never_raises(annotation, raw):
    coerce(raw, annotation)  # no debe lanzar


# ---------------------------------------------------------------------------
# _unwrap_optional es idempotente sobre el tipo ya desenvuelto.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("annotation", ALL_ANNOTS)
def test_unwrap_idempotent(annotation):
    once = _unwrap_optional(annotation)
    twice = _unwrap_optional(once)
    assert once == twice
