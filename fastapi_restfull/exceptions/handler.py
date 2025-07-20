from typing import Any, Dict, List, Union

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError
from beanie.exceptions import DocumentNotFound

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
