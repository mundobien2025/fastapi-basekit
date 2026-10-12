"""build_search_regex: escape del término y búsqueda sin acentos (Beanie)."""

import re

import pytest

from fastapi_basekit.aio.beanie.repository.base import build_search_regex


def _matches(term: str, text: str) -> bool:
    # Mismo significado que Mongo `$regex` con `$options: "i"`.
    return re.search(build_search_regex(term), text, re.IGNORECASE) is not None


@pytest.mark.parametrize(
    "text",
    ["Descripción", "descripcion", "DESCRIPCIÓN", "Descripcíon"],
)
def test_sin_tilde_encuentra_con_tilde_y_viceversa(text):
    assert _matches("descripcion", text)
    assert _matches("descripción", text)


def test_enie_y_n_son_equivalentes():
    assert _matches("ano", "Año nuevo")
    assert _matches("año", "ANO")


def test_mayusculas_acentuadas_del_termino():
    assert _matches("ÑANDÚ", "el ñandu corre")
    assert _matches("ñandú", "NANDU")


@pytest.mark.parametrize("term", ["(", "[", "*", "+", "?", "\\", "a.*", "$", "^"])
def test_caracteres_especiales_son_literales(term):
    # No deben romper la regex ni comportarse como metacaracteres.
    assert re.compile(build_search_regex(term))  # compila
    assert not _matches(term, "xyz")


def test_punto_asterisco_no_es_comodin():
    assert not _matches("a.*", "abc")
    assert _matches("a.*", "zza.*zz")


def test_parentesis_se_busca_literal():
    assert _matches("(beta)", "versión (beta) 2")
    assert not _matches("(beta)", "versión beta 2")


def test_termino_sin_acentos_no_cambia_el_resto_del_texto():
    assert _matches("whats", "WhatsApp")
    assert not _matches("telegram", "WhatsApp")
