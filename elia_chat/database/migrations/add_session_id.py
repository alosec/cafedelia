"""
Database migration to add session_id field to chat table.

This migration adds proper session deduplication by adding a unique session_id field
to replace the broken title-based matching that was causing massive duplication.
"""

import asyncio
import logging
from sqlalchemy import text
from elia_chat.database.database import engine

logger = logging.getLogger(__name__)


async def add_session_id_column():
    """Add session_id column to chat table with unique constraint."""
    async with engine.begin() as conn:
        try:
            # Add the session_id column
            await conn.execute(text("""
                ALTER TABLE chat 
                ADD COLUMN session_id VARCHAR(255) NULL
            """))
            
            # Create unique index on session_id
            await conn.execute(text("""
                CREATE UNIQUE INDEX idx_chat_session_id 
                ON chat(session_id) 
                WHERE session_id IS NOT NULL
            """))
            
            logger.info("Successfully added session_id column with unique constraint")
            
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("session_id column already exists, skipping migration")
            else:
                logger.error(f"Migration failed: {e}")
                raise


async def populate_session_ids():
    """
    Populate session_id field from existing chat titles where possible.
    
    This attempts to extract session IDs from titles that contain UUIDs,
    helping to preserve existing data during the migration.
    """
    async with engine.begin() as conn:
        try:
            # Extract session IDs from titles that look like UUIDs
            # Pattern matches: "Claude Code Session - abc123de-..." or similar
            await conn.execute(text("""
                UPDATE chat 
                SET session_id = SUBSTR(title, 
                    INSTR(title, '-') + 2,  -- Skip "Claude Code Session - "
                    36  -- UUID length
                )
                WHERE title LIKE '%-%-%-%-%' 
                AND LENGTH(title) > 36
                AND session_id IS NULL
            """))
            
            logger.info("Populated session_id fields from existing titles")
            
        except Exception as e:
            logger.warning(f"Failed to populate session_ids from titles: {e}")


async def remove_duplicate_chats():
    """
    Remove duplicate chats that have the same session_id.
    
    Keeps the chat with the most recent messages and removes older duplicates.
    """
    async with engine.begin() as conn:
        try:
            # Find and remove duplicate chats, keeping the one with latest activity
            await conn.execute(text("""
                DELETE FROM chat 
                WHERE id NOT IN (
                    SELECT DISTINCT c1.id
                    FROM chat c1
                    LEFT JOIN message m1 ON c1.id = m1.chat_id
                    WHERE c1.session_id IS NOT NULL
                    AND c1.id = (
                        SELECT c2.id
                        FROM chat c2
                        LEFT JOIN message m2 ON c2.id = m2.chat_id
                        WHERE c2.session_id = c1.session_id
                        GROUP BY c2.id
                        ORDER BY MAX(m2.timestamp) DESC, c2.id DESC
                        LIMIT 1
                    )
                )
                AND session_id IS NOT NULL
            """))
            
            logger.info("Removed duplicate chats with same session_id")
            
        except Exception as e:
            logger.warning(f"Failed to remove duplicate chats: {e}")


async def run_migration():
    """Run the complete migration process."""
    logger.info("Starting session_id migration...")
    
    await add_session_id_column()
    await populate_session_ids() 
    await remove_duplicate_chats()
    
    logger.info("Session_id migration completed successfully")


if __name__ == "__main__":
    asyncio.run(run_migration())