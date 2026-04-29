"""Reusable async SQLAlchemy session lifecycle.

Single commit / single rollback per request. Optional hooks fire after
commit (success) or rollback (error) so callers can attach logging,
metrics, sentry, retries, etc. without coupling the lifecycle to any
specific telemetry stack.

Usage:

    from fastapi_basekit.aio.sqlalchemy.session import make_session_lifecycle
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(DATABASE_URL)
    SessionFactory = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)

    async def on_error(exc, session):
        logger.exception("rollback", exc_info=exc)

    get_db = make_session_lifecycle(SessionFactory, on_error=on_error)

    # then in routes: ... session: AsyncSession = Depends(get_db)

Rule of thumb for callers:
- Services SHOULD NOT call session.flush / session.commit / session.refresh.
- Repositories own flush via BaseRepository.create / update.
- get_db owns the single commit (success) and rollback (error).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

ErrorHook = Callable[[Exception, AsyncSession], Awaitable[None]]
SuccessHook = Callable[[AsyncSession], Awaitable[None]]


def make_session_lifecycle(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    on_success: Optional[SuccessHook] = None,
    on_error: Optional[ErrorHook] = None,
) -> Callable[[], AsyncGenerator[AsyncSession, None]]:
    """Return an async generator dependency that owns the request session.

    The returned callable yields a session, commits on success, rolls back
    on error, and invokes optional hooks. Hooks must not raise — wrap them
    in try/except at the call site if their failure should not poison the
    request.
    """

    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
                if on_success is not None:
                    await on_success(session)
            except Exception as exc:
                await session.rollback()
                if on_error is not None:
                    await on_error(exc, session)
                raise

    return get_db
