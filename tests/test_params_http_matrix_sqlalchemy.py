"""Matriz HTTP end-to-end (SQLAlchemy) sobre filtros + paginación.

El resultado esperado se computa en Python desde el seed determinista y se
compara con la respuesta del API — así la matriz se parametriza ancho sin
hardcodear conteos. Valida el stack completo cbv → _params → service → repo
→ SQL bajo el refactor de `_params`.
"""

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport
from httpx import AsyncClient as HTTPXAsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from example_crud.models import Base
from example_crud.repository import UserRepository
from example_crud.service import UserService


DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Seed determinista: 12 usuarios, mezcla activo/inactivo y edades.
SEED = [
    {"name": f"User{i:02d}", "email": f"user{i:02d}@x.com", "age": 20 + i,
     "is_active": (i % 3 != 0)}
    for i in range(12)
]


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
async def async_session(async_engine):
    maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture
async def client(async_session):
    repo = UserRepository(db=async_session)
    for u in SEED:
        await repo.create(u)
        await repo.session.commit()

    from example_crud import controller as example_controller

    app = FastAPI()

    def get_user_service(request: Request):
        return UserService(
            repository=UserRepository(db=async_session), request=request
        )

    app.dependency_overrides[example_controller.get_user_service] = (
        get_user_service
    )
    app.include_router(example_controller.router)
    async with HTTPXAsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


def _expected_names(is_active, page, count):
    rows = [u for u in SEED
            if is_active is None or u["is_active"] is is_active]
    rows = sorted(rows, key=lambda u: u["name"])
    start = (page - 1) * count
    return [u["name"] for u in rows[start:start + count]], len(rows)


ACTIVE_OPTS = [None, True, False]
PAGE_OPTS = [1, 2, 3]
COUNT_OPTS = [1, 3, 5, 10, 50]


@pytest.mark.parametrize("is_active", ACTIVE_OPTS)
@pytest.mark.parametrize("page", PAGE_OPTS)
@pytest.mark.parametrize("count", COUNT_OPTS)
@pytest.mark.asyncio
async def test_filter_pagination_matrix(client, is_active, page, count):
    q = f"?page={page}&count={count}"
    if is_active is not None:
        q += f"&is_active={'true' if is_active else 'false'}"

    resp = await client.get(f"/users/{q}")
    assert resp.status_code == 200
    body = resp.json()

    exp_names, exp_total = _expected_names(is_active, page, count)
    got_names = sorted(u["name"] for u in body["data"])
    assert got_names == sorted(exp_names)
    assert body["pagination"]["total"] == exp_total
    assert body["pagination"]["page"] == page
    assert body["pagination"]["count"] == count
    # Coerción: si filtré activos, ninguno inactivo debe colarse.
    if is_active is not None:
        assert all(u["is_active"] is is_active for u in body["data"])
