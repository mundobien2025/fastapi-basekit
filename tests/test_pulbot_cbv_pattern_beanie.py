"""Verificación del patrón REAL de pulbot: `@cbv(router)` + método
`list_x(self, ...Query...)` que hace `return await super().list()`, sobre
Beanie, end-to-end por HTTP.

El viejo `_params` dependía de `inspect.currentframe()` + `skip_frames`, un
número mágico calibrado para el patrón `__call__` (clase-por-endpoint). El
patrón cbv de pulbot tiene otra profundidad de frames, y por eso a Jerson le
tiraba error / listados vacíos. El refactor lee la firma del endpoint
(`request.scope["endpoint"]`), independiente de la profundidad de frames.

Estos tests fallarían con el viejo mecanismo y pasan con el nuevo.
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


@pytest.fixture
async def init_db():
    client = mongomock_motor.AsyncMongoMockClient()
    await init_beanie(database=client.test_db, document_models=[UserDocument])
    yield
    client.close()


@pytest.fixture
async def seed(init_db):
    repo = UserBeanieRepository()
    users = [
        {"name": "Ana", "email": "ana@x.com", "age": 30, "is_active": True},
        {"name": "Beto", "email": "beto@x.com", "age": 40, "is_active": True},
        {"name": "Ciro", "email": "ciro@x.com", "age": 50, "is_active": False},
        {"name": "Dina", "email": "dina@x.com", "age": 22, "is_active": False},
    ]
    for u in users:
        await repo.create(u)
    yield users


@pytest.fixture
async def client(seed):
    """App con un controller cbv IDÉNTICO al patrón de pulbot."""
    router = APIRouter(prefix="/conv", tags=["conv"])

    def get_service(request: Request) -> UserBeanieService:
        return UserBeanieService(repository=UserBeanieRepository(), request=request)

    @cbv(router)
    class ConvController(BeanieBaseController):
        schema_class = UserBeanieSchema
        service: UserBeanieService = Depends(get_service)

        # Firma calcada del patrón pulbot: PEP-604 `bool | None`, `str | None`.
        @router.get("/", response_model=BasePaginationResponse[UserBeanieSchema])
        async def list_conversations(
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


@pytest.mark.asyncio
async def test_list_all_no_filter(client):
    r = await client.get("/conv/?count=50")
    assert r.status_code == 200
    body = r.json()
    assert body["pagination"]["total"] == 4
    assert len(body["data"]) == 4


@pytest.mark.asyncio
async def test_bool_filter_true(client):
    """El caso que fallaba: `?is_active=true` por el patrón cbv+super().list()."""
    r = await client.get("/conv/?is_active=true&count=50")
    assert r.status_code == 200
    names = {u["name"] for u in r.json()["data"]}
    assert names == {"Ana", "Beto"}


@pytest.mark.asyncio
async def test_bool_filter_false(client):
    r = await client.get("/conv/?is_active=false&count=50")
    assert r.status_code == 200
    names = {u["name"] for u in r.json()["data"]}
    assert names == {"Ciro", "Dina"}


@pytest.mark.asyncio
async def test_search(client):
    r = await client.get("/conv/?search=Ana&count=50")
    assert r.status_code == 200
    names = {u["name"] for u in r.json()["data"]}
    assert names == {"Ana"}


@pytest.mark.parametrize(
    "page,count,expected_len,expected_total",
    [
        (1, 2, 2, 4),
        (2, 2, 2, 4),
        (3, 2, 0, 4),
        (1, 3, 3, 4),
        (1, 50, 4, 4),
    ],
)
@pytest.mark.asyncio
async def test_pagination(client, page, count, expected_len, expected_total):
    r = await client.get(f"/conv/?page={page}&count={count}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["data"]) == expected_len
    assert body["pagination"]["total"] == expected_total
    assert body["pagination"]["page"] == page
    assert body["pagination"]["count"] == count


@pytest.mark.asyncio
async def test_bool_filter_combined_with_pagination(client):
    r = await client.get("/conv/?is_active=false&page=1&count=1")
    assert r.status_code == 200
    body = r.json()
    assert body["pagination"]["total"] == 2   # 2 inactivos
    assert len(body["data"]) == 1             # pero 1 por página
