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

### Row-level scoping / multi-tenant

Este es **el** seam para restringir QUÉ filas ve cada usuario (multi-tenant,
permisos por empresa, ownership). Va acá, **no** en un override de
`Service.list`: `list_paginated` llama `self.build_list_queryset()` como base y
luego aplica search + paginación encima, así que el alcance queda
**enforced en la DB**, aplica a toda lista sin importar quién llame, y no
duplica lógica ni rompe la paginación.

El contexto del request está disponible vía `self.service.request`:

```python
from sqlalchemy import exists, select

def build_list_queryset(self, **kwargs):
    query = select(self.model)
    req = getattr(self.service, "request", None)
    user = getattr(req.state, "user", None) if req else None
    roles = getattr(req.state, "user_role_codes", []) if req else []

    # Staff global ve todo; el resto solo su empresa + las permitidas
    if not any(r in {"admin_global"} for r in roles) and user and user.company_id:
        query = query.where(
            (self.model.company_id == user.company_id)
            | exists(
                select(1).where(
                    CompanyPermissions.company_id == user.company_id,
                    CompanyPermissions.permitted_company_id == self.model.id,
                )
            )
        )
    return query
```

Ojo: **permiso ≠ alcance**. El permiso (middleware / `endpoint_permissions`)
decide si el usuario ENTRA al endpoint; `build_list_queryset` decide QUÉ filas
ve. Son capas independientes — no metas el scoping de filas en la capa de
permisos ni al revés.

## Variantes

- `fastapi_basekit.aio.sqlalchemy.repository.base.BaseRepository`
- `fastapi_basekit.aio.sqlmodel.repository.base.BaseRepository`
- `fastapi_basekit.aio.beanie.repository.base.BeanieBaseRepository`

## Beanie — hooks de extensión (0.3.2+)

Beanie expone dos hooks paralelos al `build_list_queryset` de SQLAlchemy
+ un runner de aggregation con paginación atómica:

```python
class UserRepository(BeanieBaseRepository):
    model = User

    # FindMany path — equivalente directo de build_list_queryset SQL
    def build_list_queryset(self, search=None, search_fields=None,
                            filters=None, order_by=None, **kwargs):
        return self.build_filter_query(
            search=search, search_fields=search_fields or [],
            filters=filters or {}, order_by=order_by, **kwargs,
        )

    # Aggregation path — para subqueries cross-collection
    def build_list_pipeline(self, search=None, search_fields=None,
                            filters=None, order_by=None, **kwargs):
        # default: $match + $sort (con auto-$lookup en nested order)
        # override para añadir $lookup/$project/$group
        ...
```

`paginate_pipeline(pipeline, page, count, validate=True)` envuelve el
pipeline con `$facet` (`data` + `metadata.total` en una sola query).
`validate=False` cuando el `$project` produce shape distinta del modelo.

[:octicons-arrow-right-24: Patrón](../user-guide/repositories.md){ .md-button .md-button--primary }
