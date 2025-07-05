from typing import Any, Dict, List, Optional, Type, Union

from beanie import DeleteRules, Document
from beanie.odm.queries.find import FindMany
from beanie.operators import Or, RegEx


class BaseRepository:
    """
    CRUD genérico + filtros y paginación para Beanie/MongoDB.
    """

    model: Type[Document]  # Cada repositorio concreto define este atributo

    async def build_filter_query(
        self,
        search: Optional[str],
        search_fields: List[str],
        filters: dict = None,
    ) -> FindMany[Document]:
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

        for k, v in (filters or {}).items():
            if hasattr(self.model, k):
                exprs.append(getattr(self.model, k) == v)

        if exprs:
            return self.model.find(*exprs)
        return self.model.find()

    async def paginate(
        self, query: FindMany[Document], page: int, count: int
    ) -> tuple[List[Document], int]:
        total = await query.count()
        items = await query.skip(count * (page - 1)).limit(count).to_list()
        return items, total

    async def get_by_id(
        self, obj_id: str, fetch_links: bool = False
    ) -> Optional[Document]:
        return await self.model.get(
            obj_id,
            fetch_links=fetch_links,
        )

    async def get_by_field(
        self, field_name: str, value: Any, fetch_links: bool = False
    ) -> Optional[Document]:
        if not hasattr(self.model, field_name):
            raise AttributeError(
                f"{self.model.__name__} no tiene el campo '{field_name}'"
            )
        filter_expr = getattr(self.model, field_name) == value
        return await self.model.find_one(
            filter_expr,
            fetch_links=fetch_links,
        )

    async def list_all(self, fetch_links: bool = False) -> List[Document]:
        return await self.model.find_all(
            fetch_links=fetch_links,
        ).to_list()

    async def create(self, obj: Union[Document, Dict[str, Any]]) -> Document:
        if isinstance(obj, dict):
            obj = self.model(**obj)
        await obj.insert()
        return obj

    async def update(self, obj: Document, data: Dict[str, Any]) -> Document:
        for key, value in data.items():
            setattr(obj, key, value)
        await obj.save()
        return obj

    async def delete(
        self, obj: Document, link_rule: DeleteRules = DeleteRules.DELETE_LINKS
    ) -> None:
        await obj.delete(
            link_rule=link_rule,
        )
