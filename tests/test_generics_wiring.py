"""Verifica que los generics (`Generic[ModelT]`) están bien cableados en las
bases de los 3 ORMs, y que el paquete expone `py.typed` (PEP 561) para que
mypy/Pylance/IAs consuman los tipos inline.

Los generics se borran en runtime, pero su ESTRUCTURA (parámetros del Generic,
`__orig_bases__` de una subclase parametrizada, anotaciones que referencian el
TypeVar) sí es introspectable — y eso es lo que un type-checker usa.
"""

import inspect
from pathlib import Path
from typing import Optional, get_args

import fastapi_basekit
from fastapi_basekit.aio.sqlalchemy.repository.base import (
    BaseRepository as SQLARepo,
    ModelT as SQLAModelT,
)
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService as SQLASvc
from fastapi_basekit.aio.sqlmodel.repository.base import (
    BaseRepository as SMRepo,
    ModelT as SMModelT,
)
from fastapi_basekit.aio.sqlmodel.service.base import BaseService as SMSvc
from fastapi_basekit.aio.beanie.repository.base import (
    BaseRepository as BeanieRepo,
    ModelT as BeanieModelT,
)
from fastapi_basekit.aio.beanie.service.base import BaseService as BeanieSvc


REPOS = [(SQLARepo, SQLAModelT), (SMRepo, SMModelT), (BeanieRepo, BeanieModelT)]
SERVICES = [SQLASvc, SMSvc, BeanieSvc]


# ---------------------------------------------------------------------------
# py.typed marker (PEP 561) — sin esto los tipos no llegan a los consumidores
# ---------------------------------------------------------------------------

def test_py_typed_marker_shipped():
    pkg_dir = Path(inspect.getfile(fastapi_basekit)).parent
    assert (pkg_dir / "py.typed").exists(), "falta fastapi_basekit/py.typed"


# ---------------------------------------------------------------------------
# Las bases son Generic con un único parámetro (su ModelT)
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.parametrize("repo_cls,model_t", REPOS)
def test_repository_is_generic(repo_cls, model_t):
    assert getattr(repo_cls, "__parameters__", ()) == (model_t,)


@pytest.mark.parametrize("svc_cls", SERVICES)
def test_service_is_generic(svc_cls):
    params = getattr(svc_cls, "__parameters__", ())
    assert len(params) == 1


# ---------------------------------------------------------------------------
# Una subclase parametrizada registra el modelo (lo que lee el type-checker)
# ---------------------------------------------------------------------------

def test_parametrized_subclass_records_model():
    class _Dummy:
        pass

    class _Repo(SQLARepo[_Dummy]):
        model = _Dummy

    orig = _Repo.__orig_bases__[0]
    assert get_args(orig) == (_Dummy,)


# ---------------------------------------------------------------------------
# Las anotaciones de retorno referencian el TypeVar (no `Any`)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("repo_cls,model_t", REPOS)
def test_get_return_annotation_uses_typevar(repo_cls, model_t):
    getter = "get" if hasattr(repo_cls, "get") else "get_by_id"
    ann = inspect.signature(getattr(repo_cls, getter)).return_annotation
    # Optional[ModelT] == Union[ModelT, None]; el TypeVar debe estar en los args.
    assert model_t in get_args(ann), f"{repo_cls.__name__}.{getter} -> {ann}"


@pytest.mark.parametrize("repo_cls,model_t", REPOS)
def test_create_return_annotation_is_typevar(repo_cls, model_t):
    ann = inspect.signature(repo_cls.create).return_annotation
    assert ann is model_t, f"{repo_cls.__name__}.create -> {ann}"


@pytest.mark.parametrize("svc_cls", SERVICES)
def test_service_create_return_uses_typevar(svc_cls):
    ann = inspect.signature(svc_cls.create).return_annotation
    params = getattr(svc_cls, "__parameters__", ())
    assert ann is params[0], f"{svc_cls.__name__}.create -> {ann}"
