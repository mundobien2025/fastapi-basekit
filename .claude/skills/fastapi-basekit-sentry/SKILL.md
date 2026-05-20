---
name: fastapi-basekit-sentry
description: >
  Wire Sentry / GlitchTip into a fastapi-basekit project with zero-overhead
  capture, PII scrubbing, and 4xx→warning / 5xx→error levels. Use proactively
  when: adding observability/error reporting to a fastapi-basekit app, asked to
  "add Sentry", "add GlitchTip", "wire up error tracking", "report exceptions",
  "PII scrubbing on errors", or when the project has `exception_handlers.py` but
  no Sentry hook. Also trigger when a fresh project is being scaffolded and
  observability has to be in place before going live.
tools: Read, Edit, Write, Bash, Glob, Grep
---

# fastapi-basekit — Sentry / GlitchTip observability

**Source of truth project:** `eventsvileads_backend/` (vileads_events_backend).

This skill codifies the exact pattern that ships there. Sentry and GlitchTip
are wire-compatible (same DSN format, same SDK), so the same files work for
both — point `SENTRY_DSN` at either backend.

---

## Core rule — capture lives in the exception handlers, not in middleware

A fastapi-basekit project **already has global exception handlers**
(`app/utils/exception_handlers.py`) that run once per raised exception. That is
the correct place to call `capture_exception(...)`. Adding a middleware to
inspect status codes would put overhead on **every** request — including 2xx
ones — for no gain.

| Concern | Home | NOT |
|---------|------|-----|
| SDK init + integrations | `app/utils/observability.py` (`init_sentry`) | inline in `main.py` |
| Sensitive-data filtering | `_scrub_event` (`before_send` hook) | per-handler `.pop()` calls |
| Per-exception capture | each handler in `app/utils/exception_handlers.py` | a new middleware |
| Level decision (warning vs error) | the handler that knows the status | a global rule |
| Settings (DSN, sample rates, PII flag) | `app/config/settings.py` (`Settings`) | hard-coded in `init_sentry` |
| Env documentation | `.env.example` (commented block) | README only |

If you are about to write `app.add_middleware(SentryAsgiMiddleware)` or
`app.add_middleware(ErrorReportingMiddleware)`: **STOP.** The
`exception → handler` cycle already runs; the handlers are the single point
of capture, and they have the request context the SDK needs.

---

## Why 4xx → warning and 5xx → error

| Status range | Sentry level | Reason |
|--------------|--------------|--------|
| 4xx (validation, auth, integrity, value) | `warning` | Client error, expected, noisy by design (401/404/422/429). Useful for trend visibility, not for on-call paging. |
| 5xx (catch-all, unexpected) | `error` | Server bug. Should page. |

Sentry's `FastApiIntegration` automatically captures unhandled 5xx exceptions.
We still call `capture_exception` from `global_exception_handler` to **guarantee
explicit context** (`path`, `method`, `query`) and a single point of control.
This is intentional duplication — the SDK dedupes by stack signature.

---

## PII discipline — `send_default_pii=False` + scrubber, always

Sentry's `send_default_pii=True` sends IP + full headers + body. Default off.
On top of that, `_scrub_event` (the `before_send` hook) **always** filters,
even if someone flips PII on later:

**Sensitive headers (filtered to `[Filtered]`):**

```
authorization, cookie, x-api-key, stripe-signature
```

**Sensitive body / query / extra keys (filtered to `[Filtered]`):**

```
password, current_password, new_password, secret, api_key, token,
refresh_token, access_token, stripe_api_key, credit_card, card_number, cvv
```

Both lists live in `app/utils/observability.py` as module-level sets — extend
there, not at the call site.

---

## 0. Before writing anything — read first

```bash
ls app/utils/                          # confirm exception_handlers.py exists
grep -n "add_exception_handler" app/main.py
grep -n "SENTRY_" app/config/settings.py
```

If `app/utils/exception_handlers.py` does not exist, the project is too early
for this skill — wire the handlers first (basekit's `APIException`,
`DatabaseIntegrityException`, `ValidationException`, plus FastAPI's
`RequestValidationError`, Pydantic's `ValidationError`, SQLAlchemy's
`IntegrityError`, and a final `Exception` catch-all). Then come back.

---

## 1. Dependency — pin range

Add to `requirements.txt` (or `pyproject.toml`):

```
sentry-sdk[fastapi]>=2.10,<3.0
```

The `[fastapi]` extra pulls Starlette + FastAPI integration deps. SDK 2.x
introduced the current `before_send` signature used by `_scrub_event`. Pin
under 3.0 until the next major review.

GlitchTip uses the same SDK — no separate client. Just point the DSN at the
self-hosted instance.

---

## 2. Settings — `app/config/settings.py`

Add to your `Settings` class (alongside the rest):

```python
# Observability — Sentry / GlitchTip
SENTRY_DSN: Optional[str] = None
# Default cae al valor de ENVIRONMENT si no se setea explicitamente.
SENTRY_ENVIRONMENT: Optional[str] = None
# Version/release tag para agrupar errores por deploy. Idealmente el SHA
# corto del commit (lo inyecta CI/CD como env var).
SENTRY_RELEASE: Optional[str] = None
# 0.0 = sin performance traces (ahorra cuota). Subir a 0.1 si querés.
SENTRY_TRACES_SAMPLE_RATE: float = 0.0
SENTRY_PROFILES_SAMPLE_RATE: float = 0.0
# send_default_pii — Sentry incluiria headers + IP + body por defecto.
# PII discipline (decisiones cliente): False. El scrubber de
# app/utils/observability.py ademas filtra explicitamente Authorization
# y campos sensibles aunque alguien suba esto a True.
SENTRY_SEND_PII: bool = False
```

Notes:

- `SENTRY_DSN` empty → `init_sentry()` is a silent no-op. The app runs
  unchanged.
- `SENTRY_ENVIRONMENT` and `SENTRY_RELEASE` fall back to `ENVIRONMENT` and
  `VERSION` respectively at init time. Don't duplicate those values.
- Keep `SENTRY_SEND_PII` defaulting to `False`. The scrubber still runs if
  someone flips it on.

---

## 3. `app/utils/observability.py` — copy verbatim

Create the file with this exact content (copied from the reference project,
not re-derived):

```python
"""Sentry / GlitchTip — init + helpers de captura.

GlitchTip es 100% compatible con `sentry_sdk` (mismo DSN, mismo formato).
La unica diferencia es apuntar `dsn` a la instancia self-hosted en vez de
sentry.io.

Uso:

    from app.utils.observability import init_sentry, capture_exception
    init_sentry()  # una sola vez al arrancar la app

    capture_exception(exc, path="/api/v1/x", method="POST", level="warning")

Si `SENTRY_DSN` no esta seteado, `init_sentry()` es no-op silencioso y
`capture_exception()` no hace nada — el codigo de la app no necesita saber
si Sentry esta o no instalado.
"""

import logging
from typing import Any, Dict, Optional

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# Headers a NUNCA enviar a Sentry, ni siquiera con send_default_pii=True.
_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "x-api-key",
    "stripe-signature",
}

# Claves de body/query/extra a censurar.
_SENSITIVE_BODY_KEYS = {
    "password",
    "current_password",
    "new_password",
    "secret",
    "api_key",
    "token",
    "refresh_token",
    "access_token",
    "stripe_api_key",
    "credit_card",
    "card_number",
    "cvv",
}


def _scrub_event(
    event: Dict[str, Any], hint: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """`before_send` hook — limpia headers/cuerpos sensibles antes de enviar."""
    request = event.get("request") or {}

    headers = request.get("headers") or {}
    if isinstance(headers, dict):
        for key in list(headers.keys()):
            if key.lower() in _SENSITIVE_HEADERS:
                headers[key] = "[Filtered]"

    for section in ("data", "query_string"):
        block = request.get(section)
        if isinstance(block, dict):
            for key in list(block.keys()):
                if key.lower() in _SENSITIVE_BODY_KEYS:
                    block[key] = "[Filtered]"

    extra = event.get("extra") or {}
    if isinstance(extra, dict):
        for key in list(extra.keys()):
            if key.lower() in _SENSITIVE_BODY_KEYS:
                extra[key] = "[Filtered]"

    return event


def init_sentry() -> bool:
    """Inicializa el SDK si SENTRY_DSN esta seteado.

    Returns:
        True si se inicializo, False si se salto (DSN vacio o ImportError).
    """
    settings = get_settings()
    dsn = settings.SENTRY_DSN

    if not dsn:
        logger.info("Sentry no inicializado (SENTRY_DSN vacio)")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("sentry-sdk no instalado; init_sentry() saltado")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
        release=settings.SENTRY_RELEASE or settings.VERSION,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        send_default_pii=settings.SENTRY_SEND_PII,
        before_send=_scrub_event,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
    )
    logger.info(
        "Sentry inicializado — env=%s release=%s",
        settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
        settings.SENTRY_RELEASE or settings.VERSION,
    )
    return True


def capture_exception(
    exc: BaseException, *, level: str = "error", **extra: Any
) -> None:
    """Captura una excepcion a Sentry. No-op si SDK no inicializado.

    `level`: "fatal" | "error" | "warning" | "info" | "debug". Usar
    "warning" para 4xx esperados (validation, auth fail), "error" para
    5xx genuinos.

    `extra`: kwargs que van a `scope.set_extra(key, value)`. Tipico:
    `path`, `method`, `status`, `tenant_id`, `actor_user_id`.
    """
    try:
        import sentry_sdk
    except ImportError:
        return

    with sentry_sdk.push_scope() as scope:
        scope.set_level(level)
        for k, v in extra.items():
            scope.set_extra(k, v)
        sentry_sdk.capture_exception(exc)
```

Notes on what you can and cannot change:

- **Do not move** `_SENSITIVE_HEADERS` / `_SENSITIVE_BODY_KEYS` out of the
  module. Extending the sets is fine; relocating them breaks the
  "single source of scrubbing truth" rule.
- **Do not change** the `try: import sentry_sdk` guard. It's what lets the
  app boot in environments where the SDK isn't installed (CI without
  observability deps, local dev without DSN).
- Project-specific integrations (Celery, MongoDB, etc.) are added to the
  `integrations=[...]` list. Don't replace the existing four
  (`Starlette`, `FastApi`, `Sqlalchemy`, `Redis`) unless the project
  genuinely doesn't use that layer.

---

## 4. Wire the exception handlers — `app/utils/exception_handlers.py`

Each handler calls `capture_exception(exc, level=, status=, **request_context)`
**before** building the response. The shared `_request_context(request)`
helper is the only module-level def allowed in this file — it returns the dict
the SDK needs (`path`, `method`, `query`).

```python
"""Global exception handlers — basekit BaseResponse envelope.

Cada handler reporta a Sentry/GlitchTip via `app.utils.observability.capture_exception`
ANTES de armar la response. Niveles:
  - 4xx (validation / auth / integrity / value) -> level="warning"
  - 5xx (catch-all) -> level="error"

No usamos middleware para esto — el ciclo `exception -> handler` ya corre
en cada error; agregar un middleware adicional para inspeccionar status
codes pondria overhead en TODAS las requests, incluso las 2xx.
"""

from typing import Any, Dict, List, Union

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi_basekit.exceptions.api_exceptions import (
    APIException,
    DatabaseIntegrityException,
    ValidationException,
)
from fastapi_basekit.schema.base import BaseResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.utils.observability import capture_exception


def _request_context(request: Request) -> Dict[str, Any]:
    """Contexto comun para todos los eventos Sentry."""
    return {
        "path": str(request.url.path),
        "method": request.method,
        "query": str(request.url.query) or None,
    }


async def api_exception_handler(request: Request, exc: APIException):
    # APIException cubre 401/403/404/422/etc. Nivel = warning para 4xx,
    # error para 5xx (raro en este handler — los 500 reales caen en el global).
    http_status = getattr(exc, "status", 400) or 400
    capture_exception(
        exc,
        level="error" if http_status >= 500 else "warning",
        status=http_status,
        **_request_context(request),
    )
    response = BaseResponse(status=exc.status_code, message=exc.message, data=exc.data)
    return JSONResponse(status_code=exc.status, content=response.model_dump())


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Re-raise como ValidationException -> cae en api_exception_handler ->
    # ahi se reporta a Sentry. Evita doble captura.
    raise ValidationException(data=exc.errors())


async def database_exception_handler(request: Request, exc: DatabaseIntegrityException):
    http_status = getattr(exc, "status", 400) or 400
    capture_exception(
        exc,
        level="warning",
        status=http_status,
        **_request_context(request),
    )
    response = BaseResponse(status=exc.status_code, message=exc.message, data=exc.data)
    return JSONResponse(status_code=exc.status, content=response.model_dump())


async def value_exception_handler(request: Request, exc: Union[ValidationError, ValueError]):
    if isinstance(exc, ValidationError):
        error_details: List[Dict[str, Any]] = exc.errors()
    else:
        error_details = [{"error": str(exc)}]

    capture_exception(
        exc,
        level="warning",
        status=400,
        **_request_context(request),
    )

    response = BaseResponse(
        status="VALUE_ERROR",
        message="Field validation error",
        data=str(error_details),
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(mode="json"),
    )


async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Convert IntegrityError to a friendly DatabaseIntegrityException response.

    Customize the matchers below per your domain (column names, constraints).
    """
    error_orig = exc.orig if hasattr(exc, "orig") else exc
    error_msg = str(error_orig).lower()

    if "email" in error_msg and ("duplicate" in error_msg or "unique" in error_msg):
        message = "Email already in use"
    elif "foreign key" in error_msg:
        message = "Referenced record does not exist"
    else:
        message = "Database integrity error"

    capture_exception(
        exc,
        level="warning",
        status=400,
        **_request_context(request),
    )

    response = BaseResponse(status="DATABASE_INTEGRITY_ERROR", message=message, data=None)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(),
    )


async def global_exception_handler(request: Request, exc: Exception):
    # 500 catch-all. Sentry's FastApiIntegration tambien lo capturaria
    # automaticamente; reportamos aqui igualmente para garantizar contexto
    # explicito (path + method) y un solo punto de control.
    capture_exception(
        exc,
        level="error",
        status=500,
        **_request_context(request),
    )

    response = BaseResponse(
        status="ERROR_GENERIC",
        message="Unknown error",
        data={"detail": str(exc)},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(),
    )
```

Why `validation_exception_handler` re-raises instead of capturing directly:
the re-raise routes through `api_exception_handler`, which already calls
`capture_exception` — capturing in both would emit two Sentry events per
422.

---

## 5. `main.py` — call `init_sentry()` **before** `create_application()`

```python
# app/main.py
import os
from app.config.settings import get_settings as _bootstrap_settings

# ...any pre-import env bridging...

from fastapi import FastAPI
# ...rest of imports...

from app.utils import exception_handlers
from app.utils.observability import init_sentry

settings = get_settings()

# Init Sentry ANTES de crear la app — las integraciones (Starlette/FastAPI/
# Sqlalchemy/Redis) tienen que parchar las libs antes de que se instancien.
# Sin DSN seteado, init_sentry() es no-op silencioso. Cero middleware:
# las capturas de error >= 400 se hacen desde los exception_handlers que ya
# corren por cada excepcion del request flow.
init_sentry()


def create_application() -> FastAPI:
    app = FastAPI(...)

    app.add_exception_handler(APIException, exception_handlers.api_exception_handler)
    app.add_exception_handler(ValidationException, exception_handlers.api_exception_handler)
    app.add_exception_handler(DatabaseIntegrityException, exception_handlers.database_exception_handler)
    app.add_exception_handler(IntegrityError, exception_handlers.integrity_error_handler)
    app.add_exception_handler(RequestValidationError, exception_handlers.validation_exception_handler)
    app.add_exception_handler(ValidationError, exception_handlers.value_exception_handler)
    app.add_exception_handler(Exception, exception_handlers.global_exception_handler)

    # ...middleware, routers, etc...
    return app


app = create_application()
```

**Order matters.** If `init_sentry()` runs after `FastAPI()` is instantiated,
`FastApiIntegration` / `StarletteIntegration` can't patch the running app.
Same for `SqlalchemyIntegration` if engines are created before init.

---

## 6. `.env.example` — documented block

```dotenv
# -----------------------------------------------------------------------------
# Observabilidad — Sentry / Glitchtip
# -----------------------------------------------------------------------------
# DSN del proyecto. Vacio = Sentry desactivado (no se inicializa, no se reporta).
SENTRY_DSN=

# Etiqueta de entorno en Sentry. Si vacio cae a ENVIRONMENT (local/dev/prod).
SENTRY_ENVIRONMENT=

# Release/version para agrupar errores por deploy. Idealmente el SHA corto
# del commit (CI/CD puede inyectarlo automaticamente).
SENTRY_RELEASE=

# Sample rate de performance traces. 0.0 = sin traces (solo errores), ahorra
# cuota. Subir a 0.1 (10%) si querés latencias/spans visibles en Sentry.
SENTRY_TRACES_SAMPLE_RATE=0.0

# Sample rate de profiling (perfiles de CPU). Requiere traces > 0 si activas.
SENTRY_PROFILES_SAMPLE_RATE=0.0

# send_default_pii: Sentry mandaria IP + headers + body completo. Default
# false (PII discipline). El scrubber en app/utils/observability.py filtra
# Authorization/Cookie/password/etc. aunque alguien suba esto a true.
SENTRY_SEND_PII=false

# Cobertura: los exception_handlers (app/utils/exception_handlers.py)
# reportan a Sentry toda excepcion 4xx (warning) y 5xx (error). Sin
# middleware extra — cero overhead en responses 2xx. Volume warning:
# 401/404/422/429 son ruidosos por diseno. Para silenciar codes especificos,
# filtrar dentro del handler correspondiente o usar before_send en
# app/utils/observability.py.
```

---

## 7. Verification checklist

Before considering the wiring done:

- [ ] `requirements.txt` has `sentry-sdk[fastapi]>=2.10,<3.0`.
- [ ] `app/config/settings.py` has all six `SENTRY_*` settings; `SENTRY_SEND_PII` defaults to `False`.
- [ ] `app/utils/observability.py` exists, with both `_SENSITIVE_HEADERS` and `_SENSITIVE_BODY_KEYS` sets, the `_scrub_event` hook, `init_sentry`, and `capture_exception`.
- [ ] Every handler in `app/utils/exception_handlers.py` calls `capture_exception` with `level=` and `**_request_context(request)`.
- [ ] `validation_exception_handler` re-raises (does not capture directly).
- [ ] `app/main.py` calls `init_sentry()` at module level, **before** `create_application()` (or `FastAPI(...)`).
- [ ] `.env.example` has the Sentry block with the cobertura note.
- [ ] No `SentryAsgiMiddleware` / `add_middleware(...)` for error reporting anywhere.
- [ ] Booting with `SENTRY_DSN=""` logs `"Sentry no inicializado (SENTRY_DSN vacio)"` and the app starts normally.

Optional sanity check (only if a DSN is configured and the user wants smoke
verification):

```python
# Add a temporary endpoint, hit it once, then remove.
@app.get("/__sentry-test")
async def _sentry_test():
    raise RuntimeError("sentry smoke test")
```

The error should appear in the Sentry / GlitchTip UI under the configured
environment + release, with `path`, `method`, and `query` in the
"Additional Data" section, and the `Authorization` header showing as
`[Filtered]`.

---

## 8. Common pitfalls

- **Adding `SentryAsgiMiddleware` "for good measure"**. The integrations
  already wire ASGI capture. The extra middleware causes double events
  on 5xx and adds overhead to every 2xx request.
- **Calling `init_sentry()` inside `create_application()`**. Too late for
  the integrations to patch — instantiating `FastAPI()` before init means
  `FastApiIntegration` has nothing to hook into. Module-level, before
  `create_application()`.
- **Capturing inside `validation_exception_handler`**. It re-raises into
  `api_exception_handler`, which captures. Capturing in both = duplicate
  events for every 422.
- **Hardcoding the DSN in code**. Always via `SENTRY_DSN` env var.
  Different per environment (local / staging / prod), and rotation
  shouldn't need a deploy.
- **Setting `SENTRY_SEND_PII=true` "to debug a specific bug"**. Don't.
  The scrubber still runs, but the IP and unfiltered headers leak. Add
  the specific extras you need via `capture_exception(..., user_id=...)`
  instead.
- **Putting domain-specific scrub keys at the call site**. Extend
  `_SENSITIVE_BODY_KEYS` in `observability.py` — that's the single
  source. Per-handler `.pop()` calls drift over time and miss new
  endpoints.
- **Forgetting the `try: import sentry_sdk` guard in `capture_exception`**.
  Without it, the app crashes in environments where the SDK isn't
  installed (e.g. lightweight CI image).

---

## 9. When to deviate

Only with a reason that fits one of these:

- **Project doesn't use SQLAlchemy or Redis** → drop the corresponding
  integration from the `integrations=[...]` list. Don't keep a dead one
  "in case".
- **Project uses Celery / RQ / arq** → add the matching integration
  (`CeleryIntegration`, etc.) to the list. Same pattern.
- **A specific 4xx code is too noisy** (e.g. 401 floods on a public API) →
  filter inside that handler before the `capture_exception` call, or
  short-circuit in `before_send` via `event.get("level")` /
  `hint["exc_info"]`. Don't drop the whole handler.
- **You need user context** (tenant id, actor) → pass via
  `capture_exception(..., tenant_id=..., actor_user_id=...)`. Goes to
  `scope.set_extra` automatically.

Anything else, stop and ask the user before deviating from the verbatim
templates above.
