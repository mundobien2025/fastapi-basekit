from typing import Any, Dict, List, Optional, Type, Union

from bson import ObjectId
from pydantic import BaseModel
from beanie import Document
from beanie.odm.queries.find import FindMany
from beanie.operators import Or, RegEx


class BaseRepository:
    model: Type[Document]

    def _get_query_kwargs(
        self,
        fetch_links: bool = False,
        nesting_depths_per_field: Optional[Dict[str, int]] = None,
        projection: Optional[Union[List[str], Type[BaseModel]]] = None,
    ):
        kwargs = {
            "fetch_links": fetch_links,
            "nesting_depths_per_field": (
                nesting_depths_per_field if fetch_links else None
            ),
        }
        if projection is not None:
            kwargs["projection"] = projection
        return kwargs

    def build_filter_query(
        self,
        search: Optional[str],
        search_fields: List[str],
        filters: dict = None,
        **kwargs,
    ) -> FindMany[Document]:
        exprs = []

        if search and search_fields:
            exprs.append(
                Or(
                    *[
                        RegEx(
                            getattr(self.model, f),
                            f".*{search}.*",
                            options="i",
                        )
                        for f in search_fields
                    ]
                )
            )

        for k, v in (filters or {}).items():
            if hasattr(self.model, k):
                exprs.append(getattr(self.model, k) == v)

        query = self.model.find(*exprs, **self._get_query_kwargs(**kwargs))
        return query

    async def paginate(
        self, query: FindMany[Document], page: int, count: int
    ) -> tuple[List[Document], int]:
        total = await query.count()
        items = await query.skip(count * (page - 1)).limit(count).to_list()
        return items, total

    async def get_by_id(
        self,
        obj_id: Union[str, ObjectId],
        **kwargs,
    ) -> Optional[Document]:
        if not isinstance(obj_id, ObjectId):
            obj_id = ObjectId(obj_id)
        return await self.model.find_one(
            self.model.id == obj_id,
            **self._get_query_kwargs(**kwargs),
        )

    async def get_by_field(
        self,
        field_name: str,
        value: Any,
        **kwargs,
    ) -> Optional[Document]:
        if not hasattr(self.model, field_name):
            raise AttributeError(
                f"{self.model.__name__} no tiene el campo '{field_name}'"
            )
        return await self.model.find_one(
            getattr(self.model, field_name) == value,
            **self._get_query_kwargs(**kwargs),
        )

    async def get_by_fields(
        self,
        filters: Dict[str, Any],
        **kwargs,
    ) -> Optional[Document]:
        exprs = [
            getattr(self.model, f) == v
            for f, v in filters.items()
            if hasattr(self.model, f)
        ]
        if not exprs:
            return None
        return await self.model.find_one(
            *exprs, **self._get_query_kwargs(**kwargs)
        )

    async def list_all(
        self,
        **kwargs,
    ) -> List[Document]:
        query = self.model.find_all(**self._get_query_kwargs(**kwargs))
        return await query.to_list()

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

    async def delete(self, obj: Document) -> None:
        await obj.delete()
