"""SQLModel CRUD tests — Repository + Service layers.

Mirrors the SQLAlchemy CRUD tests against a SQLite-in-memory database
using the SQLModel async session. Validates that the SQLModel variant of
BaseRepository and BaseService behaves identically to the SQLAlchemy one
for the documented contract: create, list+filter+search+order, retrieve,
update, soft-delete, duplicate-check on create.
"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from example_crud_sqlmodel.models import User
from example_crud_sqlmodel.repository import UserSQLModelRepository
from example_crud_sqlmodel.schemas import UserCreateSchema, UserUpdateSchema
from example_crud_sqlmodel.service import UserSQLModelService

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_engine():
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
    async with SQLModelAsyncSession(async_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
async def repository(async_session):
    return UserSQLModelRepository(db=async_session)


@pytest.fixture
async def service(repository):
    return UserSQLModelService(repository=repository)


@pytest.fixture
async def sample_users(repository):
    users_data = [
        {"name": "Juan Pérez", "email": "juan@example.com", "age": 30, "is_active": True},
        {"name": "María García", "email": "maria@example.com", "age": 25, "is_active": True},
        {"name": "Pedro López", "email": "pedro@example.com", "age": 35, "is_active": False},
        {"name": "Ana Martínez", "email": "ana@example.com", "age": 28, "is_active": True},
        {"name": "Carlos Rodríguez", "email": "carlos@example.com", "age": 40, "is_active": True},
    ]
    created = []
    for data in users_data:
        user = await repository.create(data)
        created.append(user)
    return created


class TestSQLModelRepository:
    @pytest.mark.asyncio
    async def test_create_user(self, repository):
        user = await repository.create(
            {"name": "Test", "email": "t@example.com", "age": 25, "is_active": True}
        )
        assert user.id is not None
        assert user.email == "t@example.com"
        assert user.created_at is not None

    @pytest.mark.asyncio
    async def test_list_paginated(self, repository, sample_users):
        users, total = await repository.list_paginated(page=1, count=3)
        assert total == 5
        assert len(users) == 3

    @pytest.mark.asyncio
    async def test_list_with_filters(self, repository, sample_users):
        users, total = await repository.list_paginated(
            page=1, count=10, filters={"is_active": True}
        )
        assert total == 4
        assert all(u.is_active for u in users)

    @pytest.mark.asyncio
    async def test_list_with_search(self, repository, sample_users):
        users, total = await repository.list_paginated(
            page=1, count=10, search="María", search_fields=["name", "email"]
        )
        assert total == 1
        assert users[0].name == "María García"

    @pytest.mark.asyncio
    async def test_retrieve_user_by_id(self, repository, sample_users):
        target = sample_users[0]
        user = await repository.get(target.id)
        assert user is not None
        assert user.id == target.id
        assert user.name == "Juan Pérez"

    @pytest.mark.asyncio
    async def test_retrieve_missing_returns_none(self, repository):
        result = await repository.get(99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_user(self, repository, sample_users):
        target_id = sample_users[0].id
        updated = await repository.update(
            target_id, {"name": "Juan Actualizado", "age": 31}
        )
        assert updated.name == "Juan Actualizado"
        assert updated.age == 31
        assert updated.email == "juan@example.com"

    @pytest.mark.asyncio
    async def test_delete_user(self, repository, sample_users):
        target_id = sample_users[0].id
        result = await repository.delete(target_id)
        assert result is True
        assert await repository.get(target_id) is None

    @pytest.mark.asyncio
    async def test_get_by_filters_match(self, repository, sample_users):
        users = await repository.get_by_filters({"email": "juan@example.com"})
        assert len(users) == 1
        assert users[0].email == "juan@example.com"

    @pytest.mark.asyncio
    async def test_get_by_filters_no_match(self, repository, sample_users):
        users = await repository.get_by_filters({"email": "ghost@example.com"})
        assert len(users) == 0


class TestSQLModelService:
    @pytest.mark.asyncio
    async def test_create_duplicate_check_raises(self, service, sample_users):
        from fastapi_basekit.exceptions.api_exceptions import (
            DatabaseIntegrityException,
        )

        payload = UserCreateSchema(
            name="Otro", email="juan@example.com", age=22
        )
        with pytest.raises(DatabaseIntegrityException):
            await service.create(payload)

    @pytest.mark.asyncio
    async def test_create_success(self, service):
        payload = UserCreateSchema(
            name="Nuevo", email="nuevo@example.com", age=30
        )
        user = await service.create(payload)
        assert user.id is not None
        assert user.email == "nuevo@example.com"

    @pytest.mark.asyncio
    async def test_list_search_uses_service_fields(self, service, sample_users):
        # search_fields = ["name", "email"] declared on the service
        users, total = await service.list(page=1, count=10, search="García")
        assert total == 1
        assert users[0].name == "María García"

    @pytest.mark.asyncio
    async def test_list_filters_pass_through(self, service, sample_users):
        users, total = await service.list(
            page=1, count=10, filters={"is_active": True}
        )
        assert total == 4

    @pytest.mark.asyncio
    async def test_update_via_schema(self, service, sample_users):
        target_id = str(sample_users[0].id)
        updated = await service.update(
            target_id, UserUpdateSchema(name="Nombre Nuevo")
        )
        assert updated.name == "Nombre Nuevo"

    @pytest.mark.asyncio
    async def test_retrieve_not_found_raises(self, service):
        from fastapi_basekit.exceptions.api_exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.retrieve("99999")

    @pytest.mark.asyncio
    async def test_delete_via_service(self, service, sample_users):
        target_id = str(sample_users[0].id)
        result = await service.delete(target_id)
        assert result is True or result == "deleted"


class TestSQLModelCRUDIntegration:
    @pytest.mark.asyncio
    async def test_full_crud_flow(self, service):
        created = await service.create(
            UserCreateSchema(
                name="Flow", email="flow@example.com", age=33, is_active=True
            )
        )
        assert created.id is not None

        retrieved = await service.retrieve(str(created.id))
        assert retrieved.id == created.id

        updated = await service.update(
            str(created.id), UserUpdateSchema(age=34)
        )
        assert updated.age == 34

        await service.delete(str(created.id))
        from fastapi_basekit.exceptions.api_exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.retrieve(str(created.id))

    @pytest.mark.asyncio
    async def test_pagination_navigation(self, service, sample_users):
        page1, total = await service.list(page=1, count=2)
        page2, _ = await service.list(page=2, count=2)
        page3, _ = await service.list(page=3, count=2)
        assert total == 5
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

        # No overlap across pages (by id)
        ids_p1 = {u.id for u in page1}
        ids_p2 = {u.id for u in page2}
        ids_p3 = {u.id for u in page3}
        assert ids_p1.isdisjoint(ids_p2)
        assert ids_p2.isdisjoint(ids_p3)
