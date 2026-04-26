# Schemas

## `BaseResponse`

::: fastapi_basekit.schema.base.BaseResponse

```python
class BaseResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    message: str = "Operación exitosa"
    status: str = "success"
```

Wrapper estándar para respuestas single-object.

## `BasePaginationResponse`

::: fastapi_basekit.schema.base.BasePaginationResponse

```python
class BasePaginationResponse(BaseModel, Generic[T]):
    data: List[T]                     # ← ya es lista
    message: str = "Operación exitosa"
    status: str = "success"
    pagination: Optional[Dict[str, Any]]
```

!!! danger "BasePaginationResponse[Schema], NO BasePaginationResponse[List[Schema]]"
    Como `data` ya está declarado `List[T]`, parametrizar con `List[Schema]` lo doblanida a `List[List[Schema]]` y Pydantic itera cada fila como sub-lista.

```python
@router.get("/", response_model=BasePaginationResponse[ThingSchema])   # ✓
@router.get("/", response_model=BasePaginationResponse[List[ThingSchema]])  # ✗
```

## `TokenSchema`

::: fastapi_basekit.schema.jwt.TokenSchema

```python
class TokenSchema(BaseModel):
    sub: str
    exp: int
```

Lo retorna `JWTService().decode_token(token)`. Cast `payload.sub` a UUID si tu modelo usa UUID PKs.

## Tu `BaseSchema`

Convención: cada proyecto define `app/schemas/base.py` con:

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S")},
    )
```

`from_attributes=True` permite `Schema.model_validate(orm_instance)`.

Schemas de respuesta extienden `BaseSchema`. Schemas de request extienden `pydantic.BaseModel` directo (sin from_attributes).
