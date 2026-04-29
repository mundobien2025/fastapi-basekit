# Filtrado

## Filtros simples (query string)

```http
GET /api/v1/things/?status=active&category_id=abc-123
```

Auto-aplicados por `BaseController._params(skip_frames=2)` — cualquier query param que NO sea `page`/`count`/`search`/`order_by` se vuelve filtro.

## Filtros con relaciones (sintaxis `__`) — SQLAlchemy

```http
GET /api/v1/things/?owner__role__code=admin
GET /api/v1/things/?category__name=Premium
```

`BaseRepository._resolve_attribute()` parsea la ruta y agrega los JOINs necesarios automáticamente.

## Filtros con Beanie `Link[X]` — alias `<field>_id` (0.3.1+)

Para modelos Beanie con `Link[...]`, basekit auto-traduce el filtro a la
sintaxis Mongo nested. El caller no escribe nunca `customer.$id`:

```python
class Conversation(Document):
    customer: Link[Customer]
    user: Link[User]
    channel: Optional[str]
```

```http
# Por el campo Link directamente
GET /api/v1/conversations/?customer=507f1f77bcf86cd799439011

# Por alias `<field>_id` (más amigable para el front)
GET /api/v1/conversations/?customer_id=507f1f77bcf86cd799439011

# Combinable con campos planos
GET /api/v1/conversations/?customer_id=...&channel=whatsapp&active=true
```

Reglas de resolución (`build_filter_query`):

| Key del filter | Resultado |
|----------------|-----------|
| `customer.$id` o cualquier key con `.` o `$` | Passthrough Mongo (raw filter) |
| `customer` (existe en modelo, es Link) | `Conversation.customer.id == ObjectId(v)` |
| `customer` (existe en modelo, NO es Link) | `Conversation.customer == v` |
| `customer_id` (alias, `customer` existe y es Link) | `Conversation.customer.id == ObjectId(v)` |
| `unknown_field` | Ignorado silenciosamente |

Los `str` se castean a `ObjectId` automáticamente — útil cuando el ID viene
crudo del query string.

### Filtros forzados desde el service

Combina con `get_filters()` para auto-scope por usuario sin que el caller
escriba el filtro nested:

```python
class ConversationService(BaseService):
    def get_filters(self, filters=None):
        filters = filters or {}
        user = getattr(self.request.state, "user", None)
        if user:
            filters["user_id"] = user.id  # ← alias resolvuelto por basekit
        return super().get_filters(filters)
```

Resultado: cada `list()` filtra por `user.$id == authenticated_user.id`.

## Filtros IN

Pasa lista al filter dict:

```python
items = await repo.get_by_filters({"status": ["active", "pending"]})
# → WHERE status IN ('active', 'pending')
```

Desde HTTP, repite el param:
```http
?status=active&status=pending
```

## Filtros OR

```python
return await self.list(use_or=True)
# → WHERE status='active' OR category_id='...'
```

## Filtros forzados (del service)

```python
def get_filters(self, filters: dict | None = None) -> dict:
    filters = filters or {}
    user = getattr(self.request.state, "user", None)
    if user and not user.is_platform_admin:
        filters["company_id"] = user.company_id
    return filters
```

Este filtro NO se puede sobreescribir por query string.

## Filtros enum

Pydantic `Enum` se serializa a su `.value` automáticamente:

```python
items = await repo.get_by_filters({"status": ThingStatus.active})
# → WHERE status = 'active'
```

## Soft delete + filtros

Soft-delete NO se aplica automáticamente. Override `build_list_queryset`:

```python
def build_list_queryset(self, **kwargs):
    return select(self.model).where(self.model.deleted_at.is_(None))
```
