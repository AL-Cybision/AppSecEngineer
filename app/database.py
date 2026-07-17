from collections.abc import AsyncIterator

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str | None = None) -> AsyncEngine:
    settings = get_settings()
    if database_url or settings.database_url:
        url: str | URL = database_url or settings.database_url or ""
    elif settings.database_host and settings.database_password:
        url = URL.create(
            "postgresql+asyncpg",
            username=settings.database_user,
            password=settings.database_password,
            host=settings.database_host,
            port=settings.database_port,
            database=settings.database_name,
        )
    else:
        url = "sqlite+aiosqlite:///./expenseguard.db"
    return create_async_engine(url, pool_pre_ping=True)


engine = build_engine()
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
