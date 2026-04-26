# Relaciones

## 1:N (one-to-many)

```python
class Category(BaseModel):
    __tablename__ = "categories"
    name: Mapped[str] = mapped_column(String(100))
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(BaseModel):
    __tablename__ = "products"
    category_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    category: Mapped["Category"] = relationship(back_populates="products")
```

Eager load:
```python
items = await repo.list_paginated(joins=["category"])   # JOIN con joinedload (N:1)
```

## N:1 inverso (parent → many children)

```python
items = await category_repo.get_with_joins(category_id, joins=["products"])
# selectinload (1:N) — query separada para evitar cartesian
print(category.products)   # ya cargado, no N+1
```

## Many-to-many con tabla join

```python
class TagAssoc(BaseModel):
    __tablename__ = "thing_tags"
    __table_args__ = (
        UniqueConstraint("thing_id", "tag_id", name="uq_thing_tags"),
    )

    thing_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("things.id", ondelete="CASCADE"))
    tag_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("tags.id", ondelete="CASCADE"))


class Thing(BaseModel):
    tags: Mapped[list["Tag"]] = relationship(
        secondary="thing_tags",
        back_populates="things",
    )


class Tag(BaseModel):
    things: Mapped[list["Thing"]] = relationship(
        secondary="thing_tags",
        back_populates="tags",
    )
```

Filtros sobre relación M:N:
```http
GET /api/v1/things/?tags__name=urgent
```

`BaseRepository._resolve_attribute()` agrega los JOINs.

## Self-referential (parent/child)

```python
class Category(BaseModel):
    __tablename__ = "categories"

    parent_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    parent: Mapped["Category"] = relationship(remote_side="Category.id", back_populates="children")
    children: Mapped[list["Category"]] = relationship(back_populates="parent")
```

```http
GET /api/v1/categories/?parent__name=Root
GET /api/v1/categories/?parent__parent__slug=top   # 2 niveles
```

## Beanie Links

```python
from beanie import Document, Link


class Category(Document):
    name: str

    class Settings:
        name = "categories"


class Product(Document):
    name: str
    category: Link[Category]

    class Settings:
        name = "products"
```

Filtrar por link:
```python
# WRONG — Beanie no matchea Links por raw ObjectId
products = await Product.find(Product.category == cat_id).to_list()

# RIGHT
products = await Product.find({"category.$id": cat_id}).to_list()
```

Eager load:
```python
products = await Product.find_all(fetch_links=True).to_list()
```

## Cascade delete

```python
# CASCADE — borrar Category borra todos sus Products
category_id: Mapped[UUID] = mapped_column(
    GUID(), ForeignKey("categories.id", ondelete="CASCADE")
)

# SET NULL — borrar Category deja products huérfanos (category_id = NULL)
category_id: Mapped[UUID | None] = mapped_column(
    GUID(), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
)

# RESTRICT — DB rechaza el delete si hay products ligados
category_id: Mapped[UUID] = mapped_column(
    GUID(), ForeignKey("categories.id", ondelete="RESTRICT")
)
```

## Ordering por campo de relación

```http
GET /api/v1/products/?order_by=category__name
GET /api/v1/products/?order_by=-category__priority
```

JOIN automático.
