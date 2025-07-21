"""
Add sidechain support to message table.

Migration to add fields for tracking sidechain messages, metadata, and message source
to properly represent the complete structure of Claude Code conversations.
"""

import logging
from sqlalchemy import text
from ..database import get_session

logger = logging.getLogger(__name__)

async def add_sidechain_support():
    """Add sidechain support fields to the message table."""
    logger.info("Starting sidechain support migration...")
    
    async with get_session() as session:
        try:
            # Add is_sidechain column
            await session.exec(text("""
                ALTER TABLE message 
                ADD COLUMN is_sidechain BOOLEAN DEFAULT FALSE
            """))
            logger.info("Added is_sidechain column")
            
            # Add sidechain_metadata JSON column
            await session.exec(text("""
                ALTER TABLE message 
                ADD COLUMN sidechain_metadata TEXT DEFAULT '{}'
            """))
            logger.info("Added sidechain_metadata column")
            
            # Add message_source column
            await session.exec(text("""
                ALTER TABLE message 
                ADD COLUMN message_source VARCHAR(50) DEFAULT 'main'
            """))
            logger.info("Added message_source column")
            
            # Create index on is_sidechain for performance
            await session.exec(text("""
                CREATE INDEX idx_message_is_sidechain ON message(is_sidechain)
            """))
            logger.info("Created index on is_sidechain")
            
            # Create index on message_source for filtering
            await session.exec(text("""
                CREATE INDEX idx_message_source ON message(message_source)
            """))
            logger.info("Created index on message_source")
            
            await session.commit()
            logger.info("Sidechain support migration completed successfully")
            
        except Exception as e:
            logger.error(f"Error during sidechain support migration: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(add_sidechain_support())