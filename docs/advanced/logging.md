# Logging

La lib NO impone logging — usa Python `logging` standard. Recomendaciones para apps basekit:

## Setup mínimo en `main.py`

```python
import logging

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
```

## Per-module logger

```python
# app/services/thing_service.py
import logging

logger = logging.getLogger(__name__)


class ThingService(BaseService):
    async def publish(self, thing_id):
        logger.info("Publishing thing %s", thing_id)
        ...
```

## SQLAlchemy queries

Para ver queries en debug:

```python
# app/config/database.py
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,           # ← imprime cada query
)
```

O setear via env:
```bash
SQLALCHEMY_ECHO=true
```

## Audit log (sample model)

Si tu dominio requiere trazabilidad:

```python
class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50))      # create/update/delete
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[UUID | None] = mapped_column(GUID(), nullable=True)
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Y middleware/service hook que escribe a esta tabla en cada mutación.

## Structured logging (production)

`structlog` o `python-json-logger` para logs JSON parsables por Datadog/Loki/CloudWatch:

```python
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()
logger.info("user_login", user_id=str(user.id), ip=request.client.host)
```

## Request ID (tracing)

Middleware que asigna `X-Request-ID` por request:

```python
import uuid as _uuid
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(_uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

Loggear con `extra={"request_id": request.state.request_id}`.
