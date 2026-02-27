from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, Union
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import and_, or_, func, Select
from sqlalchemy.orm import Relationship, joinedload, selectinload

from ....exceptions.api_exceptions import NotFoundException


class BaseRepository:
    """
    Repositorio base para SQLModel Async.

    Idéntico en contrato al de SQLAlchemy pero usa:
    - ``sqlmodel.ext.asyncio.session.AsyncSession``
    - ``session.exec()`` para queries sobre modelos (devuelve escalares
      directamente, sin necesidad de ``.scalars()``)
    - ``session.execute()`` para queries de agregación (count, etc.)

    Establece ``model`` en la subclase (modelo SQLModel con ``table=True``).
    """

    model: Type[Any]
    service: Optional[Any] = None

    def __init__(self, db: AsyncSession):
        """Inicializa el repositorio con la sesión a reutilizar."""
        self._session = db
        self.service = None

    @property
    def session(self) -> AsyncSession:
        return self._session

    def _get_field(self, field_name: str):
        """Valida y retorna el atributo (columna) del modelo."""
        if not self.model:
            raise ValueError("El modelo no está definido en el repositorio")
        field = getattr(self.model, field_name, None)
        if not field:
            raise AttributeError(
                f"El campo '{field_name}' no existe en {self.model.__name__}"
            )
        return field

    def _apply_joins(
        self, query: Select[Tuple[Any]], joins: Optional[List[str]]
    ) -> Any:
        """Aplica las opciones de carga (joins) dinámicamente al query."""
        if joins:
            for relation in joins:
                if hasattr(self.model, relation):
                    relationship_attr = getattr(self.model, relation)
                    if getattr(relationship_attr.property, "uselist", False):
                        query = query.options(selectinload(relationship_attr))
                    else:
                        query = query.options(joinedload(relationship_attr))
        return query

    def _resolve_field_path(
        self, path: str
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        """
        Resuelve una ruta de campo (ej. 'user__role__name') a su atributo
        de SQLAlchemy/SQLModel y el conjunto de JOINs necesarios.

        Args:
            path: Ruta del campo con sintaxis '__'

        Returns:
            Tuple con:
            - attr: Atributo final (columna o relación) o None si no existe
            - joins_to_apply: Dict con las relaciones intermedias (name: attr)
        """
        parts = path.split("__")
        current_model = self.model
        attr = getattr(current_model, parts[0], None)
        joins_to_apply = {}

        if attr is None:
            return None, {}

        for part in parts[1:]:
            if hasattr(attr, "property") and isinstance(
                attr.property, Relationship
            ):
                relation_name = attr.key
                joins_to_apply[relation_name] = attr

                current_model = attr.property.mapper.class_
                attr = getattr(current_model, part, None)

                if attr is None:
                    return None, {}
            else:
                break

        return attr, joins_to_apply

    def _resolve_attribute(
        self, filters: Dict[str, Any]
    ) -> Tuple[Dict[str, Tuple[Any, Any]], Dict[str, Any]]:
        """
        Resuelve atributos finales y relaciones para JOINs a partir de
        filtros con sintaxis '__'.

        Soporta:
        - Filtro simple: {"status": "active"}
        - Filtro con relación: {"user_roles__role__code": "Admin"}
        """
        resolved_filters = {}
        joins_to_apply = {}

        for filter_path, value in filters.items():
            attr, field_joins = self._resolve_field_path(filter_path)

            if attr is None:
                continue

            joins_to_apply.update(field_joins)

            processed_value = value
            if (
                isinstance(value, (list, tuple))
                and value
                and hasattr(value[0], "value")
            ):
                processed_value = [v.value for v in value]
            elif hasattr(value, "value"):
                processed_value = value.value

            is_relationship = isinstance(attr.property, Relationship)
            is_column = hasattr(attr.property, "columns") or hasattr(
                attr, "comparator"
            )

            if not is_relationship and is_column:
                resolved_filters[filter_path] = (attr, processed_value)

        return resolved_filters, joins_to_apply

    def _resolve_order_by(
        self,
        order_by: Optional[Any] = None,
        special_fields: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        """
        Resuelve ordenamiento y relaciones para JOINs.

        Soporta prefijo '-' para orden descendente y rutas con '__'.

        Args:
            order_by: Campo de ordenamiento (str o expresión SQLAlchemy).
            special_fields: Mapa de aliases a atributos SQLModel.

        Returns:
            Tuple (order_expression, joins_to_apply).
        """
        if order_by is not None and not isinstance(order_by, str):
            return order_by, {}

        if not order_by:
            return None, {}

        joins_to_apply: Dict[str, Any] = {}

        has_minus_prefix = order_by.startswith("-")
        field_path = order_by.lstrip("-")

        if special_fields and field_path in special_fields:
            attr = special_fields[field_path]
            order_expression = attr.desc() if has_minus_prefix else attr.asc()
            return order_expression, {}

        attr, field_joins = self._resolve_field_path(field_path)

        if attr is None:
            return None, {}

        joins_to_apply.update(field_joins)

        is_relationship = isinstance(attr.property, Relationship)
        is_column = hasattr(attr.property, "columns") or hasattr(
            attr, "comparator"
        )

        if is_relationship or not is_column:
            return None, {}

        order_expression = attr.desc() if has_minus_prefix else attr.asc()
        return order_expression, joins_to_apply

    def _build_conditions(
        self,
        filters: Optional[Dict[str, Any]] = None,
        resolved_filters: Optional[Dict[str, Tuple[Any, Any]]] = None,
    ) -> List[Any]:
        """Construye condiciones WHERE a partir de los atributos resueltos."""
        conditions: List[Any] = []

        if resolved_filters is not None:
            for _, (field, processed_value) in resolved_filters.items():
                if isinstance(
                    processed_value, (list, tuple)
                ) and not isinstance(processed_value, str):
                    conditions.append(field.in_(processed_value))
                else:
                    conditions.append(field == processed_value)
        elif filters is not None:
            for fn, value in filters.items():
                field = self._get_field(fn)
                if isinstance(value, (list, tuple)) and not isinstance(
                    value, str
                ):
                    conditions.append(field.in_(value))
                else:
                    conditions.append(field == value)

        return conditions

    def _build_search_condition(
        self, search: Optional[str], search_fields: Optional[List[str]]
    ) -> Tuple[Optional[Any], Dict[str, Any]]:
        """Construye una condición OR para búsqueda textual (ilike).

        Soporta rutas anidadas con '__'.

        Returns:
            Tuple (search_condition, search_joins).
        """
        if not search or not search_fields:
            return None, {}

        exprs: List[Any] = []
        search_joins: Dict[str, Any] = {}

        for field_path in search_fields:
            attr, field_joins = self._resolve_field_path(field_path)

            if attr is None:
                continue

            search_joins.update(field_joins)

            is_column = hasattr(attr.property, "columns") or hasattr(
                attr, "comparator"
            )
            is_relationship = isinstance(attr.property, Relationship)

            if not is_relationship and is_column:
                exprs.append(attr.ilike(f"%{search}%"))

        if not exprs:
            return None, {}

        return or_(*exprs), search_joins

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    async def create(self, obj_in: Any | Dict) -> Any:
        """Crea un nuevo registro en la base de datos."""
        db = self.session
        if isinstance(obj_in, dict):
            obj_in = self.model(**obj_in)
        db.add(obj_in)
        await db.flush()
        await db.refresh(obj_in)
        return obj_in

    async def _get_one(
        self,
        conditions: Optional[List[Any]] = None,
        joins: Optional[List[str]] = None,
        raise_exception: bool = False,
    ) -> Optional[Any]:
        """
        Método interno unificado para obtener un único registro.

        Usa ``session.exec()`` para retornar instancias tipadas directamente.
        """
        if not self.model:
            raise ValueError("El modelo no está definido en el repositorio")

        query = select(self.model)
        if conditions:
            query = query.where(and_(*conditions))

        query = self._apply_joins(query, joins)

        result = await self.session.exec(query)
        record = result.first()

        if raise_exception and record is None:
            raise NotFoundException(
                message=f"{self.model.__name__} no encontrado"
            )

        return record

    async def get(self, record_id: Union[str, UUID]) -> Optional[Any]:
        """Obtiene un registro por su ID."""
        if not self.model:
            raise ValueError("El modelo no está definido en el repositorio")
        return await self.session.get(self.model, record_id)

    async def get_by_field(self, field_name: str, value: Any) -> Optional[Any]:
        """Obtiene un registro por un campo específico."""
        field = self._get_field(field_name)
        return await self._get_one(conditions=[field == value])

    async def get_with_joins(
        self,
        record_id: Union[str, UUID],
        joins: Optional[List[str]] = None,
    ) -> Optional[Any]:
        """Obtiene un registro por ID y carga relaciones dinámicamente."""
        return await self._get_one(
            conditions=[self.model.id == record_id], joins=joins
        )

    async def get_by_field_with_joins(
        self,
        field_name: str,
        value: Any,
        joins: Optional[List[str]] = None,
    ) -> Optional[Any]:
        """
        Obtiene un registro por un campo y carga relaciones dinámicamente.

        Soporta filtros con relaciones usando sintaxis '__'.
        """
        if "__" in field_name:
            resolved_filters, joins_to_apply = self._resolve_attribute(
                {field_name: value}
            )

            if not resolved_filters:
                return None

            _, (field, processed_value) = next(iter(resolved_filters.items()))

            query = select(self.model)

            for _, relation_attr in joins_to_apply.items():
                query = query.join(relation_attr)

            query = query.where(field == processed_value)
            query = self._apply_joins(query, joins)

            result = await self.session.exec(query)
            return result.first()
        else:
            field = self._get_field(field_name)
            return await self._get_one(
                conditions=[field == value], joins=joins
            )

    async def get_by_filters(
        self, filters: Dict[str, Any], use_or: bool = False
    ) -> Sequence[Any]:
        """
        Obtiene registros que coinciden con los filtros especificados.

        Soporta filtros simples y con relaciones usando sintaxis '__'.
        """
        if not self.model:
            raise ValueError("El modelo no está definido en el repositorio")

        resolved_filters, joins_to_apply = self._resolve_attribute(filters)

        query = select(self.model)

        for _, relation_attr in joins_to_apply.items():
            query = query.join(relation_attr)

        conditions = self._build_conditions(resolved_filters=resolved_filters)

        if not conditions:
            return []

        combined = or_(*conditions) if use_or else and_(*conditions)
        query = query.where(combined)

        result = await self.session.exec(query)
        return result.all()

    async def get_by_filters_with_joins(
        self,
        filters: Dict[str, Any],
        use_or: bool = False,
        joins: Optional[List[str]] = None,
        one: bool = False,
    ) -> Sequence[Any] | Optional[Any]:
        """
        Obtiene registros por filtros y carga relaciones dinámicamente.
        """
        resolved_filters, joins_to_apply = self._resolve_attribute(filters)

        query = select(self.model)

        for _, relation_attr in joins_to_apply.items():
            query = query.join(relation_attr)

        conditions = self._build_conditions(resolved_filters=resolved_filters)

        if not conditions:
            return None if one else []

        combined = or_(*conditions) if use_or else and_(*conditions)
        query = query.where(combined)

        query = self._apply_joins(query, joins)

        result = await self.session.exec(query)
        return result.first() if one else result.all()

    def apply_list_filters(
        self,
        queryset: Select[Tuple[Any]],
        filters: Optional[Dict[str, Any]] = None,
        use_or: bool = False,
        joins: Optional[List[str]] = None,
        order_by: Optional[Any] = None,
        search: Optional[str] = None,
        search_fields: Optional[List[str]] = None,
    ) -> Select[Tuple[Any]]:
        """Aplica filtros estándar, búsqueda y ordenamiento al query."""
        filters = filters or {}

        resolved_filters, joins_to_apply = self._resolve_attribute(filters)

        for _, relation_attr in joins_to_apply.items():
            queryset = queryset.join(relation_attr)

        conditions = self._build_conditions(resolved_filters=resolved_filters)
        combined_filters = (
            or_(*conditions)
            if (use_or and conditions)
            else and_(*conditions) if conditions else None
        )

        search_condition, search_joins = self._build_search_condition(
            search, search_fields
        )

        for _, relation_attr in search_joins.items():
            queryset = queryset.join(relation_attr)

        if combined_filters is not None and search_condition is not None:
            queryset = queryset.where(and_(combined_filters, search_condition))
        elif combined_filters is not None:
            queryset = queryset.where(combined_filters)
        elif search_condition is not None:
            queryset = queryset.where(search_condition)

        order_expression, order_joins = self._resolve_order_by(
            order_by=order_by,
        )

        for _, relation_attr in order_joins.items():
            queryset = queryset.join(relation_attr)

        if order_expression is not None:
            queryset = queryset.order_by(order_expression)

        queryset = self._apply_joins(queryset, joins)

        return queryset

    def build_list_queryset(
        self,
        **kwargs: Any,
    ) -> Select[Tuple[Any]]:
        """
        Construye el query inicial para listado.
        Retorna un objeto Select sobre el modelo SQLModel.
        """
        return select(self.model)

    async def list_paginated(
        self,
        page: int = 1,
        count: int = 25,
        filters: Optional[Dict[str, Any]] = None,
        use_or: bool = False,
        joins: Optional[List[str]] = None,
        order_by: Optional[Any] = None,
        search: Optional[str] = None,
        search_fields: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> tuple[List[Any], int]:
        # 1. Construir query base
        query_kwargs = {
            "filters": filters,
            "use_or": use_or,
            "joins": joins,
            "order_by": order_by,
            "search": search,
            "search_fields": search_fields,
        }
        try:
            queryset = self.build_list_queryset(**query_kwargs)
        except TypeError:
            queryset = self.build_list_queryset()

        # 2. Aplicar filtros estándar
        queryset = self.apply_list_filters(
            queryset=queryset,
            filters=filters,
            use_or=use_or,
            joins=joins,
            order_by=order_by,
            search=search,
            search_fields=search_fields,
        )

        db = self.session

        # Count total (usa execute() ya que es una consulta de agregación)
        count_query = select(func.count()).select_from(queryset.subquery())
        total = (await db.execute(count_query)).scalar_one()

        # Page items — usa execute() para preservar compatibilidad con
        # queries complejos (múltiples columnas / Result Hydration)
        offset = count * (page - 1)
        page_query = queryset.offset(offset).limit(count)
        result = await db.execute(page_query)
        rows = result.unique().all()

        items = []
        for row in rows:
            if len(row) == 1:
                items.append(row[0])
            else:
                # Query complejo: hidratar columnas extra sobre la entidad
                entity = row[0]
                column_keys = list(row._mapping.keys())

                for i in range(1, len(row)):
                    key = column_keys[i] if i < len(column_keys) else f"_extra_{i}"
                    setattr(entity, key, row[i])

                items.append(entity)

        return items, int(total)

    async def update(
        self,
        record_id: Union[str, UUID],
        update_data: Dict[str, Any],
    ) -> Any:
        """Actualiza un registro por ID con los campos provistos."""
        if not self.model:
            raise ValueError("El modelo no está definido en el repositorio")
        db = self.session
        record = await db.get(self.model, record_id)
        if not record:
            raise NotFoundException(
                message=f"{self.model.__name__} no encontrado"
            )
        for key, value in update_data.items():
            if value is not None and hasattr(record, key):
                setattr(record, key, value)
        await db.flush()
        await db.refresh(record)
        return record

    async def delete(
        self,
        record_id: Union[str, UUID],
        model: Optional[Type[Any]] = None,
    ) -> bool:
        """Elimina un registro por ID."""
        model = model or self.model
        if not model:
            raise ValueError("El modelo no está definido en el repositorio")
        db = self.session
        record = await db.get(model, record_id)
        if not record:
            raise NotFoundException(message=f"{model.__name__} no encontrado")
        await db.delete(record)
        await db.flush()
        return True
