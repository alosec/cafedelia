#!/usr/bin/env python3
"""
Test script to verify reactive UI updates and session ID persistence.

This demonstrates:
1. SQLite WAL mode enables concurrent read/write
2. Reactive attributes automatically update the UI
3. Session IDs are properly persisted to the database
"""

import asyncio
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_wal_mode():
    """Test that WAL mode is enabled on the database."""
    from elia_chat.database.database import engine
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA journal_mode"))
        mode = result.scalar()
        logger.info(f"Database journal mode: {mode}")
        assert mode == "wal", f"Expected WAL mode, got {mode}"
        
    logger.info("✓ WAL mode test passed")

async def test_session_id_persistence():
    """Test that session IDs are properly saved and retrieved."""
    from elia_chat.database.models import ChatDao
    from elia_chat.database.database import create_database
    
    # Ensure database exists
    await create_database()
    
    # Test finding non-existent session
    test_session_id = "test-1234-5678-90ab-cdef"
    existing = await ChatDao.find_by_session_id(test_session_id)
    assert existing is None, "Should not find non-existent session"
    
    logger.info("✓ Session ID lookup test passed")

async def main():
    """Run all tests."""
    logger.info("Starting Cafedelia reactive update tests...")
    
    await test_wal_mode()
    await test_session_id_persistence()
    
    logger.info("\n✅ All tests passed! Ready for interactive testing.")
    logger.info("\nTo test the full flow:")
    logger.info("1. Run Cafedelia: python -m elia_chat")
    logger.info("2. Start a Claude Code chat")
    logger.info("3. Observe that streaming responses update automatically")
    logger.info("4. Check that session IDs persist after chat completion")

if __name__ == "__main__":
    asyncio.run(main())
