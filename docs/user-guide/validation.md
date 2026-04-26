# Validación

## Request validation — schemas Pydantic

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ThingCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    age: int = Field(..., ge=0, le=120)
    model_config = ConfigDict(extra="ignore")
```

FastAPI valida automáticamente. Errores → `RequestValidationError` → handled por `validation_exception_handler` del `app/utils/exception_handlers.py`.

## Response validation

`from_attributes=True` en `BaseSchema` permite serializar SQLAlchemy rows directo:

```python
class ThingResponseSchema(BaseSchema):   # extends BaseSchema → from_attributes=True
    id: uuid.UUID
    name: str
    created_at: datetime
```

```python
return self.format_response(ThingResponseSchema.model_validate(thing_orm_instance))
```

!!! warning "id type matches DB type"
    Si tu PK es `Mapped[UUID]`, el schema DEBE tener `id: uuid.UUID`. Con `id: str` Pydantic falla silenciosamente.

## Duplicate check — `duplicate_check_fields`

```python
class UserService(BaseService):
    duplicate_check_fields = ["email"]
```

`service.create(payload)` consulta `repo.get_by_filters({"email": payload.email})` antes de insertar. Si existe, lanza `DatabaseIntegrityException(message="Registro ya existe")`.

## Validation errors → BaseResponse

Handler global convierte `RequestValidationError` a:

```json
{
  "data": [
    { "type": "missing", "loc": ["body", "email"], "msg": "Field required" }
  ],
  "message": "Error de validación",
  "status": "VALIDATION_ERROR"
}
```

## Custom validators

Pydantic v2 field validators:

```python
from pydantic import field_validator

class ThingCreateSchema(BaseModel):
    slug: str

    @field_validator("slug")
    @classmethod
    def slug_must_be_lowercase(cls, v: str) -> str:
        if v != v.lower():
            raise ValueError("slug must be lowercase")
        return v
```

## Nested validation

```python
class AddressSchema(BaseModel):
    city: str
    state: str


class UserCreateSchema(BaseModel):
    email: EmailStr
    address: AddressSchema   # nested
```

Pydantic valida recursivamente. Errores reportados con `loc` profundo: `["body", "address", "city"]`.
