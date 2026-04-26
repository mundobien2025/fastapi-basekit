# `BaseService`

::: fastapi_basekit.aio.sqlalchemy.service.base.BaseService
    options:
      show_source: true
      members:
        - list
        - retrieve
        - create
        - update
        - delete
        - get_filters
        - get_kwargs_query

## Atributos de clase

| Atributo | Tipo | Default | Descripción |
|---|---|---|---|
| `repository` | `BaseRepository` | required | Repo principal |
| `search_fields` | `List[str]` | `[]` | Campos para `?search=` (ILIKE) |
| `duplicate_check_fields` | `List[str]` | `[]` | Campos verificados en `create()` |
| `order_by` | `Optional[str]` | None | Default order si client no pasa `?order_by=` |
| `action` | `Optional[str]` | None | Auto-set por `BaseService.__init__` |

## Hooks de override

```python
def get_filters(self, filters: dict | None = None) -> dict:
    """Inyecta filtros forzados (ej. company_id del usuario)."""
    return filters or {}


def get_kwargs_query(self) -> dict:
    """Joins, order_by por acción."""
    if self.action == "list":
        return {"joins": ["category"]}
    return {}
```

## Variantes

- `fastapi_basekit.aio.sqlalchemy.service.base.BaseService` — async SQLAlchemy
- `fastapi_basekit.aio.sqlmodel.service.base.BaseService` — async SQLModel
- `fastapi_basekit.aio.beanie.service.base.BaseService` — async Beanie/Mongo

[:octicons-arrow-right-24: Pattern](../user-guide/services.md){ .md-button .md-button--primary }
