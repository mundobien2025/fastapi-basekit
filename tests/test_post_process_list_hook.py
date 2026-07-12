"""Verifica el hook `post_process_list` — el punto de extensión para enriquecer
los items de una página SIN reescribir la paginación ni overridear `list()`.

Debe: correr después de paginar, sobre los items de la página actual, preservar
`total`, y respetar la paginación (no recibir toda la colección).
"""

import mongomock_motor
import pytest
from beanie import Document, init_beanie
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from example_crud.models import Base
from example_crud.repository import UserRepository
from example_crud.service import UserService

from fastapi_basekit.aio.beanie.repository.base import BaseRepository as BeanieRepo
from fastapi_basekit.aio.beanie.service.base import BaseService as BeanieService


# ===========================================================================
# SQLAlchemy
# ===========================================================================

SQL_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def sql_session():
    engine = create_async_engine(
        SQL_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


class EnrichingUserService(UserService):
    async def post_process_list(self, items):
        for u in items:
            u.enriched = f"E-{u.name}"
        return items


@pytest.fixture
async def sql_seed(sql_session):
    repo = UserRepository(db=sql_session)
    for i in range(5):
        await repo.create({"name": f"U{i}", "email": f"u{i}@x.com", "age": 20 + i})
        await repo.session.commit()


@pytest.mark.asyncio
async def test_sql_post_process_runs(sql_session, sql_seed):
    svc = EnrichingUserService(repository=UserRepository(db=sql_session), request=None)
    items, total = await svc.list(count=50)
    assert total == 5
    assert all(getattr(u, "enriched", None) == f"E-{u.name}" for u in items)


@pytest.mark.asyncio
async def test_sql_post_process_only_page_items(sql_session, sql_seed):
    """El hook recibe SOLO los items de la página, no toda la colección."""
    seen = {}

    class CountingService(UserService):
        async def post_process_list(self, items):
            seen["n"] = len(items)
            return items

    svc = CountingService(repository=UserRepository(db=sql_session), request=None)
    items, total = await svc.list(page=1, count=2)
    assert total == 5          # total = colección completa
    assert seen["n"] == 2      # hook vio solo la página
    assert len(items) == 2


@pytest.mark.asyncio
async def test_sql_default_hook_noop(sql_session, sql_seed):
    svc = UserService(repository=UserRepository(db=sql_session), request=None)
    items, total = await svc.list(count=50)
    assert total == 5 and len(items) == 5


# ===========================================================================
# Beanie
# ===========================================================================

class _Doc(Document):
    name: str
    # En Beanie/pydantic el enrich solo puede setear campos DECLARADOS (o un
    # dict como `metadata`); no se pueden agregar atributos nuevos al vuelo
    # como en SQLAlchemy. Gotcha documentado en la doc de paginación.
    tag: str = ""

    class Settings:
        name = "ppdocs"


class _DocRepo(BeanieRepo):
    model = _Doc


class _EnrichSvc(BeanieService):
    async def post_process_list(self, items):
        for d in items:
            d.tag = f"T-{d.name}"
        return items


@pytest.fixture
async def beanie_db():
    client = mongomock_motor.AsyncMongoMockClient()
    await init_beanie(database=client.test_db, document_models=[_Doc])
    repo = _DocRepo()
    for i in range(5):
        await repo.create({"name": f"D{i}"})
    yield
    client.close()


@pytest.mark.asyncio
async def test_beanie_post_process_runs(beanie_db):
    svc = _EnrichSvc(repository=_DocRepo(), request=None)
    items, total = await svc.list(count=50)
    assert total == 5
    assert all(getattr(d, "tag", None) == f"T-{d.name}" for d in items)


@pytest.mark.asyncio
async def test_beanie_post_process_only_page_items(beanie_db):
    seen = {}

    class Counting(BeanieService):
        async def post_process_list(self, items):
            seen["n"] = len(items)
            return items

    svc = Counting(repository=_DocRepo(), request=None)
    items, total = await svc.list(page=1, count=2)
    assert total == 5
    assert seen["n"] == 2


@pytest.mark.asyncio
async def test_beanie_default_hook_noop(beanie_db):
    svc = BeanieService(repository=_DocRepo(), request=None)
    items, total = await svc.list(count=50)
    assert total == 5 and len(items) == 5
