# Configuración

## Variables de entorno

El proyecto generado lee `.env` vía `pydantic-settings`. Variables clave:

```bash
# Aplicación
PROJECT_NAME=My Service
VERSION=0.1.0
DEBUG=true
ENVIRONMENT=local

# Seguridad
SECRET_KEY=change-me-in-production
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_SECONDS=3600
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# Base de datos
DATABASE_URL=postgresql+asyncpg://user:secret@db:5432/mydb

# Admin seed
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeMe2026!
```

!!! warning "JWT_SECRET vs SECRET_KEY"
    `JWTService()` (de la lib) lee `JWT_SECRET` del entorno — NO `SECRET_KEY`. Pon ambos en `.env` o vas a debugear 30 min por qué falla decode_token.

## Ajustes de pydantic Settings

```python
# app/config/settings.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env" if not os.environ.get("RUNNING_IN_DOCKER") else None,
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str
    SECRET_KEY: str
    DATABASE_URL: str
    DEBUG: bool = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

`lru_cache` evita re-leer `.env` en cada request.

## Config por entorno

```bash
# Local
ENVIRONMENT=local
DEBUG=true

# Producción
ENVIRONMENT=production
DEBUG=false
ALLOWED_ORIGINS=https://app.example.com,https://api.example.com
```

En `main.py` el CORS se ajusta automáticamente:

```python
cors_origins = ["*"] if settings.DEBUG else settings.ALLOWED_ORIGINS
allow_creds = not settings.DEBUG
```

## Test mode (alembic + pytest)

`app/config/database.py` detecta automáticamente modo test y usa `NullPool` + cambia DB:

```python
def _is_test_mode() -> bool:
    return (
        os.getenv("RUNNING_TESTS") == "true"
        or os.getenv("PYTEST_CURRENT_TEST") is not None
        or "pytest" in sys.argv[0]
    )
```

Si defines `TEST_DATABASE_NAME=test_mydb` en el contenedor de tests, el engine apunta ahí.
