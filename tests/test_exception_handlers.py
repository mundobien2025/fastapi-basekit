"""register_exception_handlers: envelope unificado para toda la app."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from fastapi_basekit.exceptions import register_exception_handlers
from fastapi_basekit.exceptions.api_exceptions import NotFoundException


@pytest.fixture
def client():
    app = FastAPI()
    register_exception_handlers(app)

    class Body(BaseModel):
        n: int

    @app.get("/boom-api")
    async def boom_api():
        raise NotFoundException(message="no existe")

    @app.get("/boom-value")
    async def boom_value():
        raise ValueError("campo malo")

    @app.post("/echo")
    async def echo(body: Body):
        return {"n": body.n}

    return TestClient(app, raise_server_exceptions=False)


def test_api_exception_maps_to_envelope(client):
    r = client.get("/boom-api")
    assert r.status_code == 404
    body = r.json()
    assert body["status"] == "NOT_FOUND"
    assert body["message"] == "no existe"
    assert set(body) == {"data", "message", "status"}


def test_request_validation_maps_to_envelope(client):
    r = client.post("/echo", json={"n": "not-an-int"})
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == "VALIDATION_ERROR"
    assert isinstance(body["data"], list)


def test_value_error_maps_to_envelope(client):
    r = client.get("/boom-value")
    assert r.status_code == 400
    assert r.json()["status"] == "VALUE_ERROR"
