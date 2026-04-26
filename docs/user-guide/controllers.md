# Controllers

## Pattern: `@cbv` + `SQLAlchemyBaseController`

Class-based views de `fastapi-restful`. Una clase, múltiples endpoints, dependencies compartidas.

```python
from fastapi import APIRouter, Depends, Query
from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from fastapi_basekit.schema.base import BasePaginationResponse, BaseResponse
from fastapi_restful.cbv import cbv

router = APIRouter(prefix="/things")


@cbv(router)
class ThingController(SQLAlchemyBaseController):
    service: ThingService = Depends(get_thing_service)
    schema_class = ThingResponseSchema
    user: Users = Depends(get_dependency_service)
```

## `self.action` — automático

`BaseController.__init__` lee `request.scope["endpoint"].__name__` y lo asigna a `self.action`. Dentro de cada método, `self.action` ya equivale al nombre del método.

!!! danger "No asignes `self.action` manualmente"
    ```python
    async def list_things(self):
        self.action = "list_things"   # ❌ redundante
        return await self.list()
    ```

    Bórralo. Branches en `get_schema_class()` / `check_permissions()` / `get_filters()` usan `self.action == "list_things"` y eso ya está poblado.

## CRUD heredado

Cuatro métodos del base manejan todo:

| Método | Qué hace |
|---|---|
| `await self.list()` | `service.list()` + paginación + `format_response` |
| `await self.retrieve(id)` | `service.retrieve(id)` + `format_response` |
| `await self.create(payload)` | `service.create(payload)` + `format_response` |
| `await self.update(id, payload)` | `service.update(id, payload)` + `format_response` |
| `await self.delete(id)` | `service.delete(id)` + `format_response` |

```python
@router.get("/", response_model=BasePaginationResponse[ThingResponseSchema])
async def list_things(
    self,
    page: int = Query(1, ge=1),
    count: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
):
    return await self.list()
```

!!! warning "BasePaginationResponse[Schema], NO BasePaginationResponse[List[Schema]]"
    `BasePaginationResponse` ya declara `data: List[T]`. Wrappear con `List[]` doblanida y Pydantic valida cada fila como lista-de-filas → 8 errores por row.

## Acción custom

```python
@router.post("/{thing_id}/activate", response_model=BaseResponse[dict])
async def activate_thing(self, thing_id: uuid.UUID):
    result = await self.service.activate(thing_id)
    return self.format_response(result, message="Activado")
```

## `format_response` — único punto de salida

```python
self.format_response(data)                          # default schema_class + status="success"
self.format_response(data, message="Custom msg")
self.format_response(data, response_status="warning")
self.format_response(items, pagination={...})       # forces BasePaginationResponse
```

Bypass solo si construyes la respuesta tú (raro): `BaseResponse(data=..., message=..., status=...)`.

## Schema dinámico — `get_schema_class()`

Diferente schema por acción:

```python
def get_schema_class(self) -> Type:
    if self.action == "list_things":
        return ThingListResponseSchema       # versión slim
    return ThingDetailResponseSchema         # default
```

## Permisos por acción — `check_permissions()`

```python
from app.permissions.thing import ThingAdminPermission

def check_permissions(self):
    if self.action in ("delete_thing", "update_thing"):
        return [ThingAdminPermission]
    return []

@router.delete("/{thing_id}")
async def delete_thing(self, thing_id: uuid.UUID):
    await self.check_permissions_class()   # dispara verificación
    return await self.delete(thing_id)
```

## Reglas duras

| Regla | Razón |
|---|---|
| Branch en `self.action` (auto) — nunca asignar manual | `BaseController.__init__` ya lo setea |
| Method names = action keys, formato `verb_noun` | Feed para `get_filters()` / `get_schema_class()` / `check_permissions()` |
| Standard CRUD: `self.list()` / `self.retrieve(id)` / `self.delete(id)` | Hereda paginación, format, soft-delete |
| Custom: `self.service.method()` → `self.format_response(Schema.model_validate(obj))` | Wrapping consistente |
| `BasePaginationResponse[Schema]` (sin List wrapper) | `data: List[T]` ya declarado en base |
| `id: uuid.UUID` en response schemas | `model_validate` con UUID PK falla con `str` |
| Nunca importar `Request`, `AsyncSession`, `get_db` en controller | Concerns de dependency.py |
| `get_thing_service` factory vive en `dependency.py` | Reusable, separation of concerns |

[:octicons-arrow-right-24: Services](services.md){ .md-button .md-button--primary }
