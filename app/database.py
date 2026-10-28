from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings


def build_engine(settings: Settings):
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if not settings.database_url.startswith("sqlite"):
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            pool_recycle=1800,
        )
    return create_async_engine(settings.database_url, **kwargs)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as session:
        yield session
