# CRUD básico

Ejemplo completo: recurso `Product` con CRUD + soft delete + scoping por company.

## Modelo

```python
# app/models/product.py
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.types import GUID


class Product(BaseModel):
    __tablename__ = "products"

    company_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
```

## Schemas

```python
# app/schemas/product.py
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import BaseSchema


class ProductCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sku: str = Field(..., min_length=1, max_length=50)
    price: float = Field(..., gt=0)
    is_active: bool = True
    model_config = ConfigDict(extra="ignore")


class ProductUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    price: Optional[float] = Field(None, gt=0)
    is_active: Optional[bool] = None
    model_config = ConfigDict(extra="ignore")


class ProductResponseSchema(BaseSchema):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    sku: str
    price: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

## Repo + service + factory + controller

```python
# app/repositories/product/repository.py
from typing import Any
from fastapi_basekit.aio.sqlalchemy.repository.base import BaseRepository
from sqlalchemy import select
from app.models.product import Product


class ProductRepository(BaseRepository):
    model = Product

    def build_list_queryset(self, **kwargs: Any):
        return select(self.model).where(self.model.deleted_at.is_(None))
```

```python
# app/services/product_service.py
from typing import Optional
from fastapi import Request
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.product.repository import ProductRepository


class ProductService(BaseService):
    repository: ProductRepository
    search_fields = ["name", "sku"]
    duplicate_check_fields = ["sku"]

    def __init__(self, repository, request=None, session=None):
        super().__init__(repository, request=request)
        self.repository = repository
        self.session = session

    def get_filters(self, filters: Optional[dict] = None) -> dict:
        filters = filters or {}
        user = getattr(self.request.state, "user", None)
        if user and user.company_id and not user.is_platform_admin:
            filters["company_id"] = user.company_id
        return filters

    async def create(self, payload, check_fields=None):
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        user = getattr(self.request.state, "user", None)
        if user and user.company_id:
            data["company_id"] = user.company_id
        return await super().create(data, check_fields)
```

```python
# app/services/dependency.py — añadir
def get_product_service(request, session=Depends(get_db)):
    from app.repositories.product.repository import ProductRepository
    from app.services.product_service import ProductService
    return ProductService(ProductRepository(session), request=request, session=session)
```

```python
# app/api/v1/endpoints/product/product.py
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi_basekit.aio.sqlalchemy.controller.base import SQLAlchemyBaseController
from fastapi_basekit.schema.base import BasePaginationResponse, BaseResponse
from fastapi_restful.cbv import cbv

from app.models.auth import Users
from app.schemas.product import (
    ProductCreateSchema,
    ProductResponseSchema,
    ProductUpdateSchema,
)
from app.services.dependency import get_dependency_service, get_product_service
from app.services.product_service import ProductService

router = APIRouter(prefix="/products")


@cbv(router)
class ProductController(SQLAlchemyBaseController):
    service: ProductService = Depends(get_product_service)
    schema_class = ProductResponseSchema
    user: Users = Depends(get_dependency_service)

    @router.get("/", response_model=BasePaginationResponse[ProductResponseSchema])
    async def list_products(
        self,
        page: int = Query(1, ge=1),
        count: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
    ):
        return await self.list()

    @router.post("/", response_model=BaseResponse[ProductResponseSchema], status_code=201)
    async def create_product(self, data: ProductCreateSchema):
        created = await self.service.create(data)
        return self.format_response(ProductResponseSchema.model_validate(created), message="Created")

    @router.get("/{product_id}", response_model=BaseResponse[ProductResponseSchema])
    async def get_product(self, product_id: uuid.UUID):
        return await self.retrieve(product_id)

    @router.put("/{product_id}", response_model=BaseResponse[ProductResponseSchema])
    async def update_product(self, product_id: uuid.UUID, data: ProductUpdateSchema):
        updated = await self.service.update(str(product_id), data.model_dump(exclude_unset=True))
        return self.format_response(ProductResponseSchema.model_validate(updated), message="Updated")

    @router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_product(self, product_id: uuid.UUID):
        return await self.delete(product_id)
```

## Test

```bash
make migrate-create   # add_products_table
make migrate-up

curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Widget","sku":"WGT-001","price":29.99}'

curl http://localhost:8000/api/v1/products/?page=1&count=20&search=widget \
  -H "Authorization: Bearer $TOKEN"
```
