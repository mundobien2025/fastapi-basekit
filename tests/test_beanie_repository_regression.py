"""Regresión/caracterización del BaseRepository de Beanie en los caminos que
pulbot usa directo (y que los hallazgos de seguridad mostraron que se llaman
sin pasar por el service): filtros por Link, alias `<campo>_id`, coerción
str→ObjectId, get_by_field(s), keyset y filtros raw `$`/dot-notation.

No cambié el código del repo (solo docstring), así que esto CARACTERIZA el
comportamiento vigente y lo blinda contra regresiones futuras.
"""

from typing import Optional

import mongomock_motor
import pytest
from beanie import Document, Link, init_beanie
from bson import ObjectId
from pydantic import Field

from fastapi_basekit.aio.beanie.repository.base import BaseRepository


class Company(Document):
    name: str

    class Settings:
        name = "companies"


class Employee(Document):
    name: str
    company: Optional[Link[Company]] = None
    active: bool = True
    salary: int = 0

    class Settings:
        name = "employees"


class CompanyRepo(BaseRepository):
    model = Company


class EmployeeRepo(BaseRepository):
    model = Employee


@pytest.fixture
async def db():
    client = mongomock_motor.AsyncMongoMockClient()
    await init_beanie(
        database=client.test_db, document_models=[Company, Employee]
    )
    yield
    client.close()


@pytest.fixture
async def data(db):
    crepo = CompanyRepo()
    acme = await crepo.create({"name": "Acme"})
    globex = await crepo.create({"name": "Globex"})
    erepo = EmployeeRepo()
    emps = [
        await erepo.create(Employee(name="Ana", company=acme, active=True, salary=100)),
        await erepo.create(Employee(name="Beto", company=acme, active=False, salary=200)),
        await erepo.create(Employee(name="Ciro", company=globex, active=True, salary=300)),
    ]
    return {"acme": acme, "globex": globex, "emps": emps}


# ---------------------------------------------------------------------------
# create: dict vs Document
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_from_dict(db):
    repo = CompanyRepo()
    obj = await repo.create({"name": "Z"})
    assert obj.id is not None
    assert obj.name == "Z"


@pytest.mark.asyncio
async def test_create_from_document(db):
    repo = CompanyRepo()
    obj = await repo.create(Company(name="Y"))
    assert obj.id is not None


# ---------------------------------------------------------------------------
# get_by_id: str, ObjectId, inexistente
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_by_id_with_str(data):
    repo = CompanyRepo()
    got = await repo.get_by_id(str(data["acme"].id))
    assert got.id == data["acme"].id


@pytest.mark.asyncio
async def test_get_by_id_with_objectid(data):
    repo = CompanyRepo()
    got = await repo.get_by_id(data["acme"].id)
    assert got.name == "Acme"


@pytest.mark.asyncio
async def test_get_by_id_missing_returns_none(db):
    repo = CompanyRepo()
    assert await repo.get_by_id(ObjectId()) is None


# ---------------------------------------------------------------------------
# filtros por Link: alias `<campo>_id` y coerción str→ObjectId
# ---------------------------------------------------------------------------

# NOTA: mongomock guarda los Link como DBRef y NO matchea `campo.$id`, así que
# NO se puede verificar el RESULTADO del filtro por Link contra el mock (en
# Mongo real de pulbot sí funciona). Lo que SÍ es responsabilidad de basekit —
# construir el filtro `campo.$id` con el ObjectId coaccionado — se verifica de
# forma determinista con `get_filter_query()`, independiente del matching.

@pytest.mark.asyncio
async def test_link_id_alias_builds_dbref_filter_from_str(data):
    """`company_id=<str>` → filtro `company.$id` con ObjectId (patrón pulbot)."""
    repo = EmployeeRepo()
    query = repo.build_filter_query(
        search=None, search_fields=[],
        filters={"company_id": str(data["acme"].id)},
    )
    fq = query.get_filter_query()
    assert fq == {"company.$id": data["acme"].id}
    assert isinstance(fq["company.$id"], ObjectId)


@pytest.mark.asyncio
async def test_link_id_alias_builds_dbref_filter_from_objectid(data):
    repo = EmployeeRepo()
    query = repo.build_filter_query(
        search=None, search_fields=[],
        filters={"company_id": data["globex"].id},
    )
    assert query.get_filter_query() == {"company.$id": data["globex"].id}


@pytest.mark.asyncio
async def test_link_id_alias_invalid_objectid_passthrough(data):
    """Un `company_id` no-ObjectId no revienta: se pasa tal cual (no coacciona)."""
    repo = EmployeeRepo()
    query = repo.build_filter_query(
        search=None, search_fields=[], filters={"company_id": "not-an-oid"}
    )
    assert query.get_filter_query() == {"company.$id": "not-an-oid"}


@pytest.mark.asyncio
async def test_filter_scalar_field(data):
    repo = EmployeeRepo()
    query = repo.build_filter_query(
        search=None, search_fields=[], filters={"active": True}
    )
    rows = await query.to_list()
    assert {e.name for e in rows} == {"Ana", "Ciro"}


@pytest.mark.asyncio
async def test_mongo_style_scoping_keys_pass_through(data):
    """`user.$id` / `$or` (patrón de scoping en get_filters) NO se descartan:
    se aplican como filtro Mongo crudo. Su pérdida silenciosa sería un IDOR."""
    repo = EmployeeRepo()
    query = repo.build_filter_query(
        search=None,
        search_fields=[],
        filters={"company.$id": data["acme"].id},
    )
    assert query.get_filter_query() == {"company.$id": data["acme"].id}


@pytest.mark.asyncio
async def test_unresolvable_filter_key_warns_before_drop(data, caplog):
    """Una clave que no resuelve a ningún campo se descarta PERO avisa: si era
    un filtro de scoping, su desaparición silenciosa dejaría el listado sin
    filtrar (fuga cross-tenant). El warning hace visible la pérdida."""
    import logging

    repo = EmployeeRepo()
    with caplog.at_level(logging.WARNING):
        query = repo.build_filter_query(
            search=None,
            search_fields=[],
            filters={"nonexistent_scope": "x"},
        )
    assert query.get_filter_query() in ({}, {"$and": []})
    assert any(
        "nonexistent_scope" in r.message and "descartado" in r.message
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# get_by_field / get_by_fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_by_field(data):
    repo = EmployeeRepo()
    got = await repo.get_by_field("name", "Beto")
    assert got.salary == 200


@pytest.mark.asyncio
async def test_get_by_field_unknown_raises(db):
    repo = EmployeeRepo()
    with pytest.raises(AttributeError):
        await repo.get_by_field("nope", "x")


@pytest.mark.asyncio
async def test_get_by_fields_multi(data):
    repo = EmployeeRepo()
    got = await repo.get_by_fields({"active": True, "salary": 300})
    assert got.name == "Ciro"


@pytest.mark.asyncio
async def test_get_by_fields_empty_returns_none(db):
    repo = EmployeeRepo()
    assert await repo.get_by_fields({}) is None


# ---------------------------------------------------------------------------
# update(obj, data) / delete(obj) — firma Beanie (¡NO id!)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_takes_document(data):
    repo = EmployeeRepo()
    obj = data["emps"][0]
    updated = await repo.update(obj, {"salary": 999})
    assert updated.salary == 999
    assert (await repo.get_by_id(obj.id)).salary == 999


@pytest.mark.asyncio
async def test_update_can_set_none(data):
    repo = EmployeeRepo()
    obj = data["emps"][0]
    await repo.update(obj, {"company": None})
    fresh = await repo.get_by_id(obj.id)
    assert fresh.company is None


@pytest.mark.asyncio
async def test_delete_takes_document(data):
    repo = EmployeeRepo()
    obj = data["emps"][2]
    await repo.delete(obj)
    assert await repo.get_by_id(obj.id) is None


# ---------------------------------------------------------------------------
# paginación offset + keyset
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("page,count,expected", [
    (1, 2, 2), (2, 2, 1), (3, 2, 0), (1, 10, 3),
])
@pytest.mark.asyncio
async def test_paginate(data, page, count, expected):
    repo = EmployeeRepo()
    query = repo.build_filter_query(search=None, search_fields=[], filters={})
    items, total = await repo.paginate(query, page, count)
    assert len(items) == expected
    assert total == 3


@pytest.mark.asyncio
async def test_keyset_walk(data):
    repo = EmployeeRepo()
    query = repo.build_filter_query(search=None, search_fields=[], filters={})
    page1, more1 = await repo.paginate_keyset(query, limit=2, cursor_field="_id", ascending=True)
    assert len(page1) == 2 and more1 is True
    cursor = page1[-1].id
    query2 = repo.build_filter_query(search=None, search_fields=[], filters={})
    page2, more2 = await repo.paginate_keyset(
        query2, limit=2, cursor_field="_id", cursor_value=cursor, ascending=True
    )
    assert len(page2) == 1 and more2 is False


@pytest.mark.asyncio
async def test_list_all(data):
    repo = EmployeeRepo()
    rows = await repo.list_all()
    assert len(rows) == 3
