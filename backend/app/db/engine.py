from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db import models  # noqa: F401 — register models

_engine = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        get_engine()
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    fac = get_session_factory()
    async with fac() as session:
        yield session


async def init_db() -> None:
    if settings.database_path:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    async with get_engine().begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)


async def close_db() -> None:
    await reset_engine()


async def reset_engine() -> None:
    """Dispose engine and clear factories (e.g. tests switching DB URL)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
