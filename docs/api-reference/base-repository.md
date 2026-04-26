# `BaseRepository`

::: fastapi_basekit.aio.sqlalchemy.repository.base.BaseRepository
    options:
      show_source: true
      members:
        - get
        - get_by_field
        - get_by_filters
        - get_with_joins
        - get_by_field_with_joins
        - get_by_filters_with_joins
        - list_paginated
        - build_list_queryset
        - apply_list_filters
        - create
        - update
        - delete

## Construcción

```python
class ThingRepository(BaseRepository):
    model = Thing                    # ← obligatorio
```

## API

```python
# Por ID
thing = await repo.get(thing_id)
thing = await repo.get_with_joins(thing_id, joins=["category"])

# Por campo
user = await repo.get_by_email("foo@bar.com")  # método custom tuyo
user = await repo.get_by_field("email", "foo@bar.com")  # genérico

# Filtros (con sintaxis __ para relaciones)
items = await repo.get_by_filters({"status": "active"})
admins = await repo.get_by_filters({"user_roles__role__code": "admin"})

# Paginado
items, total = await repo.list_paginated(
    page=1, count=20,
    filters={"status": "active"},
    search="foo",
    search_fields=["name"],
    order_by="-created_at",
    joins=["category"],
)

# Mutaciones
created = await repo.create({"name": "Foo"})
updated = await repo.update(thing_id, {"name": "Bar"})   # dict positional
deleted = await repo.delete(thing_id)                    # hard delete
```

## Override `build_list_queryset`

Para queries enriquecidos o soft-delete:

```python
def build_list_queryset(self, **kwargs):
    return select(self.model).where(self.model.deleted_at.is_(None))
```

## Variantes

- `fastapi_basekit.aio.sqlalchemy.repository.base.BaseRepository`
- `fastapi_basekit.aio.sqlmodel.repository.base.BaseRepository`
- `fastapi_basekit.aio.beanie.repository.base.BeanieBaseRepository`

[:octicons-arrow-right-24: Patrón](../user-guide/repositories.md){ .md-button .md-button--primary }
