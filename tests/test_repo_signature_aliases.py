"""Firmas de lectura por id UNIFICADAS entre ORMs.

Antes: SQL usaba `get(id)`, Beanie `get_by_id(id)` — código no portable. Ahora
ambos exponen LOS DOS nombres (aliases), así una lectura por id funciona igual
sin importar el ORM.
"""

import mongomock_motor
import pytest
from beanie import init_beanie
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SMSession

from example_crud.models import Base
from example_crud.repository import UserRepository
from example_crud_sqlmodel.models import User as SMUser  # noqa: F401
from example_crud_sqlmodel.repository import UserSQLModelRepository
from example_crud_beanie.models import UserDocument
from example_crud_beanie.repository import UserBeanieRepository


# --- SQLAlchemy ------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlalchemy_get_and_get_by_id_equivalent():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        repo = UserRepository(db=s)
        u = await repo.create({"name": "A", "email": "a@x.com"})
        await s.commit()
        assert (await repo.get(u.id)).id == u.id
        assert (await repo.get_by_id(u.id)).id == u.id
    await engine.dispose()


# --- SQLModel --------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlmodel_get_and_get_by_id_equivalent():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    async with engine.begin() as c:
        await c.run_sync(SQLModel.metadata.create_all)
    async with SMSession(engine, expire_on_commit=False) as s:
        repo = UserSQLModelRepository(db=s)
        u = await repo.create({"name": "A", "email": "a@x.com"})
        await s.commit()
        assert (await repo.get(u.id)).id == u.id
        assert (await repo.get_by_id(u.id)).id == u.id
    await engine.dispose()


# --- Beanie ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_beanie_get_and_get_by_id_equivalent():
    client = mongomock_motor.AsyncMongoMockClient()
    await init_beanie(database=client.test_db, document_models=[UserDocument])
    repo = UserBeanieRepository()
    u = await repo.create({"name": "A", "email": "a@x.com"})
    assert (await repo.get_by_id(u.id)).id == u.id
    assert (await repo.get(u.id)).id == u.id      # alias nuevo en Beanie
    client.close()
