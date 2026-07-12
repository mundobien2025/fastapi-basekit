# Paginación

Built-in en `BaseService.list()` + `BaseRepository.list_paginated()`. El controller solo declara los Query params.

## Endpoint paginado

```python
@router.get("/", response_model=BasePaginationResponse[ThingResponseSchema])
async def list_things(
    self,
    page: int = Query(1, ge=1),
    count: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
):
    return await self.list()
```

`self.list()` lee los params del request, llama `service.list()`, calcula `total_pages`, retorna `BasePaginationResponse`.

## Request

```http
GET /api/v1/things/?page=2&count=20&search=foo&order_by=-created_at
```

## Response shape

```json
{
  "data": [
    { "id": "...", "name": "Thing 1" },
    { "id": "...", "name": "Thing 2" }
  ],
  "pagination": {
    "page": 2,
    "count": 20,
    "total": 153,
    "total_pages": 8
  },
  "message": "Operación exitosa",
  "status": "success"
}
```

## Search

```python
class ThingService(BaseService):
    search_fields = ["name", "description", "slug"]
```

`?search=foo` aplica `ILIKE %foo%` (case-insensitive) sobre los campos listados, combinados con OR.

Soporta paths anidados:
```python
search_fields = ["name", "category__name", "owner__email"]
```

`list_paginated` agrega los JOINs necesarios automáticamente.

## Ordenamiento — `order_by`

```http
GET /api/v1/things/?order_by=created_at        # ASC
GET /api/v1/things/?order_by=-created_at       # DESC
GET /api/v1/things/?order_by=category__name    # JOIN + ASC
GET /api/v1/things/?order_by=-owner__email     # JOIN + DESC
```

Default por servicio:
```python
class ThingService(BaseService):
    order_by = "-created_at"   # default si el cliente no lo pasa
```

## Filtros desde query string

Cualquier query param que NO sea `page`/`count`/`search`/`order_by` se trata como filtro:

```http
GET /api/v1/things/?status=active&category_id=abc-123
```

Equivale a `WHERE status='active' AND category_id='abc-123'`.

Filtros con relaciones:
```http
GET /api/v1/things/?owner__role__code=admin
```

## Filtros forzados desde el service

Para multi-tenant, sobreescribe `get_filters`:

```python
def get_filters(self, filters: dict | None = None) -> dict:
    filters = filters or {}
    user = getattr(self.request.state, "user", None)
    if user and not user.is_platform_admin:
        filters["company_id"] = user.company_id   # forzado, no overrideable por client
    return filters
```

El cliente NO puede saltarse estos filtros desde query string.

## OR en lugar de AND

Default es AND entre filtros. Para OR, llama explícito desde controller:

```python
async def list_things(self, page=Query(1), count=Query(10)):
    return await self.list(use_or=True)
```

## Eager loading — `joins`

Por acción:
```python
def get_kwargs_query(self) -> dict:
    if self.action in ("list_things", "retrieve"):
        return {"joins": ["category", "tags"]}
    return {}
```

O explícito:
```python
async def list_things(self):
    return await self.list(joins=["category"])
```

`joins` aplica `selectinload` (relación 1:N) o `joinedload` (relación N:1) automáticamente según el tipo.

## Enriquecer los items de la página — `post_process_list` (0.5.0)

Para agregar un campo derivado o un contador a cada fila DESPUÉS de paginar, sin
reescribir la paginación ni overridear `list()`:

```python
class ThingService(BaseService):
    async def post_process_list(self, items):
        ids = [t.id for t in items]
        counts = await self.child_repo.count_by_parent_ids(ids)
        for t in items:
            t.child_count = counts.get(t.id, 0)
        return items
```

Corre sobre los items de la página actual; no cambia `total` ni filtra (para
filtrar usá `get_filters`/`build_list_queryset`).

!!! danger "El motor de paginación NO se reescribe"
    El `count`/`skip`/`offset`/`limit`/`$facet` vive en el repo base
    (`list_paginated` SQL, `paginate`/`paginate_pipeline` Beanie) y no se copia.
    Toda personalización baja por un hook. Mapa completo caso→hook:
    **[Puntos de Extensión (Listados)](../pagination-extension-points.md)**.

[:octicons-arrow-right-24: Filtros avanzados](filtering.md){ .md-button .md-button--primary }
