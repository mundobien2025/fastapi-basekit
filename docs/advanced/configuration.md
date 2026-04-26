# Configuración global

## Estructura de `Settings`

```python
# app/config/settings.py
from typing import Annotated, List, Optional
from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v):
    if isinstance(v, str):
        return [o.strip() for o in v.split(",") if o.strip()]
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env" if not os.environ.get("RUNNING_IN_DOCKER") else None,
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    DATABASE_URL: str
    DEBUG: bool = True
    ALLOWED_ORIGINS: Annotated[List[str], BeforeValidator(parse_cors)] = []
```

## `lru_cache` para `get_settings()`

```python
from functools import lru_cache

@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

Re-leer `.env` por request es caro. `lru_cache` lo lee una vez por proceso.

## Override por entorno

```bash
# Local
export DEBUG=true

# Production
export DEBUG=false
export ALLOWED_ORIGINS=https://app.example.com
```

`pydantic-settings` lee env vars con prioridad sobre `.env`.

## Settings nested

```python
class RedisSettings(BaseSettings):
    HOST: str = "localhost"
    PORT: int = 6379
    PASSWORD: Optional[str] = None
    model_config = SettingsConfigDict(env_prefix="REDIS_")


class Settings(BaseSettings):
    redis: RedisSettings = RedisSettings()
```

ENV: `REDIS_HOST=foo REDIS_PORT=6380`.

## Computed properties

```python
class Settings(BaseSettings):
    REDIS_HOST: str
    REDIS_PORT: int

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"
```

## Test mode override

`app/config/database.py` ya detecta `RUNNING_TESTS=true` o `pytest` en argv → cambia a `TEST_DATABASE_NAME` y usa `NullPool`. Ver [Configuration](../getting-started/configuration.md#test-mode-alembic-pytest).

## Secrets en producción

NUNCA pongas secrets en `.env` commiteado. Opciones:

- AWS Secrets Manager + boto3 startup hook
- Doppler / Infisical
- Kubernetes Secrets vía env

```python
import boto3
import json

def load_secrets() -> dict:
    client = boto3.client("secretsmanager", region_name="us-east-1")
    secret = client.get_secret_value(SecretId="prod/myservice")
    return json.loads(secret["SecretString"])
```

## Feature flags

```python
class Settings(BaseSettings):
    FEATURE_X_ENABLED: bool = False
    FEATURE_Y_ROLLOUT: float = 0.0   # 0.0 - 1.0
```

```python
if settings.FEATURE_X_ENABLED:
    # nueva implementación
    ...
```

Para feature flags dinámicos (DB-driven), considera LaunchDarkly / Unleash.
