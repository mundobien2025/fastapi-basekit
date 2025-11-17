# 📚 Ejemplos de FastAPI BaseKit

Esta carpeta contiene ejemplos completos y reales de cómo usar FastAPI BaseKit en diferentes escenarios.

## 📁 Estructura de Ejemplos

### 1. `simple_crud/` - CRUD Básico

Ejemplo más simple para empezar. Muestra cómo crear un CRUD completo con:
- Modelo SQLAlchemy básico
- Schemas Pydantic
- Repository, Service y Controller
- Búsqueda y filtrado básico
- Validación de duplicados

**Archivos**:
- `models.py` - Modelo de usuario simple
- `schemas.py` - Schemas Pydantic
- `repository.py` - Repository base
- `service.py` - Service con búsqueda y validación
- `controller.py` - Controller con endpoints REST

**Uso**:
```python
# Importar el router
from examples.simple_crud.controller import router

# Agregar a tu app FastAPI
app.include_router(router)
```

---

### 2. `advanced_queryset/` - Queryset Personalizado

Ejemplo avanzado que muestra cómo personalizar el queryset base usando `build_queryset()`:
- Agregaciones (COUNT, SUM)
- JOINs complejos con múltiples tablas
- GROUP BY y agregaciones
- Campos calculados

**Características**:
- ✅ No necesitas reescribir `list()`
- ✅ Los filtros se aplican automáticamente sobre tu query personalizado
- ✅ Mantiene paginación y búsqueda

**Archivos**:
- `models.py` - Modelos con relaciones (User, Referral, Order)
- `schemas.py` - Schema con campos agregados (referidos_count, total_orders)
- `service.py` - **build_queryset()** con agregaciones
- `controller.py` - Controller que usa el queryset personalizado

**Ejemplo de build_queryset()**:
```python
def build_queryset(self) -> Select:
    query = (
        select(
            User,
            func.count(Referral.id).label("referidos_count"),
            func.sum(Order.total).label("total_spent"),
        )
        .outerjoin(Referral, User.id == Referral.user_id)
        .outerjoin(Order, User.id == Order.user_id)
        .group_by(User.id)
    )
    return query
```

---

### 3. `with_relations/` - Relaciones y Joins Dinámicos

Ejemplo que muestra cómo manejar relaciones y evitar queries N+1:
- Relaciones uno a muchos
- Relaciones muchos a muchos
- Joins dinámicos con `get_kwargs_query()`
- Eager loading automático

**Archivos**:
- `models.py` - Modelos con relaciones (User, Role)
- `schemas.py` - Schemas con relaciones anidadas
- `service.py` - **get_kwargs_query()** para joins dinámicos
- `controller.py` - Controller con relaciones cargadas

**Ejemplo de get_kwargs_query()**:
```python
def get_kwargs_query(self) -> dict:
    if self.action in ["list", "retrieve"]:
        return {"joins": ["role", "roles"]}
    return {}
```

---

### 4. `with_permissions/` - Sistema de Permisos

Ejemplo completo de control de acceso:
- Permisos personalizados
- Verificación por rol (admin)
- Verificación por propiedad (owner)
- Combinación de permisos

**Archivos**:
- `models.py` - Modelo de usuario con campo is_admin
- `schemas.py` - Schemas básicos
- `permissions.py` - **Permisos personalizados** (IsAdmin, IsOwnerOrAdmin)
- `service.py` - Service básico
- `controller.py` - Controller con **check_permissions()**

**Ejemplo de permisos**:
```python
class IsAdmin(BasePermission):
    async def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return getattr(user, "is_admin", False) if user else False

# En el controller
def check_permissions(self) -> List[Type[BasePermission]]:
    return [IsAdmin]
```

---

## 🚀 Cómo Usar los Ejemplos

### Opción 1: Copiar y Adaptar

1. Copia la carpeta del ejemplo que necesites
2. Adapta los modelos a tu caso de uso
3. Ajusta los schemas según tus necesidades
4. Personaliza el service si es necesario

### Opción 2: Usar como Referencia

1. Lee el código del ejemplo
2. Entiende la estructura y patrones
3. Aplica los conceptos a tu proyecto

### Opción 3: Ejecutar Directamente

```bash
# Instalar dependencias
pip install fastapi-basekit[sqlalchemy]

# Configurar base de datos
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/dbname"

# Ejecutar ejemplo
python -m examples.simple_crud
```

---

## 📖 Guía de Conceptos

### build_queryset()

Método que puedes sobrescribir en tu Service para personalizar el query base **antes** de aplicar filtros.

**Cuándo usarlo**:
- Necesitas agregaciones (COUNT, SUM, AVG)
- Quieres JOINs complejos
- Necesitas GROUP BY
- Quieres campos calculados

**Ejemplo**:
```python
def build_queryset(self) -> Select:
    return select(
        User,
        func.count(Referral.id).label("referidos_count")
    ).outerjoin(Referral, User.id == Referral.user_id).group_by(User.id)
```

### get_kwargs_query()

Método que retorna configuración adicional para el repositorio según la acción.

**Cuándo usarlo**:
- Cargar relaciones solo en ciertas acciones
- Configurar joins dinámicamente
- Aplicar opciones según el contexto

**Ejemplo**:
```python
def get_kwargs_query(self) -> dict:
    if self.action == "list":
        return {"joins": ["role"]}
    return {}
```

### get_filters()

Método que transforma o valida filtros antes de aplicarlos.

**Cuándo usarlo**:
- Transformar formatos de fecha
- Validar rangos
- Aplicar lógica de negocio a filtros

**Ejemplo**:
```python
def get_filters(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    applied = filters or {}
    if "date_from" in applied:
        # Convertir formato, validar, etc.
        pass
    return applied
```

### check_permissions()

Método que define qué permisos se requieren para cada acción.

**Cuándo usarlo**:
- Control de acceso basado en roles
- Verificación de propiedad
- Permisos combinados

**Ejemplo**:
```python
def check_permissions(self) -> List[Type[BasePermission]]:
    if self.action in ["create", "delete"]:
        return [IsAdmin]
    return [IsOwnerOrAdmin]
```

---

## 🔗 Enlaces Relacionados

- [README Principal](../README.md) - Documentación completa
- [Changelog](../CHANGELOG.md) - Historial de cambios
- [Tests](../tests/) - Tests de ejemplo

---

## 💡 Tips

1. **Empieza simple**: Usa `simple_crud/` como base
2. **Agrega complejidad gradualmente**: Añade relaciones, permisos, etc.
3. **Reutiliza patrones**: Los ejemplos muestran patrones reutilizables
4. **Personaliza según necesites**: Adapta los ejemplos a tu caso de uso

---

## ❓ Preguntas Frecuentes

**¿Puedo combinar varios ejemplos?**
Sí, puedes combinar conceptos de diferentes ejemplos. Por ejemplo, usar `build_queryset()` junto con permisos.

**¿Los ejemplos funcionan con MongoDB?**
Los ejemplos actuales usan SQLAlchemy. Para MongoDB/Beanie, adapta los modelos y queries según la documentación de Beanie.

**¿Cómo agrego más ejemplos?**
Crea una nueva carpeta en `examples/` con tu ejemplo y documenta su propósito en este README.

---

<div align="center">

**¿Tienes dudas?** Abre un [issue](https://github.com/mundobien2025/fastapi-basekit/issues) o consulta la [documentación](../README.md)

</div>

