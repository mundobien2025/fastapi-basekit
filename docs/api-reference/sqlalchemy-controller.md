# `SQLAlchemyBaseController`

Extiende [`BaseController`](base-controller.md) con métodos CRUD listos para SQLAlchemy async.

::: fastapi_basekit.aio.sqlalchemy.controller.base.SQLAlchemyBaseController
    options:
      show_source: true
      members:
        - list
        - retrieve
        - create
        - to_dict

## Métodos heredables

```python
async def list(self, *, use_or=False, joins=None, order_by=None) -> BasePaginationResponse:
    """Lista paginada con filtros desde query string."""

async def retrieve(self, id: str, *, joins=None) -> BaseResponse:
    """Retrieve por ID."""

async def create(self, validated_data, *, check_fields=None) -> BaseResponse:
    """Create con duplicate check."""
```

`update` y `delete` se heredan de `BaseController`.

## Patrón canónico

```python
from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from fastapi_basekit.schema.base import BasePaginationResponse, BaseResponse

@cbv(router)
class ThingController(SQLAlchemyBaseController):
    service: ThingService = Depends(get_thing_service)
    schema_class = ThingResponseSchema

    @router.get("/", response_model=BasePaginationResponse[ThingResponseSchema])
    async def list_things(self, page: int = Query(1), count: int = Query(10)):
        return await self.list()

    @router.get("/{id}", response_model=BaseResponse[ThingResponseSchema])
    async def get_thing(self, id: uuid.UUID):
        return await self.retrieve(id)

    @router.post("/", response_model=BaseResponse[ThingResponseSchema], status_code=201)
    async def create_thing(self, data: ThingCreateSchema):
        return await self.create(data)
```

[:octicons-arrow-right-24: Patrón completo](../user-guide/controllers.md){ .md-button .md-button--primary }
