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

## Beanie — hooks de extensión (0.3.2+)

Atributos extra de clase para servicios Beanie:

| Atributo | Tipo | Default | Descripción |
|---|---|---|---|
| `use_aggregation` | `bool` | `False` | Forza ruta de aggregation pipeline en `list()` |
| `aggregation_validate` | `bool` | `True` | Si `False`, devuelve dicts crudos del pipeline sin `model_validate` |

Hooks que delegan al repositorio (override para componer subqueries
cross-collection sin tocar el controlador):

```python
def build_list_queryset(self, search, search_fields, filters,
                        order_by, **kwargs) -> FindMany:
    """FindMany path — override para customizar query antes de paginar."""
    return self.repository.build_list_queryset(...)


def build_list_pipeline(self, search, search_fields, filters,
                        order_by, **kwargs) -> List[dict]:
    """Aggregation path — override para añadir $lookup/$project/$group."""
    return self.repository.build_list_pipeline(...)
```

Ejemplo con join cross-collection (admin users + wallets + policies):

```python
class AdminUserService(BaseService):
    repository: UserRepository
    use_aggregation = True
    aggregation_validate = False

    def build_list_pipeline(self, search=None, search_fields=None,
                            filters=None, order_by=None, **kwargs):
        pipeline = self.repository.build_list_pipeline(
            search=search, search_fields=search_fields,
            filters=filters, order_by=order_by or "-created_at",
        )
        pipeline.extend([
            {"$lookup": {"from": "wallets", "localField": "_id",
                         "foreignField": "user.$id", "as": "wallet_data"}},
            {"$unwind": {"path": "$wallet_data",
                         "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "id": {"$toString": "$_id"},
                "wallet_balance": {"$convert": {
                    "input": "$wallet_data.balance",
                    "to": "string", "onNull": None,
                }},
            }},
        ])
        return pipeline
```

[:octicons-arrow-right-24: Pattern](../user-guide/services.md){ .md-button .md-button--primary }
