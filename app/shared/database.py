from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.shared.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(url: str | None = None) -> async_sessionmaker[AsyncSession]:
    """Лінивий двигун; тести підміняють URL на in-memory SQLite."""
    global _engine, _session_factory
    url = url or get_settings().database_url
    kw = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if ":memory:" in url else {}
    _engine = create_async_engine(url, **kw)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def get_engine():
    if _engine is None:
        init_engine()
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
