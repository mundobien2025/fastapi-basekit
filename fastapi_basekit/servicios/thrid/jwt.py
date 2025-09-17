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


class JWTService:
    def __init__(self):
        # Leer variables de entorno con valores por defecto
        self.JWT_SECRET = os.getenv("JWT_SECRET", "secret_dev_key")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_EXPIRE_SECONDS = int(
            os.getenv("JWT_EXPIRE_SECONDS", "3600")
        )  # 1 hora por defecto

    def create_token(self, subject: str, extra_data: dict = None) -> str:
        expiration = int(time.time()) + self.JWT_EXPIRE_SECONDS
        payload = {"sub": str(subject), "exp": expiration}

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
