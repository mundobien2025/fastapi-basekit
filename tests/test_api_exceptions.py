import pytest
from fastapi_basekit.exceptions.api_exceptions import APIException

fastapi = pytest.importorskip("fastapi")


def test_api_exception_attributes():
    exc = APIException(
        message="msg", status_code="CODE", status=500, data={"k": "v"}
    )
    assert exc.message == "msg"
    assert exc.status_code == "CODE"
    assert exc.status == 500
    assert exc.data == {"k": "v"}
