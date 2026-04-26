"""{{ cookiecutter.project_name }} — FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi_basekit.exceptions.api_exceptions import (
    APIException,
    DatabaseIntegrityException,
    ValidationException,
)
from pydantic import ValidationError
{% if cookiecutter.orm == "sqlalchemy" -%}
from sqlalchemy.exc import IntegrityError
{%- endif %}

from app.api.v1.routers import router as api_v1_router
from app.config.database import lifespan
from app.config.settings import get_settings
from app.middleware.auth import AuthenticationMiddleware
from app.middleware.permissions import PermissionMiddleware
from app.utils import exception_handlers

settings = get_settings()


def create_application() -> FastAPI:
    app = FastAPI(
        title=f"{settings.PROJECT_NAME} API",
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        lifespan=lifespan,
    )

    app.add_exception_handler(APIException, exception_handlers.api_exception_handler)
    app.add_exception_handler(ValidationException, exception_handlers.api_exception_handler)
    app.add_exception_handler(DatabaseIntegrityException, exception_handlers.database_exception_handler)
    {% if cookiecutter.orm == "sqlalchemy" -%}
    app.add_exception_handler(IntegrityError, exception_handlers.integrity_error_handler)
    {%- endif %}
    app.add_exception_handler(RequestValidationError, exception_handlers.validation_exception_handler)
    app.add_exception_handler(ValidationError, exception_handlers.value_exception_handler)
    app.add_exception_handler(Exception, exception_handlers.global_exception_handler)

    cors_origins = ["*"] if settings.DEBUG else settings.ALLOWED_ORIGINS
    allow_creds = not settings.DEBUG

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_creds,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(PermissionMiddleware)
    app.add_middleware(AuthenticationMiddleware)

    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(exist_ok=True, parents=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema["servers"] = [{"url": "/"}]
        schema.setdefault("components", {})["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": settings.VERSION}

    return app


app = create_application()
