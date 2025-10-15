import pytest
from fastapi_basekit.aio.beanie.service.base import BaseService
from fastapi_basekit.exceptions.api_exceptions import (
    NotFoundException,
    DatabaseIntegrityException,
)

fastapi = pytest.importorskip("fastapi")


class FakeRepository:
    def __init__(self):
        self.items = {}
        self.counter = 0

    async def get_by_id(self, obj_id, **kwargs):
        return self.items.get(str(obj_id))

    async def get_by_fields(self, filters, **kwargs):
        for obj in self.items.values():
            if all(obj.get(k) == v for k, v in filters.items()):
                return obj
        return None

    async def create(self, obj):
        self.counter += 1
        obj_id = str(self.counter)
        if isinstance(obj, dict):
            obj = obj.copy()
            obj["id"] = obj_id
        self.items[obj_id] = obj
        return obj

    async def update(self, obj, data):
        obj.update(data)
        return obj

    async def delete(self, obj):
        self.items.pop(str(obj["id"]), None)

    async def build_filter_query(
        self, search=None, search_fields=None, filters=None, **kwargs
    ):
        return [
            obj
            for obj in self.items.values()
            if all(obj.get(k) == v for k, v in (filters or {}).items())
        ]

    async def paginate(self, query, page, count):
        # Si query es una coroutine, esperarla primero
        if hasattr(query, "__await__"):
            query = await query
        total = len(query)
        start = count * (page - 1)
        return query[start : start + count], total  # noqa


class ExampleService(BaseService):
    duplicate_check_fields = ["name"]

    def __init__(self, repository):
        super().__init__(repository)


@pytest.mark.anyio
async def test_create_and_duplicate_check():
    service = ExampleService(FakeRepository())
    await service.create({"name": "a"})
    with pytest.raises(DatabaseIntegrityException):
        await service.create({"name": "a"})


@pytest.mark.anyio
async def test_crud_flow():
    repo = FakeRepository()
    service = ExampleService(repo)
    item = await service.create({"name": "a"})
    retrieved = await service.retrieve(item["id"])
    assert retrieved["name"] == "a"

    updated = await service.update(item["id"], {"name": "b"})
    assert updated["name"] == "b"

    result = await service.delete(item["id"])
    assert result == "deleted"
    with pytest.raises(NotFoundException):
        await service.retrieve(item["id"])


@pytest.mark.anyio
async def test_list_pagination():
    repo = FakeRepository()
    service = ExampleService(repo)
    for i in range(5):
        await service.create({"name": f"n{i}"})

    items, total = await service.list(page=2, count=2)
    assert total == 5
    assert len(items) == 2
