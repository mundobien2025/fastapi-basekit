import pytest
from fastapi_basekit.schema.base import BaseResponse, BasePaginationResponse

pydantic = pytest.importorskip("pydantic")


def test_base_response_defaults():
    resp = BaseResponse(data={"id": 1})
    assert resp.message == "Operación exitosa"
    assert resp.status == "success"
    assert resp.data == {"id": 1}


def test_base_pagination_response():
    resp = BasePaginationResponse(
        data=[1, 2], pagination={"page": 1, "count": 2, "total": 2}
    )
    assert resp.pagination["total"] == 2
    assert resp.data == [1, 2]
