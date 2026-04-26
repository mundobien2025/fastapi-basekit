"""Alembic env — async + autodiscover all app.models submodules."""

import asyncio
from importlib import import_module
from logging.config import fileConfig
from pkgutil import walk_packages

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401
from app.models.base import BaseModel
from app.models.types import GUID, LowercaseEnum

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

models_prefix = f"{app.models.__name__}."
for module_info in walk_packages(app.models.__path__, models_prefix):
    import_module(module_info.name)

target_metadata = BaseModel.metadata


def render_item(type_, obj, autogen_context):
    if type_ == "type" and isinstance(obj, GUID):
        return "sa.String(length=36)"
    if type_ == "type" and isinstance(obj, LowercaseEnum):
        length = obj.impl.length or 50
        return f"sa.String(length={length})"
    return False


def run_migrations_offline() -> None:
    from app.config.database import get_database_url

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    from app.config.database import get_database_url

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
