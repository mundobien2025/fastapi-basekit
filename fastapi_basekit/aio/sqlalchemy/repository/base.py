from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, Union
from uuid import UUID

from sqlalchemy import Select, and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from ....exceptions.api_exceptions import NotFoundException


class BaseRepository:
    """
    Repositorio base para SQLAlchemy Async.

    Define operaciones CRUD, acceso por filtros y carga de relaciones (joins).
    Establece `model` en la subclase (modelo ORM de SQLAlchemy).
    """

    model: Type[Any]

    def __init__(self, db: AsyncSession):
        """Inicializa el repositorio con la sesión a reutilizar."""
        self._session = db

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

    def _build_conditions(self, filters: Dict[str, Any]) -> List[Any]:
        """Construye condiciones a partir del diccionario de filtros."""
        return [self._get_field(fn) == value for fn, value in filters.items()]

    def _build_search_condition(
        self, search: Optional[str], search_fields: Optional[List[str]]
    ) -> Optional[Any]:
        """Construye una condición OR para búsqueda textual en múltiples campos

        Usa ilike (insensible a mayúsculas) si hay término y campos válidos.
        Ignora campos inexistentes silenciosamente.
        """
        if not search or not search_fields:
            return None
        exprs: List[Any] = []
        for field_name in search_fields:
            try:
                field = self._get_field(field_name)
            except AttributeError:
                # Si el campo no existe en el modelo, lo omitimos
                continue
            exprs.append(field.ilike(f"%{search}%"))
        if not exprs:
            return None
        return or_(*exprs)

    async def create(self, obj_in: Any | Dict) -> Any:
        """Crea un nuevo registro en la base de datos."""
        db = self.session
        if isinstance(obj_in, dict):
            obj_in = self.model(**obj_in)
        db.add(obj_in)
        await db.flush()
        await db.refresh(obj_in)
        return obj_in

    async def get(self, record_id: Union[str, UUID]) -> Optional[Any]:
        """Obtiene un registro por su ID."""
        if not self.model:
            raise ValueError("El modelo no está definido en el repositorio")
        return await self.session.get(self.model, record_id)

    async def get_by_field(self, field_name: str, value: Any) -> Optional[Any]:
        """Obtiene un registro por un campo específico."""
        field = self._get_field(field_name)
        result = await self.session.execute(
            select(self.model).where(field == value)
        )
        return result.scalars().first()

    async def get_with_joins(
        self,
        record_id: Union[str, UUID],
        joins: Optional[List[str]] = None,
    ) -> Optional[Any]:
        """Obtiene un registro por ID y carga relaciones dinámicamente."""
        if not self.model:
            raise ValueError("El modelo no está definido en el repositorio")
        query = select(self.model).where(self.model.id == record_id)
        query = self._apply_joins(query, joins)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_field_with_joins(
        self,
        field_name: str,
        value: Any,
        joins: Optional[List[str]] = None,
    ) -> Optional[Any]:
        """Obtiene un registro por un campo y carga relaciones
        dinámicamente."""
        field = self._get_field(field_name)
        query = select(self.model).where(field == value)
        query = self._apply_joins(query, joins)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_filters(
        self, filters: Dict[str, Any], use_or: bool = False
    ) -> Sequence[Any]:
        """Obtiene registros que coinciden con los filtros especificados."""
        if not self.model:
            raise ValueError("El modelo no está definido en el repositorio")
        conditions = self._build_conditions(filters)
        combined = or_(*conditions) if use_or else and_(*conditions)
        query = select(self.model).where(combined)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_filters_with_joins(
        self,
        filters: Dict[str, Any],
        use_or: bool = False,
        joins: Optional[List[str]] = None,
        one: bool = False,
    ) -> Sequence[Any] | Optional[Any]:
        """Obtiene registros por filtros y carga relaciones dinámicamente."""
        conditions = self._build_conditions(filters)
        combined = or_(*conditions) if use_or else and_(*conditions)
        query = select(self.model).where(combined)
        query = self._apply_joins(query, joins)
        result = await self.session.execute(query)
        return result.scalars().first() if one else result.scalars().all()

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
    ) -> tuple[List[Any], int]:
        """
        Lista registros con paginación y filtros, con soporte de joins.
        Retorna (items, total)
        """
        filters = filters or {}
        conditions = self._build_conditions(filters)
        combined_filters = (
            or_(*conditions)
            if (use_or and conditions)
            else and_(*conditions) if conditions else None
        )
        # Búsqueda por texto en múltiples campos
        search_condition = self._build_search_condition(search, search_fields)

        base_query = select(self.model)
        # Combina filtros y búsqueda si ambos existen
        if combined_filters is not None and search_condition is not None:
            base_query = base_query.where(
                and_(combined_filters, search_condition)
            )
        elif combined_filters is not None:
            base_query = base_query.where(combined_filters)
        elif search_condition is not None:
            base_query = base_query.where(search_condition)
        if order_by is not None:
            base_query = base_query.order_by(order_by)
        base_query = self._apply_joins(base_query, joins)

        # Count total
        db = self.session

        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        # Page items
        offset = count * (page - 1)
        page_query = base_query.offset(offset).limit(count)
        result = await db.execute(page_query)
        items = list(result.scalars().all())
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
