from typing import Any, Dict, List, Optional, Type, Union
from typing import get_args, get_origin
import re

from bson import ObjectId, Link
from pydantic import BaseModel
from beanie import Document
from beanie.odm.queries.find import FindMany
from beanie.operators import Or, RegEx


class BaseRepository:
    model: Type[Document]
    
    def _parse_order_field(self, order_by: str) -> tuple[str, int, bool]:
        """Parse order_by string into components.
        
        Args:
            order_by: Order string, e.g., "-created_at" or "tool__name"
            
        Returns:
            tuple: (field_path, direction, is_nested)
            - field_path: "tool.name" or "created_at"
            - direction: 1 (asc) or -1 (desc)
            - is_nested: True if contains "__"
        """
        # Check for descending prefix
        direction = -1 if order_by.startswith("-") else 1
        field = order_by.lstrip("-")
        
        # Check if nested (contains __ or .)
        is_nested = "__" in field or "." in field
        
        # Convert __ to . for MongoDB field path (normalize)
        field_path = field.replace("__", ".")
        
        return field_path, direction, is_nested
    
    def _get_collection_name_from_field(self, field_name: str) -> Optional[str]:
        """Get the collection name for a Link field.
        
        Args:
            field_name: Name of the field in the model
            
        Returns:
            Collection name or None if not a Link field
        """
        if not hasattr(self.model, "model_fields"):
            return None
            
        model_fields = self.model.model_fields
        field_info = model_fields.get(field_name)
        
        if not field_info:
            return None
        
        field_type = field_info.annotation
        origin = get_origin(field_type)
        
        # Handle Link[Model]
        if origin is Link:
            args = get_args(field_type)
            if args:
                linked_model = args[0]
                if hasattr(linked_model, "Settings") and hasattr(linked_model.Settings, "name"):
                    return linked_model.Settings.name
        
        # Handle Optional[Link[Model]]
        if origin is Union:
            args = get_args(field_type)
            for arg in args:
                arg_origin = get_origin(arg)
                if arg_origin is Link:
                    link_args = get_args(arg)
                    if link_args:
                        linked_model = link_args[0]
                        if hasattr(linked_model, "Settings") and hasattr(linked_model.Settings, "name"):
                            return linked_model.Settings.name
        
        return None

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
        order_by: Optional[List[tuple]] = None,
        **kwargs,
    ) -> FindMany[Document]:
        """Versión personalizada que soporta campos Link."""
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

        # Obtener campos del modelo
        model_fields = (
            self.model.model_fields
            if hasattr(self.model, "model_fields")
            else {}
        )

        def _is_link_field(field_name: str) -> bool:
            """Verifica si un campo es de tipo Link."""
            field_info = model_fields.get(field_name)
            if not field_info:
                return False

            field_type = field_info.annotation
            origin = get_origin(field_type)

            # Caso directo: Link[Model]
            if origin is Link:
                return True

            # Caso Optional[Link[Model]] = Union[Link[Model], None]
            # O cualquier Union que contenga Link
            if origin is not None:
                args = get_args(field_type)
                for arg in args:
                    # Verificar si el argumento es Link
                    arg_origin = get_origin(arg)
                    if arg_origin is Link:
                        return True

            return False

        raw_filters: Dict[str, Any] = {}

        for k, v in (filters or {}).items():
            # MongoDB-style keys (dot-notation like "user.$id" or operators like "$or")
            # cannot be resolved via hasattr — pass them as a raw dict to find()
            if "." in k or k.startswith("$"):
                raw_filters[k] = v
            elif hasattr(self.model, k):
                field_attr = getattr(self.model, k)

                if _is_link_field(k):
                    exprs.append(field_attr.id == v)
                else:
                    exprs.append(field_attr == v)

        # Raw MongoDB filters go first so Beanie processes them as a dict condition
        query_args: list = ([raw_filters] if raw_filters else []) + exprs
        query = self.model.find(*query_args, **self._get_query_kwargs(**kwargs))
        
        # Apply ordering if provided
        if order_by:
            query = query.sort(order_by)
        
        return query

    async def paginate(
        self, query: FindMany[Document], page: int, count: int, order_by: Optional[List[tuple]] = None
    ) -> tuple[List[Document], int]:
        # Apply ordering if provided and not already applied
        if order_by:
            query = query.sort(order_by)
        
        total = await query.count()
        items = await query.skip(count * (page - 1)).limit(count).to_list()
        return items, total
    
    async def list_with_aggregation(
        self,
        search: Optional[str],
        search_fields: List[str],
        filters: dict,
        order_by: str,
        page: int,
        count: int,
        **kwargs
    ) -> tuple[List[Document], int]:
        """List with support for nested ordering using aggregation ($facet optimized)."""
        field_path, direction, is_nested = self._parse_order_field(order_by)
        pipeline = []
        
        # 1. Match stage (same as before)
        match_conditions = {}
        if filters:
            for key, value in filters.items():
                if isinstance(value, ObjectId):
                    match_conditions[key] = value
                elif hasattr(value, "id"):
                    match_conditions[f"{key}.$id"] = value.id
                else:
                    match_conditions[key] = value
        
        if search and search_fields:
            search_conditions = [
                {field: {"$regex": f".*{search}.*", "$options": "i"}}
                for field in search_fields
            ]
            if search_conditions:
                if match_conditions:
                    match_conditions = {"$and": [match_conditions, {"$or": search_conditions}]}
                else:
                    match_conditions = {"$or": search_conditions}
        
        if match_conditions:
            pipeline.append({"$match": match_conditions})
        
        # 2. Lookup & Sort (same as before)
        collection_name = None
        first_field = None
        
        if is_nested:
            parts = field_path.split(".")
            first_field = parts[0]
            collection_name = self._get_collection_name_from_field(first_field)
            
            if collection_name:
                pipeline.extend([
                    {
                        "$lookup": {
                            "from": collection_name,
                            "localField": f"{first_field}.$id",
                            "foreignField": "_id",
                            "as": f"{first_field}_data"
                        }
                    },
                    {
                        "$unwind": {
                            "path": f"${first_field}_data",
                            "preserveNullAndEmptyArrays": True
                        }
                    }
                ])
                remaining_path = ".".join(parts[1:]) if len(parts) > 1 else ""
                sort_field = f"{first_field}_data.{remaining_path}" if remaining_path else f"{first_field}_data"
            else:
                sort_field = field_path
        else:
            sort_field = field_path
            
        pipeline.append({"$sort": {sort_field: direction}})
        
        # 3. Facet for Single Query Pagination
        project_exclusion = {f"{first_field}_data": 0} if (is_nested and collection_name) else None
        
        facet_stage = {
            "$facet": {
                "metadata": [{"$count": "total"}],
                "data": [
                    {"$skip": count * (page - 1)},
                    {"$limit": count}
                ]
            }
        }
        
        # Add projection to remove join artifacts if needed
        if project_exclusion:
             facet_stage["$facet"]["data"].append({"$project": project_exclusion})
             
        pipeline.append(facet_stage)
        
        # Execute Pipeline
        results = await self.model.aggregate(pipeline).to_list()
        
        # Process Results
        if not results or not results[0].get("metadata"):
            return [], 0
            
        data = results[0]
        total = data["metadata"][0]["total"] if data["metadata"] else 0
        items_raw = data["data"]
        
        # Efficient Validation
        items = []
        for raw_item in items_raw:
            try:
                items.append(self.model.model_validate(raw_item))
            except Exception:
                continue
                
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
