import os
import time
from uuid import UUID

import jwt
from jwt.exceptions import ExpiredSignatureError, PyJWTError

try:
    from bson import ObjectId  # type: ignore
except ImportError:  # pragma: no cover - bson is opcional
    ObjectId = None  # type: ignore

from ...exceptions.api_exceptions import JWTAuthenticationException
from ...schema.jwt import TokenSchema

_INSECURE_DEV_SECRET = "secret_dev_key"
_TRUTHY = {"1", "true", "t", "yes", "on"}


class JWTService:
    """Servicio JWT (HS256 por defecto).

    Config por env: ``JWT_SECRET`` (OBLIGATORIO), ``JWT_ALGORITHM`` (def HS256),
    ``JWT_EXPIRE_SECONDS`` (def 3600).

    FALLA FUERTE si falta ``JWT_SECRET`` — antes caía a una clave pública
    (`secret_dev_key`) y firmaba tokens de producción con un secreto conocido
    por todo el mundo (cualquiera podía forjar tokens). Para desarrollo local
    podés setear ``JWT_ALLOW_INSECURE_DEV_SECRET=1`` y usar el secreto de dev.
    """

    def __init__(self):
        secret = os.getenv("JWT_SECRET")
        if not secret:
            allow_dev = (
                os.getenv("JWT_ALLOW_INSECURE_DEV_SECRET", "").strip().lower()
                in _TRUTHY
            )
            if not allow_dev:
                raise RuntimeError(
                    "JWT_SECRET no está seteado. fastapi-basekit se niega a "
                    "firmar tokens con una clave por defecto pública (riesgo: "
                    "cualquiera forja tokens de cualquier usuario). Setea "
                    "JWT_SECRET a un valor aleatorio de >=32 bytes. Solo para "
                    "desarrollo local podés setear "
                    "JWT_ALLOW_INSECURE_DEV_SECRET=1."
                )
            secret = _INSECURE_DEV_SECRET
        self.JWT_SECRET = secret
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        raw_expire = os.getenv("JWT_EXPIRE_SECONDS", "3600")
        try:
            self.JWT_EXPIRE_SECONDS = int(raw_expire)
        except (TypeError, ValueError):
            raise RuntimeError(
                f"JWT_EXPIRE_SECONDS debe ser un entero de segundos, "
                f"recibí {raw_expire!r}."
            )

    def create_token(self, subject: str, extra_data: dict = None) -> str:
        now = int(time.time())
        expiration = now + self.JWT_EXPIRE_SECONDS
        payload = {"sub": str(subject), "exp": expiration, "iat": now}

        if extra_data is not None:

            def convert_to_serializable(obj):
                if ObjectId is not None and isinstance(obj, ObjectId):
                    return str(obj)
                if isinstance(obj, UUID):
                    return str(obj)
                return obj

            payload.update(
                {k: convert_to_serializable(v) for k, v in extra_data.items()}
            )

        return jwt.encode(
            payload,
            self.JWT_SECRET,
            algorithm=self.JWT_ALGORITHM,
        )

    def decode_token(self, token: str) -> TokenSchema:
        try:
            payload = jwt.decode(
                token,
                self.JWT_SECRET,
                algorithms=[self.JWT_ALGORITHM],
            )
            return TokenSchema(**payload)
        except ExpiredSignatureError:
            raise JWTAuthenticationException(
                message="El token ha expirado", data={"token": token}
            )
        except PyJWTError:
            raise JWTAuthenticationException(
                message="Token inválido", data={"token": token}
            )

    def refresh_token(self, token: str) -> str:
        try:
            payload = jwt.decode(
                token,
                self.JWT_SECRET,
                algorithms=[self.JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            payload["exp"] = int(time.time()) + self.JWT_EXPIRE_SECONDS
            return jwt.encode(
                payload,
                self.JWT_SECRET,
                algorithm=self.JWT_ALGORITHM,
            )
        except PyJWTError:
            raise JWTAuthenticationException(
                message="Token inválido, no se puede refrescar",
                data={"token": token},
            )
