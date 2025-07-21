from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlmodel import SQLModel
from elia_chat.locations import data_directory
from sqlalchemy import text

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


sqlite_file_name = data_directory() / "cafedelia.sqlite"
sqlite_url = f"sqlite+aiosqlite:///{sqlite_file_name}"
# Enable WAL mode for better concurrent access
engine = create_async_engine(
    sqlite_url,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


async def create_database():
    async with engine.begin() as conn:
        # TODO - check if exists, use Alembic.
        await conn.run_sync(SQLModel.metadata.create_all)
        # Enable WAL mode for better concurrent read/write
        await conn.execute(text("PRAGMA journal_mode=WAL"))


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
