#!/usr/bin/env python3
"""
Non-Interactive Sync Parity Check

Quick test to validate synchronization between JSONL files in ~/.claude/projects 
and the cafedelia SQLite database.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sync.sync_validation_guard import SyncValidationGuard


async def check_parity():
    """Non-interactive parity check"""
    
    print("🔍 Cafedelia Sync Parity Check")
    print("=" * 50)
    
    # Initialize validation guard
    guard = SyncValidationGuard()
    
    # Run comprehensive validation
    print("📊 Running sync validation...")
    result = await guard.validate_sync_state(deep_validation=False)
    
    # Display results
    print(f"\n📈 Results:")
    print(f"   JSONL Sessions: {result.total_jsonl_sessions}")
    print(f"   Database Sessions: {result.total_db_sessions}")
    print(f"   Status: {result.summary}")
    
    if result.has_issues:
        print(f"\n⚠️  Issues Found:")
        
        if result.missing_in_db:
            print(f"   📥 Missing in Database: {len(result.missing_in_db)} sessions")
            # Show first few examples
            for session_id in result.missing_in_db[:3]:
                print(f"      - {session_id}")
            if len(result.missing_in_db) > 3:
                print(f"      ... and {len(result.missing_in_db) - 3} more")
        
        if result.orphaned_in_db:
            print(f"   🗑️  Orphaned in Database: {len(result.orphaned_in_db)} sessions")
            for session_id in result.orphaned_in_db[:3]:
                print(f"      - {session_id}")
            if len(result.orphaned_in_db) > 3:
                print(f"      ... and {len(result.orphaned_in_db) - 3} more")
        
        if result.content_mismatches:
            print(f"   🔄 Content Mismatches: {len(result.content_mismatches)} sessions")
        
        if result.last_modified_mismatches:
            print(f"   ⏰ Timestamp Mismatches: {len(result.last_modified_mismatches)} sessions")
        
        print(f"\n💡 Recommendations:")
        if result.missing_in_db:
            print(f"   • Run sync repair to add missing sessions to database")
        if result.orphaned_in_db:
            print(f"   • Review orphaned database entries for cleanup")
        
        return False
    else:
        print(f"\n✅ Perfect Sync!")
        print(f"   All {result.total_jsonl_sessions} JSONL sessions are properly synchronized")
        return True


async def check_paths():
    """Verify that key paths exist"""
    
    claude_projects = Path.home() / ".claude" / "projects"
    db_path = Path.home() / ".local" / "share" / "cafedelia" / "cafedelia.sqlite"
    
    print(f"📁 Path Check:")
    print(f"   Claude Projects: {claude_projects}")
    print(f"   Exists: {'✅' if claude_projects.exists() else '❌'}")
    
    if claude_projects.exists():
        project_dirs = list(claude_projects.iterdir())
        jsonl_files = []
        for project_dir in project_dirs:
            if project_dir.is_dir():
                jsonl_files.extend(project_dir.glob("*.jsonl"))
        print(f"   Found {len(project_dirs)} project directories")
        print(f"   Found {len(jsonl_files)} JSONL files")
    
    print(f"\n   Database: {db_path}")
    print(f"   Exists: {'✅' if db_path.exists() else '❌'}")
    
    if db_path.exists():
        db_size = db_path.stat().st_size
        print(f"   Size: {db_size:,} bytes ({db_size/1024/1024:.1f} MB)")
    
    return claude_projects.exists() and db_path.exists()


async def main():
    """Main test runner"""
    
    print("🚀 Starting Non-Interactive Sync Parity Check\n")
    
    try:
        # Step 1: Check paths
        paths_ok = await check_paths()
        
        if not paths_ok:
            print("\n❌ Required paths not found. Cannot proceed with sync check.")
            return False
        
        print()
        
        # Step 2: Check parity
        sync_ok = await check_parity()
        
        print(f"\n📋 Summary:")
        print(f"   Paths Valid: {'✅' if paths_ok else '❌'}")
        print(f"   Sync Valid: {'✅' if sync_ok else '❌'}")
        
        if sync_ok:
            print(f"\n🎉 Everything is in perfect sync!")
        else:
            print(f"\n⚙️  To fix sync issues, run:")
            print(f"   python test_sync_parity.py --repair")
        
        return sync_ok
        
    except Exception as e:
        print(f"\n💥 Error during parity check: {e}")
        import traceback
        traceback.print_exc()
        return False


async def repair_sync():
    """Run sync repair"""
    print("🔧 Running Sync Repair...\n")
    
    guard = SyncValidationGuard()
    
    # First validate to find issues
    result = await guard.validate_sync_state(deep_validation=False)
    
    if not result.has_issues:
        print("✅ No sync issues found. Nothing to repair.")
        return True
    
    print(f"Found issues: {result.summary}")
    print("🔄 Attempting automatic repair...")
    
    # Run repair
    repair_success = await guard.repair_sync_issues(result)
    
    if repair_success:
        print("✅ Repair completed successfully!")
        
        # Re-validate to confirm
        print("🔍 Re-validating sync state...")
        new_result = await guard.validate_sync_state(deep_validation=False)
        
        if new_result.is_valid:
            print("🎉 Sync is now perfect!")
        else:
            print(f"⚠️  Some issues remain: {new_result.summary}")
    else:
        print("❌ Some repair operations failed. Manual intervention may be required.")
    
    return repair_success


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--repair":
        success = asyncio.run(repair_sync())
    else:
        success = asyncio.run(main())
    
    sys.exit(0 if success else 1)