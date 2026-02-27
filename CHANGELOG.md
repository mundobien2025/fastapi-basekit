# Changelog

Todos los cambios importantes de fastapi-basekit serán documentados aquí.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [0.2.0] - 2026-02-27

### ✨ Agregado

- **Soporte para SQLModel ORM** (`fastapi_basekit.aio.sqlmodel`)
  - `BaseRepository` — repositorio async con `sqlmodel.ext.asyncio.session.AsyncSession`.
    Usa `session.exec()` para queries tipados sobre modelos SQLModel; mantiene
    `session.execute()` para consultas de agregación y queries complejos con
    Result Hydration. Contrato idéntico al repositorio SQLAlchemy.
  - `BaseService` — servicio base que referencia el repositorio SQLModel.
    Mismas operaciones: `retrieve`, `list`, `create`, `update`, `delete`.
  - `SQLModelBaseController` — controlador base con soporte para `joins`,
    `use_or` y `order_by`. La serialización aprovecha que los modelos SQLModel
    son también modelos Pydantic (`model_dump()` nativo).
  - `to_dict()` simplificado en el controlador gracias a la integración
    Pydantic de SQLModel.

- **Dependencia opcional `sqlmodel`** en `pyproject.toml`
  - Instalar con: `pip install fastapi-basekit[sqlmodel]`
  - Incluido en el extra `[all]`.

## [0.1.25] - 2026-02-11

### ✨ Agregado

- **Vínculo bidireccional Servicio-Repositorio**
  - `BaseRepository` ahora tiene un atributo `service` que referencia al servicio que lo utiliza.
  - `BaseService` vincula automáticamente su instancia (`self`) a todos los repositorios inyectados durante la inicialización.

### 🔧 Cambiado

- **Refactor de Construcción de QuerySet**
  - Se eliminó el método redundante `build_queryset` de `BaseService`.
  - El método `BaseRepository.list_paginated` ahora es el único responsable de iniciar la construcción del query a través de `build_list_queryset()`.
  - Se simplificó la firma de `list_paginated` eliminando el parámetro `base_query`.
  - `BaseService.list` ahora es más limpio al delegar la gestión del query completamente al repositorio.

### 🔧 Mejorado

- **Inicialización de Servicios**
  - `BaseService.__init__` ahora acepta `**kwargs` y vincula automáticamente cualquier instancia de `BaseRepository` pasada como argumento nombrado, permitiendo que servicios complejos con múltiples repositorios mantengan el vínculo correctamente.

## [0.1.16] - 2025-10-14

### ✨ Agregado

- **Controllers completamente separados por ORM/ODM**

  - `BeanieBaseController`: Controller específico para proyectos con MongoDB/Beanie
  - `SQLAlchemyBaseController`: Controller específico para proyectos con SQLAlchemy
  - Cada controller tiene implementación completa y optimizada para su ORM/ODM
  - Ya no hay herencia de un `BaseController` genérico compartido

- **SQLAlchemyBaseController: Nuevas capacidades**

  - Soporte completo para JOINs con `joins` parameter
  - Soporte para expresiones `ORDER BY` personalizadas
  - Operador `OR` en filtros con `use_or=True`
  - Método `to_dict()` mejorado para modelos SQLAlchemy
  - `_params_excluded_fields` incluye automáticamente `use_or`, `joins`, `order_by`

- **BeanieBaseController: Optimizado para MongoDB**

  - Implementación optimizada para documentos Beanie
  - Extracción automática de parámetros sin frames extras
  - Método `to_dict()` específico para documentos MongoDB

- **Documentación completa**
  - Nuevo archivo `CONTROLLERS_GUIDE.md` con guía detallada
  - Ejemplos de uso para cada controller
  - Tabla comparativa de características
  - Guía de migración desde versiones anteriores

### 🔧 Cambiado

- **Dependencias más flexibles**

  - `fastapi`: `>=0.116.1,<0.117` (antes: `==0.116.1`)
  - `pydantic`: `>=2.11.7,<3` (antes: `==2.11.7`)
  - `fastapi-restful[all]`: `>=0.6.0,<0.7` (antes: `==0.6.0`)
  - `SQLAlchemy[asyncio]`: `>=2.0.43,<3` (antes: `==2.0.43`)
  - `psycopg2`: `>=2.9.10,<3` (antes: `==2.9.10`)

- **BaseController.format_response()**
  - Parámetro `status` renombrado a `response_status` para evitar conflictos
  - Mejora la compatibilidad con imports de Starlette/FastAPI

### 🐛 Corregido

- **`_params()` ahora funciona correctamente en SQLAlchemyBaseController**

  - Solucionado problema de introspección de frames
  - Agregado parámetro `skip_frames` para navegar correctamente en la pila
  - SQLAlchemy ahora usa `skip_frames=2` para capturar parámetros correctamente

- **Eliminado conflicto con parámetro `status`**
  - El parámetro `status` en `format_response()` podía generar conflictos
  - Ahora se llama `response_status` para mayor claridad

### 📚 Documentación

- README actualizado con sección de controllers separados
- Guía completa en `CONTROLLERS_GUIDE.md`
- Ejemplos actualizados para ambos controllers
- Tabla comparativa de características

### 🔄 Migración desde v0.1.15

**Antes:**

```python
from fastapi_basekit.aio.controller.base import BaseController
```

**Ahora:**

```python
# Para SQLAlchemy
from fastapi_basekit.aio.sqlalchemy import SQLAlchemyBaseController

# Para Beanie
from fastapi_basekit.aio.beanie import BeanieBaseController
```

El `BaseController` genérico sigue disponible para compatibilidad, pero se recomienda usar los controllers específicos.

---

## [0.1.15] - 2025-10-XX

### Agregado

- Controller base genérico con soporte para Beanie y SQLAlchemy
- Sistema de permisos basado en clases
- Extracción automática de parámetros con `_params()`
- Paginación automática
- Búsqueda multi-campo

### Cambiado

- Mejoras en la estructura del proyecto

---

## [0.1.0] - 2025-XX-XX

### Agregado

- Versión inicial de fastapi-basekit
- Soporte básico para SQLAlchemy y Beanie
- Repositorios base
- Servicios base
- Schemas base

---

[0.1.25]: https://github.com/mundobien2025/fastapi-basekit/compare/v0.1.16...v0.1.25
[0.1.16]: https://github.com/mundobien2025/fastapi-basekit/compare/v0.1.15...v0.1.16
[0.1.15]: https://github.com/mundobien2025/fastapi-basekit/compare/v0.1.0...v0.1.15
[0.1.0]: https://github.com/mundobien2025/fastapi-basekit/releases/tag/v0.1.0

