# Excepciones

## Disponibles

::: fastapi_basekit.exceptions.api_exceptions
    options:
      show_source: false
      members:
        - APIException
        - ValidationException
        - NotFoundException
        - PermissionException
        - JWTAuthenticationException
        - DatabaseIntegrityException

## Uso

```python
from fastapi_basekit.exceptions.api_exceptions import (
    NotFoundException,
    ValidationException,
    DatabaseIntegrityException,
    PermissionException,
    JWTAuthenticationException,
)

# Lanza desde service/repo
raise NotFoundException(message="Usuario no encontrado")
raise ValidationException(data={"field": "name", "error": "required"})
raise DatabaseIntegrityException(message="Email ya en uso", data={"email": email})
raise PermissionException(message="No tienes permiso")
raise JWTAuthenticationException(message="Token inválido")
```

## Status codes

| Excepción | HTTP status |
|---|---|
| `ValidationException` | 422 |
| `NotFoundException` | 404 |
| `PermissionException` | 403 |
| `JWTAuthenticationException` | 401 |
| `DatabaseIntegrityException` | 400 |
| `APIException` (genérica) | depende del subclase |

## Handlers globales

Registra en `main.py`:

```python
from fastapi_basekit.exceptions.api_exceptions import (
    APIException, DatabaseIntegrityException, ValidationException,
)
from app.utils import exception_handlers

app.add_exception_handler(APIException, exception_handlers.api_exception_handler)
app.add_exception_handler(ValidationException, exception_handlers.api_exception_handler)
app.add_exception_handler(DatabaseIntegrityException, exception_handlers.database_exception_handler)
app.add_exception_handler(IntegrityError, exception_handlers.integrity_error_handler)
app.add_exception_handler(RequestValidationError, exception_handlers.validation_exception_handler)
app.add_exception_handler(ValidationError, exception_handlers.value_exception_handler)
app.add_exception_handler(Exception, exception_handlers.global_exception_handler)
```

Los handlers convierten cada excepción a `BaseResponse` JSON.

## Translation pattern (no en `get_db`)

`get_db` solo hace rollback + reraise. Translation (e.g. `IntegrityError` → mensaje friendly) vive en el handler:

```python
async def integrity_error_handler(request: Request, exc: IntegrityError):
    error_msg = str(exc.orig).lower()
    if "email" in error_msg and ("duplicate" in error_msg or "unique" in error_msg):
        message = "Email ya en uso"
    elif "foreign key" in error_msg:
        message = "Registro relacionado no existe"
    else:
        message = "Error de integridad"
    return JSONResponse(
        status_code=400,
        content=BaseResponse(
            status="DATABASE_INTEGRITY_ERROR", message=message, data=None
        ).model_dump(),
    )
```

Beneficio: domain knowledge concentrado en handlers, infra (`get_db`) limpia.
