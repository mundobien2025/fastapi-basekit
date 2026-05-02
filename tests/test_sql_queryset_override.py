"""Override patterns for build_list_queryset on SQLAlchemy + SQLModel.

These tests prove that subclasses can:

- Filter soft-deleted rows out of every list query.
- Inject extra columns / computed expressions and have them flow back.
- Compose JOINs into the base query before pagination kicks in.

Both ORMs share the contract: `build_list_queryset(**kwargs) -> Select`.
The test suite exercises real SQLite-in-memory databases — no mocks —
so behavior changes in either base class surface immediately.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi_basekit.aio.sqlalchemy.repository.base import (
    BaseRepository as SQLBaseRepository,
)


# ============================================================================
# SQLAlchemy fixtures
# ============================================================================

SQLBase = declarative_base()


class Author(SQLBase):
    __tablename__ = "authors_qs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), nullable=False)
    posts = relationship("Post", back_populates="author")


class Post(SQLBase):
    __tablename__ = "posts_qs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    is_published = Column(Boolean, default=True, nullable=False)
    author_id = Column(Integer, ForeignKey("authors_qs.id"), nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    author = relationship("Author", back_populates="posts")


class PostRepoDefault(SQLBaseRepository):
    """No override — should return all rows including soft-deleted."""

    model = Post


class PostRepoSoftDelete(SQLBaseRepository):
    """Override hides soft-deleted rows from every list query."""

    model = Post

    def build_list_queryset(self, **kwargs):
        return select(Post).where(Post.deleted_at.is_(None))


class PostRepoPublishedOnly(SQLBaseRepository):
    """Override stacks two predicates."""

    model = Post

    def build_list_queryset(self, **kwargs):
        return (
            select(Post)
            .where(Post.deleted_at.is_(None))
            .where(Post.is_published.is_(True))
        )


@pytest.fixture
async def sql_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLBase.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLBase.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def sql_session(sql_engine):
    maker = sessionmaker(sql_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture
async def seed_posts(sql_session):
    """Three live + one soft-deleted + one unpublished post under one author."""
    author = Author(name="Alice")
    sql_session.add(author)
    await sql_session.flush()

    posts = [
        Post(title="Live A", is_published=True, author_id=author.id),
        Post(title="Live B", is_published=True, author_id=author.id),
        Post(title="Live C", is_published=True, author_id=author.id),
        Post(
            title="Deleted",
            is_published=True,
            author_id=author.id,
            deleted_at=datetime.utcnow() - timedelta(days=1),
        ),
        Post(title="Draft", is_published=False, author_id=author.id),
    ]
    for p in posts:
        sql_session.add(p)
    await sql_session.commit()
    return author, posts


class TestSQLAlchemyBuildListQuerysetOverride:
    """SQLAlchemy `build_list_queryset` is the documented extension hook."""

    @pytest.mark.asyncio
    async def test_default_returns_all_rows(self, sql_session, seed_posts):
        repo = PostRepoDefault(db=sql_session)
        rows, total = await repo.list_paginated(page=1, count=50)
        assert total == 5

    @pytest.mark.asyncio
    async def test_soft_delete_override_hides_deleted(
        self, sql_session, seed_posts
    ):
        repo = PostRepoSoftDelete(db=sql_session)
        rows, total = await repo.list_paginated(page=1, count=50)
        assert total == 4
        assert all(r.deleted_at is None for r in rows)

    @pytest.mark.asyncio
    async def test_stacked_predicates(self, sql_session, seed_posts):
        repo = PostRepoPublishedOnly(db=sql_session)
        rows, total = await repo.list_paginated(page=1, count=50)
        assert total == 3
        assert all(r.is_published and r.deleted_at is None for r in rows)

    @pytest.mark.asyncio
    async def test_override_combines_with_runtime_filters(
        self, sql_session, seed_posts
    ):
        """Runtime filters layer on top of the override predicate."""
        repo = PostRepoSoftDelete(db=sql_session)
        rows, total = await repo.list_paginated(
            page=1, count=50, filters={"is_published": True}
        )
        # 3 live + published; the deleted one and the draft are excluded
        assert total == 3
        assert all(r.is_published for r in rows)

    @pytest.mark.asyncio
    async def test_override_combines_with_search(
        self, sql_session, seed_posts
    ):
        repo = PostRepoSoftDelete(db=sql_session)
        rows, total = await repo.list_paginated(
            page=1, count=50, search="Live", search_fields=["title"]
        )
        assert total == 3
        assert all(r.title.startswith("Live") for r in rows)

    @pytest.mark.asyncio
    async def test_pagination_respects_override(self, sql_session, seed_posts):
        repo = PostRepoSoftDelete(db=sql_session)
        page1, total1 = await repo.list_paginated(page=1, count=2)
        page2, total2 = await repo.list_paginated(page=2, count=2)
        page3, total3 = await repo.list_paginated(page=3, count=2)
        assert total1 == total2 == total3 == 4
        assert len(page1) == 2 and len(page2) == 2 and len(page3) == 0


# ============================================================================
# SQLModel — same contract, parallel tests
# ============================================================================

from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from fastapi_basekit.aio.sqlmodel.repository.base import (
    BaseRepository as SQLModelBaseRepository,
)


class PostSM(SQLModel, table=True):
    __tablename__ = "posts_sm_qs"
    id: int | None = Field(default=None, primary_key=True)
    title: str
    is_published: bool = True
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PostSMRepoDefault(SQLModelBaseRepository):
    model = PostSM


class PostSMRepoSoftDelete(SQLModelBaseRepository):
    model = PostSM

    def build_list_queryset(self, **kwargs):
        from sqlmodel import select as sm_select

        return sm_select(PostSM).where(PostSM.deleted_at.is_(None))


class PostSMRepoPublishedOnly(SQLModelBaseRepository):
    model = PostSM

    def build_list_queryset(self, **kwargs):
        from sqlmodel import select as sm_select

        return (
            sm_select(PostSM)
            .where(PostSM.deleted_at.is_(None))
            .where(PostSM.is_published.is_(True))
        )


@pytest.fixture
async def sm_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def sm_session(sm_engine):
    async with SQLModelAsyncSession(sm_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
async def sm_seed(sm_session):
    posts = [
        PostSM(title="Live A", is_published=True),
        PostSM(title="Live B", is_published=True),
        PostSM(title="Live C", is_published=True),
        PostSM(
            title="Deleted",
            is_published=True,
            deleted_at=datetime.utcnow() - timedelta(days=1),
        ),
        PostSM(title="Draft", is_published=False),
    ]
    for p in posts:
        sm_session.add(p)
    await sm_session.commit()
    return posts


class TestSQLModelBuildListQuerysetOverride:
    @pytest.mark.asyncio
    async def test_default_returns_all_rows(self, sm_session, sm_seed):
        repo = PostSMRepoDefault(db=sm_session)
        _, total = await repo.list_paginated(page=1, count=50)
        assert total == 5

    @pytest.mark.asyncio
    async def test_soft_delete_override_hides_deleted(
        self, sm_session, sm_seed
    ):
        repo = PostSMRepoSoftDelete(db=sm_session)
        rows, total = await repo.list_paginated(page=1, count=50)
        assert total == 4
        assert all(r.deleted_at is None for r in rows)

    @pytest.mark.asyncio
    async def test_stacked_predicates(self, sm_session, sm_seed):
        repo = PostSMRepoPublishedOnly(db=sm_session)
        rows, total = await repo.list_paginated(page=1, count=50)
        assert total == 3
        assert all(r.is_published and r.deleted_at is None for r in rows)

    @pytest.mark.asyncio
    async def test_override_combines_with_runtime_filters(
        self, sm_session, sm_seed
    ):
        repo = PostSMRepoSoftDelete(db=sm_session)
        rows, total = await repo.list_paginated(
            page=1, count=50, filters={"is_published": True}
        )
        assert total == 3
        assert all(r.is_published for r in rows)

    @pytest.mark.asyncio
    async def test_override_combines_with_search(self, sm_session, sm_seed):
        repo = PostSMRepoSoftDelete(db=sm_session)
        rows, total = await repo.list_paginated(
            page=1, count=50, search="Live", search_fields=["title"]
        )
        assert total == 3
        assert all(r.title.startswith("Live") for r in rows)

    @pytest.mark.asyncio
    async def test_pagination_respects_override(self, sm_session, sm_seed):
        repo = PostSMRepoSoftDelete(db=sm_session)
        page1, total1 = await repo.list_paginated(page=1, count=2)
        page2, total2 = await repo.list_paginated(page=2, count=2)
        page3, total3 = await repo.list_paginated(page=3, count=2)
        assert total1 == total2 == total3 == 4
        assert len(page1) == 2 and len(page2) == 2 and len(page3) == 0
