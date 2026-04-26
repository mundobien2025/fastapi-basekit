# Ordenamiento

## Query string

```http
GET /api/v1/things/?order_by=created_at        # ASC
GET /api/v1/things/?order_by=-created_at       # DESC (prefijo -)
GET /api/v1/things/?order_by=name              # alfabético
```

## Default por service

```python
class ThingService(BaseService):
    order_by = "-created_at"   # default
```

Cliente puede overridear con `?order_by=name`.

## Ordenamiento con relaciones

```http
GET /api/v1/things/?order_by=category__name
GET /api/v1/things/?order_by=-owner__email
```

`BaseRepository._resolve_order_by()` agrega los JOINs.

## Campos especiales (aliases)

Si el queryset enriquecido expone columnas calculadas con un alias:

```python
def build_list_queryset(self, **kwargs):
    member_count = (
        select(func.count(UserRoles.user_id))
        .where(UserRoles.role_id == Roles.id)
        .scalar_subquery()
        .label("member_count")
    )
    return select(Roles, member_count)
```

`?order_by=-member_count` no funciona out-of-the-box. Pasa `special_fields`:

```python
# en service
async def list_paginated(self, ...):
    return await self.repository.list_paginated(
        ...,
        special_fields={"member_count": Roles.id},  # mapea alias a expresión
    )
```

## Expresiones SQLAlchemy directas

Desde código:
```python
from app.models.thing import Thing

await self.list(order_by=Thing.created_at.desc())
```

`order_by` acepta string o expresión Pydantic — el repo detecta y procesa.
