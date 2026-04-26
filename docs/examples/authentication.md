# Autenticación

## Stack

- `JWTService` (de la lib) — encode/decode tokens
- `AuthenticationMiddleware` — extrae token del header, puebla `request.state.user`
- `get_dependency_service` — dependency que valida `request.state.user` está set
- `BasePermission` subclasses — checks por endpoint

## Login service

```python
# app/services/auth_service.py
import os, time
import jwt as pyjwt
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
from fastapi_basekit.exceptions.api_exceptions import JWTAuthenticationException
from fastapi_basekit.servicios import JWTService

from app.utils.security import verify_password


class AuthService(BaseService):
    def __init__(self, user_repository, request=None, session=None):
        super().__init__(user_repository, request=request)
        self.user_repository = user_repository
        self.session = session
        self.jwt_service = JWTService()

    async def login(self, email: str, password: str) -> dict:
        user = await self.user_repository.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise JWTAuthenticationException(message="Credenciales inválidas")
        if not user.is_active:
            raise JWTAuthenticationException(message="Usuario inactivo")
        return self._build_token_pair(user)

    async def refresh(self, refresh_token: str) -> dict:
        payload = self.jwt_service.decode_token(refresh_token)
        user = await self.user_repository.get(payload.sub)
        if not user or not user.is_active:
            raise JWTAuthenticationException(message="Usuario no encontrado")
        return self._build_token_pair(user)

    def _build_token_pair(self, user) -> dict:
        secret = os.getenv("JWT_SECRET", "dev")
        algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        now = int(time.time())
        return {
            "access_token": pyjwt.encode(
                {"sub": str(user.id), "exp": now + 3600},
                secret, algorithm=algorithm,
            ),
            "refresh_token": pyjwt.encode(
                {"sub": str(user.id), "exp": now + 7 * 86400, "type": "refresh"},
                secret, algorithm=algorithm,
            ),
            "token_type": "bearer",
        }
```

## Auth controller

```python
# app/api/v1/endpoints/auth/auth.py
from fastapi import APIRouter, Depends, status
from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from fastapi_basekit.schema.base import BaseResponse
from fastapi_restful.cbv import cbv

from app.models.auth import Users
from app.schemas.auth import LoginSchema, RefreshSchema, TokenResponseSchema
from app.schemas.user import UserResponseSchema
from app.services.auth_service import AuthService
from app.services.dependency import get_auth_service, get_dependency_service

router = APIRouter()


@cbv(router)
class AuthController(SQLAlchemyBaseController):
    service: AuthService = Depends(get_auth_service)
    schema_class = TokenResponseSchema

    @router.post("/login/", response_model=BaseResponse[TokenResponseSchema])
    async def login(self, data: LoginSchema):
        tokens = await self.service.login(data.email, data.password)
        return self.format_response(TokenResponseSchema(**tokens), message="Login OK")

    @router.post("/refresh/", response_model=BaseResponse[TokenResponseSchema])
    async def refresh(self, data: RefreshSchema):
        tokens = await self.service.refresh(data.refresh_token)
        return self.format_response(TokenResponseSchema(**tokens), message="Refreshed")

    @router.get("/me", response_model=BaseResponse[UserResponseSchema])
    async def me(self, user: Users = Depends(get_dependency_service)):
        return self.format_response(UserResponseSchema.model_validate(user), message="OK")
```

## Middleware

```python
# app/middleware/auth.py
from fastapi import Request
from fastapi_basekit.exceptions.api_exceptions import JWTAuthenticationException
from fastapi_basekit.servicios import JWTService
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import database
from app.repositories.user.repository import UserRepository


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, excluded_paths=None, excluded_path_prefixes=None):
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/api/v1/auth/login/",
            "/api/v1/auth/refresh/",
        ]
        self.excluded_path_prefixes = excluded_path_prefixes or [
            "/docs", "/redoc", "/openapi.json", "/health", "/uploads",
        ]

    def _is_excluded(self, path):
        if path in self.excluded_paths:
            return True
        return any(path.startswith(p) for p in self.excluded_path_prefixes)

    def _extract_token(self, request):
        auth = request.headers.get("Authorization", "")
        parts = auth.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        return parts[1]

    async def dispatch(self, request, call_next):
        if self._is_excluded(request.url.path):
            return await call_next(request)

        token = self._extract_token(request)
        if token:
            try:
                user_id = JWTService().decode_token(token).sub
                async with database.AsyncSessionFactory() as session:
                    user = await UserRepository(session).get(user_id)
                    if user and user.is_active:
                        request.state.user = user
            except JWTAuthenticationException:
                pass
        return await call_next(request)
```

## Dependency

```python
# app/services/dependency.py
from typing import Annotated
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi_basekit.exceptions.api_exceptions import JWTAuthenticationException

from app.models.auth import Users

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login/")


async def get_dependency_service(
    request: Request,
    token: str = Depends(oauth2_scheme),
) -> Users:
    user = getattr(request.state, "user", None)
    if not user:
        raise JWTAuthenticationException(message="No autenticado")
    return user


CurrentUser = Annotated[Users, Depends(get_dependency_service)]
```

## Excluded paths convention

Excluye en middleware:
- `/api/v1/auth/login/` (POST credenciales)
- `/api/v1/auth/refresh/` (POST refresh token)
- `/docs`, `/redoc`, `/openapi.json` (Swagger UI)
- `/health` (load balancer)
- `/uploads` (static files)
- POST `/api/v1/dealers/` (registro público)
- GET `/api/v1/public/*` (catálogo público)

## Test flow

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMe2026!"}' \
  | jq -r '.data.access_token')

# Authenticated request
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```
