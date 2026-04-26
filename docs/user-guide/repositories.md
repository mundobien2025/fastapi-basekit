# Repositories

`BaseRepository` — acceso a datos. Extiende, declara `model`, listo.

## Setup mínimo

```python
from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from app.models.thing import Thing


class ThingRepository(BaseRepository):
    model = Thing
```

## API CRUD

```python
# Por ID
thing = await repo.get(thing_id)
thing = await repo.get_with_joins(thing_id, joins=["category", "tags"])

# Por campo
thing = await repo.get_by_field("slug", "my-thing")
thing = await repo.get_by_field_with_joins("slug", "my-thing", joins=["category"])

# Multi-filtros
items = await repo.get_by_filters({"status": "active", "company_id": cid})
items = await repo.get_by_filters({"status": ["active", "pending"]})  # IN
items = await repo.get_by_filters({"status": "active"}, use_or=False)

# Filtros con relaciones (sintaxis __)
admins = await repo.get_by_filters({"user_roles__role__code": "admin"})

# Paginado + búsqueda + ordenamiento
items, total = await repo.list_paginated(
    page=1,
    count=20,
    filters={"status": "active"},
    search="foo",
    search_fields=["name", "description"],
    order_by="-created_at",
    joins=["category"],
)

# Mutaciones
created = await repo.create({"name": "Foo", "slug": "foo"})
updated = await repo.update(thing_id, {"name": "Bar"})
deleted = await repo.delete(thing_id)
```

!!! warning "`update` recibe dict positional"
    `repo.update(id, {"field": value})` — NO kwargs. `repo.update(id, field=value)` lanza TypeError.

## Soft delete

`BaseModel` provee `deleted_at`. Override `build_list_queryset` para filtrar:

```python
from sqlalchemy import select

class ThingRepository(BaseRepository):
    model = Thing

    def build_list_queryset(self, **kwargs):
        return select(self.model).where(self.model.deleted_at.is_(None))
```

!!! danger "El default NO filtra"
    `BaseRepository.build_list_queryset()` retorna `select(self.model)` sin filtro de `deleted_at`. Si quieres soft-delete transparente, override siempre.

Soft-delete via service:
```python
thing = await repo.get(thing_id)
thing.soft_delete()           # setea deleted_at = now
await session.flush()
```

## Querysets enriquecidos

`build_list_queryset` puede agregar columnas calculadas — el schema las consume directo:

```python
from sqlalchemy import select, func
from app.models.role import Roles, UserRoles


class RoleRepository(BaseRepository):
    model = Roles

    def build_list_queryset(self, **kwargs):
        member_count = (
            select(func.count(UserRoles.user_id))
            .where(UserRoles.role_id == Roles.id)
            .scalar_subquery()
            .label("member_count")
        )
        return select(Roles, member_count)
```

```python
class RoleResponseSchema(BaseSchema):
    id: uuid.UUID
    code: str
    member_count: int   # ← consumido directo
```

`list_paginated` ya hidrata el atributo extra en cada row.

## Métodos custom

Solo cuando `BaseRepository` no cubre. Ejemplos comunes:

```python
async def get_by_email(self, email: str) -> Users | None:
    result = await self.session.execute(
        select(Users).where(
            Users.email == email,
            Users.deleted_at.is_(None),
        )
    )
    return result.scalars().first()


async def get_with_relations(self, thing_id: UUID) -> Thing | None:
    stmt = (
        select(Thing)
        .options(
            selectinload(Thing.category),
            selectinload(Thing.tags),
        )
        .where(Thing.id == thing_id, Thing.deleted_at.is_(None))
    )
    result = await self.session.execute(stmt)
    return result.scalars().first()
```

!!! tip "Filtros `deleted_at.is_(None)` en TODAS tus queries custom"
    Es responsabilidad tuya. La lib no inyecta el filtro automáticamente fuera de `build_list_queryset`.

## Beanie variant

```python
from fastapi_basekit.aio.beanie.repository.base import BeanieBaseRepository

class ThingRepository(BeanieBaseRepository):
    model = Thing

    async def get_by_user(self, user_id) -> list[Thing]:
        return await Thing.find({"user.$id": user_id}).to_list()

    async def get_with_links(self, thing_id) -> Thing | None:
        return await Thing.get(thing_id, fetch_links=True)
```

[:octicons-arrow-right-24: Paginación](pagination.md){ .md-button .md-button--primary }
