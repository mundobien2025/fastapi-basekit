"""Tests completos del CRUD usando BaseController con SQLAlchemy."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from example_crud.models import Base, User
from example_crud.repository import UserRepository
from example_crud.service import UserService
from example_crud.controller import router
from example_crud.schemas import UserCreateSchema, UserUpdateSchema


# Configuración de base de datos en memoria para tests
DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_engine():
    """Crea un engine async para SQLite en memoria."""
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
    """Crea una sesión async para tests."""
    async_session_maker = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture
def app():
    """Crea una instancia de FastAPI para tests."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def repository(async_session):
    """Crea una instancia del repository con sesión de test."""
    return UserRepository(db=async_session)


@pytest.fixture
async def service(repository):
    """Crea una instancia del service con repository de test."""
    return UserService(repository=repository)


@pytest.fixture
async def sample_users(repository):
    """Crea usuarios de muestra en la base de datos."""
    users_data = [
        {
            "name": "Juan Pérez",
            "email": "juan@example.com",
            "age": 30,
            "is_active": True,
        },
        {
            "name": "María García",
            "email": "maria@example.com",
            "age": 25,
            "is_active": True,
        },
        {
            "name": "Pedro López",
            "email": "pedro@example.com",
            "age": 35,
            "is_active": False,
        },
        {
            "name": "Ana Martínez",
            "email": "ana@example.com",
            "age": 28,
            "is_active": True,
        },
        {
            "name": "Carlos Rodríguez",
            "email": "carlos@example.com",
            "age": 40,
            "is_active": True,
        },
    ]

    created_users = []
    for user_data in users_data:
        user = await repository.create(user_data)
        created_users.append(user)

    return created_users


class TestUserRepository:
    """Tests del Repository."""

    @pytest.mark.asyncio
    async def test_create_user(self, repository):
        """Test: Crear un usuario."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "age": 25,
            "is_active": True,
        }

        user = await repository.create(user_data)

        assert user.id is not None
        assert user.name == "Test User"
        assert user.email == "test@example.com"
        assert user.age == 25
        assert user.is_active is True
        assert user.created_at is not None

    @pytest.mark.asyncio
    async def test_list_users(self, repository, sample_users):
        """Test: Listar usuarios con paginación."""
        users, total = await repository.list_paginated(page=1, count=3)

        assert total == 5
        assert len(users) == 3
        assert users[0].name == "Juan Pérez"

    @pytest.mark.asyncio
    async def test_list_with_filters(self, repository, sample_users):
        """Test: Listar usuarios con filtros."""
        users, total = await repository.list_paginated(
            page=1, count=10, filters={"is_active": True}
        )

        assert total == 4
        assert all(user.is_active for user in users)

    @pytest.mark.asyncio
    async def test_list_with_search(self, repository, sample_users):
        """Test: Buscar usuarios por texto."""
        users, total = await repository.list_paginated(
            page=1, count=10, search="María", search_fields=["name", "email"]
        )

        assert total == 1
        assert users[0].name == "María García"

    @pytest.mark.asyncio
    async def test_retrieve_user(self, repository, sample_users):
        """Test: Obtener un usuario por ID."""
        user_id = sample_users[0].id
        user = await repository.get(user_id)

        assert user is not None
        assert user.id == user_id
        assert user.name == "Juan Pérez"

    @pytest.mark.asyncio
    async def test_update_user(self, repository, sample_users):
        """Test: Actualizar un usuario."""
        user_id = sample_users[0].id
        update_data = {"name": "Juan Actualizado", "age": 31}

        updated_user = await repository.update(user_id, update_data)

        assert updated_user.name == "Juan Actualizado"
        assert updated_user.age == 31
        assert updated_user.email == "juan@example.com"  # No cambia

    @pytest.mark.asyncio
    async def test_delete_user(self, repository, sample_users):
        """Test: Eliminar un usuario."""
        user_id = sample_users[0].id

        result = await repository.delete(user_id)

        assert result is True

        # Verificar que ya no existe
        deleted_user = await repository.get(user_id)
        assert deleted_user is None

    @pytest.mark.asyncio
    async def test_check_exists_by_filters(self, repository, sample_users):
        """Test: Verificar si existe un usuario con ciertos campos."""
        users = await repository.get_by_filters({"email": "juan@example.com"})
        assert len(users) > 0

        users = await repository.get_by_filters(
            {"email": "noexiste@example.com"}
        )
        assert len(users) == 0


class TestUserService:
    """Tests del Service."""

    @pytest.mark.asyncio
    async def test_create_with_duplicate_check(self, service, sample_users):
        """Test: Crear usuario con validación de duplicados."""
        from fastapi_basekit.exceptions.api_exceptions import (
            DatabaseIntegrityException,
        )

        user_data = UserCreateSchema(
            name="Nuevo Usuario",
            email="juan@example.com",  # Email duplicado
            age=30,
        )

        with pytest.raises(DatabaseIntegrityException):
            await service.create(user_data)

    @pytest.mark.asyncio
    async def test_create_success(self, service):
        """Test: Crear usuario exitosamente."""
        user_data = UserCreateSchema(
            name="Usuario Nuevo", email="nuevo@example.com", age=30
        )

        user = await service.create(user_data)

        assert user.id is not None
        assert user.email == "nuevo@example.com"

    @pytest.mark.asyncio
    async def test_list_with_search(self, service, sample_users):
        """Test: Listar con búsqueda usando search_fields del service."""
        users, total = await service.list(page=1, count=10, search="García")

        assert total == 1
        assert users[0].name == "María García"

    @pytest.mark.asyncio
    async def test_update_user(self, service, sample_users):
        """Test: Actualizar usuario a través del service."""
        user_id = str(sample_users[0].id)
        update_data = UserUpdateSchema(name="Nombre Actualizado")

        updated_user = await service.update(user_id, update_data)

        assert updated_user.name == "Nombre Actualizado"

    @pytest.mark.asyncio
    async def test_retrieve_not_found(self, service):
        """Test: Intentar obtener un usuario que no existe."""
        from fastapi_basekit.exceptions.api_exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.retrieve("99999")

    @pytest.mark.asyncio
    async def test_delete_user(self, service, sample_users):
        """Test: Eliminar usuario."""
        user_id = str(sample_users[0].id)

        result = await service.delete(user_id)

        assert result is True

        # Verificar que ya no se puede obtener
        from fastapi_basekit.exceptions.api_exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.retrieve(user_id)


class TestCRUDIntegration:
    """Tests de integración completa del CRUD."""

    @pytest.mark.asyncio
    async def test_full_crud_flow(self, service):
        """Test: Flujo completo de CRUD."""
        # 1. Crear
        user_data = UserCreateSchema(
            name="Usuario Test", email="test@example.com", age=30
        )
        created_user = await service.create(user_data)
        assert created_user.id is not None
        user_id = str(created_user.id)

        # 2. Obtener
        retrieved_user = await service.retrieve(user_id)
        assert retrieved_user.email == "test@example.com"

        # 3. Actualizar
        update_data = UserUpdateSchema(name="Usuario Actualizado", age=31)
        updated_user = await service.update(user_id, update_data)
        assert updated_user.name == "Usuario Actualizado"
        assert updated_user.age == 31

        # 4. Listar
        users, total = await service.list(page=1, count=10)
        assert total >= 1

        # 5. Eliminar
        result = await service.delete(user_id)
        assert result is True

        # 6. Verificar eliminación
        from fastapi_basekit.exceptions.api_exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.retrieve(user_id)

    @pytest.mark.asyncio
    async def test_pagination_navigation(self, service, sample_users):
        """Test: Navegación por páginas."""
        # Página 1
        users_p1, total = await service.list(page=1, count=2)
        assert len(users_p1) == 2
        assert total == 5

        # Página 2
        users_p2, _ = await service.list(page=2, count=2)
        assert len(users_p2) == 2

        # Página 3
        users_p3, _ = await service.list(page=3, count=2)
        assert len(users_p3) == 1

        # Verificar que no hay duplicados
        all_user_ids = (
            [u.id for u in users_p1]
            + [u.id for u in users_p2]
            + [u.id for u in users_p3]
        )
        assert len(all_user_ids) == len(set(all_user_ids))

    @pytest.mark.asyncio
    async def test_complex_filtering(self, service, sample_users):
        """Test: Filtrado complejo."""
        # Usuarios activos mayores de 25 años
        users, total = await service.list(
            page=1, count=10, filters={"is_active": True}
        )

        # Filtrar manualmente por edad (esto debería hacerse en el repository)
        users_over_25 = [u for u in users if u.age and u.age > 25]
        assert len(users_over_25) >= 2
