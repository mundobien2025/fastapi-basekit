import time
import pytest

jwt = pytest.importorskip("jwt")
pydantic = pytest.importorskip("pydantic")

from fastapi_basekit.servicios.thrid.jwt import JWTService


def test_create_and_decode_token():
    service = JWTService()
    token = service.create_token("user1")
    data = service.decode_token(token)
    assert data.sub == "user1"


def test_invalid_token_raises_exception():
    service = JWTService()
    with pytest.raises(Exception):
        service.decode_token("invalid")


def test_refresh_token_extends_expiration():
    service = JWTService()
    token = service.create_token("user1")
    original = service.decode_token(token)
    time.sleep(1)
    refreshed = service.refresh_token(token)
    new_data = service.decode_token(refreshed)
    assert new_data.exp > original.exp
