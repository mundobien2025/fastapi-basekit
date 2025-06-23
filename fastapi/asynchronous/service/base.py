# app/services/base.py
from abc import ABC
from typing import Any, ClassVar, Dict, Generic, List, Optional, Type, TypeVar

from fastapi import Query
from fastapi.asynchronous.repository.base import BaseRepository
from fastapi.exceptions.api_exceptions import NotFoundException
from fastapi.schema.base import BasePaginationResponse, BaseResponse
from pydantic import BaseModel
from beanie import Document


ModelType = TypeVar("ModelType", bound=Document)
RepoType = TypeVar("RepoType", bound=BaseRepository)


class BaseService(ABC, Generic[ModelType, RepoType]):
    """
    Lógica de negocio: orquesta repositorio, validaciones de BD y
    transforma a esquemas de entrada/salida.
    """

    repository: RepoType
    schema_in: ClassVar[Optional[Type[BaseModel]]]
    schema_out: ClassVar[Optional[Type[BaseModel]]]
    search_fields: ClassVar[Optional[List[str]]] = []
    default_count: int = 25
    # Ejemplo: { "commune_id": CommuneRepository(),
    # "company_id": CompanyRepository() }
    foreign_keys: Dict[str, BaseRepository] = {}

    def __init__(self, repository: RepoType):
        self.repository = repository

    async def _validate_foreign_keys(self, data: Dict[str, Any]):
        """
        Recorre self.foreign_keys y para cada campo verifica que exista
        un registro con ese ID. Lanza 404 si no lo encuentra.
        """
        for field, repo in self.foreign_keys.items():
            val = data.get(field)
            if val is not None:
                exists = await repo.get_by_id(val)
                if not exists:
                    raise NotFoundException(
                        f"{repo.model.__name__} con id={val} no existe"
                    )

    async def get_object(self, id: str) -> ModelType:
        obj = await self.repository.get_by_id(id, fetch_links=True)
        if not obj:
            raise NotFoundException(f"id={id} no encontrado")
        return obj

    async def list(
        self,
        search: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        count: int = Query(default_count, ge=1),
    ) -> BasePaginationResponse:
        # 1) Construir query con filtros
        query = self.repository.build_filter_query(search, self.search_fields)
        # 2) Aplicar paginación y conteo
        items, total = await self.repository.paginate(query, page, count)
        # 3) Serializar
        data = [self.schema_out.model_validate(i) for i in items]
        total_pages = (total + count - 1) // count

        return BasePaginationResponse(
            data=data,
            pagination={
                "total_items": total,
                "total_pages": total_pages,
                "current_page": page,
                "count": count,
            },
            message="Operación exitosa",
            status="success",
        )

    async def retrieve(self, id: str) -> BaseResponse:
        obj = await self.get_object(id)
        return BaseResponse(data=self.schema_out.model_validate(obj))

    async def create(self, payload: BaseModel) -> BaseResponse:
        # 1) Convertir payload validado a dict
        data = payload.model_dump()
        # 2) Validar claves foráneas
        await self._validate_foreign_keys(data)
        # 3) Ejecutar creación en BD
        created = await self.repository.create(data)
        # 4) Serializar salida
        return BaseResponse(data=self.schema_out.model_validate(created))

    async def update(self, id: str, payload: BaseModel) -> BaseResponse:
        # 1) Asegurarse de que exista el objeto
        obj = await self.get_object(id)
        # 2) Sólo los campos que vienen en la request
        data = payload.model_dump(exclude_unset=True)
        # 3) Validar claves foráneas sobre los campos actualizados
        await self._validate_foreign_keys(data)
        # 4) Ejecutar update en BD
        updated = await self.repository.update(obj, data)
        # 5) Serializar salida
        return BaseResponse(data=self.schema_out.model_validate(updated))

    async def delete(self, id: str) -> BaseResponse:
        obj = await self.get_object(id)
        await self.repository.delete(obj)
        return BaseResponse(data="deleted")
