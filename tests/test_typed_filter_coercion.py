"""Regresión: `_params` coacciona filtros de query al tipo declarado.

Antes, `_params` leía valores YA tipados por FastAPI desde el stack-frame del
endpoint (`inspect.currentframe()` + `skip_frames`). El refactor eliminó esa
magia y ahora coacciona `request.query_params` (strings) usando la firma del
endpoint (`request.scope["endpoint"]`).

El riesgo concreto de ese refactor: un filtro booleano tipado, ej.
`?is_active=false`, debe llegar al repo como Python `False`, NO como el string
`"false"` (que es truthy y filtraría al revés). Este test lo ejerce por el flujo
HTTP real (cbv → _params → service → repo → SQL).
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
    maker = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with maker() as session:
        yield session


@pytest.fixture
async def mixed_users(async_session):
    """Dos activos, un inactivo."""
    repo = UserRepository(db=async_session)
    for data in [
        {"name": "Ana", "email": "ana@x.com", "age": 30, "is_active": True},
        {"name": "Beto", "email": "beto@x.com", "age": 40, "is_active": True},
        {"name": "Ciro", "email": "ciro@x.com", "age": 50, "is_active": False},
    ]:
        await repo.create(data)
        await repo.session.commit()


@pytest.fixture
async def client(async_session, mixed_users):
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


@pytest.mark.asyncio
async def test_bool_filter_false_coerced_not_stringy(client):
    """`?is_active=false` → solo el usuario inactivo (string 'false' truthy roto)."""
    resp = await client.get("/users/?is_active=false&count=50")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Ciro"
    assert data[0]["is_active"] is False


@pytest.mark.asyncio
async def test_bool_filter_true_coerced(client):
    """`?is_active=true` → solo los dos activos."""
    resp = await client.get("/users/?is_active=true&count=50")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert {u["name"] for u in data} == {"Ana", "Beto"}
    assert all(u["is_active"] is True for u in data)


@pytest.mark.asyncio
async def test_no_filter_returns_all(client):
    """Sin filtro booleano se devuelven los tres."""
    resp = await client.get("/users/?count=50")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 3
