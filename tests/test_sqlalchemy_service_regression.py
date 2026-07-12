"""Regresión del BaseService de SQLAlchemy + aislamiento de mutable-defaults.

Incluye el test del fix issue #7: mutar `self.search_fields` en una instancia
NO debe filtrarse a la clase ni a otras instancias (antes solo estaba corregido
en Beanie).
"""

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from example_crud.models import Base
from example_crud.repository import UserRepository
from example_crud.service import UserService
from example_crud.schemas import UserCreateSchema, UserUpdateSchema
from fastapi_basekit.exceptions.api_exceptions import (
    NotFoundException,
    DatabaseIntegrityException,
)


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
async def service(session):
    return UserService(repository=UserRepository(db=session), request=None)


@pytest.fixture
async def seeded(service):
    created = []
    for n, e, a in [("Ana", "ana@x.com", 30), ("Beto", "beto@x.com", 40)]:
        created.append(
            await service.create(UserCreateSchema(name=n, email=e, age=a))
        )
        await service.repository.session.commit()
    return created


# ---------------------------------------------------------------------------
# CRUD service
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_found(seeded, service):
    got = await service.retrieve(str(seeded[0].id))
    assert got.name == "Ana"


@pytest.mark.asyncio
async def test_retrieve_not_found(service):
    with pytest.raises(NotFoundException):
        await service.retrieve("999999")


@pytest.mark.asyncio
async def test_create(service):
    obj = await service.create(UserCreateSchema(name="New", email="new@x.com", age=1))
    assert obj.id is not None


@pytest.mark.asyncio
async def test_create_duplicate(seeded, session):
    class DupService(UserService):
        duplicate_check_fields = ["email"]

    svc = DupService(repository=UserRepository(db=session), request=None)
    with pytest.raises(DatabaseIntegrityException):
        await svc.create(UserCreateSchema(name="X", email="ana@x.com", age=1))


@pytest.mark.asyncio
async def test_update(seeded, service):
    updated = await service.update(str(seeded[0].id), UserUpdateSchema(name="Ana2"))
    assert updated.name == "Ana2"


@pytest.mark.asyncio
async def test_delete(seeded, service):
    ok = await service.delete(str(seeded[1].id))
    assert ok is True
    with pytest.raises(NotFoundException):
        await service.retrieve(str(seeded[1].id))


@pytest.mark.asyncio
async def test_list(seeded, service):
    items, total = await service.list(count=50)
    assert total == 2


# ---------------------------------------------------------------------------
# get_filters scoping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_filters_scoping(seeded, session):
    class ActiveScopedService(UserService):
        def get_filters(self, filters=None):
            filters = super().get_filters(filters)
            filters["name"] = "Ana"
            return filters

    svc = ActiveScopedService(repository=UserRepository(db=session), request=None)
    items, total = await svc.list(count=50)
    assert {u.name for u in items} == {"Ana"}


# ---------------------------------------------------------------------------
# Fix issue #7: aislamiento de mutable-defaults por instancia
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mutable_defaults_isolated_between_instances(session):
    svc1 = UserService(repository=UserRepository(db=session), request=None)
    svc2 = UserService(repository=UserRepository(db=session), request=None)

    svc1.search_fields.append("hacked")

    assert "hacked" not in svc2.search_fields
    assert "hacked" not in UserService.search_fields


@pytest.mark.asyncio
async def test_mutable_defaults_are_copies_not_class_refs(session):
    svc = UserService(repository=UserRepository(db=session), request=None)
    assert svc.search_fields is not UserService.search_fields
    assert svc.duplicate_check_fields is not UserService.duplicate_check_fields
    assert svc.kwargs_query is not UserService.kwargs_query
