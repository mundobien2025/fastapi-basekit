"""Tests unitarios que simulan llamadas de API reales con permisos."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, Request, Depends
from fastapi.testclient import TestClient
from httpx import AsyncClient as HTTPXAsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi_basekit.aio.sqlalchemy.controller.base import (
    SQLAlchemyBaseController,
)
from fastapi_basekit.aio.permissions.base import BasePermission
from fastapi_basekit.exceptions.api_exceptions import PermissionException

from example_crud.models import Base
from example_crud.repository import UserRepository
from example_crud.service import UserService
from example_crud.schemas import UserSchema


DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# Mock de permisos para testing
class MockPermission(BasePermission):
    """Permiso mock para testing."""

    def __init__(self, should_allow: bool = True):
        self.should_allow = should_allow
        self.message_exception = "Permiso denegado"

    async def has_permission(self, request: Request) -> bool:
        return self.should_allow


class IsAuthenticated(BasePermission):
    """Permiso de autenticación mock."""

    message_exception = "Usuario no autenticado"

    async def has_permission(self, request: Request) -> bool:
        return (
            hasattr(request.state, "user") and request.state.user is not None
        )


class IsAdmin(BasePermission):
    """Permiso de administrador mock."""

    message_exception = "Solo administradores"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return user and getattr(user, "is_admin", False)


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
def mock_request():
    """Crea un mock de Request de FastAPI."""
    request = MagicMock(spec=Request)
    request.scope = {}
    request.query_params = {}
    request.state = MagicMock()
    return request


@pytest.fixture
async def repository(async_session):
    """Crea una instancia del repository con sesión de test."""
    return UserRepository(db=async_session)


@pytest.fixture
async def service(repository, mock_request):
    """Crea una instancia del service con repository de test."""
    return UserService(repository=repository, request=mock_request)


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
    ]

    created_users = []
    for user_data in users_data:
        user = await repository.create(user_data)
        created_users.append(user)
        await repository.session.commit()

    return created_users


class TestControllerAutoPermissions:
    """Tests para verificar que los permisos se ejecutan automáticamente."""

    @pytest.mark.asyncio
    async def test_prepare_action_sets_action(self, repository, mock_request):
        """Test: prepare_action() configura correctamente la acción."""
        service = UserService(repository=repository, request=mock_request)

        class TestController(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = service

        controller = TestController()
        controller.request = mock_request

        # Verificar que prepare_action configura la acción
        await controller.prepare_action("list")
        assert controller.action == "list"

        # Verificar que el método list es callable
        list_method = getattr(controller, "list")
        assert callable(list_method)

    @pytest.mark.asyncio
    async def test_prepare_action_executes_automatically(
        self, repository, mock_request, sample_users
    ):
        """Test: prepare_action() se ejecuta automáticamente."""
        mock_request.query_params = {"page": "1", "count": "10"}

        service = UserService(repository=repository, request=mock_request)

        class TestController(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = service

        controller = TestController()
        controller.request = mock_request

        # Verificar que el método list es callable
        list_method = getattr(controller, "list")
        assert callable(list_method)

        # Mock para verificar que prepare_action se llama
        with patch.object(
            controller, "prepare_action", new_callable=AsyncMock
        ) as mock_prepare_action:

            # Simular llamada al método list
            # prepare_action se ejecuta automáticamente al inicio
            await controller.list()

            # Verificar que prepare_action se ejecutó
            mock_prepare_action.assert_called_once_with("list")

    @pytest.mark.asyncio
    async def test_permissions_check_automatically(
        self, repository, mock_request
    ):
        """Test: Los permisos se verifican automáticamente."""
        endpoint_mock = MagicMock()
        endpoint_mock.__name__ = "list"
        mock_request.scope = {"endpoint": endpoint_mock}
        mock_request.query_params = {}

        service = UserService(repository=repository, request=mock_request)

        class TestController(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = service
            permission_classes = [MockPermission]

        controller = TestController()
        controller.request = mock_request

        # Mock para verificar que check_permissions se llama
        with patch.object(
            controller, "check_permissions", new_callable=AsyncMock
        ) as mock_check_permissions:

            # Simular llamada
            await controller.list()

            # Verificar que check_permissions se ejecutó
            mock_check_permissions.assert_called_once()

    @pytest.mark.asyncio
    async def test_permission_denied_raises_exception(
        self, repository, mock_request
    ):
        """Test: Si el permiso falla, se lanza excepción."""
        endpoint_mock = MagicMock()
        endpoint_mock.__name__ = "list"
        mock_request.scope = {"endpoint": endpoint_mock}
        mock_request.query_params = {}

        service = UserService(repository=repository, request=mock_request)

        class DeniedPermission(BasePermission):
            message_exception = "Acceso denegado"

            async def has_permission(self, request: Request) -> bool:
                return False

        class TestController(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = service
            permission_classes = [DeniedPermission]

        controller = TestController()
        controller.request = mock_request

        # Verificar que se lanza excepción cuando el permiso falla
        with pytest.raises(PermissionException, match="Acceso denegado"):
            await controller.list()

    @pytest.mark.asyncio
    async def test_custom_method_auto_permissions(
        self, repository, mock_request
    ):
        """Test: Métodos personalizados también ejecutan _before_action()."""
        endpoint_mock = MagicMock()
        endpoint_mock.__name__ = "custom_action"
        mock_request.scope = {"endpoint": endpoint_mock}

        service = UserService(repository=repository, request=mock_request)

        class TestController(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = service
            permission_classes = [IsAuthenticated]

            async def custom_action(self):
                # Los métodos personalizados deben llamar a prepare_action
                await self.prepare_action("custom_action")
                return self.format_response(data={"custom": "data"})

        controller = TestController()
        controller.request = mock_request

        # Verificar que el método es callable
        custom_method = getattr(controller, "custom_action")
        assert callable(custom_method)

        # Mock para verificar que check_permissions se llama
        with patch.object(
            controller, "check_permissions", new_callable=AsyncMock
        ) as mock_check_permissions:

            # Simular llamada al método personalizado
            result = await controller.custom_action()

            # Verificar que check_permissions se ejecutó
            mock_check_permissions.assert_called_once()

            # Verificar que el método se ejecutó correctamente
            assert result.data == {"custom": "data"}


class TestControllerWithFastAPITestClient:
    """Tests usando TestClient de FastAPI para simular requests HTTP reales."""

    @pytest.fixture
    def app(self, async_session):
        """Crea una app FastAPI para tests."""
        app = FastAPI()

        def get_user_service(request: Request):
            repository = UserRepository(db=async_session)
            return UserService(repository=repository, request=request)

        @app.get("/users/")
        class ListUsers(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = Depends(get_user_service)

        @app.get("/users/{id}")
        class GetUser(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = Depends(get_user_service)

        @app.post("/users/")
        class CreateUser(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = Depends(get_user_service)

        return app

    @pytest.mark.asyncio
    async def test_list_endpoint_with_auto_permissions(
        self, app, sample_users
    ):
        """Test: Endpoint GET /users/ ejecuta permisos automáticamente."""
        # Mock para verificar que prepare_action se llama
        call_count = {"count": 0}

        original_prepare_action = SQLAlchemyBaseController.prepare_action

        async def tracked_prepare_action(self, action_name):
            call_count["count"] += 1
            return await original_prepare_action(self, action_name)

        with patch.object(
            SQLAlchemyBaseController,
            "prepare_action",
            tracked_prepare_action,
        ):
            # Ejecutar request HTTP real
            with TestClient(app) as client:
                response = client.get("/users/?page=1&count=10")

            # Verificar que prepare_action se ejecutó
            assert call_count["count"] > 0
            assert response.status_code == 200
            assert "data" in response.json()

    @pytest.mark.asyncio
    async def test_retrieve_endpoint_with_auto_permissions(
        self, app, sample_users
    ):
        """Test: Endpoint GET /users/{id} ejecuta permisos automáticamente."""
        user_id = sample_users[0].id

        call_count = {"count": 0}
        original_prepare_action = SQLAlchemyBaseController.prepare_action

        async def tracked_prepare_action(self, action_name):
            call_count["count"] += 1
            return await original_prepare_action(self, action_name)

        with patch.object(
            SQLAlchemyBaseController,
            "prepare_action",
            tracked_prepare_action,
        ):
            with TestClient(app) as client:
                response = client.get(f"/users/{user_id}")

            assert call_count["count"] > 0
            assert response.status_code == 200
            assert "data" in response.json()

    @pytest.mark.asyncio
    async def test_create_endpoint_with_auto_permissions(self, app):
        """Test: Endpoint POST /users/ ejecuta permisos automáticamente."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "age": 25,
            "is_active": True,
        }

        call_count = {"count": 0}
        original_prepare_action = SQLAlchemyBaseController.prepare_action

        async def tracked_prepare_action(self, action_name):
            call_count["count"] += 1
            return await original_prepare_action(self, action_name)

        with patch.object(
            SQLAlchemyBaseController,
            "prepare_action",
            tracked_prepare_action,
        ):
            with TestClient(app) as client:
                response = client.post("/users/", json=user_data)

            assert call_count["count"] > 0
            assert response.status_code == 200
            assert "data" in response.json()

    @pytest.mark.asyncio
    async def test_permission_classes_applied_to_all_endpoints(
        self, app, sample_users
    ):
        """Test: permission_classes se aplica a todos los endpoints."""
        call_count = {"count": 0}
        original_check_permissions = SQLAlchemyBaseController.check_permissions

        async def tracked_check_permissions(self):
            call_count["count"] += 1
            return await original_check_permissions(self)

        with patch.object(
            SQLAlchemyBaseController,
            "check_permissions",
            tracked_check_permissions,
        ):
            with TestClient(app) as client:
                # Test list
                response = client.get("/users/?page=1&count=10")
                assert response.status_code == 200

                # Test retrieve
                user_id = sample_users[0].id
                response = client.get(f"/users/{user_id}")
                assert response.status_code == 200

                # Test create
                user_data = {
                    "name": "New User",
                    "email": "new@example.com",
                }
                response = client.post("/users/", json=user_data)
                assert response.status_code == 200

            # Verificar que check_permissions se llamó para cada endpoint
            assert call_count["count"] >= 3


class TestControllerCustomPermissions:
    """Tests para permisos personalizados por acción."""

    @pytest.mark.asyncio
    async def test_custom_permissions_by_action(
        self, repository, mock_request
    ):
        """Test: Permisos personalizados según la acción."""
        mock_request.scope = {"endpoint": MagicMock(__name__="list")}
        mock_request.query_params = {}

        service = UserService(repository=repository, request=mock_request)

        class TestController(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = service
            permission_classes = [IsAuthenticated]

            def get_permissions(self):
                if self.action == "list":
                    return [IsAuthenticated]
                elif self.action == "create":
                    return [IsAdmin]
                return []

        controller = TestController()
        controller.request = mock_request
        controller.action = "list"

        # Verificar que get_permissions retorna los permisos correctos
        permissions = controller.get_permissions()
        assert len(permissions) == 1
        assert permissions[0] == IsAuthenticated

    @pytest.mark.asyncio
    async def test_permission_class_default_applied(
        self, repository, mock_request
    ):
        """Test: permission_classes se aplica por defecto."""
        endpoint_mock = MagicMock()
        endpoint_mock.__name__ = "list"
        mock_request.scope = {"endpoint": endpoint_mock}

        service = UserService(repository=repository, request=mock_request)

        class TestController(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = service
            permission_classes = [IsAuthenticated]

        controller = TestController()
        controller.request = mock_request

        # Verificar que permission_classes se incluye automáticamente
        permissions = controller.get_permissions()
        assert len(permissions) == 1
        assert permissions[0] == IsAuthenticated

    @pytest.mark.asyncio
    async def test_multiple_methods_call_prepare_action(
        self, repository, mock_request
    ):
        """Test: Múltiples métodos deben llamar prepare_action."""
        service = UserService(repository=repository, request=mock_request)

        class TestController(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = service

            async def method1(self):
                await self.prepare_action("method1")
                return self.format_response(data={"method": "1"})

            async def method2(self):
                await self.prepare_action("method2")
                return self.format_response(data={"method": "2"})

        # Test method1
        controller1 = TestController()
        controller1.request = mock_request

        with patch.object(
            controller1, "check_permissions", new_callable=AsyncMock
        ) as mock_check:
            result = await controller1.method1()
            mock_check.assert_called_once()
            assert result.data == {"method": "1"}

        # Test method2
        controller2 = TestController()
        controller2.request = mock_request

        with patch.object(
            controller2, "check_permissions", new_callable=AsyncMock
        ) as mock_check:
            result = await controller2.method2()
            mock_check.assert_called_once()
            assert result.data == {"method": "2"}

    @pytest.mark.asyncio
    async def test_real_api_flow_with_permissions(
        self, repository, mock_request, sample_users
    ):
        """Test: Flujo completo de API con permisos automáticos."""
        endpoint_mock = MagicMock()
        endpoint_mock.__name__ = "list"
        mock_request.scope = {"endpoint": endpoint_mock}
        mock_request.query_params = {"page": "1", "count": "10"}

        service = UserService(repository=repository, request=mock_request)

        class TestController(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = service
            permission_classes = [IsAuthenticated]

        controller = TestController()
        controller.request = mock_request

        # Simular usuario autenticado
        mock_user = MagicMock()
        mock_user.is_admin = False
        mock_request.state.user = mock_user

        # Ejecutar el flujo completo
        result = await controller.list()

        # Verificar que se ejecutó correctamente
        assert result is not None
        assert hasattr(result, "data")
        assert hasattr(result, "pagination")

    @pytest.mark.asyncio
    async def test_permission_class_none_no_check(
        self, repository, mock_request
    ):
        """Test: Si permission_class es None, no se verifica."""
        endpoint_mock = MagicMock()
        endpoint_mock.__name__ = "list"
        mock_request.scope = {"endpoint": endpoint_mock}
        mock_request.query_params = {}

        service = UserService(repository=repository, request=mock_request)

        class TestController(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = service
            permission_classes = []  # Sin permisos

        controller = TestController()
        controller.request = mock_request

        # Verificar que get_permissions retorna lista vacía
        permissions = controller.get_permissions()
        assert len(permissions) == 0

        # El método debería ejecutarse sin problemas
        # (aunque no hay datos, no debería lanzar excepción de permisos)
        try:
            await controller.list()
        except PermissionException:
            pytest.fail(
                "No debería lanzar PermissionException si no hay permisos"
            )


class TestControllerRealAPIRequests:
    """Tests que simulan requests HTTP reales usando AsyncClient."""

    @pytest.fixture
    async def app(self, async_session):
        """Crea una app FastAPI para tests async."""
        app = FastAPI()

        def get_user_service(request: Request):
            repository = UserRepository(db=async_session)
            return UserService(repository=repository, request=request)

        @app.get("/users/")
        class ListUsers(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = Depends(get_user_service)

        @app.get("/users/{id}")
        class GetUser(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = Depends(get_user_service)

        @app.post("/users/")
        class CreateUser(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = Depends(get_user_service)

        @app.put("/users/{id}")
        class UpdateUser(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = Depends(get_user_service)

        @app.delete("/users/{id}")
        class DeleteUser(SQLAlchemyBaseController):
            schema_class = UserSchema
            service = Depends(get_user_service)

        return app

    @pytest.mark.asyncio
    async def test_real_http_get_list(self, app, sample_users):
        """Test: Request HTTP GET real a /users/."""
        async with HTTPXAsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/users/?page=1&count=10")

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert "pagination" in data
            assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_real_http_get_retrieve(self, app, sample_users):
        """Test: Request HTTP GET real a /users/{id}."""
        user_id = sample_users[0].id

        async with HTTPXAsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/users/{user_id}")

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert data["data"]["id"] == user_id

    @pytest.mark.asyncio
    async def test_real_http_post_create(self, app):
        """Test: Request HTTP POST real a /users/."""
        user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "age": 25,
            "is_active": True,
        }

        async with HTTPXAsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/users/", json=user_data)

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert data["data"]["name"] == "Test User"
            assert data["data"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_real_http_put_update(self, app, sample_users):
        """Test: Request HTTP PUT real a /users/{id}."""
        user_id = sample_users[0].id
        update_data = {"name": "Updated Name"}

        async with HTTPXAsyncClient(app=app, base_url="http://test") as client:
            response = await client.put(f"/users/{user_id}", json=update_data)

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert data["data"]["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_real_http_delete(self, app, sample_users):
        """Test: Request HTTP DELETE real a /users/{id}."""
        user_id = sample_users[0].id

        async with HTTPXAsyncClient(app=app, base_url="http://test") as client:
            response = await client.delete(f"/users/{user_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Eliminado exitosamente"

    @pytest.mark.asyncio
    async def test_permissions_executed_on_all_http_methods(
        self, app, sample_users
    ):
        """Test: Los permisos se ejecutan en todos los métodos HTTP."""
        call_count = {"count": 0}
        original_check_permissions = SQLAlchemyBaseController.check_permissions

        async def tracked_check_permissions(self):
            call_count["count"] += 1
            return await original_check_permissions(self)

        with patch.object(
            SQLAlchemyBaseController,
            "check_permissions",
            tracked_check_permissions,
        ):
            async with HTTPXAsyncClient(
                app=app, base_url="http://test"
            ) as client:
                # GET list
                await client.get("/users/?page=1&count=10")

                # GET retrieve
                user_id = sample_users[0].id
                await client.get(f"/users/{user_id}")

                # POST create
                await client.post(
                    "/users/",
                    json={"name": "New", "email": "new@example.com"},
                )

            # Verificar que check_permissions se ejecutó para cada request
            assert call_count["count"] >= 3
