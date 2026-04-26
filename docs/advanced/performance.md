# Performance

## N+1 queries → `joins`

Mal:
```python
things = await repo.list_paginated()
for t in things:
    print(t.category.name)   # ← una query extra por thing
```

Bien — eager load:
```python
things, _ = await repo.list_paginated(joins=["category"])
```

`BaseRepository._apply_joins()` detecta tipo de relación:
- `uselist=True` (1:N) → `selectinload`
- `uselist=False` (N:1) → `joinedload`

## Joins por acción — `get_kwargs_query`

```python
def get_kwargs_query(self) -> dict:
    if self.action == "list_things":
        return {"joins": ["category", "owner"]}
    if self.action == "retrieve":
        return {"joins": ["category", "owner", "tags", "comments"]}
    return {}
```

## `selectinload` vs `joinedload`

- **`selectinload`** — segunda query con `WHERE id IN (...)`. Mejor para 1:N (sin row multiplication).
- **`joinedload`** — un JOIN, devuelve cartesian product. Mejor para N:1 simple.

```python
from sqlalchemy.orm import joinedload, selectinload

stmt = (
    select(Thing)
    .options(
        selectinload(Thing.tags),       # 1:N → 2 queries
        joinedload(Thing.category),     # N:1 → 1 query con JOIN
    )
)
```

## Connection pool

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,         # default 5
    max_overflow=10,      # default 10
    pool_pre_ping=True,   # ping antes de usar conexión (evita stale)
    pool_recycle=3600,    # reciclar cada hora
)
```

`NullPool` solo para tests (cada query abre + cierra conexión).

## Indexes

Models DEBEN declarar indexes en columnas filtradas/buscadas/joineadas:

```python
class Thing(BaseModel):
    __tablename__ = "things"

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    company_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("companies.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
```

Compound indexes:
```python
from sqlalchemy import Index

class Thing(BaseModel):
    __table_args__ = (
        Index("ix_things_company_status", "company_id", "status"),
    )
```

## Query profiling

```python
engine = create_async_engine(DATABASE_URL, echo=True)
```

Con `echo=True` cada query SQL se imprime. Cuenta tu N+1 ahí.

Para producción usa SQLAlchemy events:

```python
from sqlalchemy import event
import time

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before(conn, cursor, statement, parameters, context, executemany):
    context._query_start = time.time()

@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after(conn, cursor, statement, parameters, context, executemany):
    elapsed = time.time() - context._query_start
    if elapsed > 0.5:   # log slow queries
        logger.warning("Slow query (%.2fs): %s", elapsed, statement)
```

## Caching con Redis

```python
import json
from app.config.settings import settings
import redis.asyncio as aioredis


redis_client = aioredis.from_url(settings.redis_url)


async def get_cached(key: str):
    data = await redis_client.get(key)
    return json.loads(data) if data else None


async def set_cached(key: str, value: dict, ttl: int = 60):
    await redis_client.setex(key, ttl, json.dumps(value, default=str))
```

Cache aggressively read-heavy endpoints (catalogs, configs). Invalida en mutations.

## Async vs sync

Toda la lib es async. NO bloquees el event loop con:
- `requests.get()` → usa `httpx.AsyncClient`
- `time.sleep()` → usa `asyncio.sleep()`
- `boto3` → usa `aioboto3`

Para CPU-bound work (image resize, ML inference) usa `run_in_executor` o ARQ background tasks.

## Background tasks

```python
# Con ARQ
from arq.connections import ArqRedis

async def schedule_task(redis: ArqRedis, thing_id):
    await redis.enqueue_job("process_thing", thing_id)
```

Worker corre en proceso separado, libera el request thread.
