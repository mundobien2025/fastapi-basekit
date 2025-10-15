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
[Changelog](./CHANGELOG.md) •
[Contribuir](./CONTRIBUTING.md)

</div>

---

## ✨ Características

- 🎯 **CRUD Automático**: Controllers base con operaciones CRUD listas para usar
- 🔍 **Búsqueda Inteligente**: Búsqueda multi-campo con filtros dinámicos
- 📊 **Paginación Avanzada**: Paginación automática con `has_next`, `has_prev`
- 🔗 **Relaciones Optimizadas**: Joins dinámicos para evitar queries N+1 (SQLAlchemy)
- 🎨 **Type-Safe**: Type hints completos para mejor DX
- 🧪 **Testeable**: Diseño que facilita testing
- 🗃️ **Multi-DB**: Controllers separados para SQLAlchemy y Beanie (MongoDB)
- 🔒 **Permisos**: Sistema de permisos basado en clases
- ⚡ **Performance**: Queries optimizados y lazy loading
- 📝 **Validación**: Validación automática con Pydantic

> 🆕 **v0.1.16+**: Controllers base ahora están completamente separados por ORM/ODM. Ver [CONTROLLERS_GUIDE.md](./CONTROLLERS_GUIDE.md) para detalles.

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

## 🎯 Controllers Separados por ORM/ODM

A partir de la **v0.1.16**, los controllers están completamente separados:

### 🐘 SQLAlchemy (PostgreSQL, MySQL, etc.)

```python
from fastapi_basekit.aio.sqlalchemy import SQLAlchemyBaseController

class UserController(SQLAlchemyBaseController):
    # Soporte para JOINs, ORDER BY, operador OR
    pass
```

### 🍃 Beanie (MongoDB)

```python
from fastapi_basekit.aio.beanie import BeanieBaseController

class UserController(BeanieBaseController):
    # Optimizado para documentos MongoDB
    pass
```

📖 **Guía completa**: Ver [CONTROLLERS_GUIDE.md](./CONTROLLERS_GUIDE.md) para ejemplos detallados y diferencias.

---

## 🚀 Inicio Rápido

### 1. Modelo (SQLAlchemy)

```python
# models/user.py
from sqlalchemy import Column, String, Boolean
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
```

### 2. Schema (Pydantic)

```python
# schemas/user.py
from pydantic import BaseModel, EmailStr

class UserSchema(BaseModel):
    id: str
    name: str
    email: EmailStr
    is_active: bool

class UserCreateSchema(BaseModel):
    name: str
    email: EmailStr
```

### 3. Repository

```python
# repositories/user.py
from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from models.user import User

class UserRepository(BaseRepository):
    model = User
```

### 4. Service

```python
# services/user.py
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService

class UserService(BaseService):
    search_fields = ["name", "email"]
    duplicate_check_fields = ["email"]
```

### 5. Controller

```python
# controllers/user.py
from fastapi import APIRouter, Query, Depends
from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from schemas.user import UserSchema, UserCreateSchema
from services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
class ListUsers(SQLAlchemyBaseController):
    schema_class = UserSchema
    service = Depends(UserService)

    async def __call__(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: str = Query(None),
        is_active: bool = Query(None),
        order_by: str = Query(None),
    ):
        return await self.list()

@router.get("/{id}")
class GetUser(SQLAlchemyBaseController):
    schema_class = UserSchema
    service = Depends(UserService)

    async def __call__(self, id: str):
        return await self.retrieve(id)

@router.post("/")
class CreateUser(SQLAlchemyBaseController):
    schema_class = UserSchema
    service = Depends(UserService)

    async def __call__(self, data: UserCreateSchema):
        return await self.create(data)
```

### 6. ¡Listo! 🎉

Ya tienes un CRUD completo con:

✅ Paginación automática  
✅ Búsqueda por nombre o email  
✅ Filtrado por `is_active`  
✅ Ordenamiento configurable  
✅ Validación de duplicados  
✅ Type hints completos

---

## 📚 Ejemplos de Uso

### Listar con Filtros y Paginación

```bash
# Página 1, 10 items
GET /users?page=1&count=10

# Buscar usuarios
GET /users?search=john

# Filtrar activos
GET /users?is_active=true

# Ordenar por nombre
GET /users?order_by=name&order_direction=asc

# Combinar filtros
GET /users?search=john&is_active=true&order_by=created_at&order_direction=desc
```

**Respuesta:**

```json
{
  "data": [
    {
      "id": "123",
      "name": "John Doe",
      "email": "john@example.com",
      "is_active": true
    }
  ],
  "pagination": {
    "page": 1,
    "count": 10,
    "total": 100,
    "pages": 10,
    "total_pages": 10,
    "has_next": true,
    "has_prev": false,
    "next_page": 2,
    "prev_page": null
  },
  "message": "Operación exitosa",
  "status": "success"
}
```

### Obtener un Usuario

```bash
GET /users/123
```

**Respuesta:**

```json
{
  "data": {
    "id": "123",
    "name": "John Doe",
    "email": "john@example.com",
    "is_active": true
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
  "email": "jane@example.com"
}
```

**Respuesta:**

```json
{
  "data": {
    "id": "124",
    "name": "Jane Doe",
    "email": "jane@example.com",
    "is_active": true
  },
  "message": "Creado exitosamente",
  "status": "success"
}
```

---

## 🎯 Características Avanzadas

### Relaciones y Joins

```python
# models/user.py
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String)
    role_id = Column(String, ForeignKey("roles.id"))

    # Relación
    role = relationship("Role", back_populates="users")

# controller
@router.get("/")
async def list_users(
    self,
    include_role: bool = Query(False),
):
    # Si include_role=true, carga la relación automáticamente
    if include_role:
        self.service.kwargs_query = {"joins": ["role"]}
    return await self.list()
```

### Permisos Personalizados

```python
from fastapi_basekit.aio.permissions.base import BasePermission

class IsAdmin(BasePermission):
    message_exception = "Solo administradores pueden acceder"

    async def has_permission(self, request: Request) -> bool:
        user = request.state.user
        return user.is_admin

class UserController(SQLAlchemyBaseController):
    schema_class = UserSchema
    service = Depends(UserService)

    def check_permissions(self) -> List[Type[BasePermission]]:
        if self.action in ["create", "delete"]:
            return [IsAdmin]
        return []
```

### Soft Deletes

```python
# models/user.py
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String)
    deleted_at = Column(DateTime, nullable=True)

# repository
class UserRepository(BaseRepository):
    model = User
    enable_soft_delete = True

# controller
@router.delete("/{id}")
async def delete_user(self, id: str, hard: bool = False):
    """
    Soft delete por defecto.
    hard=true para eliminación física.
    """
    await self.service.delete(id, hard_delete=hard)
    return self.format_response(None, message="Usuario eliminado")
```

### Validación de Duplicados

```python
class UserService(BaseService):
    # Validar que email sea único antes de crear
    duplicate_check_fields = ["email"]

# Intento de crear usuario con email duplicado
# → DatabaseIntegrityException: "Registro ya existe"
```

---

## 🔧 Configuración

```python
# main.py
from fastapi import FastAPI
from fastapi_basekit import configure

# Configurar el toolkit globalmente
configure(
    default_page_size=25,
    max_page_size=200,
    log_level="INFO",
    strict_filter_validation=True,
)

app = FastAPI(title="Mi API")
```

Variables de entorno:

```bash
# .env
FASTAPI_BASEKIT_DEFAULT_PAGE_SIZE=25
FASTAPI_BASEKIT_MAX_PAGE_SIZE=200
FASTAPI_BASEKIT_LOG_LEVEL=DEBUG
FASTAPI_BASEKIT_STRICT_FILTER_VALIDATION=true
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
│    Service      │  ← Lógica de negocio, validaciones
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Repository    │  ← Acceso a datos, queries
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Database     │
└─────────────────┘
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
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["name"] == "Test User"
    assert data["message"] == "Creado exitosamente"
```

---

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Por favor lee [CONTRIBUTING.md](./CONTRIBUTING.md) para detalles.

### Desarrollo Local

```bash
# Clonar
git clone https://github.com/mundobien2025/fastapi-basekit.git
cd fastapi-basekit

# Instalar con Poetry
poetry install

# Activar entorno virtual
poetry shell

# Ejecutar tests
pytest

# Linting
black fastapi_basekit
flake8 fastapi_basekit
mypy fastapi_basekit
```

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
