from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .base import Base

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # Allow runtime even when python-dotenv is not installed.
    pass


DEFAULT_DATABASE_URL = "mysql+aiomysql://root:password@localhost:3306/local_on"
_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_engine_from_env(echo: bool = False) -> AsyncEngine:
    return create_async_engine(get_database_url(), echo=echo, pool_pre_ping=True)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_engine_from_env()
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _session_maker


async def dispose_engine() -> None:
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _session_maker = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_maker()() as session:
        yield session


async def create_schema(async_engine: AsyncEngine | None = None) -> None:
    target_engine = async_engine or get_engine()
    owns_engine = async_engine is None
    try:
        async with target_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        if owns_engine:
            # In one-shot scripts, explicitly close pooled connections before loop shutdown.
            await dispose_engine()
