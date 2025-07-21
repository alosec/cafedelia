#!/usr/bin/env python3
"""
Test script for WTE integration

Quick test to verify the WTE pipeline architecture works with cafedelia.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from sync.wte.server import WTEPipelineServer
from sync.database_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_wte_server():
    """Test WTE pipeline server initialization"""
    logger.info("Testing WTE Pipeline Server")
    
    try:
        # Initialize database manager
        logger.info("Initializing database manager")
        db_manager = DatabaseManager()
        
        # Initialize WTE server
        logger.info("Creating WTE pipeline server")
        server = WTEPipelineServer(db_manager)
        
        # Start server
        logger.info("Starting WTE pipeline server")
        await server.start_server()
        
        # Check server status
        logger.info("Checking server health")
        health = server.is_healthy()
        logger.info(f"Server health: {health}")
        
        # Get pipeline status
        logger.info("Getting pipeline status")
        all_status = server.get_all_pipeline_status()
        for pipeline_id, info in all_status.items():
            logger.info(f"Pipeline {pipeline_id}: {info.status.value}")
        
        # Let it run for a few seconds
        logger.info("Running for 5 seconds...")
        await asyncio.sleep(5)
        
        # Stop server
        logger.info("Stopping WTE pipeline server")
        await server.stop_server()
        
        logger.info("✅ WTE Pipeline Server test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ WTE Pipeline Server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_database_manager():
    """Test database manager functionality"""
    logger.info("Testing Database Manager")
    
    try:
        db_manager = DatabaseManager()
        
        # Test health check
        health = await db_manager.health_check()
        logger.info(f"Database health: {health}")
        
        # Test getting stats
        stats = await db_manager.get_database_stats()
        logger.info(f"Database stats: {stats}")
        
        # Test listing sessions
        sessions = await db_manager.list_sessions(limit=5)
        logger.info(f"Found {len(sessions)} sessions")
        
        logger.info("✅ Database Manager test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database Manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test runner"""
    logger.info("🚀 Starting WTE Integration Tests")
    
    results = []
    
    # Test database manager
    results.append(await test_database_manager())
    
    # Test WTE server
    results.append(await test_wte_server())
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    logger.info(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.error("💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)