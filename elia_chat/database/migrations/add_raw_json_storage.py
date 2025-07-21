"""
Add raw JSON storage capability to MessageDao.

Migration to add raw_json, message_type, and metadata fields for atomic
Claude Code message persistence with complete fidelity.
"""

import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from elia_chat.database.database import get_session

logger = logging.getLogger(__name__)


async def add_raw_json_storage():
    """Add raw JSON storage fields to message table."""
    logger.info("Starting raw JSON storage migration...")
    
    try:
        async with get_session() as session:
            # Add raw_json field for storing original Claude Code JSON
            await session.exec(text("""
                ALTER TABLE message 
                ADD COLUMN raw_json TEXT DEFAULT NULL
            """))
            logger.info("Added raw_json column")
            
            # Add message_type field for structured message typing
            await session.exec(text("""
                ALTER TABLE message 
                ADD COLUMN message_type TEXT DEFAULT 'assistant'
            """))
            logger.info("Added message_type column")
            
            # Add message_metadata field for additional message information
            await session.exec(text("""
                ALTER TABLE message 
                ADD COLUMN message_metadata TEXT DEFAULT '{}'
            """))
            logger.info("Added message_metadata column")
            
            # Create indexes for performance
            await session.exec(text("""
                CREATE INDEX IF NOT EXISTS idx_message_type 
                ON message(message_type)
            """))
            logger.info("Created message_type index")
            
            await session.exec(text("""
                CREATE INDEX IF NOT EXISTS idx_message_source_type 
                ON message(message_source, message_type)
            """))
            logger.info("Created compound message_source/message_type index")
            
            # Update existing messages to have proper message_type based on role
            await session.exec(text("""
                UPDATE message 
                SET message_type = CASE 
                    WHEN role = 'user' THEN 'user'
                    WHEN role = 'assistant' THEN 'assistant'
                    WHEN role = 'system' THEN 'system'
                    ELSE 'assistant'
                END
                WHERE message_type = 'assistant'
            """))
            logger.info("Updated existing message types")
            
            await session.commit()
            logger.info("Raw JSON storage migration completed successfully")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


async def rollback_raw_json_storage():
    """Rollback raw JSON storage migration."""
    logger.info("Starting raw JSON storage rollback...")
    
    try:
        async with get_session() as session:
            # Drop indexes
            await session.exec(text("""
                DROP INDEX IF EXISTS idx_message_type
            """))
            await session.exec(text("""
                DROP INDEX IF EXISTS idx_message_source_type
            """))
            logger.info("Dropped indexes")
            
            # Drop columns (SQLite doesn't support DROP COLUMN easily, so we'd need to recreate table)
            # For now, just mark columns as unused by setting them to NULL
            await session.exec(text("""
                UPDATE message 
                SET raw_json = NULL, message_metadata = NULL
            """))
            logger.info("Cleared raw JSON storage data")
            
            await session.commit()
            logger.info("Raw JSON storage rollback completed")
            
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise


if __name__ == "__main__":
    # Run migration directly
    async def main():
        await add_raw_json_storage()
    
    asyncio.run(main())