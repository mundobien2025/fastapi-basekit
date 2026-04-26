"""Global exception handlers — basekit BaseResponse envelope."""

from typing import Any, Dict, List, Union

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi_basekit.exceptions.api_exceptions import (
    APIException,
    DatabaseIntegrityException,
    ValidationException,
)
from fastapi_basekit.schema.base import BaseResponse
from pydantic import ValidationError
{% if cookiecutter.orm == "sqlalchemy" -%}
from sqlalchemy.exc import IntegrityError
{%- endif %}


async def api_exception_handler(request: Request, exc: APIException):
    response = BaseResponse(status=exc.status_code, message=exc.message, data=exc.data)
    return JSONResponse(status_code=exc.status, content=response.model_dump())


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    raise ValidationException(data=exc.errors())


async def database_exception_handler(request: Request, exc: DatabaseIntegrityException):
    response = BaseResponse(status=exc.status_code, message=exc.message, data=exc.data)
    return JSONResponse(status_code=exc.status, content=response.model_dump())


async def value_exception_handler(request: Request, exc: Union[ValidationError, ValueError]):
    if isinstance(exc, ValidationError):
        error_details: List[Dict[str, Any]] = exc.errors()
    else:
        error_details = [{"error": str(exc)}]

    response = BaseResponse(
        status="VALUE_ERROR",
        message="Field validation error",
        data=str(error_details),
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(mode="json"),
    )


{% if cookiecutter.orm == "sqlalchemy" %}
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Convert IntegrityError to a friendly DatabaseIntegrityException response.

    Customize the matchers below per your domain (column names, constraints).
    """
    error_orig = exc.orig if hasattr(exc, "orig") else exc
    error_msg = str(error_orig).lower()

    if "email" in error_msg and ("duplicate" in error_msg or "unique" in error_msg):
        message = "Email already in use"
    elif "foreign key" in error_msg:
        message = "Referenced record does not exist"
    else:
        message = "Database integrity error"

    response = BaseResponse(status="DATABASE_INTEGRITY_ERROR", message=message, data=None)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(),
    )
{% endif %}


async def global_exception_handler(request: Request, exc: Exception):
    response = BaseResponse(
        status="ERROR_GENERIC",
        message="Unknown error",
        data={"detail": str(exc)},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(),
    )
