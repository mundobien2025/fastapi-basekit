# Búsqueda textual

## `search_fields` en el service

```python
class ThingService(BaseService):
    search_fields = ["name", "description", "slug"]
```

## Request

```http
GET /api/v1/things/?search=foo
```

Aplica `WHERE (name ILIKE '%foo%' OR description ILIKE '%foo%' OR slug ILIKE '%foo%')`.

## Búsqueda con relaciones

```python
search_fields = ["name", "category__name", "owner__email"]
```

`?search=alice` busca en `things.name`, `categories.name`, `users.email` con OR + JOINs automáticos.

## Combinado con filtros

```http
GET /api/v1/things/?search=foo&status=active&category_id=abc-123
```

→ `WHERE (search_condition) AND status='active' AND category_id='abc-123'`

## Case-sensitive

`search_fields` usa `ILIKE` (case-insensitive en Postgres/SQLite, `LIKE` con collation case-insensitive en MariaDB). Para case-sensitive, override `_build_search_condition` en el repo.

## Beanie (MongoDB)

```python
class ThingRepository(BeanieBaseRepository):
    model = Thing

    async def search(self, term: str) -> list[Thing]:
        return await Thing.find(
            {"$or": [
                {"name": {"$regex": term, "$options": "i"}},
                {"description": {"$regex": term, "$options": "i"}},
            ]}
        ).to_list()
```
