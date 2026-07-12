"""Matriz HTTP end-to-end (Beanie, patrón cbv de pulbot) sobre filtros +
paginación. Expected computado desde el seed. Este es el stack que corre
pulbot en producción; el refactor de `_params` debe soportarlo entero.
"""

import mongomock_motor
import pytest
from beanie import init_beanie
from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi_restful.cbv import cbv
from httpx import ASGITransport
from httpx import AsyncClient as HTTPXAsyncClient

from fastapi_basekit.aio.beanie.controller.base import BeanieBaseController
from fastapi_basekit.schema.base import BasePaginationResponse

from example_crud_beanie.models import UserDocument
from example_crud_beanie.repository import UserBeanieRepository
from example_crud_beanie.service import UserBeanieService
from example_crud_beanie.schemas import UserBeanieSchema


SEED = [
    {"name": f"U{i:02d}", "email": f"u{i:02d}@x.com", "age": 20 + i,
     "is_active": (i % 3 != 0)}
    for i in range(12)
]


@pytest.fixture
async def init_db():
    client = mongomock_motor.AsyncMongoMockClient()
    await init_beanie(database=client.test_db, document_models=[UserDocument])
    yield
    client.close()


@pytest.fixture
async def client(init_db):
    repo = UserBeanieRepository()
    for u in SEED:
        await repo.create(u)

    router = APIRouter(prefix="/u")

    def get_service(request: Request):
        return UserBeanieService(repository=UserBeanieRepository(), request=request)

    @cbv(router)
    class Ctrl(BeanieBaseController):
        schema_class = UserBeanieSchema
        service: UserBeanieService = Depends(get_service)

        @router.get("/", response_model=BasePaginationResponse[UserBeanieSchema])
        async def list_users(
            self,
            page: int = Query(1, ge=1),
            count: int = Query(20, ge=1, le=100),
            is_active: bool | None = Query(None),
            search: str | None = Query(None),
        ):
            return await super().list()

    app = FastAPI()
    app.include_router(router)
    async with HTTPXAsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


def _expected(is_active, page, count):
    rows = [u for u in SEED if is_active is None or u["is_active"] is is_active]
    rows = sorted(rows, key=lambda u: u["name"])
    start = (page - 1) * count
    return [u["name"] for u in rows[start:start + count]], len(rows)


@pytest.mark.parametrize("is_active", [None, True, False])
@pytest.mark.parametrize("page", [1, 2, 3])
@pytest.mark.parametrize("count", [1, 3, 5, 10, 50])
@pytest.mark.asyncio
async def test_filter_pagination_matrix_beanie(client, is_active, page, count):
    q = f"?page={page}&count={count}"
    if is_active is not None:
        q += f"&is_active={'true' if is_active else 'false'}"

    resp = await client.get(f"/u/{q}")
    assert resp.status_code == 200
    body = resp.json()

    exp_names, exp_total = _expected(is_active, page, count)
    got = sorted(u["name"] for u in body["data"])
    assert got == sorted(exp_names)
    assert body["pagination"]["total"] == exp_total
    if is_active is not None:
        assert all(u["is_active"] is is_active for u in body["data"])


@pytest.mark.parametrize("term,expected", [
    ("U00", {"U00"}),
    ("U1", {"U10", "U11"}),
    ("zzz", set()),
])
@pytest.mark.asyncio
async def test_search_beanie(client, term, expected):
    resp = await client.get(f"/u/?search={term}&count=50")
    assert resp.status_code == 200
    assert {u["name"] for u in resp.json()["data"]} == expected
