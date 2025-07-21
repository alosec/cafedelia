#!/usr/bin/env python3
"""
Run all necessary database migrations for Cafedelia.
"""

import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_migrations():
    """Run all database migrations in order."""
    # Ensure database exists
    from elia_chat.database.database import create_database
    await create_database()
    logger.info("Database initialized")
    
    # Run WAL mode migration
    try:
        from elia_chat.database.migrations.enable_wal_mode import run_migration as enable_wal
        await enable_wal()
    except Exception as e:
        logger.warning(f"WAL mode migration failed (may already be applied): {e}")
    
    # Run session_id migration  
    try:
        from elia_chat.database.migrations.add_session_id import run_migration as add_session_id
        await add_session_id()
    except Exception as e:
        logger.warning(f"Session ID migration failed (may already be applied): {e}")
    
    logger.info("All migrations completed!")

if __name__ == "__main__":
    asyncio.run(run_migrations())
