---
name: fastapi-basekit-crud
description: >
  Complete guide for building a new CRUD resource with fastapi-basekit (SQLAlchemy async).
  Use proactively when: creating a new API endpoint, model, service, repository, or controller
  in any FastAPI project that uses fastapi-basekit. Covers the full stack: SQLAlchemy model,
  Pydantic schemas, BaseRepository, BaseService, CBV controller (@cbv from fastapi_restful),
  and dependency factory in dependency.py. Also trigger when verifying/fixing a controller
  pattern, checking if a service/repo is built correctly, or scaffolding a new feature module.
  Do NOT trigger for Beanie/MongoDB — this skill is SQLAlchemy-only.
tools: Read, Edit, Write, Bash, Glob, Grep
---

# fastapi-basekit CRUD — Full Stack Pattern

This skill scaffolds and validates the complete pattern for a new resource in a FastAPI project
using `fastapi-basekit` with SQLAlchemy async.

## Architecture overview

```
app/
├── models/resource.py          ← SQLAlchemy ORM model
├── schemas/resource.py         ← Pydantic schemas (Create, Update, Response)
├── repositories/resource/
│   ├── __init__.py
│   └── repository.py           ← BaseRepository subclass
├── services/
│   ├── resource_service.py     ← BaseService subclass (business logic)
│   └── dependency.py           ← get_resource_service() factory ← ALWAYS HERE
└── api/v1/endpoints/resource/
    ├── __init__.py
    └── controller.py           ← @cbv(router) class
```

---

## Step 1: Read existing code first

Before generating anything, scan what already exists:
```bash
find app/ -name "*.py" | head -30
```
Read the closest existing controller and service as style reference.
Match the project's base model class (UUID vs int PK, soft-delete pattern, etc).

---

## Step 2: SQLAlchemy Model

```python
# app/models/resource.py
import uuid
from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel  # project's base (has id, created_at, updated_at, soft-delete)

class Resource(BaseModel):
    __tablename__ = "resources"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

Add the import to `app/models/__init__.py` so Alembic detects it.

---

## Step 3: Pydantic Schemas

```python
# app/schemas/resource.py
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ResourceCreateSchema(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True
    model_config = ConfigDict(extra="ignore")

class ResourceUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    model_config = ConfigDict(extra="ignore")

class ResourceResponseSchema(BaseModel):
    id: uuid.UUID          # MUST be uuid.UUID (not str) for model_validate to work
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**Key rule:** `id` field type in response schema must be `uuid.UUID`, not `str`.
`model_validate(orm_obj)` fails silently or raises if types don't match.

---

## Step 4: Repository

```python
# app/repositories/resource/repository.py
from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from app.models.resource import Resource

class ResourceRepository(BaseRepository):
    model = Resource

    # Add custom query methods here ONLY if BaseRepository doesn't cover the need
    # DO NOT add CRUD here — BaseRepository already handles get, list, create, update, delete
```

`BaseRepository` provides: `get(id)`, `list_paginated(...)`, `create(data)`, `update(id, data_dict)`, `delete(id)`.
`self.session` is the AsyncSession. Constructor param is `db` but stored as `self._session`.

---

## Step 5: Service

```python
# app/services/resource_service.py
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
from app.repositories.resource.repository import ResourceRepository

class ResourceService(BaseService):
    search_fields = ["name"]              # fields for ?search= query param
    duplicate_check_fields = ["name"]     # checked on create for uniqueness

    # repo is accessible as self.repository
    # self.request is the FastAPI Request (injected by dependency)

    # Add custom business logic methods here:
    async def my_custom_action(self, resource_id: uuid.UUID) -> dict:
        resource = await self.repository.get(resource_id)
        if not resource:
            raise ValueError(f"Resource {resource_id} not found")
        # ... logic ...
        return {"result": "ok"}
```

---

## Step 6: Dependency factory — ALWAYS in `dependency.py`

```python
# app/services/dependency.py  (ADD to existing file, never create a new one)
from app.repositories.resource.repository import ResourceRepository
from app.services.resource_service import ResourceService

def get_resource_service(request: Request, db: AsyncSession = Depends(get_db)) -> ResourceService:
    repo = ResourceRepository(db=db)
    return ResourceService(repository=repo, request=request)
```

**Never** put this factory inside the controller file.

---

## Step 7: Controller — CBV pattern with @cbv

```python
# app/api/v1/endpoints/resource/controller.py
import uuid
from typing import List

from fastapi import APIRouter, Depends, Query, status
from fastapi_restful.cbv import cbv

from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from fastapi_basekit.schema.base import BasePaginationResponse, BaseResponse

from app.models.auth import Users
from app.schemas.resource import ResourceCreateSchema, ResourceResponseSchema, ResourceUpdateSchema
from app.services.dependency import get_dependency_service, get_resource_service
from app.services.resource_service import ResourceService

router = APIRouter(prefix="/resources", tags=["Resources"])

@cbv(router)
class ResourceController(SQLAlchemyBaseController):

    service: ResourceService = Depends(get_resource_service)
    schema_class = ResourceResponseSchema
    user: Users = Depends(get_dependency_service)   # auth guard (omit if no auth needed)

    @router.get("/", response_model=BasePaginationResponse[ResourceResponseSchema])
    async def list(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(20, ge=1, le=100),
    ):
        return await super().list()

    @router.post("/", response_model=BaseResponse[ResourceResponseSchema], status_code=201)
    async def create(self, data: ResourceCreateSchema):
        resource = await self.service.create(data)           # BaseService.create()
        return BaseResponse(data=ResourceResponseSchema.model_validate(resource))

    @router.get("/{id}", response_model=BaseResponse[ResourceResponseSchema])
    async def get(self, id: uuid.UUID):
        return await super().retrieve(id)

    @router.patch("/{id}", response_model=BaseResponse[ResourceResponseSchema])
    async def update(self, id: uuid.UUID, data: ResourceUpdateSchema):
        resource = await self.service.update(str(id), data)  # BaseService.update()
        return BaseResponse(data=ResourceResponseSchema.model_validate(resource))

    @router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete(self, id: uuid.UUID):
        return await super().delete(id)

    # Custom action — follows the same pattern as above
    @router.post("/{id}/activate", response_model=BaseResponse[dict])
    async def activate(self, id: uuid.UUID):
        result = await self.service.my_custom_action(id)
        return BaseResponse(data=result)
```

### Controller rules (HARD)

| Rule | Why |
|------|-----|
| `get_xyz_service` factory lives in `dependency.py` only | Separation of concerns; reusable across controllers |
| Standard CRUD: always `super().list()`, `super().retrieve(id)`, `super().delete(id)` | Inherits pagination, formatting, error handling |
| Custom create/update: `self.service.method()` → `BaseResponse(data=Schema.model_validate(obj))` | Consistent response wrapping |
| Custom actions: same as above — `self.service.action(id)` → `BaseResponse(data=result)` | |
| NEVER import `Request`, `AsyncSession`, `get_db`, or repo classes in the controller | Those are dependency concerns |
| `BasePaginationResponse[List[Schema]]` — use `List` from `typing`, not built-in `list` | CBV class bodies require it |
| `id: uuid.UUID` in response schema | `model_validate` fails if `id` is typed as `str` |

---

## Step 8: Register the router

```python
# app/api/v1/routers.py
from app.api.v1.endpoints.resource.controller import router as resource_router
# ... include in api_v1_router:
api_v1_router.include_router(resource_router)
```

---

## Step 9: Alembic migration

```bash
uv run alembic revision --autogenerate -m "add_resources_table"
uv run alembic upgrade head
```

---

## Common pitfalls

| Mistake | Symptom | Fix |
|---------|---------|-----|
| `id: str` in response schema | `model_validate` returns wrong id or errors | Change to `id: uuid.UUID` |
| Factory in controller file | Hard to reuse, hidden dependency | Move to `dependency.py` |
| `list` instead of `List` in `BasePaginationResponse[list[...]]` in `@cbv` | TypeError in class body | Import `from typing import List` |
| Calling `repo.list_paginated()` directly from controller | Bypasses service, inconsistent | Use `super().list()` |
| Not adding model to `__init__.py` | Alembic doesn't detect the table | Import in `app/models/__init__.py` |
| `self.repository.update(id, **kwargs)` | Wrong signature | Use `self.repository.update(id, {"key": val})` — dict, not kwargs |
