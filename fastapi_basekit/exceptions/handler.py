from typing import Any, Dict, List, Union

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

try:  # pragma: no cover - dependencia opcional
    from pymongo.errors import DuplicateKeyError  # type: ignore
except ImportError:  # pragma: no cover
    class DuplicateKeyError(Exception):  # type: ignore[no-redef]
        """Fallback cuando pymongo no está instalado."""

        ...

try:  # pragma: no cover - dependencia opcional
    from beanie.exceptions import DocumentNotFound  # type: ignore
except ImportError:  # pragma: no cover
    class DocumentNotFound(Exception):  # type: ignore[no-redef]
        """Fallback cuando beanie no está instalado."""

        ...

from ..schema.base import BaseResponse

from .api_exceptions import (
    APIException,
    DatabaseIntegrityException,
    ValidationException,
)


async def api_exception_handler(request: Request, exc: APIException):
    response = BaseResponse(
        status=exc.status_code, message=exc.message, data=exc.data
    )
    return JSONResponse(status_code=exc.status, content=response.model_dump())


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    """
    Maneja errores de validación de FastAPI / Pydantic.
    """
    raise ValidationException(data=exc.errors())


async def duplicate_key_exception_handler(
    request: Request, exc: DuplicateKeyError
):
    """
    Maneja errores de clave duplicada en MongoDB (índices únicos).
    """
    raise DatabaseIntegrityException(
        message="Clave duplicada detectada en la base de datos.",
        data={"detail": str(exc)},
    )


async def document_not_found_handler(request: Request, exc: DocumentNotFound):
    """
    Maneja error cuando no se encuentra un documento en Beanie.
    """
    response = BaseResponse(
        status="NOT_FOUND",
        message="Documento no encontrado",
        data={"detail": str(exc)},
    )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=response.model_dump(),
    )


async def global_exception_handler(request: Request, exc: Exception):
    """
    Manejador global para errores no controlados.
    """
    response = BaseResponse(
        status="ERROR_GENERIC",
        message="Ocurrió un error desconocido",
        data={"detail": str(exc)},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(),
    )


async def value_exception_handler(
    request: Request, exc: Union[ValidationError, ValueError]
):
    """
    Maneja errores de validación o valores incorrectos.
    """
    if isinstance(exc, ValidationError):
        error_details: List[Dict[str, Any]] = exc.errors()
    else:
        error_details = [{"error": str(exc)}]

    response = BaseResponse(
        status="VALUE_ERROR",
        message="Ocurrió un error en uno de los campos",
        data=str(error_details),
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(mode="json"),
    )


async def request_validation_handler(
    request: Request, exc: RequestValidationError
):
    """FastAPI request validation → envelope unificado (no relanza).

    Equivalente a `validation_exception_handler` pero devuelve la respuesta
    directamente, sin depender de que otro handler capture la excepción
    relanzada. Cuerpo idéntico al que produciría `ValidationException`.
    """
    response = BaseResponse(
        status="VALIDATION_ERROR",
        message="Error de validación",
        data=exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response.model_dump(mode="json"),
    )


async def integrity_error_handler(request: Request, exc: Exception):
    """SQLAlchemy IntegrityError → envelope de integridad (HTTP 400)."""
    detail = getattr(exc, "orig", None)
    response = BaseResponse(
        status="DATABASE_INTEGRITY_ERROR",
        message="Registro ya existe o viola una restricción de integridad",
        data={"detail": str(detail) if detail is not None else str(exc)},
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(mode="json"),
    )


def register_exception_handlers(
    app,
    *,
    sqlalchemy: bool = True,
    mongo: bool = True,
) -> None:
    """Registra el conjunto completo de handlers sobre una app FastAPI.

    Un solo punto de cableado para que cada proyecto NO copie-pegue el
    mapeo de excepciones → ``BaseResponse``. Todas las subclases de
    ``APIException`` (NotFound, Permission, JWT, Validation, Integrity,
    Global...) las atiende ``api_exception_handler`` vía resolución por MRO.

    Args:
        app: instancia FastAPI.
        sqlalchemy: registra el handler de ``IntegrityError`` (requiere
            SQLAlchemy instalado).
        mongo: registra handlers de Mongo/Beanie si están disponibles.
    """
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(
        RequestValidationError, request_validation_handler
    )
    app.add_exception_handler(ValidationError, value_exception_handler)
    app.add_exception_handler(ValueError, value_exception_handler)

    if sqlalchemy:
        try:  # pragma: no cover - dependencia opcional
            from sqlalchemy.exc import IntegrityError

            app.add_exception_handler(
                IntegrityError, integrity_error_handler
            )
        except ImportError:
            pass

    if mongo:
        # Solo registra si las clases reales (no los fallbacks) existen.
        if DuplicateKeyError.__module__ != __name__:
            app.add_exception_handler(
                DuplicateKeyError, duplicate_key_exception_handler
            )
        if DocumentNotFound.__module__ != __name__:
            app.add_exception_handler(
                DocumentNotFound, document_not_found_handler
            )

    # Catch-all al final; las subclases de APIException ya tienen prioridad
    # por especificidad de tipo.
    app.add_exception_handler(Exception, global_exception_handler)
