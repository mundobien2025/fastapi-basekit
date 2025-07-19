import pytest

fastapi = pytest.importorskip('fastapi')

from fastapi_toolkit.exceptions.api_exceptions import APIException


def test_api_exception_attributes():
    exc = APIException(message='msg', status_code='CODE', status=500, data={'k':'v'})
    assert exc.message == 'msg'
    assert exc.status_code == 'CODE'
    assert exc.status == 500
    assert exc.data == {'k':'v'}
