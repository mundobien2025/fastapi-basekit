# fastapi-basekit

Clases base para APIs FastAPI async. **Soporta dos ORMs: SQLAlchemy/SQLModel (SQL) y Beanie (MongoDB).** Muchas firmas difieren entre ellos — ver la tabla de divergencias. Es la fuente #1 de errores al escribir código con esta lib.

## Modelo mental (una sola idea)

Tres capas, cada una con UN trabajo. El request baja y sube por ellas:

```
Controller (@cbv)   → HTTP: rutas, status, wrapping de respuesta. NADA de lógica.
   └─ Service        → reglas de negocio, orquestación, scoping (get_filters), validación.
        └─ Repository → queries y persistencia. NADA de reglas de negocio.
```

Regla dura: el controller es delgado (`return await super().list()` o delega al service). La lógica vive en el service; las queries en el repo. Un `def _helper` suelto en cualquiera de esos archivos es un smell.

## Qué ORM estoy tocando (verifícalo SIEMPRE primero)

```
fastapi_basekit/aio/
├── sqlalchemy/{controller,repository,service}/base.py   ← SQL (AsyncSession)
├── sqlmodel/{...}                                        ← SQL (wrapper delgado de SQLAlchemy)
├── beanie/{controller,repository,service}/base.py        ← MongoDB (Document/Link)
└── controller/base.py                                    ← BaseController agnóstico (heredan todos)
```

`import` del proyecto consumidor te dice cuál es: `from beanie import Document` → Beanie; `AsyncSession`/`DeclarativeBase` → SQL. **pulbot-backend usa Beanie.** axion_accounter usa SQLAlchemy.

## Tabla de divergencias — nivel REPOSITORY (esto rompe a la IA)

El **service** unifica la API (ver más abajo). El **repository** NO. Si llamas un repo directo, usa la firma del ORM correcto:

| Operación | SQLAlchemy repo | Beanie repo |
|-----------|-----------------|-------------|
| get por id | `get(id)` → `Optional` | **`get_by_id(id)`** → `Optional` |
| crear | `create(obj_in \| dict)` | `create(obj \| dict)` |
| actualizar | `update(id, dict)` — **salta valores None** | **`update(obj, dict)`** — el 1er arg es el **Document**, no el id; sí setea None |
| borrar | `delete(id)` → `bool` | **`delete(obj)`** → `None` — recibe el Document |
| por campo | `get_by_field(name, val)` | `get_by_field(name, val)` · `get_by_fields(dict)` |
| construir listado | `build_list_queryset(...)` + `list_paginated(...)` | `build_list_queryset(...)`→FindMany + `paginate(...)` · o `build_list_pipeline(...)` + `paginate_pipeline(...)` para joins/`$lookup` |

Trampa clásica: en Beanie **`repo.update(id, {...})` está MAL** (setea atributos sobre el string del id). Correcto: `obj = await repo.get_by_id(id); await repo.update(obj, {...})`. O mejor, usa el service.

## API del SERVICE (unificada — preferí SIEMPRE esta capa)

Ambos ORMs exponen la MISMA firma de service, así que el código de negocio es portable:

- `retrieve(id)` → obj o `NotFoundException`
- `list(search=, page=, count=, filters=, order_by=)` → `(items, total)`
- `create(payload)` — valida `duplicate_check_fields`
- `update(id, data)` — fetch + update (internamente resuelve la divergencia del repo)
- `delete(id)`

Seams para override (aquí va tu personalización, NO overrideando handlers):

- **`get_filters(filters)`** → scoping por tenant/owner. **Este es el seam de seguridad.** Filtra el listado a lo que el user puede ver.
- `get_order()` → orden por defecto, `[("created_at", -1)]`.
- `get_kwargs_query()` → opciones de query (ej. Beanie `fetch_links`).
- `build_list_queryset(...)` / `build_list_pipeline(...)` → componer query antes de paginar.
- `post_process_list(items)` → enriquecer los items YA paginados (después de paginar, sobre la página).
- Config de clase: `search_fields`, `duplicate_check_fields`, `order_by`, `use_aggregation` (Beanie, fuerza pipeline).

Ver la sección **PAGINACIÓN** abajo para el mapa completo caso→hook — es la parte donde la IA más se equivoca.

### Alcance ≠ permiso (seam de seguridad)
`get_filters()` decide QUÉ filas ve el user (row-level scoping). Va en el service (o `repo.build_list_queryset`). **Llamar `repository.get_by_id(id)` directo BYPASSEA `get_filters()`** → un user lee/edita recursos de otro tenant (clase de bug IDOR). Si necesitas un objeto por id con scope, usa `service.retrieve(id)` o agrega el check de owner explícito. No metas alcance en `check_permissions` (eso es permiso, no alcance).

## PAGINACIÓN — el motor NO se toca (la regla más importante)

> Esta es la parte donde la IA se confunde MÁS. Léela entera antes de escribir
> cualquier endpoint de listado.

**REGLA DE HIERRO: nunca reescribas el loop de paginación.** El `count`, el
`skip`/`offset`, el `limit` y el `$facet` viven en UN solo lugar por ORM y no se
copian:
- SQL: `BaseRepository.list_paginated` (repo).
- Beanie: `BaseRepository.paginate` (FindMany) y `paginate_pipeline` (aggregation).

El endpoint de listado casi siempre es UNA línea: declara los `Query(...)` (solo
para OpenAPI/validación) y hace `return await super().list()`. TODA la
personalización baja por un HOOK. Si estás escribiendo `func.count(`, `.offset(`,
`.skip(`, `.limit(` o armando el `PaginationResponse` a mano dentro de un
listado, elegiste el hook equivocado.

### Mapa: "quiero X en el listado" → hook exacto

| Necesidad | Hook / seam | Capa |
|-----------|-------------|------|
| Scope multi-tenant / por usuario (seguridad) | `get_filters` (o `build_list_queryset` leyendo `request.state` — candado que NO depende del front) | Service / Repo |
| Renombrar filtro del front → campo del modelo | `get_filters` | Service |
| Filtro por rango de fechas / operadores (`>=`,`<=`,`EXISTS`,`IN`,`ilike`) | `build_list_queryset` (SQL) · `build_list_pipeline`/`build_filter_query` (Beanie) — **basekit solo resuelve `==`/`in`; los rangos van acá** | Repo |
| Filtro específico simple | `get_filters` | Service |
| Orden por defecto | atributo `order_by` / `get_order()` | Service |
| Columnas computadas / `*_name` en cada fila | `build_list_queryset` (subqueries `.label()`, SQL — se hidratan solas) · `build_list_pipeline` (`$lookup`+`$project`, Beanie) | Repo |
| Eager-load / joins SEGÚN la acción | `get_kwargs_query()` + `self.action` | Service |
| Schema de respuesta distinto por acción (list vs detalle) | `get_schema_class()` + `self.action` | Controller |
| **Consultar modelos DISTINTOS en un mismo controller** | switch por `self.action` dentro de `get_kwargs_query`/`build_list_queryset`, o el service elige repo/query por acción | Service |
| Enriquecer los items DE LA PÁGINA (contador, campo derivado, +1 `await`) | **`post_process_list(items)`** (corre después de paginar) | Service |
| Join `$lookup` + shape plano (no-modelo) | `use_aggregation=True` + `aggregation_validate=False` + `build_list_pipeline` (Beanie) | Service |
| Búsqueda de texto | atributo `search_fields` | Service |
| Soft-delete (no listar borrados) | filtro extra en `get_filters` o `where deleted_at is null` en `build_list_queryset` | Service / Repo |
| Scroll infinito / cursor | `paginate_keyset` en un método + endpoint DEDICADO (no mezclar con el `list` CRUD) | Repo / Controller |
| Dropdown / lista completa sin paginar | método propio del service, NO `self.list()` | Service / Controller |

### `self.action` = el nombre de la función del endpoint

`self.action` NO es solo "list/retrieve/create". basekit lo setea al
`request.scope["endpoint"].__name__`, o sea el nombre de TU método
(`list_conversations`, `list_users`, `summary`, `list_for_checkin`…). Por eso los
switches bifurcan por esos nombres. Fíjalo a mano al inicio del handler si tu
endpoint no delega en el CRUD estándar.

### Ejemplos mínimos de cada seam

```python
# Service: scope + orden + join por acción + enrich de la página
class ConversationService(BaseService[Conversation]):
    search_fields = ["title"]
    order_by = "-last_message_at"            # orden por defecto

    def get_filters(self, filters=None):     # scope de seguridad
        filters = super().get_filters(filters)
        filters["user.$id"] = self.request.state.user.id
        return filters

    def get_kwargs_query(self):              # eager-load solo en list/retrieve
        if self.action in ("list_conversations", "retrieve"):
            return {"fetch_links": True}
        return super().get_kwargs_query()

    async def post_process_list(self, items):   # enrich de la página (sin romper paginado)
        ids = [c.id for c in items]
        counts = await self.msg_repo.count_by_conversation_ids(ids)
        for c in items:
            c.unread = counts.get(c.id, 0)
        return items
```

```python
# Repo: rango de fechas + columna computada (SQL). basekit solo hace ==, el
# rango se arma acá. NO se toca count/offset.
def build_list_queryset(self, **kwargs):
    filters = kwargs.get("filters") or {}
    q = select(self.model, company_name_subq.label("company_name"))
    if filters.get("date_from"): q = q.where(self.model.created_at >= filters["date_from"])
    if filters.get("date_to"):   q = q.where(self.model.created_at <= filters["date_to"])
    return q
```

### ANTI-PATRONES reales (lo que NO se hace)

Vistos en los proyectos — todos son "reescribir el motor en vez de usar el hook":
- **Reescribir el loop en el service** (`func.count()` + `.offset().limit()` propios). Es duplicar `list_paginated`. La resolución/permiso que motivó el override va en `get_filters`/`build_list_queryset`.
- **Métodos `list_*_paginated` con skip/limit/count a mano en el repo** para el listado del endpoint. Solo válido en métodos de dominio con nombre propio que NO son el `list` CRUD (historial, stats) — nunca para reemplazar el listado estándar.
- **Armar `{items, total, page, limit}` a mano en el controller** en vez de `super().list()` + `BasePaginationResponse`. Si solo cambia el mapeo de salida, usa `get_schema_class`/`model_validator` del schema o `post_process_list`.
- **Override de `build_list_queryset` HUÉRFANO**: overridear el hook pero que el endpoint llame a otro método (`list_all`) — el hook nunca corre. Si overrideas el hook, el endpoint debe terminar en `super().list()`.
- **`build_queryset()` fantasma en el service**: el hook de query vive en el REPO (`build_list_queryset`), no en el service.
- **Early-return con tipo malo** en un override de `list()`: debe devolver la tupla `([], 0)`, no `[]`.
- **Abandonar basekit y rehacer un motor de paginación propio** (pasó en salescontrol): el resultado de "la IA reescribe el loop" elevado a arquitectura. No.

Doc completa con más casos: `docs/pagination-extension-points.md`.

## Permisos — NO hay metaclass (regla que la IA suele romper)

`permission_classes` NO se aplican solos. `prepare_action(action)` corre `check_permissions()`, y se llama EXPLÍCITO:

- Los CRUD base (`super().list()`, `super().retrieve(id)`, etc.) ya lo llaman. Si tu endpoint solo delega, estás cubierto.
- **Un endpoint CUSTOM corre SIN check de permisos** salvo que su primera línea sea `await self.prepare_action("<accion>")`. Olvidarlo salta `permission_classes` en silencio.

```python
@router.post("/{id}/approve")
async def approve(self, id: str):
    await self.prepare_action("approve")   # ← SIN esto no hay permiso
    return await self.service.approve(id)
```

## De dónde salen page/count/search/filters (magia de `_params`)

El `BaseController.list()` NO recibe esos args por firma. `_params()` los reconstruye leyendo `request.query_params` + introspección del stack-frame del método llamador (`inspect.currentframe()`). Por eso los ves aparecer "de la nada". Gotcha: el frame-skip difiere por capa — base usa `skip_frames=1`, `BeanieBaseController.list` usa `skip_frames=2`. Si escribes un `list` custom y la paginación sale vacía, es el `skip_frames`. Declara los `Query(...)` en la firma del endpoint para que FastAPI los valide; `_params` los recoge.

## Errores — dos idiomas, cuándo cada uno

- **`APIException` y subclases** (`exceptions/api_exceptions.py`: `NotFoundException`, `PermissionException`, `DatabaseIntegrityException`, …) — traen el HTTP status horneado. Las lanza la lib y las traduce `register_exception_handlers`. Úsalas para casos estándar CRUD.
- **`DomainError`** (`exceptions/domain.py`) — error de dominio con `STATUS_CODE_MAP`; subclaséalo para errores de negocio propios y tradúcelo a HTTP en el endpoint. NO está registrado en el handler global, así que un `DomainError` que escape del endpoint cae al 500 genérico — atrápalo o mapéalo tú.

No lances `HTTPException` cruda desde services/repos (acopla la capa web a la lógica).

## Patrón canónico de código

### Controller `@cbv` (una clase, N endpoints)

```python
router = APIRouter(prefix="/resources", tags=["Resources"])

@cbv(router)
class ResourceController(BeanieBaseController):        # o SQLAlchemyBaseController
    service: ResourceService = Depends(get_resource_service)
    schema_class = ResourceResponseSchema
    permission_classes = [IsAuthenticated]

    @router.get("/", response_model=BasePaginationResponse[ResourceResponseSchema])
    async def list(self, page: int = Query(1, ge=1), count: int = Query(20)):
        return await super().list()

    @router.post("/", response_model=BaseResponse[ResourceResponseSchema])
    async def create(self, data: ResourceCreateSchema):
        return await super().create(data)
```

### Factory de dependencia — SIEMPRE en `dependency.py`

```python
# SQLAlchemy
def get_resource_service(request: Request, db: AsyncSession = Depends(get_db)) -> ResourceService:
    return ResourceService(repository=ResourceRepository(db=db), request=request)

# Beanie (sin session; el Document ya está inicializado en el lifespan)
def get_resource_service(request: Request) -> ResourceService:
    return ResourceService(repository=ResourceRepository(), request=request)
```

### Scoping por tenant en el service

```python
class ResourceService(BaseService):
    search_fields = ["name"]

    def get_filters(self, filters=None):
        filters = super().get_filters(filters)
        filters["user_id"] = self.request.state.user.id   # row-level scope
        return filters
```

## GOTCHAS que tumban a la IA (leer antes de codear)

1. **NO hay metaclass** — endpoints custom sin `prepare_action` corren sin permisos. (arriba)
2. **Beanie `update`/`delete`/`get_by_id` toman el DOCUMENT o nombre distinto**, no el id como en SQL. (tabla)
3. **`repository.get_by_id(id)` directo bypassea `get_filters()`** → IDOR. Usa `service.retrieve`.
4. **`update` en SQL salta None; en Beanie no.** No puedes "nullear" una columna vía `repo.update` en SQL. (`get(id)`/`get_by_id(id)` ya funcionan en ambos.)
5. **Operadores de filtro `__gte`/`__lte`/`__in`/`__ne`/`__like`/`__ilike`: SQL (SQLAlchemy Y SQLModel).** Beanie NO los tiene (usa dict `$gte` en `build_list_pipeline`). La sintaxis `__` sin operador conocido navega relaciones (`user__role__code`).
6. **`_params` lee la firma del endpoint** (no frames) — si un filtro no aplica, revisa que el param esté DECLARADO en la firma con su tipo.
7. **`JWTService` FALLA si falta `JWT_SECRET`** (ya no cae a clave pública). Setea el env; para dev local, `JWT_ALLOW_INSECURE_DEV_SECRET=1`.
8. **Response schemas: `id: uuid.UUID` (SQL) / convertir ObjectId→str (Beanie)** para que `model_validate` no falle.

## Tipos: Generics (parametriza tus bases)

Las bases son `Generic[ModelT]`. Declara el modelo en el parámetro genérico y
tu IDE/mypy/IA infieren TODO el CRUD tipado (el paquete trae `py.typed`, así que
los tipos SÍ llegan a los consumidores):

```python
class UserRepository(BaseRepository[User]):   # SQLAlchemy/SQLModel/Beanie
    model = User

class UserService(BaseService[User]):
    repository: UserRepository
```

A partir de ahí:
- `repo.get(id)` / `repo.get_by_id(id)` → `Optional[User]`
- `repo.create(...)` / `repo.update(...)` → `User`
- `service.retrieve(id)` / `service.create(...)` → `User`
- `service.list(...)` → `tuple[list[User], int]`

Sin el parámetro genérico (`class UserRepository(BaseRepository)`) todo cae a
`Any` y pierdes autocompletado/checks — SIEMPRE parametriza.

## Convenciones

- Response schema con `from_attributes=True`; campos derivados con `@computed_field`/`model_validator` EN el schema, no en el controller.
- En cuerpos `@cbv`, usar `List` de `typing` en `BasePaginationResponse[...]`.
- No importar `Request`/`AsyncSession`/`get_db` en controllers.

## Comandos

```bash
pytest tests/                 # tests
python -m build               # build (requiere `pip install build`)
pip install -e .              # dev
```

## Skills en `.claude/skills/`

- **`fastapi-basekit-crud`** — scaffold completo de recurso CRUD (SQLAlchemy + Beanie).
- **`fastapi-basekit-docker-layout`** — layout Docker del proyecto.
- **`fastapi-basekit-sentry`** — wire Sentry/GlitchTip (observability + captura desde handlers, PII scrubbing).

## Estado / deuda (issue #12 del repo)

Hecho (2026-07-12, sin commit aún):
- `_params` sin introspección de frames (coerción por firma del endpoint, cacheada por endpoint) — arregla listados vacíos/errores en controllers cbv.
- `Generic[ModelT]` (OPCIONAL — subclase sin `[Model]` funciona igual) + `py.typed` en repos/services de los 3 ORMs.
- Fix mutable-default leak portado a los services SQLAlchemy/SQLModel.
- Lectura por id UNIFICADA: `get(id)` **y** `get_by_id(id)` funcionan en los 3 ORMs (aliases).
- Operadores de filtro (`__gte`/`__lte`/`__in`/`__ne`/`__like`/`__ilike`) portados a SQLModel (antes los descartaba en silencio).
- `JWTService` FALLA FUERTE si falta `JWT_SECRET` (antes clave pública `secret_dev_key`); guard de `JWT_EXPIRE_SECONDS`; `iat` en tokens.
- `DomainError` que escapa del endpoint ahora se mapea a su `STATUS_CODE_MAP` (antes caía al 500 genérico).
- `psycopg2-binary` en extras (evita build de fuente).
- Hooks de paginación completos + guard-rails "NO REIMPLEMENTES" en el motor (ver sección PAGINACIÓN).
- Metaclass de auto-permisos: NO viable con el cbv actual (rompe rutas) — endpoints custom deben llamar `prepare_action` a mano.

Pendiente (único, diferido a propósito):
- Dedup interno SQLAlchemy↔SQLModel (~90% duplicado) → factorizar un mixin SQL compartido. Es refactor de mantenibilidad, alto blast-radius; hacerlo como cambio propio con validación del suite de consumidores. `update(id,dict)` (SQL, omite None) vs `update(obj,dict)` (Beanie, setea None) siguen divergentes por semántica — documentado en la tabla, no se unifican por diseño.
