"""Generic domain-error base class with declarative HTTP mapping.

Services raise `DomainError` (or a subclass) with a stable string `code` and
a human `message`. Endpoints catch and re-raise as HTTPException via
`exc.to_http()`. The status code per `code` is declared on the subclass via
`STATUS_CODE_MAP`, so each domain owns its mapping in one place — no inline
`if/elif` translator helpers in endpoint files.

Pattern:

    class MyDomainError(DomainError):
        STATUS_CODE_MAP = {
            "unauthorized": status.HTTP_401_UNAUTHORIZED,
            "not_found": status.HTTP_404_NOT_FOUND,
            "conflict": status.HTTP_409_CONFLICT,
        }

    # Service:
    raise MyDomainError("not_found", "Recurso no encontrado")

    # Endpoint:
    try:
        await service.do_thing()
    except MyDomainError as exc:
        raise exc.to_http()
"""

from typing import ClassVar

from fastapi import HTTPException, status


class DomainError(Exception):
    """Base for service-layer domain errors with HTTP mapping baked in.

    Subclasses override `STATUS_CODE_MAP` to map their codes to HTTP
    statuses. Codes not present fall back to `DEFAULT_STATUS`.
    """

    DEFAULT_STATUS: ClassVar[int] = status.HTTP_400_BAD_REQUEST
    STATUS_CODE_MAP: ClassVar[dict[str, int]] = {}

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def http_status(self) -> int:
        return self.STATUS_CODE_MAP.get(self.code, self.DEFAULT_STATUS)

    def to_http(self) -> HTTPException:
        return HTTPException(
            status_code=self.http_status(), detail=self.message
        )

    def __str__(self) -> str:
        return f"{type(self).__name__}[{self.code}]: {self.message}"
