"""Tests completos del CRUD usando BeanieBaseController con MongoDB."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi import FastAPI, Request
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import mongomock_motor

from example_crud_beanie.models import UserDocument
from example_crud_beanie.repository import UserBeanieRepository
from example_crud_beanie.service import UserBeanieService
from example_crud_beanie.controller import router
from example_crud_beanie.schemas import (
    UserBeanieCreateSchema,
    UserBeanieUpdateSchema,
)


# Configuración de MongoDB en memoria con mongomock
@pytest.fixture
async def mongo_client():
    """Crea un cliente MongoDB en memoria para tests."""
    client = mongomock_motor.AsyncMongoMockClient()
    yield client
    client.close()


@pytest.fixture
async def init_db(mongo_client):
    """Inicializa Beanie con MongoDB en memoria."""
    await init_beanie(
        database=mongo_client.test_db, document_models=[UserDocument]
    )
    yield
    # Limpiar después de cada test
    try:
        collection = UserDocument.get_settings().motor_db[
            UserDocument.get_settings().name
        ]
        await collection.drop()
    except Exception:
        pass  # Si falla la limpieza, no importa


@pytest.fixture
def app():
    """Crea una instancia de FastAPI para tests."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def repository():
    """Crea una instancia del repository."""
    return UserBeanieRepository()


@pytest.fixture
def service(repository):
    """Crea una instancia del service con repository de test."""
    return UserBeanieService(repository=repository)


@pytest.fixture
async def sample_users(init_db, repository):
    """Crea usuarios de muestra en MongoDB."""
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
        user = UserDocument(**user_data)
        await user.insert()
        created_users.append(user)

    return created_users


class TestUserBeanieRepository:
    """Tests del Repository para Beanie."""

    @pytest.mark.asyncio
    async def test_create_user(self, init_db, repository):
        """Test: Crear un usuario en MongoDB."""
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

    @pytest.mark.asyncio
    async def test_list_users(self, init_db, repository, sample_users):
        """Test: Listar usuarios con paginación."""
        items, total = await repository.paginate(
            query=UserDocument.find_all(), page=1, count=3
        )

        assert total == 5
        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_list_with_filters(self, init_db, repository, sample_users):
        """Test: Listar usuarios con filtros."""
        query = repository.build_filter_query(
            search=None, search_fields=[], filters={"is_active": True}
        )
        items, total = await repository.paginate(query=query, page=1, count=10)

        assert total == 4
        assert all(user.is_active for user in items)

    @pytest.mark.asyncio
    async def test_list_with_search(self, init_db, repository, sample_users):
        """Test: Buscar usuarios por texto."""
        query = repository.build_filter_query(
            search="María", search_fields=["name", "email"], filters=None
        )
        items, total = await repository.paginate(query=query, page=1, count=10)

        assert total == 1
        assert items[0].name == "María García"

    @pytest.mark.asyncio
    async def test_retrieve_user(self, init_db, repository, sample_users):
        """Test: Obtener un usuario por ID."""
        user_id = str(sample_users[0].id)
        user = await repository.get_by_id(user_id)

        assert user is not None
        assert str(user.id) == user_id
        assert user.name == "Juan Pérez"

    @pytest.mark.asyncio
    async def test_update_user(self, init_db, repository, sample_users):
        """Test: Actualizar un usuario."""
        user_obj = sample_users[0]
        update_data = {"name": "Juan Actualizado", "age": 31}

        updated_user = await repository.update(user_obj, update_data)

        assert updated_user.name == "Juan Actualizado"
        assert updated_user.age == 31
        assert updated_user.email == "juan@example.com"  # No cambia

    @pytest.mark.asyncio
    async def test_delete_user(self, init_db, repository, sample_users):
        """Test: Eliminar un usuario."""
        user_obj = sample_users[0]
        user_id = str(user_obj.id)

        await repository.delete(user_obj)

        # Verificar que ya no existe
        deleted_user = await repository.get_by_id(user_id)
        assert deleted_user is None

    @pytest.mark.asyncio
    async def test_check_exists_by_filters(
        self, init_db, repository, sample_users
    ):
        """Test: Verificar si existe un usuario con ciertos campos."""
        user = await repository.get_by_fields({"email": "juan@example.com"})
        assert user is not None

        user = await repository.get_by_fields(
            {"email": "noexiste@example.com"}
        )
        assert user is None


class TestUserBeanieService:
    """Tests del Service para Beanie."""

    @pytest.mark.asyncio
    async def test_create_with_duplicate_check(
        self, init_db, service, sample_users
    ):
        """Test: Crear usuario con validación de duplicados."""
        from fastapi_basekit.exceptions.api_exceptions import (
            DatabaseIntegrityException,
        )

        user_data = UserBeanieCreateSchema(
            name="Nuevo Usuario",
            email="juan@example.com",  # Email duplicado
            age=30,
        )

        with pytest.raises(DatabaseIntegrityException):
            await service.create(user_data)

    @pytest.mark.asyncio
    async def test_create_success(self, init_db, service):
        """Test: Crear usuario exitosamente."""
        user_data = UserBeanieCreateSchema(
            name="Usuario Nuevo", email="nuevo@example.com", age=30
        )

        user = await service.create(user_data)

        assert user.id is not None
        assert user.email == "nuevo@example.com"

    @pytest.mark.asyncio
    async def test_list_with_search(self, init_db, service, sample_users):
        """Test: Listar con búsqueda usando search_fields del service."""
        users, total = await service.list(page=1, count=10, search="García")

        assert total == 1
        assert users[0].name == "María García"

    @pytest.mark.asyncio
    async def test_update_user(self, init_db, service, sample_users):
        """Test: Actualizar usuario a través del service."""
        user_id = str(sample_users[0].id)
        update_data = UserBeanieUpdateSchema(name="Nombre Actualizado")

        updated_user = await service.update(user_id, update_data)

        assert updated_user.name == "Nombre Actualizado"

    @pytest.mark.asyncio
    async def test_retrieve_not_found(self, init_db, service):
        """Test: Intentar obtener un usuario que no existe."""
        from fastapi_basekit.exceptions.api_exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.retrieve("507f1f77bcf86cd799439011")

    @pytest.mark.asyncio
    async def test_delete_user(self, init_db, service, sample_users):
        """Test: Eliminar usuario."""
        user_id = str(sample_users[0].id)

        await service.delete(user_id)

        # Verificar que ya no se puede obtener
        from fastapi_basekit.exceptions.api_exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.retrieve(user_id)


class TestBeanieCRUDIntegration:
    """Tests de integración completa del CRUD con Beanie."""

    @pytest.mark.asyncio
    async def test_full_crud_flow(self, init_db, service):
        """Test: Flujo completo de CRUD con MongoDB."""
        # 1. Crear
        user_data = UserBeanieCreateSchema(
            name="Usuario Test", email="test@example.com", age=30
        )
        created_user = await service.create(user_data)
        assert created_user.id is not None
        user_id = str(created_user.id)

        # 2. Obtener
        retrieved_user = await service.retrieve(user_id)
        assert retrieved_user.email == "test@example.com"

        # 3. Actualizar
        update_data = UserBeanieUpdateSchema(
            name="Usuario Actualizado", age=31
        )
        updated_user = await service.update(user_id, update_data)
        assert updated_user.name == "Usuario Actualizado"
        assert updated_user.age == 31

        # 4. Listar
        users, total = await service.list(page=1, count=10)
        assert total >= 1

        # 5. Eliminar
        await service.delete(user_id)

        # 6. Verificar eliminación
        from fastapi_basekit.exceptions.api_exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.retrieve(user_id)

    @pytest.mark.asyncio
    async def test_pagination_navigation(self, init_db, service, sample_users):
        """Test: Navegación por páginas en MongoDB."""
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
            [str(u.id) for u in users_p1]
            + [str(u.id) for u in users_p2]
            + [str(u.id) for u in users_p3]
        )
        assert len(all_user_ids) == len(set(all_user_ids))

    @pytest.mark.asyncio
    async def test_search_functionality(self, init_db, service, sample_users):
        """Test: Búsqueda por texto en MongoDB."""
        # Buscar por nombre
        users, total = await service.list(page=1, count=10, search="María")
        assert total == 1
        assert users[0].name == "María García"

        # Buscar por email
        users, total = await service.list(
            page=1, count=10, search="carlos@example.com"
        )
        assert total == 1
        assert users[0].email == "carlos@example.com"
