"""Database configuration."""
{% if cookiecutter.orm == "sqlalchemy" %}
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_basekit.aio.sqlalchemy import make_session_lifecycle
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import get_settings
from app.models.base import BaseModel

settings = get_settings()


def _is_test_mode() -> bool:
    return (
        os.getenv("RUNNING_TESTS") == "true"
        or os.getenv("PYTEST_CURRENT_TEST") is not None
        or (len(sys.argv) > 0 and "pytest" in sys.argv[0])
    )


def get_database_url() -> str:
    return settings.DATABASE_URL


engine_kwargs: dict = {"future": True}
if _is_test_mode():
    engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(get_database_url(), **engine_kwargs)

AsyncSessionFactory = async_sessionmaker(
    engine,
    autoflush=False,
    expire_on_commit=False,
)

# Single commit/rollback per request. Wire on_error / on_success hooks
# here for logging, sentry, metrics, etc. — services must NOT call
# session.flush / session.commit / session.refresh; repos own flush
# via BaseRepository.create / update.
get_db = make_session_lifecycle(AsyncSessionFactory)


async def init_db():
    async with engine.begin() as conn:
        import app.models  # noqa: F401
        await conn.run_sync(BaseModel.metadata.create_all)


async def close_db():
    await engine.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        await close_db()
{% elif cookiecutter.orm == "beanie" %}
from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from app.config.settings import get_settings
from app.models.auth import Users

settings = get_settings()

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.DATABASE_URL)
    return _client


async def init_db() -> None:
    client = get_client()
    db = client[settings.DATABASE_NAME]
    await init_beanie(database=db, document_models=[Users])


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        yield
    finally:
        await close_db()
{% endif %}
