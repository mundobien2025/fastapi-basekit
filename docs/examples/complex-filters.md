# Filtros complejos

## Multi-tenant + status + búsqueda combinados

```python
class OrderService(BaseService):
    repository: OrderRepository
    search_fields = ["reference", "customer__email"]

    def get_filters(self, filters: Optional[dict] = None) -> dict:
        filters = filters or {}
        # Multi-tenant forzado
        user = getattr(self.request.state, "user", None)
        if user and user.company_id:
            filters["company_id"] = user.company_id
        return filters
```

```http
GET /api/v1/orders/?status=pending&customer__country=US&search=ORD-2024
```

→ `WHERE company_id='...' AND status='pending' AND customer.country='US' AND (reference ILIKE '%ORD-2024%' OR customer.email ILIKE '%ORD-2024%')`

## Filtros temporales (date range)

```python
@router.get("/", response_model=BasePaginationResponse[OrderResponseSchema])
async def list_orders(
    self,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    count: int = Query(20, ge=1, le=100),
):
    return await self.list()
```

```python
class OrderRepository(BaseRepository):
    model = Order

    def build_list_queryset(self, **kwargs):
        qs = select(self.model).where(self.model.deleted_at.is_(None))
        # Filtros desde request
        request = self.service.request if self.service else None
        if request:
            date_from = request.query_params.get("date_from")
            date_to = request.query_params.get("date_to")
            if date_from:
                qs = qs.where(Order.created_at >= date_from)
            if date_to:
                qs = qs.where(Order.created_at <= date_to)
        return qs
```

## Multi-relation deep filter

```http
GET /api/v1/things/?category__parent__slug=electronics
```

`BaseRepository._resolve_attribute()` parsea cadena de relaciones, agrega JOINs anidados:

```sql
SELECT things.*
FROM things
JOIN categories ON things.category_id = categories.id
JOIN categories AS parent ON categories.parent_id = parent.id
WHERE parent.slug = 'electronics'
```

## OR entre filtros

```python
@router.get("/")
async def list_things(self):
    return await self.list(use_or=True)
```

→ `WHERE status='active' OR category_id='...'`

## Filtros con Enum

Pydantic `Enum` se serializa a `.value`:

```python
items = await repo.get_by_filters({"status": OrderStatus.pending})
# WHERE status = 'pending'

items = await repo.get_by_filters({"status": [OrderStatus.pending, OrderStatus.processing]})
# WHERE status IN ('pending', 'processing')
```

## Subqueries

```python
class OrderRepository(BaseRepository):
    def build_list_queryset(self, **kwargs):
        # Solo orders con items > $100 total
        big_items_subq = (
            select(OrderItem.order_id)
            .group_by(OrderItem.order_id)
            .having(func.sum(OrderItem.amount) > 100)
            .scalar_subquery()
        )
        return select(Order).where(
            Order.id.in_(big_items_subq),
            Order.deleted_at.is_(None),
        )
```

## Filtros condicionales por rol

```python
def get_filters(self, filters):
    filters = filters or {}
    user = self.request.state.user
    if user.role == UserRoleEnum.admin:
        pass  # admin ve todo (modulo company)
    elif user.role == UserRoleEnum.manager:
        filters["branch_id"] = user.branch_id
    else:
        filters["created_by"] = user.id   # ven solo lo suyo
    return filters
```
