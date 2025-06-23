# app/controllers/base.py
from typing import Any, ClassVar, Type
from fastapi import Body, Depends, HTTPException, status,Request
from fastapi.asynchronous.service.base import BaseService
from fastapi.exceptions.api_exceptions import APIException
from pydantic import BaseModel, ValidationError



class BaseController:
    """
    Monta rutas CRUD genéricas y captura errores de negocio.
    Define métodos que pueden heredarse sin repetir try/except.
      GET    /          → list
      GET    /{id}      → retrieve
      POST   /          → create
      PATCH  /{id}      → update
      DELETE /{id}      → delete
    """

    service: BaseService = Depends()
    schema_out: ClassVar[Type[BaseModel]]
    action: ClassVar[Type[str]] = None
    request: Request

    def __init__(self):
        """
        Al instanciarse (por cada petición), el atributo `self.request`
        ya existe porque FastAPI lo inyectó como dependencia.
        Aquí fijamos `self.action` al nombre del método (endpoint) actual.
        """
        # La clave es `scope["endpoint"]`: FastAPI llena esta clave con
        # la función Python que está sirviendo esta ruta.
        endpoint_func = self.request.scope.get("endpoint")
        if endpoint_func:
            # El nombre del endpoint será, por ejemplo:
            # "create_invoice", "list_business_types", etc.
            self.action = endpoint_func.__name__
        else:
            self.action = None

    async def list(
        self, search: str | None = None, page: int = 1, count: int = 25
    ):
        return await self._execute(self.service.list, search, page, count)

    async def retrieve(self, id: str):
        return await self._execute(self.service.retrieve, id)

    async def create(self, validated_data: Any):
        # validated_data viene validado por FastAPI
        result = await self._execute(self.service.create, validated_data)
        if self.schema_out:
            return self.schema_out.model_validate(result)
        return result

    async def update(self, id: str, validated_data: Any):
        result = await self._execute(self.service.update, id, validated_data)
        if self.schema_out:
            return self.schema_out.from_orm(result)
        return result

    async def delete(self, id: str):
        return await self._execute(self.service.delete, id)

    async def _execute(self, func, *args):
        try:
            return await func(*args)
        except APIException as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)
