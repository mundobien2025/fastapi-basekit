# Primer CRUD

Recurso completo en 5 archivos. Ejemplo: `Invoice`.

## 1. Modelo

```python
# app/models/invoice.py
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.types import GUID


class Invoice(BaseModel):
    __tablename__ = "invoices"

    customer_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

Agrega el import a `app/models/__init__.py` para que alembic lo detecte:

```python
from app.models.invoice import Invoice
__all__ += ["Invoice"]
```

## 2. Schemas

```python
# app/schemas/invoice.py
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import BaseSchema


class InvoiceCreateSchema(BaseModel):
    customer_id: uuid.UUID
    amount: float = Field(..., gt=0)
    issued_at: datetime
    note: Optional[str] = None
    model_config = ConfigDict(extra="ignore")


class InvoiceUpdateSchema(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    note: Optional[str] = None
    model_config = ConfigDict(extra="ignore")


class InvoiceResponseSchema(BaseSchema):
    id: uuid.UUID
    customer_id: uuid.UUID
    amount: float
    issued_at: datetime
    note: Optional[str]
    created_at: datetime
    updated_at: datetime
```

!!! warning "id: uuid.UUID"
    Si pones `id: str`, `model_validate` falla silenciosamente sobre rows con UUID PK.

## 3. Repository

```python
# app/repositories/invoice/repository.py
from typing import Any

from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from sqlalchemy import select

from app.models.invoice import Invoice


class InvoiceRepository(BaseRepository):
    model = Invoice

    def build_list_queryset(self, **kwargs: Any):
        return select(self.model).where(self.model.deleted_at.is_(None))
```

## 4. Service

```python
# app/services/invoice_service.py
from typing import Optional

from fastapi import Request
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.invoice.repository import InvoiceRepository


class InvoiceService(BaseService):
    repository: InvoiceRepository
    search_fields = ["note"]

    def __init__(self, repository, request=None, session=None):
        super().__init__(repository, request=request)
        self.repository = repository
        self.session = session

    def get_filters(self, filters: Optional[dict] = None) -> dict:
        filters = filters or {}
        user = getattr(self.request.state, "user", None)
        if user and user.dealer_id:
            filters["customer_id"] = user.dealer_id
        return filters
```

## 5. Factory + controller

```python
# app/services/dependency.py — añadir
def get_invoice_service(request, session=Depends(get_db)):
    from app.repositories.invoice.repository import InvoiceRepository
    from app.services.invoice_service import InvoiceService
    return InvoiceService(InvoiceRepository(session), request=request, session=session)
```

```python
# app/api/v1/endpoints/invoice/invoice.py
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from fastapi_basekit.schema.base import BasePaginationResponse, BaseResponse
from fastapi_restful.cbv import cbv

from app.models.auth import Users
from app.schemas.invoice import (
    InvoiceCreateSchema,
    InvoiceResponseSchema,
    InvoiceUpdateSchema,
)
from app.services.dependency import get_dependency_service, get_invoice_service
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices")


@cbv(router)
class InvoiceController(SQLAlchemyBaseController):
    service: InvoiceService = Depends(get_invoice_service)
    schema_class = InvoiceResponseSchema
    user: Users = Depends(get_dependency_service)

    @router.get("/", response_model=BasePaginationResponse[InvoiceResponseSchema])
    async def list_invoices(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
    ):
        return await self.list()

    @router.post("/", response_model=BaseResponse[InvoiceResponseSchema], status_code=201)
    async def create_invoice(self, data: InvoiceCreateSchema):
        created = await self.service.create(data)
        return self.format_response(InvoiceResponseSchema.model_validate(created))

    @router.get("/{invoice_id}", response_model=BaseResponse[InvoiceResponseSchema])
    async def get_invoice(self, invoice_id: uuid.UUID):
        return await self.retrieve(invoice_id)

    @router.put("/{invoice_id}", response_model=BaseResponse[InvoiceResponseSchema])
    async def update_invoice(self, invoice_id: uuid.UUID, data: InvoiceUpdateSchema):
        updated = await self.service.update(str(invoice_id), data.model_dump(exclude_unset=True))
        return self.format_response(InvoiceResponseSchema.model_validate(updated))

    @router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_invoice(self, invoice_id: uuid.UUID):
        return await self.delete(invoice_id)
```

## 6. Registrar en routers

```python
# app/api/v1/routers.py
from app.api.v1.endpoints.invoice import invoice_router
router.include_router(invoice_router, tags=["Invoices"])
```

## 7. Migrar + correr

```bash
make migrate-create   # mensaje: add_invoices_table
make migrate-up
```

Listo: `GET /api/v1/invoices/?page=1&count=10&search=foo` funciona.

[:octicons-arrow-right-24: Aprende paginación](../user-guide/pagination.md){ .md-button .md-button--primary }
