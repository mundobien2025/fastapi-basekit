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

### Starting a NEW project? Use `basekit init`

The library ships a cookiecutter scaffolder. Don't hand-roll `app/main.py`, `config/database.py`, alembic env, etc. — generate them:

```bash
pip install fastapi-basekit[init]
basekit init                                                    # interactive
basekit init --no-input                                         # defaults
basekit init --extra-context project_name="My Service" \
             --extra-context orm=sqlalchemy \
             --extra-context database=postgres \
             --extra-context cache=redis \
             --extra-context bucket=s3 \
             --extra-context license=MIT
```

Choices exposed (see `cookiecutter.json`): `orm` (sqlalchemy / beanie), `database` (postgres / mariadb / sqlite / mongodb), `server` (uvicorn / gunicorn), `cache` (none / redis), `background_tasks` (none / arq), `bucket` (none / s3), `include_alembic` (yes / no), `include_docker` (yes / no), `license` (MIT / Apache-2.0 / GPL-3.0 / Proprietary).

Pre-gen hook validates ORM ↔ database compatibility (beanie ⇒ mongodb, sqlalchemy ⇒ SQL). Post-gen hook prunes alembic/Docker if disabled.

Generated project boots with: `cp .env.example .env && make up-d && make migrate-create && make migrate-up && make seed`.

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
        # self.action is auto-set to the endpoint method name (e.g. "list_things").
        # Override to return a different schema per action.
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
        return await self.list()

    @router.post("/", response_model=BaseResponse[ThingResponseSchema], status_code=201)
    async def create_thing(self, data: ThingCreateSchema):
        thing = await self.service.create(data)
        return self.format_response(ThingResponseSchema.model_validate(thing))

    @router.get("/{thing_id}", response_model=BaseResponse[ThingResponseSchema])
    async def get_thing(self, thing_id: uuid.UUID):
        return await self.retrieve(thing_id)

    @router.patch("/{thing_id}", response_model=BaseResponse[ThingResponseSchema])
    async def update_thing(self, thing_id: uuid.UUID, data: ThingUpdateSchema):
        await self.check_permissions_class()
        thing = await self.service.update(str(thing_id), data.model_dump(exclude_unset=True))
        return self.format_response(
            ThingResponseSchema.model_validate(thing),
            message="Actualizado exitosamente",
        )

    @router.delete("/{thing_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_thing(self, thing_id: uuid.UUID):
        await self.check_permissions_class()
        return await self.delete(thing_id)

    # Custom action
    @router.post("/{thing_id}/activate", response_model=BaseResponse[dict])
    async def activate_thing(self, thing_id: uuid.UUID):
        result = await self.service.my_custom_action(thing_id)
        return self.format_response(result, message="Activado exitosamente")
```

**`self.action` is automatic — do NOT assign it manually.**

`BaseController.__init__` (and `BaseService.__init__`) read `request.scope["endpoint"].__name__` and assign it to `self.action`. So inside every endpoint method, `self.action` already equals that method's name (e.g. inside `list_things`, `self.action == "list_things"`). Branch on it in `get_schema_class()` / `check_permissions()` / `get_filters()` using the method name as the key — no boilerplate `self.action = "..."` line needed.

**Override only if you need a different key** than the method name (rare — usually a sign you should rename the method instead).

**Controller rules (hard):**

| Rule | Why |
|------|-----|
| Branch on `self.action` (auto = method name) — never assign it manually | `BaseController.__init__` reads it from `request.scope["endpoint"].__name__` per request |
| Method names ARE the action keys — name them `verb_noun` (e.g. `list_things`, `update_thing`) | They feed `get_filters()`, `get_schema_class()`, `check_permissions()` dispatch |
| Standard CRUD: `self.list()`, `self.retrieve(id)`, `self.delete(id)` | Inherits pagination, formatting, soft-delete |
| Custom create/update: `self.service.method()` → `self.format_response(Schema.model_validate(obj))` | Consistent wrapping |
| `self.format_response(data, message="...")` — NOT raw `BaseResponse(data=...)` | Uses controller's schema class and standard format |
| `BasePaginationResponse[Schema]` (NOT `BasePaginationResponse[List[Schema]]`) | The class already declares `data: List[T]`; wrapping with `List[]` doubles to `List[List[T]]` and Pydantic validates each row as a list-of-rows, raising `model_attributes_type` 8× per row |
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
        # self.action == "list_things" automatically (auto-set in __init__)
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

**Always generate via CLI — never hand-craft a migration script.**

```bash
# Inside the API container (so it picks up the models + render_item config)
alembic revision --autogenerate -m "add_things_table"
alembic upgrade head

# Output naming (alembic.ini configured): 20250310_1200_abc123_add_things_table.py
make migrate-create   # convenience wrapper (asks for message interactively)
make migrate-up
make migrate-down
```

`alembic/env.py` imports ALL models from `app.models` via `pkgutil.walk_packages` so Alembic detects them all. Adding a new model to `app/models/__init__.py` is enough.

**Workflow rules (hard):**

| Rule | Why |
|------|-----|
| Never edit `alembic/versions/*.py` by hand | Drifts `alembic_version` from the model graph; future autogens emit nonsense diffs |
| Always inspect the generated file before `upgrade head` | Autogen misses things (e.g. server_default changes, `LowercaseEnum` rendering — see §23) |
| Regenerate, don't patch | If the diff is wrong, fix the model + `render_item`, delete the file, run `alembic revision --autogenerate` again |
| Run inside the API container | Local `alembic` binary may resolve to a different env / pickup wrong DB URL |

### ⚠️ ENUM columns — STOP and ask the user

Native `sa.Enum(...)` and database-level ENUM types break autogen in subtle ways:

- Adding a value to an existing enum: autogen emits an `op.alter_column` that may DROP/recreate the column on Postgres, losing data
- Removing a value: silently rejected on upgrade if rows still hold it
- Renaming the enum class: autogen sometimes emits no diff at all
- Switching ENUM ↔ String/`LowercaseEnum`: emits a destructive recreate

**Whenever a change touches an enum column** (adding/removing values, switching enum class, swapping ENUM ↔ String/LowercaseEnum), pause before running `alembic revision --autogenerate` and ask the user how to proceed:

> "This change touches enum `<X>` (model: `<Model.field>`). Autogen's diff is unreliable here — do you want me to: (a) generate and let you review, (b) hand-write the upgrade with explicit `op.execute("ALTER TYPE ...")`, or (c) revert the model change?"

**Prefer `LowercaseEnum` (TypeDecorator on `String`) over native `sa.Enum`** in new models — it stores values as plain strings, so adding/removing enum members is a code-only change with no DDL needed, and `render_item` (§23) handles the autogen rendering cleanly.

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
| Manually assigning `self.action = "..."` | Redundant + diverges from method name; future readers wonder why it's there | `self.action` is auto-set by `BaseController.__init__` to `request.scope["endpoint"].__name__` — branch on it, never assign |
| `response_model=BasePaginationResponse[List[Schema]]` | Returns `data` validated as `List[List[Schema]]`; rows get treated as iterables of `(field_name, value)` tuples → 8 validation errors per row | Drop `List[]` — use `BasePaginationResponse[Schema]`. The class already has `data: List[T]` |
| Hard deleting records | Breaks audit trail | Always `soft_delete()` or `BaseService.delete()` |
| Not adding model import to `app/models/__init__.py` | Alembic doesn't detect table | Import in `__init__.py` |
| `BaseResponse(data=...)` directly in controller | Bypasses `format_response` message/status | Use `self.format_response(data, message=...)` |
| `request.state.db` in auth middleware | `AttributeError` | Use `AsyncSessionFactory()` directly in middleware |
| Beanie: raw ObjectId in filter | Beanie doesn't match Links by raw ID | Use `{"field.$id": object_id}` |
| Accessing `self.db` in SQLAlchemy repo | `AttributeError` | Use `self.session` (stored as `self._session`) |
| Importing `Request`, `AsyncSession`, `get_db` in controller | Breaks separation of concerns, coupling | Those belong only in `dependency.py` |
| Soft-delete not filtered in custom queries | Deleted records appear in results | Always add `.where(Model.deleted_at.is_(None))` |
| Hand-written migration script | Drifts `alembic_version`; future autogens emit garbage | Always `alembic revision --autogenerate -m "..."` — never hand-craft `alembic/versions/*.py` (see §17) |
| Autogen run after touching native `sa.Enum` | Destructive `ALTER TYPE` / silent no-op / data loss | STOP — ask user before generating; prefer `LowercaseEnum` for new fields (see §17 ⚠️ block) |
| Service without `self.repository` attr called by `format_response` | `AttributeError: object has no attribute 'repository'` | Every service used by a `SQLAlchemyBaseController` must expose `self.repository` (real repo or `None`) — see §22 |
| Alembic autogen emits `app.models.types.LowercaseEnum(...)` | `NameError: name 'app' is not defined` at upgrade | Add `LowercaseEnum` to `render_item` in `alembic/env.py` — see §23 |
| `JWTService().encode_token(...)` | `AttributeError: 'JWTService' object has no attribute 'encode_token'` | Real method is `create_token(subject, extra_data=None)` — see §24 |
| Service ctor missing `super().__init__(repository, request=...)` | `format_response` schema lookup fails / `self.action` always `None` | Always call `super().__init__(repository, request=request)` in service `__init__` |

---

## 22. Always extend `BaseService` — even for non-CRUD services

Same uniformity rule as controllers (§25): **every service extends `BaseService`**, even when it doesn't have standard CRUD semantics. You get:

- `self.action` auto-set from `request.scope["endpoint"].__name__` per request — usable in `get_filters()` / `get_kwargs_query()` overrides
- `self.repository` wired automatically (`BaseService.__init__` does `self.repository = repository` and `repository.service = self` if non-None)
- `self.params` dict pre-seeded for `list()` (search/page/count/filters/order_by)
- Consistent constructor shape across the codebase — `super().__init__(repository, request=request)`

`BaseService.__init__` accepts `repository=None` (it has an `if self.repository:` guard internally), so services without a single primary repo still extend cleanly.

### Standard single-repo CRUD service

```python
class UserService(BaseService):
    repository: UserRepository
    search_fields = ["email", "full_name"]
    duplicate_check_fields = ["email"]

    def __init__(self, repository, request=None, session=None):
        super().__init__(repository, request=request)
        self.repository = repository  # explicit alias (BaseService sets it too)
        self.session = session
```

### Multi-repo service — pick a "primary" for `format_response`

Services that depend on several repositories (e.g. `CatalogService` → states + makes + models) still pass ONE primary to `super().__init__`. The other repos hang off `self` as named attrs:

```python
class CatalogService(BaseService):
    repository: VenezuelanStateRepository

    def __init__(self, state_repository, make_repository, model_repository,
                 request=None, session=None):
        super().__init__(state_repository, request=request)  # primary = states
        self.state_repository = state_repository
        self.make_repository = make_repository
        self.model_repository = model_repository
        self.session = session
```

The "primary" should be whatever the controller's default `schema_class` validates — that schema is what `format_response` uses when no `get_schema_class` override fires.

### No-repo service (pure aggregations / cross-cutting)

`AnalyticsService` runs ad-hoc aggregation queries — no single ORM model owns the result. Pass `None`:

```python
class AnalyticsService(BaseService):
    def __init__(self, request=None, session=None):
        super().__init__(None, request=request)  # no primary repository
        self.session = session

    async def dashboard(self) -> dict:
        # raw select(func.count(...)).where(...) over multiple models
        ...
```

When you do this, the controller MUST wrap raw return values in a Pydantic schema before calling `self.format_response(...)` — `format_response` uses `schema.model_validate(data)` on dict input, which fails if the dict shape doesn't match `schema_class`. Either:

```python
# Option A — wrap into a dedicated schema
@router.get("/metrics")
async def metrics(self):
    result = await self.service.metrics()
    return self.format_response(PlatformMetricsSchema(**result), message="OK")
    # data is now a BaseModel instance → format_response passes it through
```

```python
# Option B — define a per-action schema via get_schema_class
def get_schema_class(self) -> Type:
    if self.action == "metrics":
        return PlatformMetricsSchema
    return DealerResponseSchema
```

Combine both for the cleanest pattern: dedicated schema + `get_schema_class` dispatch.

### Why not skip `BaseService` for non-CRUD services?

You can — a plain `class FooService:` with `self.repository = None` works at runtime. But:

1. Future readers can't tell at a glance whether `Foo` is intentionally non-basekit or just outdated.
2. You re-implement the `request`/`action` boilerplate by hand (or omit it and lose `self.action`).
3. When the service eventually needs ONE list endpoint, you have to refactor the constructor.

Cost of extending: one `super().__init__(repository, request=request)` line. Always do it.

---

## 23. Alembic `render_item` for custom column types

Custom `TypeDecorator` columns (`GUID`, `LowercaseEnum`, etc.) make autogen emit `app.models.types.GUID(...)` literals into the migration script — which fail at runtime because the migration file doesn't import `app`. Fix with `render_item` in `alembic/env.py`:

```python
from app.models.types import GUID, LowercaseEnum

def render_item(type_, obj, autogen_context):
    if type_ == "type" and isinstance(obj, GUID):
        return "sa.String(length=36)"
    if type_ == "type" and isinstance(obj, LowercaseEnum):
        length = obj.impl.length or 50
        return f"sa.String(length={length})"
    return False  # default rendering for everything else

# In both run_migrations_offline / do_run_migrations:
context.configure(..., render_item=render_item)
```

Without this, `alembic upgrade head` fails with `NameError: name 'app' is not defined` on the first migration that references the custom type.

---

## 24. JWT integration with `fastapi_basekit.servicios.JWTService`

The library ships a `JWTService` that reads three env vars:

```bash
JWT_SECRET=<secret>          # required
JWT_ALGORITHM=HS256          # default
JWT_EXPIRE_SECONDS=3600      # default 1h
```

Set these in `docker-compose.yml` or `.env`. Real API:

```python
from fastapi_basekit.servicios import JWTService

jwt = JWTService()
token = jwt.create_token(subject=str(user.id), extra_data={"role": "admin"})
payload = jwt.decode_token(token)         # → TokenSchema(sub: str, exp: int)
refreshed = jwt.refresh_token(token)      # extends expiry, same payload
```

The class only emits ONE expiration window (`JWT_EXPIRE_SECONDS`). For per-token-type expirations (access vs refresh), encode manually with `pyjwt`:

```python
import os, time
import jwt as pyjwt

def build_token_pair(user, settings) -> dict:
    secret = os.getenv("JWT_SECRET", settings.SECRET_KEY)
    alg = os.getenv("JWT_ALGORITHM", "HS256")
    now = int(time.time())
    return {
        "access_token": pyjwt.encode(
            {"sub": str(user.id), "exp": now + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60},
            secret, algorithm=alg,
        ),
        "refresh_token": pyjwt.encode(
            {"sub": str(user.id),
             "exp": now + settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
             "type": "refresh"},
            secret, algorithm=alg,
        ),
        "token_type": "bearer",
    }
```

**Do NOT call** `JWTService().encode_token(...)` — that method does not exist. Use `create_token` for single-window tokens, or `pyjwt.encode` directly for asymmetric expirations. `decode_token` always returns `TokenSchema(sub, exp)`; cast `payload.sub` to `UUID` if your model uses UUID PKs.

---

## 25. When to extend `SQLAlchemyBaseController`

**Default: extend it everywhere**, even for controllers that have no standard CRUD endpoints. You get:

- `self.format_response(data, message=, pagination=)` — uniform JSON envelope, schema auto-validation
- `self.get_schema_class()` — switch schema per `self.action` for list vs detail vs custom
- `self.check_permissions()` / `self.check_permissions_class()` — uniform permission enforcement
- `self.action` set automatically from the endpoint function name
- `self._params(skip_frames=2)` — pulls `page`/`count`/`search`/filters from query string

The only requirement: the underlying `service` must expose `.repository` (see §22). `self.action` is filled in automatically — name your endpoint methods `verb_noun` and they'll work as dispatch keys for `get_schema_class()` / `check_permissions()` / `get_filters()`. The boilerplate is minimal and worth it because:

1. Controllers stay uniform across the codebase — same shape, same response envelope.
2. New endpoints fall into `format_response` automatically; no drift to raw `BaseResponse(...)` constructions.
3. `get_schema_class()` lets one controller serve list/detail/custom schemas without duplicating routes.

Only skip extension if the controller is genuinely outside the response-envelope convention (e.g. a webhook receiver returning plain `{"ok": true}` for a third-party integration).

---

## 26. Pinned dependencies (current `fastapi-basekit==0.2.1`)

The library hard-pins:

```
fastapi==0.116.1
pydantic==2.11.7
```

Your project's `requirements.txt` MUST match these (or pip resolves to `ResolutionImpossible`). Compatible companions:

```
fastapi==0.116.1
pydantic[email]==2.11.7
pydantic-settings==2.7.1
fastapi-restful==0.6.0
SQLAlchemy[asyncio]==2.0.36
greenlet==3.1.1
PyJWT==2.10.1            # used by JWTService internally
```

For Postgres async, use `asyncpg==0.30.0` and switch the URL: `postgresql+asyncpg://user:pw@host:5432/db`. For MariaDB/MySQL, `aiomysql==0.2.0` plus `mysql+aiomysql://`.

---

## 27. Cleanup when migrating an existing sync project

When porting a sync SQLAlchemy project to fastapi-basekit:

1. **Wipe alembic versions** (`rm alembic/versions/*.py`) and generate ONE new baseline — UUID PKs and the `GUID` type don't autogenerate cleanly on top of integer-PK history.
2. **Drop `app/database.py`** in favor of `app/config/database.py` (async engine + `AsyncSessionFactory` + `lifespan`). Update every `from app.database import ...` import in models.
3. **Drop `app/core/security.py` + `app/core/deps.py`** — JWT lives in `JWTService` + `AuthenticationMiddleware`, auth dep lives in `app/services/dependency.py:get_dependency_service`.
4. **Move sync DB-touching helpers (matching engines, calculators) to `app/domain/`** as async functions accepting `AsyncSession`. Stale `db.query(...)` calls won't run on `AsyncSession`.
5. **Routers (`app/routers/*.py`) → `app/api/v1/endpoints/<domain>/<resource>.py`** as `@cbv` classes extending `SQLAlchemyBaseController`.
6. **Schemas: `id: int` → `id: uuid.UUID`** in every response model. Pydantic `model_validate` on a SQLAlchemy row with UUID PK silently fails when the schema expects `str`.
7. **Set `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_SECONDS`** in `docker-compose.yml` env so `JWTService()` picks them up — do not rely on the library's `secret_dev_key` default.
8. **Soft-delete every domain table going forward** — basekit's `BaseRepository` and example services assume `deleted_at` exists. Always filter `.where(Model.deleted_at.is_(None))` in custom queries; the default `build_list_queryset` does not filter for you unless you override it to do so.

---

## 28. `get_db` stays lean — error translation lives in handlers, not the generator

The async `get_db` dependency must do ONE thing: yield a session, commit on success, rollback + reraise on failure. Domain-specific error translation (e.g. duplicate-email → friendly message) belongs in `app/utils/exception_handlers.py`, registered at app startup with `app.add_exception_handler(IntegrityError, integrity_error_handler)`.

```python
# app/config/database.py — CORRECT
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

```python
# app/utils/exception_handlers.py — translation lives HERE
async def integrity_error_handler(request: Request, exc: IntegrityError):
    error_msg = str(exc.orig).lower()
    if "email" in error_msg and ("duplicate" in error_msg or "unique" in error_msg):
        message = "Email ya en uso"
    elif "foreign key" in error_msg:
        message = "Registro relacionado no existe"
    else:
        message = "Error de integridad en la base de datos"
    return JSONResponse(
        status_code=400,
        content=BaseResponse(
            status="DATABASE_INTEGRITY_ERROR", message=message, data=None
        ).model_dump(),
    )

# app/main.py
from sqlalchemy.exc import IntegrityError
app.add_exception_handler(IntegrityError, integrity_error_handler)
```

**Why:**
- Single responsibility — `get_db` only manages the session lifecycle.
- The handler runs in the regular FastAPI middleware chain, so it composes with `BaseResponse`, the OpenAPI schema, and other handlers.
- Error matchers (column names, constraint names) belong with the per-project domain knowledge, not buried in infrastructure code.
- Pre-emptive validation in services (e.g. `await repo.get_by_email(email)` before insert) catches duplicates before the DB roundtrip; `IntegrityError` only fires on race conditions, where the global handler is the safety net.

**Anti-pattern (don't do this):** the `mariadb-template`-style `get_db` that walks the error message and raises `DatabaseIntegrityException` inline. It mixes session management with domain rules and forces every project to copy/paste the same conditional ladder.
