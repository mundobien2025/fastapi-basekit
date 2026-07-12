"""JWTService: config robusta / fail-loud (fix seguridad H3).

Antes caía a `secret_dev_key` (clave pública) si faltaba JWT_SECRET → cualquiera
forjaba tokens. Ahora falla fuerte, salvo flag explícito de dev.
"""

import jwt as pyjwt
import pytest

from fastapi_basekit.servicios.thrid.jwt import JWTService, _INSECURE_DEV_SECRET


def test_missing_secret_raises(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_ALLOW_INSECURE_DEV_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        JWTService()


def test_missing_secret_dev_flag_allows(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("JWT_ALLOW_INSECURE_DEV_SECRET", "1")
    svc = JWTService()
    assert svc.JWT_SECRET == _INSECURE_DEV_SECRET


@pytest.mark.parametrize("flag", ["1", "true", "TRUE", "yes", "on"])
def test_dev_flag_truthy_variants(monkeypatch, flag):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("JWT_ALLOW_INSECURE_DEV_SECRET", flag)
    assert JWTService().JWT_SECRET == _INSECURE_DEV_SECRET


@pytest.mark.parametrize("flag", ["0", "false", "no", "", "off"])
def test_dev_flag_falsy_still_raises(monkeypatch, flag):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("JWT_ALLOW_INSECURE_DEV_SECRET", flag)
    with pytest.raises(RuntimeError):
        JWTService()


def test_secret_set_works(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "a-real-secret-value")
    svc = JWTService()
    assert svc.JWT_SECRET == "a-real-secret-value"


def test_bad_expire_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("JWT_EXPIRE_SECONDS", "not-a-number")
    with pytest.raises(RuntimeError, match="JWT_EXPIRE_SECONDS"):
        JWTService()


def test_token_has_iat(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x")
    svc = JWTService()
    token = svc.create_token("user-1")
    decoded = pyjwt.decode(token, "x", algorithms=["HS256"])
    assert "iat" in decoded and "exp" in decoded
    assert decoded["sub"] == "user-1"
