# `BaseController`

Controller base agnóstico de ORM.

::: fastapi_basekit.aio.controller.base.BaseController
    options:
      show_source: true
      members:
        - format_response
        - get_schema_class
        - check_permissions
        - check_permissions_class
        - to_dict
        - _params

## Atributos de clase

| Atributo | Tipo | Default | Descripción |
|---|---|---|---|
| `service` | `Depends()` | required | Service inyectado |
| `schema_class` | `Type[BaseModel]` | required | Schema para serializar response |
| `action` | `Optional[str]` | None | Auto-set a `request.scope["endpoint"].__name__` |
| `request` | `Request` | injected | FastAPI request |

## Comportamiento

- `__init__` lee endpoint → puebla `self.action`
- `format_response()` valida `data` contra `get_schema_class()` y wrappea en `BaseResponse` o `BasePaginationResponse`
- `_params(skip_frames=2)` extrae `page`/`count`/`search`/`order_by` + filtros del request

## Ejemplo

```python
from fastapi_basekit.aio.controller.base import BaseController

@cbv(router)
class ThingController(BaseController):
    service: ThingService = Depends(get_thing_service)
    schema_class = ThingResponseSchema

    @router.get("/")
    async def list_things(self):
        items, total = await self.service.list()
        return self.format_response(
            items,
            pagination={"page": 1, "count": 10, "total": total, "total_pages": 1},
        )
```

Para SQLAlchemy con joins/CRUD inherited, usa [`SQLAlchemyBaseController`](sqlalchemy-controller.md).
