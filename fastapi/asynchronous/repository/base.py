# app/repositories/base.py
from abc import ABC
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from beanie import DeleteRules, Document
from beanie.odm.queries.find import FindMany
from beanie.operators import Or, RegEx

ModelType = TypeVar("ModelType", bound=Document)


class BaseRepository(ABC, Generic[ModelType]):
    """
    CRUD genérico + filtros y paginación para Beanie/MongoDB.
    """

    model: Type[ModelType]  # Cada repositorio concreto define este atributo

    async def build_filter_query(
        self,
        search: Optional[str],
        search_fields: List[str],
        filters: dict = None,
    ) -> FindMany[ModelType]:
        # Search sobre campos configurados
        exprs = []
        if search and search_fields:
            exprs.append(
                Or(
                    *[
                        RegEx(
                            getattr(self.model, field),
                            f".*{search}.*",
                            options="i",
                        )
                        for field in search_fields
                    ]
                )
            )

        # Filtros directos (exactos)
        for k, v in filters.items():
            if hasattr(self.model, k):
                exprs.append(getattr(self.model, k) == v)

        if exprs:
            return self.model.find(*exprs)
        return self.model.find()

    async def paginate(
        self, query: FindMany[ModelType], page: int, count: int
    ) -> tuple[List[ModelType], int]:
        """
        Aplica skip/limit y devuelve (items, total_items).
        """
        total = await query.count()
        items = await query.skip(count * (page - 1)).limit(count).to_list()
        return items, total

    async def get_by_id(
        self, obj_id: str, fetch_links: bool = False
    ) -> Optional[ModelType]:
        """Obtiene un objeto por su ID."""
        return await self.model.get(obj_id, fetch_links=fetch_links)

    async def list_all(self, fetch_links: bool = False) -> List[ModelType]:
        """Devuelve todos los registros (sin paginar)."""
        return await self.model.find_all(fetch_links=fetch_links).to_list()

    async def create(self, obj: Union[ModelType, Dict[str, Any]]) -> ModelType:
        """Crea un nuevo documento."""
        if isinstance(obj, dict):
            obj = self.model(**obj)
        await obj.insert()
        return obj

    async def update(self, obj: ModelType, data: Dict[str, Any]) -> ModelType:
        """Actualiza un documento existente."""
        for key, value in data.items():
            setattr(obj, key, value)
        await obj.save()
        return obj

    async def delete(
        self, obj: ModelType, link_rule: DeleteRules = DeleteRules.DELETE_LINKS
    ) -> None:
        """
        Elimina un documento. Por defecto NO elimina los enlaces.
        Para borrado en cascada de todos los links, pasa
          link_rule=DeleteRules.DELETE_LINKS
        """
        await obj.delete(link_rule=link_rule)
