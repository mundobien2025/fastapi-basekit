# FastAPI BaseKit

Utilidades asíncronas y clases base para construir APIs con **FastAPI** usando **Beanie (MongoDB)** o **SQLAlchemy (AsyncSession)**. Provee una arquitectura consistente de **repositorios**, **servicios** y **controladores**, con tipado estricto vía **Pydantic**.

## Características

* **Clases genéricas listas para heredar**:

  * Repositorio: `BaseRepository`
  * Servicio: `BaseService`
  * Controlador: `BaseController` (Beanie) y `SQLAlchemyBaseController` (SQLA)
* **Esquemas de respuesta unificados**: `BaseResponse`, `BasePaginationResponse`.
* **Manejo de errores** con excepciones y handlers listos.
* **Servicios comunes** (ej. JWT).
* **Totalmente asíncrono**, facilita escalado horizontal.
* **Soporta Beanie y/o SQLAlchemy** mediante *extras* opcionales.
* **Consultas pluggables** por acción con `get_kwargs_query()` en servicios.

## Instalación

El núcleo es liviano; elige tu stack:

```bash
# Base (sin ORM)
pip install fastapi-basekit

# Beanie
pip install "fastapi-basekit[beanie]"

# SQLAlchemy (async)
pip install "fastapi-basekit[sqlalchemy]"

# Todo
pip install "fastapi-basekit[all]"
```

---

## Ejemplo 1: Beanie (MongoDB) — CRUD mínimo en 4 pasos

> Crea un CRUD funcional sobre un `Item` con paginación y búsqueda.

```python
# app.py
from contextlib import asynccontextmanager
from typing import Annotated,Optional

from beanie import Document, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import Depends, FastAPI, Query, APIRouter
from fastapi_restful.cbv import cbv

from fastapi_basekit.aio.beanie.repository.base import BaseRepository
from fastapi_basekit.aio.beanie.service.base import BaseService
from fastapi_basekit.aio.controller.base import BaseController
from fastapi_basekit.schema.base import BaseResponse, BasePaginationResponse
from fastapi_basekit.exceptions.handler import (
    api_exception_handler,
    validation_exception_handler,
)

# 1) Modelo Beanie
class Item(Document):
    name: str
    description: str | None = None

# 2) Repositorio
class ItemRepository(BaseRepository):
    model = Item

# 3) Servicio (reglas de negocio)
class ItemService(BaseService):
    repository: ItemRepository

    def __init__(self, repository: ItemRepository | None = None):
        super().__init__(repository or ItemRepository())
        self.search_fields = ["name", "description"]
        self.duplicate_check_fields = ["name"]  # opcional

    def get_kwargs_query(self) -> dict:
        # Personaliza por acción: list / retrieve / create / update / delete
        if self.action == "retrieve":
            return {"fetch_links": False}
        return super().get_kwargs_query()


# 3) Schemas

class ItemResponseSchema(BaseSchema):
    name: str
    description: Optional[str] = None

class ItemPResponseSchema(BasePaginationResponse[ItemResponseSchema]):
    pass    

# 4) Controlador (entra/sale HTTP)

item_router = APIRouter(tags=["core"])

@cbv(item_router)
class ItemController(BaseController):
    service: ItemService = Depends(ItemService)
    schema_class = Item  # para serializar/validar IO

    @item_router.get("/", response_model=ItemPResponseSchema)
    async def list(  # override para añadir paginación/búsqueda
        self,
        page: int = Query(1, ge=1, description="Número de página"),
        count: int = Query(10, ge=1, description="Cantidad de elementos"),
        search: str | None = Query(None, description="Término de búsqueda"),
    ) :
        return await super().list()

# FastAPI + Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(database=client.basekit_demo, document_models=[Item])
    yield

app = FastAPI(title="BaseKit Beanie Demo", lifespan=lifespan)

# Handlers de error recomendados
app.add_exception_handler(Exception, api_exception_handler)
app.add_exception_handler(ValueError, validation_exception_handler)

# Rutas
app.include_router(item_router, prefix="/api/v1")


**Qué te da este ejemplo**

* CRUD completo con **paginación** (`page`, `limit`) y **búsqueda** (`search`) sin reescribir lógica.
* Posibilidad de **personalizar las consultas** por acción desde el servicio (`get_kwargs_query`).
* Respuestas uniformes con `BaseResponse`/`BasePaginationResponse`.

---

## Ejemplo 2: SQLAlchemy (Async) — CRUD mínimo con sesión por request

> Patrón recomendado: middleware que inyecta `AsyncSession` en la request.

```python
# app_sqlalchemy.py
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from starlette.middleware.base import BaseHTTPMiddleware

from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from fastapi_basekit.schema.base import BaseResponse, BasePaginationResponse
from fastapi_basekit.exceptions.handler import global_exception_handler, validation_exception_handler

# 0) Base declarativa y modelo
class Base(DeclarativeBase): pass

class ItemORM(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]
    description: Mapped[str | None]

# 1) Motor y sessionmaker
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/basekit"
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

# 2) Middleware de sesión por request
class DatabaseSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        async with SessionLocal() as session:
            request.state.db_session = session
            try:
                response = await call_next(request)
                await session.commit()
                return response
            except Exception:
                await session.rollback()
                raise

def get_db_session(request: Request) -> AsyncSession:
    if not hasattr(request.state, "db_session"):
        raise RuntimeError("DatabaseSessionMiddleware no está configurado")
    return request.state.db_session

# 3) Repositorio
class ItemSQLARepository(BaseRepository):
    model = ItemORM

# 4) Servicio
class ItemSQLAService(BaseService):
    repository: ItemSQLARepository

    def __init__(self, repository: ItemSQLARepository, request: Request):
        super().__init__(repository=repository, request=request)
        self.search_fields = ["name", "description"]

    def get_kwargs_query(self) -> dict:
        # Por ejemplo, joins sólo en retrieve
        if self.action == "retrieve":
            return {"joins": []}
        return super().get_kwargs_query()

def get_item_service(request: Request) -> ItemSQLAService:
    db = get_db_session(request)
    repo = ItemSQLARepository(db)
    return ItemSQLAService(repository=repo, request=request)

# 5) Controlador + rutas
router = APIRouter()

class ItemsController(SQLAlchemyBaseController):
    service: Annotated[ItemSQLAService, Depends(get_item_service)]
    schema_class = ItemORM  # para tipado de respuesta

    @router.get("/items", response_model=BasePaginationResponse[ItemORM])
    async def list_items(
        self,
        page: Annotated[int, Query(1, ge=1)],
        limit: Annotated[int, Query(10, ge=1, le=100)],
        search: Annotated[str | None, Query(None)] = None,
    ):
        return await self.list(page=page, count=limit, search=search)

    @router.get("/items/{id}", response_model=BaseResponse[ItemORM])
    async def retrieve_item(self, id: int):
        return await self.retrieve(id)

    @router.post("/items", response_model=BaseResponse[ItemORM])
    async def create_item(self, payload: dict):
        return await self.create(payload)

    @router.patch("/items/{id}", response_model=BaseResponse[ItemORM])
    async def update_item(self, id: int, payload: dict):
        return await self.update(id, payload)

    @router.delete("/items/{id}")
    async def delete_item(self, id: int):
        return await self.delete(id)

app = FastAPI(title="BaseKit SQLAlchemy Demo")
app.add_middleware(DatabaseSessionMiddleware)
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(ValueError, validation_exception_handler)
app.include_router(router, prefix="")
```

**Notas rápidas**

* El **repositorio** recibe la sesión `AsyncSession` en el constructor.
* El **servicio** centraliza reglas (ej. campos de búsqueda, duplicados, `get_kwargs_query`).
* El **controlador** sólo adapta IO HTTP y reusa los métodos base.

---

## Convenciones clave

* **Acciones**: `list`, `retrieve`, `create`, `update`, `delete`.
  En `BaseService` puedes leer `self.action` para decidir comportamiento por acción.
* **Búsqueda**: define `self.search_fields` en el servicio.
* **Chequeo de duplicados**: usa `self.duplicate_check_fields`.
* **Consultas por acción**: sobreescribe `get_kwargs_query()` en el servicio.
* **Respuestas**: usa `BaseResponse[T]` y `BasePaginationResponse[T]` para uniformidad.

## Errores y handlers

Incluye los handlers recomendados para respuestas limpias:

```python
from fastapi_basekit.exceptions.handler import (
    api_exception_handler,
    duplicate_key_exception_handler,  # útil en Beanie/Mongo
    global_exception_handler,
    validation_exception_handler,
    value_exception_handler,
)
```

## Servicios adicionales

* **JWTService**: creación/validación/refresh de JWT (importa desde `fastapi_basekit.servicios`).

## Tests

Instala dependencias y ejecuta:

```bash
pytest
```

---

## Licencia

MIT

