from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, Union
from uuid import UUID

from sqlalchemy import Select, and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Relationship, joinedload, selectinload

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

    def _resolve_attribute(
        self, filters: Dict[str, Any]
    ) -> Tuple[Dict[str, Tuple[Any, Any]], Dict[str, Any]]:
        """
        Resuelve los atributos finales y las relaciones para JOINs a partir
        de una ruta con '__'.

        Soporta filtrado avanzado con relaciones usando sintaxis de doble
        guion bajo (__). Por ejemplo:
        - Filtro simple: {"status": "active"} → WHERE users.status = 'active'
        - Filtro con relación: {"user_roles__role__code": "Impulsado"} →
          JOINs automáticos + condición WHERE

        Args:
            filters: Diccionario con filtros que pueden incluir rutas con '__'

        Returns:
            Tuple con:
            - resolved_filters: Dict con (columna/atributo final, valor
              procesado)
            - joins_to_apply: Dict con las relaciones que necesitan JOINs
              (nombre_relacion: atributo_relacion)

        Note:
            Los filtros que no se pueden resolver (campos/relaciones
            inexistentes) se omiten silenciosamente. Si todos los filtros
            son omitidos, `resolved_filters` estará vacío y los métodos
            que usan este resultado deben manejar este caso (retornando
            lista vacía o None según corresponda).
        """
        resolved_filters = {}
        joins_to_apply = {}

        for filter_path, value in filters.items():
            parts = filter_path.split("__")

            # Inicialización
            current_model = self.model
            attr = getattr(current_model, parts[0], None)

            if attr is None:
                # Si no existe el campo base, omitir silenciosamente
                # (mantiene compatibilidad con código existente)
                continue

            # Procesar valor (manejo de Enum a su valor/lista de valores)
            processed_value = value
            if (
                isinstance(value, (list, tuple))
                and value
                and hasattr(value[0], "value")
            ):
                processed_value = [v.value for v in value]
            elif hasattr(value, "value"):
                processed_value = value.value

            # 1. Recorrer la cadena de relaciones intermedias
            for part in parts[1:]:
                # Chequear si el atributo actual es una relación ORM
                if hasattr(attr.property, "entity") and isinstance(
                    attr.property, Relationship
                ):
                    # Es una relación: Añadir al diccionario de JOINs si no
                    # está ya
                    relation_name = (
                        attr.key
                    )  # Nombre del atributo en el modelo
                    # (e.g., 'user_roles')
                    joins_to_apply[relation_name] = attr

                    # Mover al modelo relacionado y obtener el siguiente
                    # atributo
                    current_model = attr.property.mapper.class_
                    attr = getattr(current_model, part, None)

                    if attr is None:
                        break  # El siguiente campo no existe
                else:
                    # No es una relación (parte final del path), romper el
                    # bucle
                    break

            # 2. Si el atributo final es válido, añadir a las condiciones
            # resueltas
            # Verificamos si es una Columna (o un campo scalar)
            # Para columnas simples, attr.property.columns existe
            # Para relaciones, attr.property es Relationship
            if attr is not None:
                # Verificar que no sea una relación (solo queremos columnas)
                is_relationship = isinstance(attr.property, Relationship)
                # Verificar que sea una columna o atributo válido
                is_column = hasattr(attr.property, "columns") or hasattr(
                    attr, "comparator"
                )

                if not is_relationship and is_column:
                    resolved_filters[filter_path] = (attr, processed_value)

        return resolved_filters, joins_to_apply

    def _build_conditions(
        self,
        filters: Optional[Dict[str, Any]] = None,
        resolved_filters: Optional[Dict[str, Tuple[Any, Any]]] = None,
    ) -> List[Any]:
        """
        Construye condiciones WHERE a partir de los atributos resueltos.

        Soporta dos modos de uso:
        1. Modo legacy (retrocompatibilidad): Pasa filters directamente
        2. Modo avanzado: Pasa resolved_filters con atributos ya resueltos

        Args:
            filters: Diccionario de filtros simples (modo legacy)
            resolved_filters: Diccionario con (atributo, valor_procesado)
                             (modo avanzado)

        Returns:
            Lista de condiciones SQLAlchemy
        """
        conditions: List[Any] = []

        # Modo avanzado: usar resolved_filters si está disponible
        if resolved_filters is not None:
            for _, (field, processed_value) in resolved_filters.items():
                # Aplicar la lógica de IN o ==
                if isinstance(
                    processed_value, (list, tuple)
                ) and not isinstance(processed_value, str):
                    conditions.append(field.in_(processed_value))
                else:
                    conditions.append(field == processed_value)
        # Modo legacy: compatibilidad con código existente
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

    async def _get_one(
        self,
        conditions: Optional[List[Any]] = None,
        joins: Optional[List[str]] = None,
        raise_exception: bool = False,
    ) -> Optional[Any]:
        """
        Método interno unificado para obtener un único registro.

        Args:
            conditions: Lista de condiciones WHERE
            joins: Lista de relaciones para carga eager
            raise_exception: Si True, lanza excepción si no se encuentra

        Returns:
            Registro encontrado o None
        """
        if not self.model:
            raise ValueError("El modelo no está definido en el repositorio")

        query = select(self.model)
        if conditions:
            query = query.where(and_(*conditions))

        query = self._apply_joins(query, joins)

        result = await self.session.execute(query)
        record = result.scalars().first()

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
        # Si el campo tiene sintaxis '__', usar resolución de atributos
        if "__" in field_name:
            # Resolver el atributo y aplicar JOINs necesarios
            resolved_filters, joins_to_apply = self._resolve_attribute(
                {field_name: value}
            )

            if not resolved_filters:
                return None

            # Obtener el atributo resuelto
            _, (field, processed_value) = next(iter(resolved_filters.items()))

            # Construir query con JOINs de filtrado
            query = select(self.model)

            # Aplicar JOINs de filtrado
            for relation_name, relation_attr in joins_to_apply.items():
                query = query.join(relation_attr)

            # Aplicar condición
            query = query.where(field == processed_value)

            # Aplicar joins de carga
            query = self._apply_joins(query, joins)

            result = await self.session.execute(query)
            return result.scalars().first()
        else:
            # Campo simple, usar método estándar
            field = self._get_field(field_name)
            return await self._get_one(
                conditions=[field == value], joins=joins
            )

    async def get_by_filters(
        self, filters: Dict[str, Any], use_or: bool = False
    ) -> Sequence[Any]:
        """
        Obtiene registros que coinciden con los filtros especificados.

        Soporta filtros simples y filtros con relaciones usando sintaxis '__'.
        """
        if not self.model:
            raise ValueError("El modelo no está definido en el repositorio")

        # Resolver filtros y JOINs necesarios
        resolved_filters, joins_to_apply = self._resolve_attribute(filters)

        # Inicializar query
        query = select(self.model)

        # Aplicar JOINs de filtrado si hay relaciones
        for relation_name, relation_attr in joins_to_apply.items():
            query = query.join(relation_attr)

        # Construir condiciones
        conditions = self._build_conditions(resolved_filters=resolved_filters)

        # Verificar si hay condiciones antes de combinarlas
        # and_() y or_() requieren al menos un argumento
        if not conditions:
            # Si no hay condiciones válidas después de resolver filtros,
            # retornar lista vacía (comportamiento restrictivo)
            return []

        combined = or_(*conditions) if use_or else and_(*conditions)
        query = query.where(combined)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_filters_with_joins(
        self,
        filters: Dict[str, Any],
        use_or: bool = False,
        joins: Optional[List[str]] = None,
        one: bool = False,
    ) -> Sequence[Any] | Optional[Any]:
        """
        Obtiene registros por filtros y carga relaciones dinámicamente.

        Soporta filtros simples y filtros con relaciones usando sintaxis '__'.
        Los JOINs de filtrado se aplican automáticamente cuando se detectan
        relaciones en los filtros.
        """
        # Resolver filtros y JOINs necesarios
        resolved_filters, joins_to_apply = self._resolve_attribute(filters)

        # Inicializar query
        query = select(self.model)

        # Aplicar JOINs de filtrado
        for relation_name, relation_attr in joins_to_apply.items():
            query = query.join(relation_attr)

        # Construir condiciones
        conditions = self._build_conditions(resolved_filters=resolved_filters)

        # Verificar si hay condiciones antes de combinarlas
        # and_() y or_() requieren al menos un argumento
        if not conditions:
            # Retornar None si one=True, o lista vacía si one=False
            return None if one else []

        combined = or_(*conditions) if use_or else and_(*conditions)
        query = query.where(combined)

        # Aplicar joins de carga (joinedload/selectinload)
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
        base_query: Optional[Select[Tuple[Any]]] = None,
    ) -> tuple[List[Any], int]:
        """
        Lista registros con paginación, filtros universales y soporte de joins.

        Soporta filtrado avanzado con relaciones usando sintaxis '__'.
        Por ejemplo:
        - Filtro simple: {"status": "active"}
        - Filtro con relación: {"user_roles__role__code": "Impulsado"}
        - Múltiples valores: {"status": ["active", "pending"]}

        Args:
            base_query: Query base personalizado. Si no se proporciona,
                       se usa select(self.model) por defecto.
            filters: Diccionario de filtros que puede incluir rutas con '__'
            use_or: Si True, combina filtros con OR en lugar de AND
            joins: Lista de relaciones para carga eager
                   (joinedload/selectinload)
            order_by: Expresión de ordenamiento
            search: Término de búsqueda textual
            search_fields: Campos donde buscar el término de búsqueda
            page: Número de página (1-indexed)
            count: Cantidad de items por página

        Returns:
            Tuple con (items, total)
        """
        filters = filters or {}

        # 1. Inicializar query base
        if base_query is None:
            base_query = select(self.model)

        # 2. RESOLUCIÓN UNIVERSAL DE FILTROS (JOINs de filtrado y atributos)
        resolved_filters, joins_to_apply = self._resolve_attribute(filters)

        # 3. Aplicar JOINs de filtrado
        for relation_name, relation_attr in joins_to_apply.items():
            base_query = base_query.join(relation_attr)

        # 4. Construir las condiciones WHERE a partir de los atributos
        # resueltos
        conditions = self._build_conditions(resolved_filters=resolved_filters)
        combined_filters = (
            or_(*conditions)
            if (use_or and conditions)
            else and_(*conditions) if conditions else None
        )

        # 5. Aplicar búsqueda textual (search)
        search_condition = self._build_search_condition(search, search_fields)

        # 6. Combina todos los filtros (combined_filters, search_condition)
        if combined_filters is not None and search_condition is not None:
            base_query = base_query.where(
                and_(combined_filters, search_condition)
            )
        elif combined_filters is not None:
            base_query = base_query.where(combined_filters)
        elif search_condition is not None:
            base_query = base_query.where(search_condition)

        # 7. Aplicar orden y joins de carga
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
        rows = result.unique().all()

        # Procesar filas para soportar "Result Hydration"
        items = []
        for row in rows:
            # Si la fila tiene un solo elemento, tratarlo como escalar normal
            if len(row) == 1:
                items.append(row[0])
            else:
                # Fila compleja: tomar el primer elemento como entidad
                entity = row[0]

                # Obtener las claves de las columnas del resultado
                # La primera columna es la entidad, las demás son
                # anotaciones/etiquetas
                column_keys = list(row._mapping.keys())

                # Inyectar dinámicamente los valores extra en la entidad
                # principal. Empezar desde el índice 1 (el índice 0 es la
                # entidad principal)
                for i in range(1, len(row)):
                    # Obtener el nombre de la columna (puede ser una etiqueta
                    # o nombre de columna)
                    if i < len(column_keys):
                        key = column_keys[i]
                    else:
                        # Si no hay nombre de columna, usar un nombre genérico
                        key = f"_extra_{i}"

                    value = row[i]

                    # Inyectar el valor como atributo dinámico en la entidad
                    setattr(entity, key, value)

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
