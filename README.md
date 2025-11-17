# 🚀 FastAPI BaseKit

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3.8+-blue?style=for-the-badge&logo=python)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?style=for-the-badge)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)

**Toolkit base para desarrollo rápido de APIs REST con FastAPI**

[Documentación](https://github.com/mundobien2025/fastapi-basekit) •
[Ejemplos](./examples) •
[Changelog](./CHANGELOG.md)

</div>

---

## ✨ Características

- 🎯 **CRUD Automático**: Controllers base con operaciones CRUD listas para usar
- 🔍 **Búsqueda Inteligente**: Búsqueda multi-campo con filtros dinámicos
- 📊 **Paginación Avanzada**: Paginación automática con metadata completa
- 🔗 **Relaciones Optimizadas**: Joins dinámicos para evitar queries N+1 (SQLAlchemy)
- 🎨 **Type-Safe**: Type hints completos para mejor DX
- 🧪 **Testeable**: Diseño que facilita testing
- 🗃️ **Multi-DB**: Controllers separados para SQLAlchemy y Beanie (MongoDB)
- 🔒 **Permisos**: Sistema de permisos basado en clases
- ⚡ **Performance**: Queries optimizados y lazy loading
- 📝 **Validación**: Validación automática con Pydantic
- 🔧 **Queryset Personalizable**: Personaliza queries sin reescribir métodos

---

## 📦 Instalación

```bash
# Instalación básica
pip install fastapi-basekit

# Con soporte SQLAlchemy (PostgreSQL, MySQL, etc.)
pip install fastapi-basekit[sqlalchemy]

# Con soporte Beanie (MongoDB)
pip install fastapi-basekit[beanie]

# Con todo
pip install fastapi-basekit[all]
```

---

## 🚀 Inicio Rápido

### Ejemplo Simple: CRUD Básico

#### 1. Modelo (SQLAlchemy)

```python
# models/user.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    age = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
```

#### 2. Schema (Pydantic)

```python
# schemas/user.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserSchema(BaseModel):
    id: int
    name: str
    email: EmailStr
    age: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserCreateSchema(BaseModel):
    name: str
    email: EmailStr
    age: Optional[int] = None
    is_active: bool = True
```

#### 3. Repository

```python
# repositories/user.py
from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from models.user import User

class UserRepository(BaseRepository):
    model = User
```

#### 4. Service

```python
# services/user.py
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService

class UserService(BaseService):
    # Campos por los que se puede buscar
    search_fields = ["name", "email"]

    # Campos que deben ser únicos al crear
    duplicate_check_fields = ["email"]
```

#### 5. Controller

```python
# controllers/user.py
from typing import Optional
from fastapi import APIRouter, Query, Depends, Request
from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from schemas.user import UserSchema, UserCreateSchema, UserUpdateSchema
from services.user import UserService
from repositories.user import UserRepository

router = APIRouter(prefix="/users", tags=["users"])

def get_user_service(request: Request) -> UserService:
    repository = UserRepository(db=request.state.db)
    return UserService(repository=repository, request=request)

@router.get("/")
class ListUsers(SQLAlchemyBaseController):
    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
        is_active: Optional[bool] = Query(None),
    ):
        return await self.list()

@router.get("/{id}")
class GetUser(SQLAlchemyBaseController):
    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, id: int):
        return await self.retrieve(str(id))

@router.post("/", status_code=201)
class CreateUser(SQLAlchemyBaseController):
    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, data: UserCreateSchema):
        return await self.create(data)

@router.put("/{id}")
class UpdateUser(SQLAlchemyBaseController):
    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, id: int, data: UserUpdateSchema):
        return await self.update(str(id), data)

@router.delete("/{id}")
class DeleteUser(SQLAlchemyBaseController):
    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    async def __call__(self, id: int):
        return await self.delete(str(id))
```

#### 6. ¡Listo! 🎉

Ya tienes un CRUD completo con:

- ✅ Paginación automática
- ✅ Búsqueda por nombre o email
- ✅ Filtrado por `is_active`
- ✅ Validación de duplicados
- ✅ Type hints completos

---

## 📚 Ejemplos Avanzados

### Ejemplo 1: Queryset Personalizado con Agregaciones

**Caso de uso**: Listar usuarios con COUNT de referidos y SUM de órdenes sin reescribir `list()`.

```python
# services/user.py
from sqlalchemy import Select, func, select
from sqlalchemy.orm import aliased
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
from models.user import User, Referral, Order

class UserService(BaseService):
    search_fields = ["name", "email"]
    duplicate_check_fields = ["email"]

    def build_queryset(self) -> Select:
        """
        Personaliza el queryset base para incluir agregaciones.
        Este método se ejecuta ANTES de aplicar filtros.
        """
        referral_alias = aliased(Referral)
        order_alias = aliased(Order)

        query = (
            select(
                User,
                func.count(func.distinct(referral_alias.id)).label("referidos_count"),
                func.count(func.distinct(order_alias.id)).label("total_orders"),
                func.coalesce(func.sum(order_alias.total), 0).label("total_spent"),
            )
            .outerjoin(referral_alias, User.id == referral_alias.user_id)
            .outerjoin(order_alias, User.id == order_alias.user_id)
            .group_by(User.id)
        )
        return query
```

**Schema con agregaciones**:

```python
# schemas/user.py
class UserWithStatsSchema(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime
    referidos_count: int
    total_orders: Optional[int] = None
    total_spent: Optional[int] = None  # En centavos

    class Config:
        from_attributes = True
```

**Controller** (sin cambios en `list()`):

```python
@router.get("/")
class ListUsersWithStats(SQLAlchemyBaseController):
    schema_class = UserWithStatsSchema
    service: UserService = Depends(get_user_service)

    async def __call__(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
    ):
        # El queryset personalizado se aplica automáticamente
        return await self.list(search=search)
```

**Resultado**:

```json
{
  "data": [
    {
      "id": 1,
      "name": "Juan Pérez",
      "email": "juan@example.com",
      "created_at": "2024-01-01T00:00:00",
      "referidos_count": 5,
      "total_orders": 12,
      "total_spent": 150000
    }
  ],
  "pagination": { ... }
}
```

### Ejemplo 2: Joins Dinámicos con Relaciones

**Caso de uso**: Cargar relaciones automáticamente para evitar queries N+1.

```python
# services/user.py
class UserService(BaseService):
    search_fields = ["name", "email"]
    duplicate_check_fields = ["email"]

    def get_kwargs_query(self) -> dict:
        """
        Define joins según la acción.
        En 'list' y 'retrieve' carga automáticamente las relaciones.
        """
        if self.action in ["list", "retrieve"]:
            return {"joins": ["role", "roles"]}
        return {}
```

**Modelo con relaciones**:

```python
# models/user.py
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100), unique=True)
    role_id = Column(Integer, ForeignKey("roles.id"))

    # Relación uno a muchos
    role = relationship("Role", foreign_keys=[role_id])

    # Relación muchos a muchos
    roles = relationship("Role", secondary=user_roles, back_populates="users")
```

**Controller**:

```python
@router.get("/")
class ListUsers(SQLAlchemyBaseController):
    schema_class = UserSchema  # Incluye role y roles
    service: UserService = Depends(get_user_service)

    async def __call__(self, ...):
        # Los joins se aplican automáticamente desde get_kwargs_query()
        return await self.list()
```

### Ejemplo 3: Sistema de Permisos

**Caso de uso**: Control de acceso basado en roles y propiedad.

```python
# permissions/user.py
from fastapi_basekit.aio.permissions.base import BasePermission

class IsAdmin(BasePermission):
    message_exception = "Solo administradores pueden realizar esta acción"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return getattr(user, "is_admin", False) if user else False

class IsOwnerOrAdmin(BasePermission):
    message_exception = "Solo el propietario o un administrador puede realizar esta acción"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if not user:
            return False

        resource_id = request.path_params.get("id")
        if getattr(user, "is_admin", False):
            return True

        return str(user.id) == str(resource_id)
```

**Controller con permisos**:

```python
@router.get("/{id}")
class GetUser(SQLAlchemyBaseController):
    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    def check_permissions(self) -> List[Type[BasePermission]]:
        return [IsOwnerOrAdmin]

    async def __call__(self, id: int):
        return await self.retrieve(str(id))

@router.post("/", status_code=201)
class CreateUser(SQLAlchemyBaseController):
    schema_class = UserSchema
    service: UserService = Depends(get_user_service)

    def check_permissions(self) -> List[Type[BasePermission]]:
        return [IsAdmin]  # Solo admins pueden crear

    async def __call__(self, data: UserCreateSchema):
        return await self.create(data)
```

### Ejemplo 4: Filtros Personalizados

**Caso de uso**: Transformar filtros antes de aplicarlos.

```python
# services/user.py
class UserService(BaseService):
    search_fields = ["name", "email"]
    duplicate_check_fields = ["email"]

    def get_filters(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Transforma filtros antes de aplicarlos.
        Ejemplo: convertir age_min en filtro de edad.
        """
        applied = filters or {}

        # Si viene age_min, lo convertimos en filtro de edad
        if "age_min" in applied:
            age_min = applied.pop("age_min")
            # Aquí podrías agregar lógica adicional
            # Por ejemplo, aplicar filtro de edad mínima

        return applied
```

---

## 📖 Uso de la API

### Listar con Filtros y Paginación

```bash
# Página 1, 10 items
GET /users?page=1&count=10

# Buscar usuarios
GET /users?search=john

# Filtrar activos
GET /users?is_active=true

# Combinar filtros
GET /users?search=john&is_active=true&page=1&count=10
```

**Respuesta**:

```json
{
  "data": [
    {
      "id": 1,
      "name": "John Doe",
      "email": "john@example.com",
      "age": 30,
      "is_active": true,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": null
    }
  ],
  "pagination": {
    "page": 1,
    "count": 10,
    "total": 100,
    "total_pages": 10
  },
  "message": "Operación exitosa",
  "status": "success"
}
```

### Crear Usuario

```bash
POST /users
Content-Type: application/json

{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "age": 25,
  "is_active": true
}
```

**Respuesta**:

```json
{
  "data": {
    "id": 2,
    "name": "Jane Doe",
    "email": "jane@example.com",
    "age": 25,
    "is_active": true,
    "created_at": "2024-01-02T00:00:00",
    "updated_at": null
  },
  "message": "Creado exitosamente",
  "status": "success"
}
```

---

## 🎯 Características Avanzadas

### build_queryset(): Personalización de Queries

El método `build_queryset()` permite personalizar el query base **antes** de aplicar filtros, búsqueda y paginación. Esto es útil para:

- Agregar JOINs complejos
- Incluir agregaciones (COUNT, SUM, AVG)
- Aplicar GROUP BY
- Seleccionar campos calculados
- Optimizar queries específicas

**Ventajas**:

- ✅ No necesitas reescribir `list()`
- ✅ Los filtros se aplican automáticamente sobre tu query personalizado
- ✅ Mantiene toda la funcionalidad de paginación y búsqueda

### get_kwargs_query(): Configuración Dinámica

Permite definir configuración de queries según la acción:

```python
def get_kwargs_query(self) -> dict:
    if self.action == "list":
        return {"joins": ["role", "profile"]}
    elif self.action == "retrieve":
        return {"joins": ["role", "profile", "orders"]}
    return {}
```

### get_filters(): Transformación de Filtros

Transforma o valida filtros antes de aplicarlos:

```python
def get_filters(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    applied = filters or {}

    # Validar o transformar filtros
    if "date_from" in applied:
        # Convertir formato de fecha, etc.
        pass

    return applied
```

---

## 📁 Estructura de Ejemplos

El proyecto incluye ejemplos completos en la carpeta `examples/`:

```
examples/
├── simple_crud/          # CRUD básico
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py
│   └── controller.py
│
├── advanced_queryset/    # Queryset personalizado con agregaciones
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py        # build_queryset() con COUNT y SUM
│   └── controller.py
│
├── with_relations/       # Relaciones y joins dinámicos
│   ├── models.py
│   ├── schemas.py
│   ├── repository.py
│   ├── service.py        # get_kwargs_query() con joins
│   └── controller.py
│
└── with_permissions/     # Sistema de permisos
    ├── models.py
    ├── schemas.py
    ├── repository.py
    ├── service.py
    ├── permissions.py    # Permisos personalizados
    └── controller.py
```

---

## 🔧 Configuración

### Variables de Entorno

```bash
# .env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
FASTAPI_BASEKIT_DEFAULT_PAGE_SIZE=25
FASTAPI_BASEKIT_MAX_PAGE_SIZE=200
```

### Setup de Base de Datos

```python
# database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/dbname")
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session_maker() as session:
        yield session
```

### Middleware para DB

```python
# main.py
from fastapi import FastAPI, Request
from database import get_db

app = FastAPI()

@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    async for session in get_db():
        request.state.db = session
        response = await call_next(request)
        await session.commit()
        return response
```

---

## 🧪 Testing

```python
# tests/test_user_controller.py
import pytest
from fastapi.testclient import TestClient

def test_list_users(client: TestClient):
    response = client.get("/users?page=1&count=10")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "pagination" in data
    assert data["pagination"]["page"] == 1

def test_create_user(client: TestClient):
    user_data = {
        "name": "Test User",
        "email": "test@example.com"
    }
    response = client.post("/users", json=user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["data"]["name"] == "Test User"
```

---

## 📊 Arquitectura

```
┌─────────────┐
│   Client    │
└─────┬───────┘
      │ HTTP Request
      ▼
┌─────────────────┐
│   Controller    │  ← Validación, permisos, formato de respuesta
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Service      │  ← Lógica de negocio, build_queryset(), get_filters()
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Repository    │  ← Acceso a datos, queries optimizados
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Database     │
└─────────────────┘
```

---

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Por favor lee [CONTRIBUTING.md](./CONTRIBUTING.md) para detalles.

### Desarrollo Local

```bash
# Clonar
git clone https://github.com/mundobien2025/fastapi-basekit.git
cd fastapi-basekit

# Instalar dependencias
pip install -e ".[dev]"

# Ejecutar tests
pytest

# Linting
black fastapi_basekit
flake8 fastapi_basekit
mypy fastapi_basekit
```

---

## 📄 Licencia

Este proyecto está licenciado bajo la licencia MIT - ver [LICENSE](./LICENSE) para detalles.

---

## 🙏 Agradecimientos

- [FastAPI](https://fastapi.tiangolo.com/) - El framework web moderno y rápido
- [SQLAlchemy](https://www.sqlalchemy.org/) - El ORM SQL para Python
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Validación de datos usando Python type hints

---

## 📞 Soporte

- 📖 [Documentación](https://github.com/mundobien2025/fastapi-basekit)
- 🐛 [Issues](https://github.com/mundobien2025/fastapi-basekit/issues)
- 💬 [Discussions](https://github.com/mundobien2025/fastapi-basekit/discussions)

---

<div align="center">

**Hecho con ❤️ para la comunidad FastAPI**

⭐ Si te gusta este proyecto, dale una estrella en GitHub

</div>
