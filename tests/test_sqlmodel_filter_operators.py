"""Operadores de filtro en SQLModel (`__gte`/`__lte`/`__in`/`__ilike`/...).

Antes SQLModel los descartaba en silencio (devolvía TODO). El parser se portó
del repo SQLAlchemy. Este test prueba que ahora filtran de verdad, end-to-end.
"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from example_crud_sqlmodel.models import User
from example_crud_sqlmodel.repository import UserSQLModelRepository


DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def engine():
    e = create_async_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with e.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield e
    async with e.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await e.dispose()


@pytest.fixture
async def repo(engine):
    async with SQLModelAsyncSession(engine, expire_on_commit=False) as s:
        r = UserSQLModelRepository(db=s)
        for i, name in enumerate(["Ana", "Beto", "Ciro", "Dina"]):
            await r.create({"name": name, "email": f"{name}@x.com", "age": 20 + i * 10})
            await s.commit()
        yield r


def test_split_operator():
    repo = UserSQLModelRepository.__new__(UserSQLModelRepository)
    assert repo._split_operator("age__gte") == ("age", "gte")
    assert repo._split_operator("name__ilike") == ("name", "ilike")
    assert repo._split_operator("id__in") == ("id", "in")
    assert repo._split_operator("name") == ("name", "eq")
    assert repo._split_operator("user__role__code") == ("user__role__code", "eq")


@pytest.mark.asyncio
async def test_gte(repo):
    items, total = await repo.list_paginated(filters={"age__gte": 40}, count=50)
    assert {u.name for u in items} == {"Ciro", "Dina"}  # 40, 50


@pytest.mark.asyncio
async def test_lte(repo):
    items, total = await repo.list_paginated(filters={"age__lte": 30}, count=50)
    assert {u.name for u in items} == {"Ana", "Beto"}  # 20, 30


@pytest.mark.asyncio
async def test_gt_lt(repo):
    items, _ = await repo.list_paginated(filters={"age__gt": 20, "age__lt": 50}, count=50)
    assert {u.name for u in items} == {"Beto", "Ciro"}


@pytest.mark.asyncio
async def test_in(repo):
    items, _ = await repo.list_paginated(filters={"age__in": [20, 50]}, count=50)
    assert {u.name for u in items} == {"Ana", "Dina"}


@pytest.mark.asyncio
async def test_ne(repo):
    items, _ = await repo.list_paginated(filters={"name__ne": "Ana"}, count=50)
    assert "Ana" not in {u.name for u in items}
    assert len(items) == 3


@pytest.mark.asyncio
async def test_ilike(repo):
    items, _ = await repo.list_paginated(filters={"name__ilike": "an"}, count=50)
    assert {u.name for u in items} == {"Ana"}


@pytest.mark.asyncio
async def test_plain_eq_still_works(repo):
    items, _ = await repo.list_paginated(filters={"name": "Beto"}, count=50)
    assert {u.name for u in items} == {"Beto"}
