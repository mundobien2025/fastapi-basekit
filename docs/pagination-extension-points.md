# Paginación y listados — puntos de extensión (la parte donde la IA se confunde)

Referencia autoritativa. Destilada de TODOS los proyectos que usan fastapi-basekit
(pulbot/Beanie, axion_accounter/SQL, sereno, predator, eventsvileads, auxilio_ve).
Si vas a escribir o modificar un endpoint de listado, esta es la fuente de verdad.

---

## La regla de hierro

**El motor de paginación NO se toca.** El `count`, el `skip`/`offset`, el `limit`
y el `$facet` viven en UN método por ORM:

- SQL: `BaseRepository.list_paginated`
- Beanie: `BaseRepository.paginate` (FindMany) y `paginate_pipeline` (aggregation)

Copiar/reescribir ese loop en un service o controller es el anti-patrón #1 de la
librería. Toda personalización baja por un **hook**. El endpoint casi siempre es:

```python
@router.get("/", response_model=BasePaginationResponse[XSchema])
async def list_x(self, page: int = Query(1, ge=1), count: int = Query(20),
                 is_active: bool | None = Query(None)):
    return await super().list()     # ← una línea; los Query son solo para OpenAPI
```

Señales de que estás reescribiendo el motor (= hook equivocado): `func.count(`,
`.offset(`, `.skip(`, `.limit(`, o armar `{items, total, page, count}` a mano
dentro de un listado.

---

## Cómo fluye un listado (la cadena de hooks)

```
Controller.list()                     # arma params desde los Query, llama service.list, formatea
  └─ Service.list()                   # get_filters + get_order + get_kwargs_query + build_list_*
       └─ Repository.list_paginated / paginate / paginate_pipeline   # ← EL MOTOR, no se toca
            └─ build_list_queryset / build_list_pipeline / apply_list_filters   # hooks de query
       └─ Service.post_process_list() # enrich de la página, después de paginar
```

Cada capa tiene su punto de extensión. Elegí el más ALTO que resuelva tu caso
(un filtro simple → `get_filters`, no `build_list_queryset`).

---

## Mapa caso → hook

| Necesidad | Hook | Capa |
|-----------|------|------|
| Scope multi-tenant / por usuario (seguridad) | `get_filters` o `build_list_queryset` leyendo `request.state` | Service / Repo |
| Renombrar filtro front → campo del modelo | `get_filters` | Service |
| Rango de fechas / operadores `>=` `<=` `EXISTS` `IN` `ilike` | `build_list_queryset` (SQL) · `build_list_pipeline`/`build_filter_query` (Beanie) | Repo |
| Filtro simple | `get_filters` | Service |
| Orden por defecto | atributo `order_by` / `get_order()` | Service |
| Columnas computadas / `*_name` por fila | `build_list_queryset` (subqueries `.label()`) · `build_list_pipeline` (`$lookup`) | Repo |
| Eager-load / joins según acción | `get_kwargs_query()` + `self.action` | Service |
| Schema distinto por acción | `get_schema_class()` + `self.action` | Controller |
| Consultar modelos DISTINTOS por acción | switch por `self.action` en `get_kwargs_query`/`build_list_queryset` o elección de repo | Service |
| Enriquecer items de la página | `post_process_list(items)` | Service |
| `$lookup` + shape plano (no-modelo) | `use_aggregation=True` + `aggregation_validate=False` + `build_list_pipeline` | Service |
| Búsqueda de texto | atributo `search_fields` | Service |
| Soft-delete | `get_filters` o `where deleted_at is null` en `build_list_queryset` | Service / Repo |
| Scroll infinito / cursor | `paginate_keyset` en método + endpoint DEDICADO | Repo / Controller |
| Dropdown / lista completa | método propio del service, NO `self.list()` | Service / Controller |

---

## Los hooks, uno por uno

### `get_filters(filters)` — filtros que dependen del usuario/acción (Service)
El seam más usado. Scoping de seguridad, rename de params, rango de fechas simple.
Cierra SIEMPRE con `super().get_filters(filters)`.

```python
def get_filters(self, filters=None):
    filters = super().get_filters(filters)
    filters["user.$id"] = self.request.state.user.id      # scope (Beanie)
    # rename de param del front:
    if "status" in filters: filters["crm_status"] = filters.pop("status")
    return filters
```

**Alcance ≠ permiso.** `get_filters` decide QUÉ filas ve el user. El permiso
decide si ENTRA al endpoint. No los mezcles. Y el scope de seguridad NO debe
depender de que el front mande el filtro — para candado duro, aplícalo en
`build_list_queryset` leyendo `request.state` (así aplica siempre).

### `order_by` / `get_order()` — orden por defecto (Service)
```python
order_by = "-created_at"          # SQL: string
# Beanie: def get_order(self): return [("last_message_at", -1)]
```

### `get_kwargs_query()` + `self.action` — comportamiento por acción (Service)
Eager-load caro solo cuando conviene; o elegir joins/opciones por acción.
```python
def get_kwargs_query(self):
    if self.action in ("list_addresses", "retrieve"):
        return {"joins": ["customer", "country"]}     # SQL
        # Beanie: return {"fetch_links": True, "nesting_depths_per_field": {...}}
    return super().get_kwargs_query()
```

### `build_list_queryset(**kwargs)` — la query base (Repo, SQL)
Para lo que `get_filters` no puede: rangos, `EXISTS`, `OR` entre FKs, columnas
computadas con subqueries, scoping duro. Recibe `filters` en kwargs. NO toques
count/offset — solo devuelve el `Select`.
```python
def build_list_queryset(self, **kwargs):
    filters = kwargs.get("filters") or {}
    q = select(self.model, company_name_subq.label("company_name"))
    if filters.get("date_from"): q = q.where(self.model.created_at >= filters["date_from"])
    # candado de seguridad (SIEMPRE, no depende del front):
    user = getattr(self.service.request.state, "user", None)
    if user and not is_master(user):
        q = q.where(self.model.company_id == user.company_id)
    return q
```
Las columnas `.label()` se hidratan solas sobre la entidad en `list_paginated`.

### `build_list_pipeline(...)` + `use_aggregation` — agregación (Repo/Service, Beanie)
Para `$lookup` cross-collection o un shape plano. Activa `use_aggregation=True`;
si la proyección no es el modelo, `aggregation_validate=False`. Devuelve las
etapas SIN el `$facet` (ese lo pone `paginate_pipeline`).

### `post_process_list(items)` — enrich de la página (Service) **[nuevo]**
Corre DESPUÉS de paginar, sobre los items de la página. Para agregar un contador,
resolver un campo derivado, etc. Reemplaza el viejo patrón de "override `list()`
para enriquecer" (que rompe el paginado si olvidas `super().list()`).
```python
async def post_process_list(self, items):
    ids = [c.id for c in items]
    counts = await self.conv_repo.count_by_customer_ids(ids)
    for c in items:
        c.metadata = {**(c.metadata or {}), "conversation_count": counts.get(c.id, 0)}
    return items
```
NO cambies `total` ni filtres items acá (el total es de la query completa).
**Gotcha Beanie/pydantic:** solo podés setear campos DECLARADOS del Document (o
un dict como `metadata`); no atributos nuevos al vuelo como en SQLAlchemy.

### `paginate_keyset` — scroll infinito / cursor (Repo)
Para historial/scroll a escala (sin `count()` ni `skip` profundo). Va en un
método + endpoint DEDICADO, NO se mezcla con el `list` CRUD. El mismo recurso
puede tener ambos: `list` offset genérico y `list_keyset` para scroll.

---

## Consultar modelos DISTINTOS en un mismo controller

Bifurca por `self.action` (el nombre del endpoint). Dos formas:

```python
# En el service: elegir query/repo según la acción
def build_list_queryset(self, **kwargs):
    if self.action == "list_archived":
        return select(ArchivedX)
    return select(X)

# O el controller elige el schema de salida por acción
def get_schema_class(self):
    return XDetailSchema if self.action in ("retrieve", "create") else XListSchema
```

`self.action` se puebla del nombre de la función endpoint; fíjalo a mano
(`self.action = "list_units"`) si tu handler no delega en el CRUD estándar.

---

## Anti-patrones reales (lo que NO se hace)

Todos vistos en el código de los proyectos. Son "reescribir el motor en vez de
usar el hook":

1. **Loop reescrito en el service** — `func.count()` + `.offset().limit()` propios
   que duplican `list_paginated`. La razón que motivó el override (resolver un id,
   inyectar permiso) va en `get_filters`/`build_list_queryset`.
2. **Métodos `list_*_paginated` con skip/limit/count a mano** para el listado del
   endpoint. Solo válido en métodos de dominio con nombre propio que NO son el
   `list` CRUD (historial, stats, drains).
3. **Armar `{items, total, page, limit}` a mano en el controller** en vez de
   `super().list()` + `BasePaginationResponse`. Si solo cambia el mapeo, usa
   `get_schema_class`/`model_validator` del schema o `post_process_list`.
4. **Hook `build_list_queryset` huérfano** — overrideado pero el endpoint llama a
   otro método (`list_all`), así que nunca corre. Si overrideas el hook, el
   endpoint termina en `super().list()`.
5. **`build_queryset()` fantasma en el service** — el hook de query vive en el
   REPO (`build_list_queryset`), no en el service. Un método así no lo llama nadie.
6. **Early-return con tipo malo** en un override de `list()` — devolvé `([], 0)`,
   no `[]`. La firma es `Tuple[List, int]`.
7. **Scoping de seguridad que depende de un filtro del front** — el candado
   multi-tenant se aplica SIEMPRE en `build_list_queryset` leyendo `request.state`.
8. **Suponer operadores en las claves de filtro** (`campo__gte`) — basekit resuelve
   solo `==`/`in`; la sintaxis `__` es para navegar relaciones (`user__role__code`),
   no operadores. Los rangos van a mano en `build_list_queryset`.
9. **Abandonar basekit y rehacer el motor de paginación** — el final de camino de
   "la IA reescribe el loop". No.

---

## Checklist antes de mergear un endpoint de listado

- [ ] ¿El handler termina en `return await super().list()`? (o hay razón real documentada)
- [ ] ¿Hay `func.count(`/`.offset(`/`.skip(`/`.limit(` fuera del repo base? → mover a un hook
- [ ] ¿El scope de seguridad aplica SIEMPRE (no depende del front)?
- [ ] ¿El enrich va en `post_process_list`, no en un override de `list()`?
- [ ] ¿El filtro de rango/operador va en `build_list_queryset`, no inventando `campo__gte`?
