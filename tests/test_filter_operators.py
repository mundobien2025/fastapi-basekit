"""Operadores de filtro en BaseRepository (sufijo campo__op)."""

import uuid

from sqlalchemy import String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository


class Base(DeclarativeBase):
    pass


class Widget(Base):
    __tablename__ = "widgets"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String)
    qty: Mapped[int] = mapped_column(default=0)


class WidgetRepository(BaseRepository):
    model = Widget


def _repo() -> WidgetRepository:
    return WidgetRepository.__new__(WidgetRepository)


def test_split_operator_detects_known_suffix():
    repo = _repo()
    assert repo._split_operator("qty__gte") == ("qty", "gte")
    assert repo._split_operator("name__ilike") == ("name", "ilike")
    assert repo._split_operator("id__in") == ("id", "in")


def test_split_operator_keeps_relationship_paths():
    repo = _repo()
    # 'code' no es operador → path se conserva, op por defecto eq.
    assert repo._split_operator("user__role__code") == (
        "user__role__code",
        "eq",
    )
    assert repo._split_operator("status") == ("status", "eq")


def _sql(condition) -> str:
    return str(
        select(Widget).where(condition).compile(
            compile_kwargs={"literal_binds": True}
        )
    )


def test_condition_for_each_operator():
    f = Widget.qty
    assert ">=" in _sql(BaseRepository._condition_for(f, 5, "gte"))
    assert ">" in _sql(BaseRepository._condition_for(f, 5, "gt"))
    assert "<=" in _sql(BaseRepository._condition_for(f, 5, "lte"))
    assert "<" in _sql(BaseRepository._condition_for(f, 5, "lt"))
    assert "!=" in _sql(BaseRepository._condition_for(f, 5, "ne"))
    assert "IN" in _sql(BaseRepository._condition_for(f, [1, 2], "in"))
    assert "LIKE" in _sql(
        BaseRepository._condition_for(Widget.name, "ab", "like")
    )
    assert "lower(" in _sql(
        BaseRepository._condition_for(Widget.name, "ab", "ilike")
    ).lower()


def test_condition_for_eq_keeps_list_in_semantics():
    sql = _sql(BaseRepository._condition_for(Widget.qty, [1, 2], "eq"))
    assert "IN" in sql
    sql_scalar = _sql(BaseRepository._condition_for(Widget.qty, 1, "eq"))
    assert "=" in sql_scalar
