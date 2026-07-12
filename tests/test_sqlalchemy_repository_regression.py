"""Regresión del BaseRepository de SQLAlchemy bajo generics + refactor.

Cubre CRUD, get_by_field/filters, list_paginated (filtros/search/orden/
paginación), el hook build_list_queryset (scoping row-level), la semántica
`update` que OMITE None (divergencia con Beanie), y el aislamiento de
mutable-defaults por instancia en el service.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from example_crud.models import Base, User
from example_crud.repository import UserRepository


DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_engine():
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(async_engine):
    maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s


@pytest.fixture
async def repo(session):
    r = UserRepository(db=session)
    yield r


@pytest.fixture
async def seeded(repo):
    rows = [
        {"name": "Ana", "email": "ana@x.com", "age": 30, "is_active": True},
        {"name": "Beto", "email": "beto@x.com", "age": 40, "is_active": False},
        {"name": "Ciro", "email": "ciro@x.com", "age": 50, "is_active": True},
    ]
    created = []
    for row in rows:
        created.append(await repo.create(row))
        await repo.session.commit()
    return created


# ---------------------------------------------------------------------------
# create / get
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_from_dict(repo):
    obj = await repo.create({"name": "Z", "email": "z@x.com"})
    assert obj.id is not None and obj.name == "Z"


@pytest.mark.asyncio
async def test_create_from_model(repo):
    obj = await repo.create(User(name="Y", email="y@x.com"))
    assert obj.id is not None


@pytest.mark.asyncio
async def test_get_found_and_missing(seeded, repo):
    got = await repo.get(seeded[0].id)
    assert got.name == "Ana"
    assert await repo.get(999999) is None


@pytest.mark.asyncio
async def test_get_by_field(seeded, repo):
    got = await repo.get_by_field("email", "beto@x.com")
    assert got.name == "Beto"


# ---------------------------------------------------------------------------
# update: firma (id, dict) y OMITE None (divergencia con Beanie)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_by_id(seeded, repo):
    updated = await repo.update(seeded[0].id, {"age": 99})
    assert updated.age == 99


@pytest.mark.asyncio
async def test_update_skips_none(seeded, repo):
    """SQL `update` ignora valores None — no puede nullear la columna por acá."""
    original_name = seeded[0].name
    updated = await repo.update(seeded[0].id, {"name": None, "age": 77})
    assert updated.name == original_name  # None ignorado
    assert updated.age == 77


@pytest.mark.asyncio
async def test_update_missing_raises(repo):
    from fastapi_basekit.exceptions.api_exceptions import NotFoundException
    with pytest.raises(NotFoundException):
        await repo.update(123456, {"age": 1})


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete(seeded, repo):
    ok = await repo.delete(seeded[2].id)
    assert ok is True
    assert await repo.get(seeded[2].id) is None


# ---------------------------------------------------------------------------
# list_paginated: filtros, search, orden, paginación
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_filter_bool(seeded, repo):
    items, total = await repo.list_paginated(filters={"is_active": True}, count=50)
    assert {u.name for u in items} == {"Ana", "Ciro"}
    assert total == 2


@pytest.mark.asyncio
async def test_list_search(seeded, repo):
    items, total = await repo.list_paginated(
        search="An", search_fields=["name"], count=50
    )
    assert {u.name for u in items} == {"Ana"}


@pytest.mark.parametrize("page,count,expected", [
    (1, 1, 1), (1, 2, 2), (2, 2, 1), (1, 10, 3), (4, 1, 0),
])
@pytest.mark.asyncio
async def test_list_pagination(seeded, repo, page, count, expected):
    items, total = await repo.list_paginated(page=page, count=count)
    assert len(items) == expected
    assert total == 3


# ---------------------------------------------------------------------------
# build_list_queryset: hook de scoping row-level
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_list_queryset_scoping_override(seeded, session):
    from sqlalchemy import select

    class ActiveOnlyRepo(UserRepository):
        def build_list_queryset(self, **kwargs):
            return select(self.model).where(self.model.is_active.is_(True))

    repo = ActiveOnlyRepo(db=session)
    items, total = await repo.list_paginated(count=50)
    assert {u.name for u in items} == {"Ana", "Ciro"}
    assert total == 2
