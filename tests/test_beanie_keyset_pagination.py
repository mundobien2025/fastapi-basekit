"""Tests de `BaseRepository.paginate_keyset` (paginación por cursor, sin skip/count)."""

import pytest
import mongomock_motor
from beanie import init_beanie

from example_crud_beanie.models import UserDocument
from example_crud_beanie.repository import UserBeanieRepository


@pytest.fixture
async def init_db():
    client = mongomock_motor.AsyncMongoMockClient()
    await init_beanie(database=client.test_db, document_models=[UserDocument])
    yield
    client.close()


async def _seed(n: int):
    for i in range(n):
        await UserDocument(
            name=f"u{i:02d}", email=f"u{i}@x.com", age=i
        ).insert()


class TestKeysetPagination:
    async def test_desc_latest_first_and_cursor_walk(self, init_db):
        repo = UserBeanieRepository()
        await _seed(25)

        # Página 1: los más "nuevos" por age desc.
        items, has_more = await repo.paginate_keyset(
            repo.model.find(), limit=10, cursor_field="age", ascending=False
        )
        assert [d.age for d in items] == list(range(24, 14, -1))
        assert has_more is True

        # Página 2 vía cursor (age del último item).
        items2, has_more2 = await repo.paginate_keyset(
            repo.model.find(),
            limit=10,
            cursor_field="age",
            cursor_value=items[-1].age,
            ascending=False,
        )
        assert [d.age for d in items2] == list(range(14, 4, -1))
        assert has_more2 is True

        # Página 3 (final): quedan 5, sin has_more.
        items3, has_more3 = await repo.paginate_keyset(
            repo.model.find(),
            limit=10,
            cursor_field="age",
            cursor_value=items2[-1].age,
            ascending=False,
        )
        assert [d.age for d in items3] == list(range(4, -1, -1))
        assert has_more3 is False

    async def test_ascending_order(self, init_db):
        repo = UserBeanieRepository()
        await _seed(5)
        items, has_more = await repo.paginate_keyset(
            repo.model.find(), limit=3, cursor_field="age", ascending=True
        )
        assert [d.age for d in items] == [0, 1, 2]
        assert has_more is True

    async def test_no_skip_or_count_on_empty(self, init_db):
        repo = UserBeanieRepository()
        items, has_more = await repo.paginate_keyset(
            repo.model.find(), limit=10, cursor_field="age", ascending=False
        )
        assert items == []
        assert has_more is False
