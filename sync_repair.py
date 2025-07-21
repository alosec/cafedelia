#!/usr/bin/env python3
"""
Sync Repair Tool

Repairs sync issues by importing JSONL sessions into the database.
Uses the existing sync infrastructure to populate the database.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from simple_sync_check import find_jsonl_sessions, find_database_sessions, compare_sync_state
from sync.service import SyncService


async def repair_missing_sessions(missing_session_ids, jsonl_sessions):
    """Repair missing sessions by running sync service on specific files"""
    
    print(f"🔧 Starting repair of {len(missing_session_ids)} missing sessions...")
    
    # Initialize sync service
    sync_service = SyncService()
    await sync_service.start()
    
    success_count = 0
    error_count = 0
    
    for i, session_id in enumerate(missing_session_ids, 1):
        try:
            print(f"   [{i}/{len(missing_session_ids)}] Processing {session_id}...")
            
            jsonl_info = jsonl_sessions[session_id]
            jsonl_path = jsonl_info['path']
            
            # Use the existing transformer to import this session
            from sync.jsonl_transformer import JSONLTransformer
            transformer = JSONLTransformer()
            
            # Import the session
            result = await transformer.transform_and_store_session(jsonl_path)
            
            if result:
                success_count += 1
                print(f"      ✅ Successfully imported {session_id}")
            else:
                error_count += 1
                print(f"      ❌ Failed to import {session_id}")
                
        except Exception as e:
            error_count += 1
            print(f"      💥 Error importing {session_id}: {e}")
            
        # Progress update every 10 sessions
        if i % 10 == 0:
            print(f"   Progress: {i}/{len(missing_session_ids)} ({success_count} success, {error_count} errors)")
    
    print(f"\n📊 Repair Summary:")
    print(f"   Total Processed: {len(missing_session_ids)}")
    print(f"   Successful: {success_count}")
    print(f"   Errors: {error_count}")
    print(f"   Success Rate: {success_count/len(missing_session_ids)*100:.1f}%")
    
    await sync_service.stop()
    
    return success_count, error_count


async def verify_repair():
    """Verify that repair was successful"""
    
    print(f"\n🔍 Verifying repair...")
    
    # Re-run sync check
    jsonl_sessions = find_jsonl_sessions()
    db_sessions = find_database_sessions()
    result = compare_sync_state(jsonl_sessions, db_sessions)
    
    if result['is_synced']:
        print(f"✅ Repair verification passed! All sessions now synchronized.")
    else:
        print(f"⚠️  Some issues remain:")
        print(f"   Missing in DB: {len(result['missing_in_db'])}")
        print(f"   Orphaned in DB: {len(result['orphaned_in_db'])}")
    
    return result['is_synced']


async def main():
    """Main repair function"""
    
    print("🔧 Cafedelia Sync Repair Tool")
    print("=" * 50)
    
    # Step 1: Assess current state
    print("📊 Assessing sync state...")
    jsonl_sessions = find_jsonl_sessions()
    db_sessions = find_database_sessions()
    
    if not jsonl_sessions:
        print("❌ No JSONL sessions found. Nothing to repair.")
        return False
    
    result = compare_sync_state(jsonl_sessions, db_sessions)
    
    if result['is_synced']:
        print("✅ No repair needed. Database is already synchronized.")
        return True
    
    # Step 2: Ask for confirmation
    missing_count = len(result['missing_in_db'])
    orphaned_count = len(result['orphaned_in_db'])
    
    print(f"\n🔧 Repair Plan:")
    if missing_count > 0:
        print(f"   • Import {missing_count} missing JSONL sessions to database")
    if orphaned_count > 0:
        print(f"   • Review {orphaned_count} orphaned database entries (manual)")
    
    # Auto-proceed for now (could add interactive confirmation)
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        proceed = True
    else:
        response = input(f"\n🤔 Proceed with repair? [Y/n]: ").strip().lower()
        proceed = response in ('', 'y', 'yes')
    
    if not proceed:
        print("❌ Repair cancelled by user.")
        return False
    
    # Step 3: Perform repair
    if result['missing_in_db']:
        success_count, error_count = await repair_missing_sessions(
            result['missing_in_db'], jsonl_sessions
        )
        
        if error_count > 0:
            print(f"⚠️  Some imports failed. Check logs for details.")
    
    # Step 4: Verify repair
    repair_successful = await verify_repair()
    
    if repair_successful:
        print(f"\n🎉 Sync repair completed successfully!")
        print(f"   Database now contains all {len(jsonl_sessions)} JSONL sessions")
    else:
        print(f"\n⚠️  Repair partially successful. Some issues may require manual intervention.")
    
    return repair_successful


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n🛑 Repair cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error during repair: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)