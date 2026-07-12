"""Back-compat: consumidores que overridean `_params` y llaman
`super()._params(skip_frames + 1)` NO deben romperse tras el refactor.

pulbot tiene `app/mixins/path_filter_mixin.py::PathFilterMixin` que hace
exactamente eso para inyectar path params como filtros. El refactor quitó la
lógica de `skip_frames` pero conserva el parámetro (ignorado) para no romper
este patrón. Aquí lo replicamos idéntico y verificamos:

1. No hay TypeError al llamar `super()._params(skip_frames + 1)`.
2. El path param se agrega como filtro y llega hasta la query (end-to-end cbv).
"""

from typing import Any, ClassVar, Dict, Optional

import mongomock_motor
import pytest
from beanie import Document, init_beanie
from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi_restful.cbv import cbv
from httpx import ASGITransport
from httpx import AsyncClient as HTTPXAsyncClient

from fastapi_basekit.aio.beanie.controller.base import BeanieBaseController
from fastapi_basekit.aio.beanie.repository.base import BaseRepository
from fastapi_basekit.aio.beanie.service.base import BaseService
from fastapi_basekit.aio.controller.base import BaseController
from fastapi_basekit.schema.base import BasePaginationResponse
from pydantic import BaseModel as PydModel


# --- Réplica EXACTA del mixin de pulbot ------------------------------------
class PathFilterMixin:
    path_params_config: ClassVar[Optional[Dict[str, Any]]] = None

    def _params(self, skip_frames: int = 1) -> Dict[str, Any]:
        params = super()._params(skip_frames + 1)
        config = self.path_params_config or {}
        enabled = config.get("enabled", True)
        mapping = config.get("mapping", {})
        exclude = config.get("exclude", {"id"})
        if not enabled:
            return params
        if hasattr(self, "request") and self.request:
            path_params = self.request.path_params or {}
            for param_name, param_value in path_params.items():
                if param_name in exclude:
                    continue
                if mapping and param_name in mapping:
                    filter_name = mapping[param_name]
                else:
                    filter_name = (
                        param_name[:-3]
                        if param_name.endswith("_id")
                        else param_name
                    )
                params["filters"][filter_name] = str(param_value)
        return params


# ---------------------------------------------------------------------------
# 1) Unit: llamar super()._params(skip_frames+1) no revienta
# ---------------------------------------------------------------------------

class _FakeReq:
    def __init__(self, qp, path_params):
        self.query_params = qp
        self.path_params = path_params
        self.scope = {}


def test_super_params_accepts_skip_frames_no_typeerror():
    class Ctrl(PathFilterMixin, BaseController):
        pass

    ctrl = Ctrl.__new__(Ctrl)
    ctrl.request = _FakeReq({"page": "2"}, {"flow_id": "F1", "id": "X"})
    params = ctrl._params()  # entra al mixin → super()._params(2)
    assert params["page"] == 2
    assert params["filters"]["flow"] == "F1"   # flow_id → flow
    assert "id" not in params["filters"]        # excluido por default


@pytest.mark.parametrize("skip", [1, 2, 3, 5, 10])
def test_base_params_ignores_any_skip_frames(skip):
    ctrl = BaseController.__new__(BaseController)
    ctrl.request = _FakeReq({"count": "7"}, {})
    # Llamada directa con skip_frames arbitrario: ignorado, no revienta.
    assert ctrl._params(skip)["count"] == 7


# ---------------------------------------------------------------------------
# 2) End-to-end: path param como filtro por el patrón cbv de pulbot
# ---------------------------------------------------------------------------

class Node(Document):
    name: str
    flow: str

    class Settings:
        name = "nodes"


class NodeRepo(BaseRepository):
    model = Node


class NodeService(BaseService):
    search_fields = ["name"]


class NodeSchema(PydModel):
    id: str
    name: str
    flow: str

    @classmethod
    def model_validate(cls, obj, *a, **k):  # tolera ObjectId→str
        if hasattr(obj, "model_dump"):
            d = obj.model_dump()
            d["id"] = str(d.get("id") or getattr(obj, "id", ""))
            d["flow"] = str(d.get("flow"))
            return super().model_validate(d, *a, **k)
        return super().model_validate(obj, *a, **k)


@pytest.fixture
async def client():
    mongo = mongomock_motor.AsyncMongoMockClient()
    await init_beanie(database=mongo.test_db, document_models=[Node])
    repo = NodeRepo()
    await repo.create({"name": "n1", "flow": "A"})
    await repo.create({"name": "n2", "flow": "A"})
    await repo.create({"name": "n3", "flow": "B"})

    router = APIRouter()

    def get_service(request: Request):
        return NodeService(repository=NodeRepo(), request=request)

    @cbv(router)
    class NodeController(PathFilterMixin, BeanieBaseController):
        schema_class = NodeSchema
        service: NodeService = Depends(get_service)

        @router.get(
            "/flows/{flow_id}/nodes/",
            response_model=BasePaginationResponse[NodeSchema],
        )
        async def list_nodes(
            self,
            flow_id: str,
            page: int = Query(1, ge=1),
            count: int = Query(20, ge=1, le=100),
        ):
            return await super().list()

    app = FastAPI()
    app.include_router(router)
    async with HTTPXAsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    mongo.close()


@pytest.mark.asyncio
async def test_path_param_becomes_filter_flow_a(client):
    r = await client.get("/flows/A/nodes/?count=50")
    assert r.status_code == 200
    names = {n["name"] for n in r.json()["data"]}
    assert names == {"n1", "n2"}


@pytest.mark.asyncio
async def test_path_param_becomes_filter_flow_b(client):
    r = await client.get("/flows/B/nodes/?count=50")
    assert r.status_code == 200
    names = {n["name"] for n in r.json()["data"]}
    assert names == {"n3"}
