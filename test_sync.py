#!/usr/bin/env python3
"""
Test script to verify session sync functionality
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from bridge.session_sync import get_session_sync


async def test_session_sync():
    """Test session synchronization"""
    sync = get_session_sync()
    
    print("🔍 Testing cafed backend health...")
    health = await sync.health_check()
    print(f"Health check: {health}")
    
    if health.get('overall_status') != 'ok':
        print("❌ Backend not healthy, cannot test sync")
        return
    
    print("\n📥 Syncing sessions from backend...")
    result = await sync.sync_all_sessions()
    print(f"Sync result: {result}")
    
    print("\n📋 Getting local sessions from database...")
    local_sessions = await sync.get_local_sessions()
    print(f"Found {len(local_sessions)} sessions in local database")
    
    if local_sessions:
        # Show first few sessions
        for i, session in enumerate(local_sessions[:3]):
            print(f"  {i+1}. {session.project_name} - {session.session_uuid[:8]}... ({session.conversation_turns} turns)")
    
    await sync.close()
    print("✅ Session sync test complete")


if __name__ == "__main__":
    asyncio.run(test_session_sync())