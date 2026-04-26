{% if cookiecutter.orm == "sqlalchemy" -%}
"""SQLAlchemy declarative base — UUID PK + timestamps + soft delete."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.sql import func

from app.models.types import GUID


class BaseModel(DeclarativeBase):
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(tz=timezone.utc)

    def restore(self) -> None:
        self.deleted_at = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
{%- elif cookiecutter.orm == "beanie" -%}
"""Beanie base — timestamps + soft delete."""

from datetime import datetime

from beanie import Document, before_event, Insert, Replace
from pydantic import Field


class CustomBaseModel(Document):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None

    class Settings:
        abstract = True

    @before_event(Replace, Insert)
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    def soft_delete(self) -> None:
        self.deleted_at = datetime.utcnow()

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    async def delete_relations(self):
        return None

    async def delete(self, *args, **kwargs):
        await self.delete_relations()
        return await super().delete(*args, **kwargs)
{%- endif %}
