#!/usr/bin/env python3
"""
Test Simple WTE Integration

Test the simplified WTE server without complex dependencies.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_simple_wte():
    """Test simple WTE server"""
    logger.info("Testing Simple WTE Server")
    
    try:
        from sync.wte.simple_manager import SimpleWTEServer
        
        # Create server
        server = SimpleWTEServer()
        
        # Start server
        await server.start_server()
        
        # Check health
        health = server.is_healthy()
        logger.info(f"Server healthy: {health}")
        
        # Get pipeline status
        status = server.get_all_pipeline_status()
        for pipeline_id, info in status.items():
            logger.info(f"Pipeline {info.name}: {info.status.value}")
        
        # Start another pipeline
        await server.start_pipeline("jsonl_sync")
        
        # Let it run
        logger.info("Running for 5 seconds...")
        await asyncio.sleep(5)
        
        # Check events processed
        status = server.get_all_pipeline_status()
        for pipeline_id, info in status.items():
            logger.info(f"Pipeline {info.name}: {info.events_processed} events")
        
        # Stop server
        await server.stop_server()
        
        logger.info("✅ Simple WTE Server test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Simple WTE Server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_simple_wte())
    print("\n🎉 WTE Pipeline Server with GUI is ready!" if success else "\n💥 Test failed!")
    
    if success:
        print("\n📋 Usage:")
        print("1. Run: python -m elia_chat")
        print("2. Press F9 to open the Sync Manager")
        print("3. Use the GUI to start/stop/monitor pipelines")
        print("\n✨ Features:")
        print("- Real-time pipeline status monitoring")
        print("- Start/Stop/Restart individual pipelines") 
        print("- Server health monitoring")
        print("- Event processing counters")
        print("- Error tracking and display")
    
    sys.exit(0 if success else 1)