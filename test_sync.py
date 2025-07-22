#!/usr/bin/env python3
"""Test script to manually trigger session sync"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bridge.session_sync import get_session_sync

async def test_sync():
    print("🔍 Testing session sync...")
    
    sync = get_session_sync()
    
    # Check health first
    print("📊 Checking health...")
    health = await sync.health_check()
    print(f"Health: {health}")
    
    if health.get('overall_status') != 'ok':
        print("❌ Health check failed, cannot sync")
        return
    
    # Try to sync
    print("🔄 Starting sync...")
    try:
        results = await sync.sync_all_sessions()
        print(f"📈 Sync results: {results}")
        
        if results.get('errors'):
            print("❌ Errors occurred:")
            for error in results.get('errors', []):
                print(f"  - {error}")
        
        created = results.get('created', 0)
        updated = results.get('updated', 0)
        fetched = results.get('total_fetched', 0)
        
        print(f"✅ Sync complete: {fetched} fetched, {created} created, {updated} updated")
        
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
    
    await sync.close()

if __name__ == "__main__":
    asyncio.run(test_sync())