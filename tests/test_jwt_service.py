import time
from uuid import uuid4

import pytest

try:
    from bson import ObjectId  # type: ignore
except ImportError:  # pragma: no cover - bson es opcional
    ObjectId = None

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


def test_service_serializes_uuid_extra_data():
    service = JWTService()
    identifier = uuid4()
    token = service.create_token("user1", extra_data={"identifier": identifier})
    decoded_payload = jwt.decode(
        token, service.JWT_SECRET, algorithms=[service.JWT_ALGORITHM]
    )
    assert decoded_payload["identifier"] == str(identifier)


@pytest.mark.skipif(ObjectId is None, reason="bson no está instalado")
def test_service_serializes_object_id_extra_data():
    service = JWTService()
    identifier = ObjectId()
    token = service.create_token("user1", extra_data={"identifier": identifier})
    decoded_payload = jwt.decode(
        token, service.JWT_SECRET, algorithms=[service.JWT_ALGORITHM]
    )
    assert decoded_payload["identifier"] == str(identifier)
