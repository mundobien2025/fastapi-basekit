---
name: fastapi-basekit-crud
description: >
  Complete guide for building with fastapi-basekit following the real project conventions
  from axion_accounter_backend (SQLAlchemy/MariaDB), pulbot-backend (Beanie/MongoDB),
  and fastapi-mariadb-template. Use proactively when: creating any new resource (model,
  repo, service, controller, schema), adding an endpoint, fixing a controller or service
  pattern, scaffolding a feature module, or starting a new project with fastapi-basekit.
  Covers SQLAlchemy async + Beanie. Also trigger for permissions, auth middleware,
  dependency.py factories, test scaffolding, Alembic migrations, and seed scripts.
tools: Read, Edit, Write, Bash, Glob, Grep
---

# fastapi-basekit — Canonical Patterns

**Source of truth projects:**
- SQLAlchemy: `axion_accounter_backend/` + `fastapi-mariadb-template/`
- Beanie: `pulbot-backend/`
- Library source: `fastapi-basekit/`

---

## 0. Before writing anything — read first

```bash
find app/ -name "*.py" | head -40
```

Read one existing controller + service + repo to match the project's exact style.
Check if it uses SQLAlchemy or Beanie. Check if `app/models/base.py` has `deleted_at` (soft delete).

---

## 1. Canonical project structure

```
project/
├── app/
│   ├── api/v1/
│   │   ├── endpoints/
│   │   │   ├── auth/auth.py          ← AuthController (@cbv)
│   │   │   ├── user/user.py          ← UserController (@cbv)
│   │   │   └── <domain>/<resource>.py
│   │   └── routers.py                ← include_router for all domains
│   ├── config/
│   │   ├── database.py               ← engine, AsyncSessionFactory, get_db, lifespan
│   │   ├── settings.py               ← BaseSettings + lru_cache get_settings()
│   │   ├── arq.py                    ← ARQ_REDIS_SETTINGS
│   │   └── worker.py                 ← WorkerSettings with task functions list
│   ├── deferred/tasks.py             ← ARQ background task functions
│   ├── middleware/
│   │   ├── auth.py                   ← AuthenticationMiddleware (sets request.state.user)
│   │   └── permissions.py            ← PermissionMiddleware (checks endpoint_permissions table)
│   ├── models/
│   │   ├── base.py                   ← BaseModel (DeclarativeBase + UUID PK + soft delete)
│   │   ├── types.py                  ← GUID TypeDecorator, LowercaseEnum
│   │   ├── enums.py
│   │   ├── auth.py                   ← Users, UserRoles, Sessions
│   │   └── admin.py                  ← Roles, Modules, Actions, Permissions, RolePermissions, EndpointPermissions
│   ├── permissions/
│   │   └── user.py                   ← BasePermission subclasses
│   ├── repositories/
│   │   ├── user/user.py
│   │   └── admin/                    ← permission, role, module, endpoint_permission repos
│   ├── schemas/
│   │   ├── base.py                   ← BaseSchema (from_attributes=True + json_encoders)
│   │   └── user/                     ← auth.py, base.py, me.py, profile.py
│   ├── scripts/
│   │   ├── init.py                   ← master seed orchestrator
│   │   └── init_*.py                 ← per-entity seed scripts
│   ├── services/
│   │   ├── dependency.py             ← get_dependency_service + CurrentUser alias
│   │   └── system/user/              ← user.py, auth.py
│   ├── utils/
│   │   ├── exception_handlers.py
│   │   ├── schema.py                 ← UrlSchema (S3 URL mixin)
│   │   └── security.py               ← get_password_hash, verify_password
│   └── main.py                       ← create_application() factory
├── alembic/
│   ├── env.py
│   └── versions/                     ← date-prefixed: 20250310_1200_abc123_add_thing.py
├── docker/local/
├── requirements/base.txt
├── Makefile
└── alembic.ini
```

---

## 2. Base model (SQLAlchemy)

```python
# app/models/base.py
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr
from app.models.types import GUID, uuid4, UUID

class BaseModel(DeclarativeBase):
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()  # always override explicitly in subclasses

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(tz=timezone.utc)

    def restore(self) -> None:
        self.deleted_at = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
```

**UUID type** (`app/models/types.py`): `GUID` = `TypeDecorator` on `String(36)` — MariaDB stores as string, Python returns `uuid.UUID`. Always use `GUID()` as column type, never `UUID` directly.

---

## 3. Base model (Beanie)

```python
# app/models/base.py (pulbot)
from beanie import Document, before_event, Replace, Insert
from datetime import datetime
from pydantic import Field

class CustomBaseModel(Document):
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        abstract = True

    @before_event(Replace, Insert)
    def update_updated_at(self):
        self.updated_at = datetime.now()

    async def delete_relations(self):
        return None  # override to cascade-delete linked documents

    async def delete(self, *args, **kwargs):
        await self.delete_relations()
        return await super().delete(*args, **kwargs)

class BaseModelSD(CustomBaseModel):
    class Settings:
        abstract = True
```

Beanie models use `Link[OtherModel]` (not raw ObjectId) and declare `Settings.name` (collection name) and `Settings.indexes`.

---

## 4. SQLAlchemy model for a new resource

```python
# app/models/<resource>.py
import uuid
from sqlalchemy import String, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from app.models.types import GUID

class Thing(BaseModel):
    __tablename__ = "things"

    company_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="1", nullable=False)

    company: Mapped["Company"] = relationship("Company", back_populates="things")
```

- **Always** add the import to `app/models/__init__.py` so Alembic detects it
- **Always** `deleted_at` from `BaseModel` — NEVER hard-delete
- FK uses `GUID()` type + `ondelete="SET NULL"` (or `CASCADE`)
- `server_default="1"` for booleans (MariaDB compatible)

---

## 5. Pydantic schemas

```python
# app/schemas/<resource>.py
import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.base import BaseSchema  # has from_attributes=True + json_encoders

class ThingCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: bool = True
    model_config = ConfigDict(extra="ignore")

class ThingUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    model_config = ConfigDict(extra="ignore")

class ThingResponseSchema(BaseSchema):  # extends BaseSchema, NOT plain BaseModel
    id: uuid.UUID           # MUST be uuid.UUID — model_validate fails with str
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

**`BaseSchema`** (`app/schemas/base.py`):
```python
class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S")},
    )
```

---

## 6. Repository (SQLAlchemy)

```python
# app/repositories/<resource>/repository.py
from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from app.models.<resource> import Thing

class ThingRepository(BaseRepository):
    model = Thing
    # BaseRepository provides: get(id), list_paginated(), create(data), update(id, dict), delete(id), get_by_field(), get_by_filters()
    # self.session = AsyncSession

    # Add custom methods ONLY when BaseRepository doesn't cover the need:
    async def get_by_company(self, company_id: uuid.UUID) -> list[Thing]:
        result = await self.session.execute(
            select(Thing).where(Thing.company_id == company_id, Thing.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    def build_list_queryset(self, **kwargs):
        # Override to enrich the list() query (e.g. joins, subqueries)
        query = select(self.model).where(self.model.deleted_at.is_(None))
        return query
```

`BaseRepository.update(id, data_dict)` — positional dict, NOT kwargs: `repo.update(id, {"field": value})`.

---

## 7. Repository (Beanie)

```python
# app/repositories/<resource>/repository.py
from fastapi_basekit.aio.beanie.repository.base import BeanieBaseRepository
from app.models.<resource> import Thing

class ThingRepository(BeanieBaseRepository):
    model = Thing

    async def get_by_user(self, user_id) -> list[Thing]:
        return await Thing.find({"user.$id": user_id}).to_list()

    async def get_with_links(self, thing_id) -> Thing | None:
        return await Thing.get(thing_id, fetch_links=True)
```

---

## 8. Service (SQLAlchemy)

```python
# app/services/<resource>_service.py
from typing import Optional
from uuid import UUID
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
from app.repositories.<resource>.repository import ThingRepository

class ThingService(BaseService):
    repository: ThingRepository
    search_fields = ["name"]           # enables ?search= param
    duplicate_check_fields = ["name"]  # checked on create

    def __init__(
        self,
        repository: ThingRepository,
        request: Optional[Request] = None,
        session: Optional[AsyncSession] = None,
    ):
        super().__init__(repository, request=request)
        self.repository = repository
        self.session = session

    def get_filters(self, filters=None):
        # Scope results to current user's context
        filters = filters or {}
        user = getattr(self.request.state, "user", None) if self.request else None
        if user and hasattr(user, "company_id") and user.company_id:
            filters["company_id"] = user.company_id
        return filters

    def build_queryset(self):
        # Override for enriched list queries
        return self.repository.build_list_queryset()

    async def my_custom_action(self, thing_id: UUID) -> dict:
        thing = await self.repository.get(thing_id)
        if not thing:
            raise NotFoundException(message="Thing not found")
        # ... logic ...
        return {"result": "ok"}
```

---

## 9. Service (Beanie)

```python
# app/services/<resource>_service.py
from fastapi_basekit.aio.beanie.service.base import BaseService
from app.repositories.<resource>.repository import ThingRepository

class ThingService(BaseService):
    repository: ThingRepository

    def __init__(self, request, repository=None):
        super().__init__(repository or ThingRepository(), request)

    def get_filters(self, filters=None):
        filters = filters or {}
        user = getattr(self.request.state, "user", None)
        if user:
            filters["user.$id"] = user.id
        return super().get_filters(filters)

    def get_kwargs_query(self):
        return {"fetch_links": True}  # eager-load Link[] fields
```

---

## 10. Dependency factory — ALWAYS in `app/services/dependency.py`

```python
# app/services/dependency.py  (ADD to existing file, never new one)
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import get_db
from app.repositories.<resource>.repository import ThingRepository
from app.services.<resource>_service import ThingService

def get_thing_service(
    request: Request, session: AsyncSession = Depends(get_db)
) -> ThingService:
    repository = ThingRepository(session)
    return ThingService(repository=repository, request=request, session=session)
```

Multi-repo factory:
```python
def get_user_service(
    request: Request, session: AsyncSession = Depends(get_db)
) -> UserService:
    user_repo = UserRepository(session)
    role_repo = RoleRepository(session)
    permission_repo = PermissionRepository(session)
    return UserService(
        repository=user_repo,
        role_repository=role_repo,
        permission_repository=permission_repo,
        request=request,
        session=session,
    )
```

**NEVER** put factory functions inside controller files.

---

## 11. Controller (SQLAlchemy)

```python
# app/api/v1/endpoints/<domain>/<resource>.py
import uuid
from typing import List, Optional, Type

from fastapi import APIRouter, Depends, Query, status
from fastapi.requests import Request
from fastapi_restful.cbv import cbv

from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from fastapi_basekit.schema.base import BasePaginationResponse, BaseResponse

from app.models.auth import Users
from app.schemas.<resource> import ThingCreateSchema, ThingResponseSchema, ThingUpdateSchema
from app.services.dependency import get_dependency_service, get_thing_service
from app.services.<resource>_service import ThingService

router = APIRouter(prefix="/things", tags=["things"])

@cbv(router)
class ThingController(SQLAlchemyBaseController):

    service: ThingService = Depends(get_thing_service)
    schema_class = ThingResponseSchema
    user: Users = Depends(get_dependency_service)  # auth guard; omit for public endpoints

    def get_schema_class(self) -> Type:
        # Override to return different schema per action (e.g. list vs detail)
        if self.action == "list_things":
            return ThingListResponseSchema
        return super().get_schema_class()

    def check_permissions(self):
        # Return BasePermission subclasses to enforce for current action
        if self.action in ("delete_thing", "update_thing"):
            return [ThingAdminPermission]
        return []

    @router.get("/", response_model=BasePaginationResponse[ThingResponseSchema])
    async def list_things(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
    ):
        self.action = "list_things"
        return await self.list()

    @router.post("/", response_model=BaseResponse[ThingResponseSchema], status_code=201)
    async def create_thing(self, data: ThingCreateSchema):
        self.action = "create_thing"
        thing = await self.service.create(data)
        return self.format_response(ThingResponseSchema.model_validate(thing))

    @router.get("/{thing_id}", response_model=BaseResponse[ThingResponseSchema])
    async def get_thing(self, thing_id: uuid.UUID):
        self.action = "get_thing"
        return await self.retrieve(thing_id)

    @router.patch("/{thing_id}", response_model=BaseResponse[ThingResponseSchema])
    async def update_thing(self, thing_id: uuid.UUID, data: ThingUpdateSchema):
        self.action = "update_thing"
        await self.check_permissions_class()
        thing = await self.service.update(str(thing_id), data.model_dump(exclude_unset=True))
        return self.format_response(
            ThingResponseSchema.model_validate(thing),
            message="Actualizado exitosamente",
        )

    @router.delete("/{thing_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_thing(self, thing_id: uuid.UUID):
        self.action = "delete_thing"
        await self.check_permissions_class()
        return await self.delete(thing_id)

    # Custom action
    @router.post("/{thing_id}/activate", response_model=BaseResponse[dict])
    async def activate_thing(self, thing_id: uuid.UUID):
        self.action = "activate_thing"
        result = await self.service.my_custom_action(thing_id)
        return self.format_response(result, message="Activado exitosamente")
```

**Controller rules (hard):**

| Rule | Why |
|------|-----|
| Always `self.action = "verb_noun"` before calling `self.list()` / `self.retrieve()` / `self.delete()` | Needed for `get_filters()`, `get_schema_class()`, `check_permissions()` dispatch |
| Standard CRUD: `self.list()`, `self.retrieve(id)`, `self.delete(id)` | Inherits pagination, formatting, soft-delete |
| Custom create/update: `self.service.method()` → `self.format_response(Schema.model_validate(obj))` | Consistent wrapping |
| `self.format_response(data, message="...")` — NOT raw `BaseResponse(data=...)` | Uses controller's schema class and standard format |
| `BasePaginationResponse[List[Schema]]` — use `List` from `typing` in `@cbv` class bodies | Built-in `list` fails inside CBV class body |
| `id: uuid.UUID` in response schemas | `model_validate` fails if typed as `str` |
| NEVER import `Request`, `AsyncSession`, `get_db`, repo classes, or `BaseModel` in controller | Those are dependency concerns |
| `get_thing_service` factory lives in `dependency.py` only | Reusable, separation of concerns |

---

## 12. Controller (Beanie)

```python
from fastapi_basekit.aio.beanie.controller.base import BeanieBaseController

router = APIRouter(prefix="/things", tags=["things"])

@cbv(router)
class ThingController(BeanieBaseController):
    service: ThingService = Depends(get_thing_service)
    schema_class = ThingResponseSchema
    user = Depends(get_dependency_service_beanie)

    @router.get("/", response_model=BasePaginationResponse[ThingResponseSchema])
    async def list_things(self, page: int = Query(1, ge=1), count: int = Query(10)):
        self.action = "list_things"
        return await self.list()
```

---

## 13. Auth dependency (`app/services/dependency.py` — existing pattern)

```python
from typing import Annotated
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi_basekit.exceptions.api_exceptions import JWTAuthenticationException
from app.models.auth import Users

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token/")

async def get_dependency_service(
    request: Request,
    token: str = Depends(oauth2_scheme),  # keeps OAuth2 schema, value unused
) -> Users:
    user = getattr(request.state, "user", None)
    if not user:
        raise JWTAuthenticationException(message="Usuario no autenticado.")
    return user

CurrentUser = Annotated[Users, Depends(get_dependency_service)]
```

`request.state.user` is set by `AuthenticationMiddleware` before route handlers run.

---

## 14. Permission class

```python
# app/permissions/user.py
from fastapi_basekit.aio.permissions.base import BasePermission
from fastapi import Request

class ThingAdminPermission(BasePermission):
    message_exception: str = "No tienes permiso para esta acción"

    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if not user:
            return False
        role_codes = getattr(request.state, "user_role_codes", [])
        return "admin" in role_codes or "superadmin" in role_codes
```

Used in controller: `def check_permissions(self): return [ThingAdminPermission]`
Enforced by: `await self.check_permissions_class()` (call manually in routes that need it).

---

## 15. Router registration

```python
# app/api/v1/endpoints/<domain>/__init__.py
from .thing import router as thing_router
__all__ = ["thing_router"]

# app/api/v1/routers.py
from app.api.v1.endpoints.<domain> import thing_router
router.include_router(thing_router, prefix="/admin", tags=["admin"])
# or without prefix for top-level:
router.include_router(thing_router)
```

---

## 16. `main.py` pattern

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_application() -> FastAPI:
    app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

    # Exception handlers (order doesn't matter)
    app.add_exception_handler(APIException, exception_handlers.api_exception_handler)
    app.add_exception_handler(ValidationException, exception_handlers.api_exception_handler)
    app.add_exception_handler(DatabaseIntegrityException, exception_handlers.database_exception_handler)
    app.add_exception_handler(IntegrityError, exception_handlers.integrity_error_handler)
    app.add_exception_handler(RequestValidationError, exception_handlers.validation_exception_handler)
    app.add_exception_handler(ValidationError, exception_handlers.value_exception_handler)
    app.add_exception_handler(Exception, exception_handlers.global_exception_handler)

    # Middleware: last registered = first to run
    # Execution order: AuthenticationMiddleware → PermissionMiddleware → CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=settings.ALLOWED_ORIGINS, ...)
    app.add_middleware(PermissionMiddleware)
    app.add_middleware(AuthenticationMiddleware)

    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": settings.VERSION}

    return app

app = create_application()
```

---

## 17. Alembic migration

```bash
# Naming: date + time prefix (alembic.ini configured)
# Output: alembic/versions/20250310_1200_abc123_add_things_table.py
make migrate-create  # interactive, asks for message
# or:
alembic revision --autogenerate -m "add_things_table"
alembic upgrade head
```

`alembic/env.py` imports ALL models from `app.models` via `pkgutil.walk_packages` so Alembic detects them all. Adding a new model to `app/models/__init__.py` is enough.

---

## 18. Seed script pattern

```python
# app/scripts/init_things.py
from app.config.database import AsyncSessionFactory
from app.models.thing import Thing

THINGS_DATA = [
    {"name": "Default Thing", "is_active": True},
]

async def init_things():
    async with AsyncSessionFactory() as session:
        for data in THINGS_DATA:
            existing = await session.execute(select(Thing).where(Thing.name == data["name"]))
            if not existing.scalar():
                session.add(Thing(**data))
        await session.commit()

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_things())
```

Add it to `app/scripts/init.py` master orchestrator in dependency order.

---

## 19. Test pattern

```
app/tests/e2e/<domain>/
├── conftest.py        ← domain fixtures
├── dependency.py      ← static class with API call helpers (e.g. ThingDependency.list_things(client, headers))
├── factory.py         ← ThingFactory.create_data(**overrides) → dict
├── helper.py          ← extraction helpers
└── test_thing.py      ← pytest classes with pytestmark = pytest.mark.asyncio
```

```python
# test_thing.py
import pytest
pytestmark = pytest.mark.asyncio

class TestThingListing:
    async def test_list_things_success(self, async_client, super_admin_user):
        response = await ThingDependency.list_things(async_client, super_admin_user["headers"])
        assert response["status"] == "success"
        assert isinstance(response["data"], list)
        assert "pagination" in response

class TestThingCreation:
    async def test_create_thing_success(self, async_client, super_admin_user):
        data = ThingFactory.create_data(name="Test Thing")
        response = await ThingDependency.create_thing(async_client, super_admin_user["headers"], data)
        assert response["status"] == "success"
        assert response["data"]["name"] == "Test Thing"
```

`super_admin_user` fixture returns: `{"token": ..., "headers": {"Authorization": "Bearer ..."}, "user_id": ..., "email": ...}`

---

## 20. Makefile commands reference

```makefile
make format         # black + isort
make lint           # flake8
make up             # docker compose up --build
make migrate-create # alembic revision --autogenerate (interactive)
make migrate-up     # alembic upgrade head
make migrate-down   # alembic downgrade -1
make seed           # python3 -m app.scripts.init (in container)
make test           # pytest
make test-e2e       # docker compose --profile tests run --rm tests
```

---

## 21. Common pitfalls

| Mistake | Symptom | Fix |
|---------|---------|-----|
| `id: str` in response schema | `model_validate` silently wrong or raises | Change to `id: uuid.UUID` |
| Factory function in controller file | Untestable, hard to reuse | Move to `app/services/dependency.py` |
| `list` instead of `List` in `@cbv` class body | `TypeError` at class definition | `from typing import List` |
| `repo.update(id, key=val)` kwargs | `TypeError` — wrong signature | `repo.update(id, {"key": val})` dict |
| Missing `self.action = "..."` before `self.list()` | Wrong filters, schema, or permissions applied | Always set before calling base methods |
| Hard deleting records | Breaks audit trail | Always `soft_delete()` or `BaseService.delete()` |
| Not adding model import to `app/models/__init__.py` | Alembic doesn't detect table | Import in `__init__.py` |
| `BaseResponse(data=...)` directly in controller | Bypasses `format_response` message/status | Use `self.format_response(data, message=...)` |
| `request.state.db` in auth middleware | `AttributeError` | Use `AsyncSessionFactory()` directly in middleware |
| Beanie: raw ObjectId in filter | Beanie doesn't match Links by raw ID | Use `{"field.$id": object_id}` |
| Accessing `self.db` in SQLAlchemy repo | `AttributeError` | Use `self.session` (stored as `self._session`) |
| Importing `Request`, `AsyncSession`, `get_db` in controller | Breaks separation of concerns, coupling | Those belong only in `dependency.py` |
| Soft-delete not filtered in custom queries | Deleted records appear in results | Always add `.where(Model.deleted_at.is_(None))` |
