# Services

`BaseService` — capa de lógica de negocio entre controller y repository.

## Setup mínimo

```python
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService

class ThingService(BaseService):
    repository: ThingRepository
    search_fields = ["name", "description"]
    duplicate_check_fields = ["slug"]

    def __init__(self, repository, request=None, session=None):
        super().__init__(repository, request=request)
        self.repository = repository
        self.session = session
```

## API heredada

| Método | Comportamiento |
|---|---|
| `await service.list(...)` | Paginado vía `repo.list_paginated()`, aplica `get_filters()` + `get_kwargs_query()` + `search_fields` |
| `await service.retrieve(id, joins=None)` | `repo.get_with_joins()` con fallback a `repo.get()` → `NotFoundException` si no existe |
| `await service.create(payload, check_fields=None)` | Valida `duplicate_check_fields`, crea via `repo.create()` |
| `await service.update(id, payload)` | `repo.update()` con `exclude_unset=True` si payload es BaseModel |
| `await service.delete(id)` | `repo.delete()` |

## Hooks de extensión

### `get_filters()` — scoping automático

Filtros aplicados a TODA query de listado/búsqueda. Útil para multi-tenant:

```python
def get_filters(self, filters: dict | None = None) -> dict:
    filters = filters or {}
    user = getattr(self.request.state, "user", None)
    if user and user.company_id and not user.is_platform_admin:
        filters["company_id"] = user.company_id
    return filters
```

### `get_kwargs_query()` — joins por acción

```python
def get_kwargs_query(self) -> dict:
    if self.action in ("list_users", "retrieve"):
        return {"joins": ["user_roles", "company"]}
    return {}
```

`self.action` se autopobla del nombre del endpoint (ver [Controllers](controllers.md)).

### Override `create()` para lógica custom

```python
async def create(self, payload, check_fields=None):
    data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)

    user = getattr(self.request.state, "user", None)
    if user and user.company_id:
        data["company_id"] = user.company_id

    return await super().create(data, check_fields)
```

## Servicios sin repo principal

Servicios cross-cutting (analytics, dashboards, multi-repo) **igual extienden `BaseService`** — pasa `None` o un repo "primary":

```python
class AnalyticsService(BaseService):
    def __init__(self, request=None, session=None):
        super().__init__(None, request=request)   # no primary repo
        self.session = session

    async def dashboard(self) -> dict:
        # raw select(...).where(...) sobre múltiples modelos
        ...
```

Multi-repo: pasa el "primary" al super, otros como attrs:

```python
class CatalogService(BaseService):
    repository: StateRepository

    def __init__(self, state_repo, make_repo, model_repo, request=None, session=None):
        super().__init__(state_repo, request=request)
        self.state_repository = state_repo
        self.make_repository = make_repo
        self.model_repository = model_repo
```

!!! tip "¿Por qué SIEMPRE extender BaseService?"
    Aunque tu service no tenga CRUD: ganas `self.action` auto-set, `request.scope["endpoint"]` wiring, `params` dict, repo `service` back-reference. Costo: 1 línea `super().__init__(...)`. Beneficio: shape uniforme en todo el codebase.

## Métodos custom (lógica de negocio)

```python
async def publish(self, thing_id: UUID) -> dict:
    thing = await self.repository.get(thing_id)
    if not thing:
        raise NotFoundException("Thing no encontrado")
    if thing.status != ThingStatus.draft:
        raise ValidationException("Solo drafts se pueden publicar")

    thing.status = ThingStatus.published
    thing.published_at = datetime.now(tz=timezone.utc)
    await self.session.flush()
    return {"id": str(thing.id), "status": thing.status.value}
```

Llamado desde controller:
```python
@router.post("/{thing_id}/publish", response_model=BaseResponse[dict])
async def publish_thing(self, thing_id: uuid.UUID):
    result = await self.service.publish(thing_id)
    return self.format_response(result, message="Publicado")
```

[:octicons-arrow-right-24: Repositories](repositories.md){ .md-button .md-button--primary }
