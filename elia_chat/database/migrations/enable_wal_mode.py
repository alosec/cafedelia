"""
Database migration to enable WAL mode for better concurrent access.

WAL (Write-Ahead Logging) mode allows readers and writers to work simultaneously,
preventing the UI from missing updates during streaming responses.
"""

import asyncio
import logging
from sqlalchemy import text
from elia_chat.database.database import engine

logger = logging.getLogger(__name__)


async def enable_wal_mode():
    """Enable WAL mode on the SQLite database."""
    async with engine.begin() as conn:
        try:
            # Enable WAL mode
            result = await conn.execute(text("PRAGMA journal_mode=WAL"))
            mode = result.scalar()
            
            if mode == "wal":
                logger.info("Successfully enabled WAL mode")
            else:
                logger.warning(f"Failed to enable WAL mode, current mode: {mode}")
            
            # Set other performance pragmas
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA cache_size=10000"))
            await conn.execute(text("PRAGMA temp_store=MEMORY"))
            
            logger.info("Applied performance optimizations")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise


async def run_migration():
    """Run the WAL mode migration."""
    logger.info("Starting WAL mode migration...")
    await enable_wal_mode()
    logger.info("WAL mode migration completed successfully")


if __name__ == "__main__":
    asyncio.run(run_migration())
