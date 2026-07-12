"""Dos garantías que Jerson exigió:

1. Los generics son OPCIONALES — subclasear SIN parametrizar
   (`class UserRepository(BaseRepository)`, como en TODOS los proyectos) funciona
   igual, cero cambio en runtime. Los generics solo agregan tipos SI parametrizas.
2. `_params` NO recomputa la firma del endpoint en cada request — la cachea por
   endpoint (menor cómputo en el hot path de listados).
"""

import mongomock_motor
import pytest
from beanie import Document, init_beanie

from fastapi_basekit.aio.beanie.repository.base import BaseRepository as BeanieRepo
from fastapi_basekit.aio.beanie.service.base import BaseService as BeanieService
from fastapi_basekit.aio.controller.base import _endpoint_param_types_cached


# ===========================================================================
# 1) Generics OPCIONALES — subclase sin parametrizar (el patrón de los proyectos)
# ===========================================================================

class _Thing(Document):
    name: str
    active: bool = True

    class Settings:
        name = "opt_things"


# EXACTAMENTE como escriben todos los proyectos: SIN `[_Thing]`.
class ThingRepo(BeanieRepo):
    model = _Thing


class ThingService(BeanieService):
    search_fields = ["name"]


@pytest.fixture
async def db():
    client = mongomock_motor.AsyncMongoMockClient()
    await init_beanie(database=client.test_db, document_models=[_Thing])
    yield
    client.close()


def test_non_parametrized_subclass_is_valid():
    # No revienta al definir/instanciar sin parámetro genérico.
    repo = ThingRepo()
    assert repo.model is _Thing


@pytest.mark.asyncio
async def test_non_parametrized_crud_works(db):
    repo = ThingRepo()
    created = await repo.create({"name": "x"})
    assert created.id is not None
    got = await repo.get_by_id(created.id)
    assert got.name == "x"

    svc = ThingService(repository=ThingRepo(), request=None)
    for i in range(3):
        await repo.create({"name": f"n{i}", "active": i % 2 == 0})
    items, total = await svc.list(count=50)
    assert total == 4  # x + n0,n1,n2


def test_base_still_generic_even_if_unused():
    # La base sigue siendo Generic (para quien SÍ quiera tipos), pero no obliga.
    assert getattr(BeanieRepo, "__parameters__", ()) != ()


# ===========================================================================
# 2) Caché de firma del endpoint (menor cómputo por request)
# ===========================================================================

def _endpoint_sample(self, page: int = 1, is_active: bool = False, name: str = ""):
    ...


def test_signature_cache_hits():
    _endpoint_param_types_cached.cache_clear()
    first = _endpoint_param_types_cached(_endpoint_sample)
    second = _endpoint_param_types_cached(_endpoint_sample)
    # Mismo objeto dict devuelto → vino de la caché, no se recomputó.
    assert first is second
    info = _endpoint_param_types_cached.cache_info()
    assert info.hits >= 1
    assert info.misses == 1  # un solo cómputo real


def test_signature_cache_extracts_annotations():
    _endpoint_param_types_cached.cache_clear()
    types_map = _endpoint_param_types_cached(_endpoint_sample)
    assert types_map["page"] is int
    assert types_map["is_active"] is bool
    assert types_map["name"] is str
    assert "self" not in types_map  # sin anotación → excluido
