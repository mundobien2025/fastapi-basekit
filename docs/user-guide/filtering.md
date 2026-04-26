# Filtrado

## Filtros simples (query string)

```http
GET /api/v1/things/?status=active&category_id=abc-123
```

Auto-aplicados por `BaseController._params(skip_frames=2)` — cualquier query param que NO sea `page`/`count`/`search`/`order_by` se vuelve filtro.

## Filtros con relaciones (sintaxis `__`)

```http
GET /api/v1/things/?owner__role__code=admin
GET /api/v1/things/?category__name=Premium
```

`BaseRepository._resolve_attribute()` parsea la ruta y agrega los JOINs necesarios automáticamente.

## Filtros IN

Pasa lista al filter dict:

```python
items = await repo.get_by_filters({"status": ["active", "pending"]})
# → WHERE status IN ('active', 'pending')
```

Desde HTTP, repite el param:
```http
?status=active&status=pending
```

## Filtros OR

```python
return await self.list(use_or=True)
# → WHERE status='active' OR category_id='...'
```

## Filtros forzados (del service)

```python
def get_filters(self, filters: dict | None = None) -> dict:
    filters = filters or {}
    user = getattr(self.request.state, "user", None)
    if user and not user.is_platform_admin:
        filters["company_id"] = user.company_id
    return filters
```

Este filtro NO se puede sobreescribir por query string.

## Filtros enum

Pydantic `Enum` se serializa a su `.value` automáticamente:

```python
items = await repo.get_by_filters({"status": ThingStatus.active})
# → WHERE status = 'active'
```

## Soft delete + filtros

Soft-delete NO se aplica automáticamente. Override `build_list_queryset`:

```python
def build_list_queryset(self, **kwargs):
    return select(self.model).where(self.model.deleted_at.is_(None))
```
