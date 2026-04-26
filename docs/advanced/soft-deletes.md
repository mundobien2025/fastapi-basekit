# Soft Deletes

`BaseModel` provee `deleted_at: datetime | None`. La librería NO filtra automáticamente — tú decides cuándo aplicar.

## Marcar un row como borrado

```python
thing = await repo.get(thing_id)
thing.soft_delete()       # setea deleted_at = now (UTC)
await session.flush()
```

## Restaurar

```python
thing.restore()           # deleted_at = None
await session.flush()
```

## `is_deleted` property

```python
if thing.is_deleted:
    print("borrado")
```

## Filtrar listados

Override `build_list_queryset` en el repo:

```python
from sqlalchemy import select

class ThingRepository(BaseRepository):
    model = Thing

    def build_list_queryset(self, **kwargs):
        return select(self.model).where(self.model.deleted_at.is_(None))
```

Aplica a `service.list()` automáticamente.

## Filtrar queries custom

Cada query custom DEBE incluir el filtro:

```python
async def get_by_email(self, email: str) -> Users | None:
    result = await self.session.execute(
        select(Users).where(
            Users.email == email,
            Users.deleted_at.is_(None),     # ← obligatorio
        )
    )
    return result.scalars().first()
```

!!! danger "Olvidar el filtro = leak de rows borrados"
    No hay magia que lo aplique. Si tu query no filtra `deleted_at`, los rows borrados aparecen.

## Service.delete() default

`BaseService.delete()` llama a `repo.delete()` que es **hard delete**. Para soft delete, override:

```python
async def delete(self, thing_id) -> bool:
    thing = await self.repository.get(thing_id)
    if not thing:
        raise NotFoundException("Thing no encontrado")
    thing.soft_delete()
    await self.session.flush()
    return True
```

## Cascada manual

Soft delete no cascadea automáticamente. Si borras un `User`, sus `Posts` siguen ahí. Hazlo manual:

```python
async def delete(self, user_id) -> bool:
    user = await self.repository.get_with_joins(user_id, joins=["posts"])
    if not user:
        raise NotFoundException("User no encontrado")
    user.soft_delete()
    for post in user.posts:
        post.soft_delete()
    await self.session.flush()
    return True
```

## Listar incluyendo borrados (admin)

```python
def build_list_queryset(self, **kwargs):
    user = getattr(self.service.request.state, "user", None) if self.service else None
    qs = select(self.model)
    if not (user and user.is_platform_admin):
        qs = qs.where(self.model.deleted_at.is_(None))
    return qs
```

Platform admins ven todo, resto solo activos.
