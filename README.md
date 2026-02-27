# FastAPI BaseKit

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)
![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square&logo=python)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?style=flat-square)
![SQLModel](https://img.shields.io/badge/SQLModel-0.0.21+-orange?style=flat-square)
![MongoDB](https://img.shields.io/badge/MongoDB-Beanie-47A248?style=flat-square&logo=mongodb)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

Clases base para construir APIs REST con FastAPI de forma rápida: repositorios, servicios y controllers con CRUD, paginación, búsqueda, filtros y ordenamiento ya resueltos.

Soporta **SQLAlchemy**, **SQLModel** y **Beanie (MongoDB)**.

---

## Instalación  

```bash
# Solo lo base (sin ORM)
pip install fastapi-basekit

# SQLAlchemy (PostgreSQL / MySQL / SQLite)
pip install fastapi-basekit[sqlalchemy]

# SQLModel
pip install fastapi-basekit[sqlmodel]

# Beanie (MongoDB)
pip install fastapi-basekit[beanie]

# Todo
pip install fastapi-basekit[all]
```

---

## Inicio rápido — SQLAlchemy

El patrón real usado en producción: class-based views con `@cbv` de `fastapi-restful`.

### 1. Modelo

```python
# app/models/auth.py
from sqlalchemy import String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import BaseModel  # tu Base con id, created_at, etc.
from .enums import UserStatusEnum

class Users(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    document: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[UserStatusEnum] = mapped_column(SAEnum(UserStatusEnum))

    # Relación many-to-many
    user_roles: Mapped[list["UserRoles"]] = relationship(back_populates="user")
```

### 2. Schemas

Puedes tener múltiples schemas por recurso — el controller decide cuál usar por acción.

```python
# app/schemas/user.py
from pydantic import BaseModel, ConfigDict
from uuid import UUID

class UserListResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    full_name: str | None
    role_name: str | None   # columna extra del queryset enriquecido

class UserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    full_name: str | None
    document: str | None
    phone: str | None
    status: str
```

### 3. Repository

En el 90% de los casos el repositorio solo necesita declarar el modelo. Todo el CRUD ya está implementado en `BaseRepository`.

```python
# app/repositories/user.py
from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from app.models.auth import Users

class UserRepository(BaseRepository):
    model = Users
```

Sobreescribe `build_list_queryset` solo si necesitas un query base distinto al `select(model)` por defecto — por ejemplo para agregar columnas calculadas que el schema pueda consumir directamente:

```python
from sqlalchemy import select, func
from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from app.models.auth import Roles, UserRoles

class RoleRepository(BaseRepository):
    model = Roles

    def build_list_queryset(self, **kwargs):
        """Agrega el conteo de usuarios por rol como columna extra."""
        member_count = (
            select(func.count(UserRoles.user_id))
            .where(UserRoles.role_id == Roles.id)
            .scalar_subquery()
            .label("member_count")
        )
        return select(Roles, member_count)
```

El schema recibe `member_count` directamente (no hace falta nada más):

```python
class RoleResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    code: str
    member_count: int
```

### Métodos disponibles en BaseRepository

```python
# Por ID
user = await repo.get(user_id)
user = await repo.get_with_joins(user_id, joins=["user_roles", "company"])

# Por campo
user = await repo.get_by_field("email", "john@example.com")
user = await repo.get_by_field_with_joins("email", "john@example.com", joins=["user_roles"])

# Por múltiples filtros
users = await repo.get_by_filters({"status": "active", "company_id": company_id})
users = await repo.get_by_filters({"status": ["active", "pending"]})  # IN
users = await repo.get_by_filters({"status": "active"}, use_or=False)

# Con joins + filtros
user = await repo.get_by_filters_with_joins(
    {"email": "john@example.com"}, joins=["user_roles"], one=True
)

# Filtros en relaciones con sintaxis __
admins = await repo.get_by_filters({"user_roles__role__code": "admin"})

# CRUD
created = await repo.create({"email": "new@example.com", "full_name": "Jane"})
updated = await repo.update(user_id, {"full_name": "Jane Doe"})
deleted = await repo.delete(user_id)
```

### 4. Service

El servicio usa los métodos del repositorio en sus métodos de negocio. No necesita escribir SQL.

```python
# app/services/user.py
from fastapi import Request, Depends
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
from fastapi_basekit.exceptions.api_exceptions import NotFoundException, DatabaseIntegrityException
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import get_db
from app.repositories.user import UserRepository

class UserService(BaseService):
    repository: UserRepository

    # Búsqueda textual sobre estos campos (ILIKE %term%)
    search_fields = ["full_name", "email", "document", "phone"]

    # Verifica duplicados en estos campos al crear
    duplicate_check_fields = ["email"]

    def get_kwargs_query(self) -> dict:
        """Joins cargados automáticamente según la acción."""
        if self.action in ["list_users", "retrieve"]:
            return {"joins": ["user_roles"]}
        return {}

    def get_filters(self, filters: dict | None = None) -> dict:
        """Inyecta filtros de negocio antes de consultar."""
        filters = {k: v for k, v in (filters or {}).items() if v is not None}
        user = getattr(self.request.state, "user", None) if self.request else None
        if user and "company_id" not in filters:
            filters["company_id"] = user.company_id
        return filters

    # Métodos de negocio usando las herramientas del repositorio
    async def get_by_email(self, email: str):
        user = await self.repository.get_by_field("email", email)
        if not user:
            raise NotFoundException(message="Usuario no encontrado")
        return user

    async def get_with_roles(self, user_id: str):
        return await self.repository.get_with_joins(user_id, joins=["user_roles"])

    async def get_active_by_company(self, company_id):
        return await self.repository.get_by_filters(
            {"company_id": company_id, "status": "active"}
        )

    async def find_admins(self):
        # Filtro sobre relación: user_roles → role → code
        return await self.repository.get_by_filters(
            {"user_roles__role__code": "admin"}
        )


def get_user_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> UserService:
    return UserService(
        repository=UserRepository(session),
        request=request,
    )
```

### 5. Controller

```python
# app/api/v1/endpoints/user/user.py
from typing import List, Optional, Type
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi_restful.cbv import cbv
from pydantic import BaseModel

from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from fastapi_basekit.aio.permissions.base import BasePermission
from fastapi_basekit.schema.base import BaseResponse, BasePaginationResponse

from app.schemas.user import UserResponseSchema, UserListResponseSchema
from app.services.user import UserService, get_user_service
from app.permissions.user import IsAdminPermission

router = APIRouter(prefix="/users", tags=["users"])


@cbv(router)
class UserController(SQLAlchemyBaseController):
    service: UserService = Depends(get_user_service)
    schema_class = UserResponseSchema

    def get_schema_class(self) -> Type[BaseModel]:
        """Schema diferente según la acción."""
        if self.action == "list_users":
            return UserListResponseSchema  # incluye role_name
        return UserResponseSchema

    def check_permissions(self) -> List[Type[BasePermission]]:
        """Permisos por acción."""
        if self.action in ["delete_user"]:
            return [IsAdminPermission]
        return []

    @router.get(
        "/",
        response_model=BasePaginationResponse[UserListResponseSchema],
        status_code=status.HTTP_200_OK,
    )
    async def list_users(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None, description="Busca en nombre, email, documento, teléfono"),
        order_by: Optional[str] = Query(None, description="Ej: created_at, -created_at"),
        status: Optional[str] = Query(None),
    ):
        """Lista usuarios con paginación, búsqueda y filtros."""
        return await self.list()

    @router.get("/{user_id}/", response_model=BaseResponse[UserResponseSchema])
    async def get_user(self, user_id: UUID):
        return await self.retrieve(str(user_id))

    @router.delete("/{user_id}/", response_model=BaseResponse[None])
    async def delete_user(self, user_id: UUID):
        await self.check_permissions_class()
        await self.service.delete(str(user_id))
        return BaseResponse(data=None, message="Usuario eliminado")
```

---

## Características destacadas

### Búsqueda multi-campo

Define `search_fields` en el servicio. El parámetro `search` del query se convierte automáticamente en `ILIKE %term%` sobre todos esos campos con `OR`.

```python
class UserService(BaseService):
    search_fields = ["full_name", "email", "document", "phone"]
```

```
GET /users?search=juan          → busca "juan" en full_name, email, document, phone
GET /users?search=@gmail.com    → encuentra todos los emails de gmail
```

Soporta rutas anidadas con `__`:

```python
search_fields = ["name", "user_roles__role__name"]  # busca también en rol relacionado
```

---

### Filtros automáticos desde query params

Todo lo que el endpoint declara como `Query(...)` (que no sea `page`, `count`, `search`, `order_by`) se pasa automáticamente como filtro. No necesitas extraerlos manualmente.

```python
@router.get("/")
async def list_tools(
    self,
    page: int = Query(1, ge=1),
    count: int = Query(10),
    search: Optional[str] = Query(None),
    active: bool | None = Query(None),      # → filters["active"]
    tool_type: str | None = Query(None),    # → filters["tool_type"]
    platform: str | None = Query(None),     # → filters["platform"]
):
    return await self.list()  # _params() extrae todos los filtros del frame
```

Soporta filtros con relaciones usando `__`:

```
GET /users?user_roles__role__code=admin   → JOIN automático + WHERE
```

---

### Filtros inyectados desde el servicio

Usa `get_filters()` para agregar, transformar o validar filtros antes de consultar. Muy útil para filtrar por el usuario autenticado.

```python
def get_filters(self, filters: dict | None = None) -> dict:
    filters = super().get_filters(filters)
    filters = {k: v for k, v in filters.items() if v is not None}

    # Inyectar company_id del usuario autenticado
    user = getattr(self.request.state, "user", None) if self.request else None
    if user and "company_id" not in filters:
        filters["company_id"] = user.company_id

    # Mapear parámetros de query a columnas internas
    if "folder_id" in filters:
        filters["parent_id"] = filters.pop("folder_id")

    return filters
```

---

### Ordenamiento

El parámetro `order_by` acepta:

| Valor | Resultado |
|---|---|
| `created_at` | ORDER BY created_at ASC |
| `-created_at` | ORDER BY created_at DESC |
| `user__full_name` | JOIN users + ORDER BY users.full_name ASC |
| `-user__email` | JOIN users + ORDER BY users.email DESC |

```
GET /users?order_by=-created_at           → más recientes primero
GET /tools?order_by=tool_type__name       → ordenado por nombre del tipo
```

Para Beanie, soporta ordenamiento anidado usando pipeline de agregación automáticamente:

```
GET /tools?order_by=-created_at           → sort simple
GET /tools?order_by=tool_type__name       → $lookup + $sort automático
```

---

### Joins / eager loading (SQLAlchemy)

Define qué relaciones cargar según la acción para evitar queries N+1:

```python
def get_kwargs_query(self) -> dict:
    if self.action in ["list_users", "retrieve"]:
        return {"joins": ["user_roles"]}          # selectinload para listas
    return {}
```

O pásalos directamente desde el controller:

```python
async def retrieve(self, id: UUID):
    return await self.service.retrieve(str(id), joins=["user_roles", "company"])
```

---

### Queryset personalizado con subconsultas

Sobreescribe `build_list_queryset()` en el repositorio para cambiar el query base del listado. Los filtros, búsqueda, ordenamiento y paginación se aplican encima automáticamente — no necesitas tocar `list()`.

Los parámetros que recibe son los mismos kwargs estándar de `list_paginated` (`filters`, `search`, `order_by`, etc.) — úsalos si quieres tomar decisiones en el query base.

```python
from sqlalchemy import select
from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from app.models.auth import Users, UserRoles, Roles

class UserRepository(BaseRepository):
    model = Users

    def build_list_queryset(self, **kwargs):
        # Subconsulta correlacionada: nombre del primer rol del usuario
        role_name_subq = (
            select(Roles.name)
            .join(UserRoles, UserRoles.role_id == Roles.id)
            .where(UserRoles.user_id == Users.id)
            .limit(1)
            .scalar_subquery()
            .label("role_name")
        )
        return (
            select(Users, role_name_subq)
            .where(Users.deleted_at.is_(None))
        )
```

El schema recibe la columna extra directamente gracias a `from_attributes=True`:

```python
class UserListResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    full_name: str | None
    role_name: str | None  # inyectada desde la subconsulta
```

---

### Múltiples schemas por controller

```python
def get_schema_class(self) -> Type[BaseModel]:
    if self.action in ["retrieve", "create", "update"]:
        return ToolDResponseSchema   # detallado con relaciones
    return ToolResponseSchema        # resumido para el listado
```

---

### Múltiples repositorios en un servicio

```python
class UserService(BaseService):
    def __init__(
        self,
        repository: UserRepository,
        user_role_repository: UserRoleRepository,
        role_repository: RoleRepository,
        permission_repository: PermissionRepository,
        request: Request | None = None,
    ):
        super().__init__(repository, request=request)
        self.user_role_repository = user_role_repository
        self.role_repository = role_repository
        self.permission_repository = permission_repository


def get_user_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> UserService:
    return UserService(
        repository=UserRepository(session),
        user_role_repository=UserRoleRepository(session),
        role_repository=RoleRepository(session),
        permission_repository=PermissionRepository(session),
        request=request,
    )
```

---

### Permisos

```python
# app/permissions/user.py
from fastapi import Request
from fastapi_basekit.aio.permissions.base import BasePermission

class IsAdminPermission(BasePermission):
    message_exception = "Solo administradores pueden realizar esta acción"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        role_codes = getattr(request.state, "user_role_codes", [])
        return "admin" in role_codes if user else False
```

Aplicar en el controller:

```python
def check_permissions(self) -> List[Type[BasePermission]]:
    if self.action in ["delete_user", "update_profile"]:
        return [IsAdminPermission]
    return []

# O manualmente en un método:
async def delete_user(self, user_id: UUID):
    await self.check_permissions_class()
    await self.service.delete(str(user_id))
```

---

## Beanie (MongoDB)

El mismo patrón, usando `BeanieBaseController` y `BeanieBaseService`.

```python
# app/api/v1/endpoints/tool/tool.py
from fastapi_basekit.aio.beanie.controller.base import BeanieBaseController
from fastapi_basekit.aio.beanie.service.base import BaseService

@cbv(router)
class ToolController(BeanieBaseController):
    service: ToolService = Depends(get_tool_service)
    schema_class = ToolResponseSchema

    def get_schema_class(self):
        if self.action in ["retrieve", "create", "update"]:
            return ToolDResponseSchema
        return ToolResponseSchema

    @router.get("/", response_model=ToolPResponseSchema)
    async def list(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1),
        search: str | None = Query(None),
        tool_type: PydanticObjectId | None = Query(None),
        active: bool | None = Query(None),
        order_by: str | None = Query(None),
    ):
        return await super().list()
```

### fetch_links (relaciones en Beanie)

```python
class ToolService(BaseService):
    search_fields = ["name", "description"]

    def get_kwargs_query(self) -> dict:
        """Carga relaciones según la acción."""
        if self.action in ["list", "retrieve", "create", "update"]:
            return {
                "fetch_links": True,
                "nesting_depths_per_field": {"tool_type": 2, "platform": 1},
            }
        return {}
```

### get_filters en Beanie

```python
def get_filters(self, filters: dict | None = None) -> dict:
    filters = {k: v for k, v in (filters or {}).items() if v is not None}

    user = getattr(self.request.state, "user", None) if self.request else None
    if user:
        category = filters.pop("category", "user")
        if category == "user":
            filters["user"] = user.id
        elif category == "global":
            filters["category"] = ToolCategoryEnum.GLOBAL
        # category="all" → sin filtro adicional

    return filters
```

---

## SQLModel

Mismo contrato que SQLAlchemy, solo cambia la sesión y la forma de definir modelos.

```python
pip install fastapi-basekit[sqlmodel]
```

```python
from sqlmodel import SQLModel, Field, Relationship

class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    team_id: int | None = Field(default=None, foreign_key="team.id")
    team: "Team | None" = Relationship(back_populates="heroes")
```

```python
from fastapi_basekit.aio.sqlmodel import (
    SQLModelBaseController,
    BaseRepository,
    BaseService,
)

class HeroRepository(BaseRepository):
    model = Hero

class HeroService(BaseService):
    search_fields = ["name"]
    duplicate_check_fields = ["name"]

@cbv(router)
class HeroController(SQLModelBaseController):
    service: HeroService = Depends(get_hero_service)
    schema_class = HeroSchema
```

La sesión usa `sqlmodel.ext.asyncio.session.AsyncSession` internamente. Los queries usan `session.exec()` para tipos seguros.

---

## Formato de respuesta

Todas las respuestas siguen el mismo envelope:

```python
# Detalle / create / update
BaseResponse[Schema]
{
    "data": { ... },
    "message": "Operación exitosa",
    "status": "success"
}

# Listado paginado
BasePaginationResponse[Schema]
{
    "data": [ ... ],
    "pagination": {
        "page": 1,
        "count": 10,
        "total": 87,
        "total_pages": 9
    },
    "message": "Operación exitosa",
    "status": "status"
}
```

Declara el `response_model` en el decorador para que FastAPI genere el OpenAPI correcto:

```python
@router.get("/", response_model=BasePaginationResponse[UserListResponseSchema])
async def list_users(self, ...):
    return await self.list()

@router.get("/{id}/", response_model=BaseResponse[UserResponseSchema])
async def get_user(self, id: UUID):
    return await self.retrieve(str(id))
```

---

## Excepciones

```python
from fastapi_basekit.exceptions.api_exceptions import (
    NotFoundException,          # 404
    DatabaseIntegrityException, # 400 — registro duplicado
    ValidationException,        # 422
    PermissionException,        # 403
    JWTAuthenticationException, # 401
    GlobalException,            # 500
)

# Uso en servicio o repositorio
raise NotFoundException(message="Usuario no encontrado")
raise DatabaseIntegrityException(message="El email ya está en uso", data={"email": email})
```

Registra el handler global en `main.py`:

```python
from fastapi_basekit.exceptions.handler import register_exception_handlers

app = FastAPI()
register_exception_handlers(app)
```

---

## Arquitectura

```
Controller  ←  valida parámetros, permisos, schema de respuesta
    ↓
Service     ←  lógica de negocio, get_filters(), build_queryset()
    ↓
Repository  ←  acceso a datos, queries SQL/Mongo, build_list_queryset()
    ↓
DB          ←  SQLAlchemy / SQLModel / Beanie
```

---

## Changelog

Ver [CHANGELOG.md](./CHANGELOG.md)

---

## Licencia

MIT — ver [LICENSE](./LICENSE)
