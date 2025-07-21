#!/usr/bin/env python3
"""
Simple Non-Interactive Sync Parity Check

Direct comparison between JSONL files and database without complex dependencies.
"""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def find_jsonl_sessions():
    """Find all JSONL sessions in ~/.claude/projects"""
    
    claude_projects = Path.home() / ".claude" / "projects"
    
    if not claude_projects.exists():
        print(f"❌ Claude projects directory not found: {claude_projects}")
        return {}
    
    sessions = {}
    total_files = 0
    
    for project_dir in claude_projects.iterdir():
        if not project_dir.is_dir():
            continue
            
        for jsonl_file in project_dir.glob("*.jsonl"):
            total_files += 1
            
            try:
                # Extract session ID from filename (UUID format)
                session_id = jsonl_file.stem
                
                # Get file stats
                stat = jsonl_file.stat()
                
                # Count lines/messages
                line_count = 0
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            line_count += 1
                
                sessions[session_id] = {
                    'path': str(jsonl_file),
                    'project': project_dir.name,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'message_count': line_count
                }
                
            except Exception as e:
                print(f"⚠️  Error reading {jsonl_file}: {e}")
                continue
    
    print(f"📁 Found {total_files} JSONL files across {len(list(claude_projects.iterdir()))} projects")
    print(f"📊 Successfully parsed {len(sessions)} sessions")
    
    return sessions


def find_database_sessions():
    """Find all sessions in cafedelia database"""
    
    db_path = Path.home() / ".local" / "share" / "cafedelia" / "cafedelia.sqlite"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return {}
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        
        # Query chats with session_ids (using correct schema)
        cursor = conn.execute("""
            SELECT id, title, session_id, model, started_at
            FROM chat 
            WHERE session_id IS NOT NULL AND session_id != ''
            ORDER BY started_at DESC
        """)
        
        sessions = {}
        for row in cursor.fetchall():
            session_id = row['session_id']
            
            sessions[session_id] = {
                'chat_id': row['id'],
                'title': row['title'],
                'model': row['model'],
                'started_at': row['started_at']
            }
        
        conn.close()
        
        print(f"🗄️  Found {len(sessions)} database sessions with session_ids")
        return sessions
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
        return {}


def compare_sync_state(jsonl_sessions, db_sessions):
    """Compare JSONL and database sessions"""
    
    jsonl_ids = set(jsonl_sessions.keys())
    db_ids = set(db_sessions.keys())
    
    # Find differences
    missing_in_db = jsonl_ids - db_ids
    orphaned_in_db = db_ids - jsonl_ids
    common_sessions = jsonl_ids & db_ids
    
    print(f"\n📊 Sync Analysis:")
    print(f"   JSONL Sessions: {len(jsonl_ids)}")
    print(f"   Database Sessions: {len(db_ids)}")
    print(f"   Common Sessions: {len(common_sessions)}")
    print(f"   Missing in DB: {len(missing_in_db)}")
    print(f"   Orphaned in DB: {len(orphaned_in_db)}")
    
    # Detailed analysis
    if missing_in_db:
        print(f"\n📥 Sessions Missing in Database ({len(missing_in_db)}):")
        for i, session_id in enumerate(sorted(missing_in_db)):
            if i >= 5:  # Show first 5
                print(f"      ... and {len(missing_in_db) - 5} more")
                break
            jsonl_info = jsonl_sessions[session_id]
            print(f"      {session_id} ({jsonl_info['project']}, {jsonl_info['message_count']} messages)")
    
    if orphaned_in_db:
        print(f"\n🗑️  Orphaned Database Sessions ({len(orphaned_in_db)}):")
        for i, session_id in enumerate(sorted(orphaned_in_db)):
            if i >= 5:  # Show first 5
                print(f"      ... and {len(orphaned_in_db) - 5} more")
                break
            db_info = db_sessions[session_id]
            print(f"      {session_id} ({db_info['title']})")
    
    # Check timestamp consistency for common sessions
    timestamp_issues = []
    for session_id in common_sessions:
        jsonl_info = jsonl_sessions[session_id]
        db_info = db_sessions[session_id]
        
        try:
            # Parse database timestamp (using started_at)
            db_time = datetime.fromisoformat(db_info['started_at'].replace('Z', '+00:00'))
            jsonl_time = jsonl_info['modified']
            
            # Check if timestamps are significantly different (more than 1 hour)
            time_diff = abs((db_time.replace(tzinfo=None) - jsonl_time).total_seconds())
            if time_diff > 3600:  # 1 hour tolerance
                timestamp_issues.append({
                    'session_id': session_id,
                    'jsonl_time': jsonl_time,
                    'db_time': db_time.replace(tzinfo=None),
                    'diff_hours': time_diff / 3600
                })
        except Exception:
            continue
    
    if timestamp_issues:
        print(f"\n⏰ Timestamp Inconsistencies ({len(timestamp_issues)}):")
        for issue in timestamp_issues[:3]:
            print(f"      {issue['session_id']} (diff: {issue['diff_hours']:.1f}h)")
    
    # Overall assessment
    is_synced = len(missing_in_db) == 0 and len(orphaned_in_db) == 0
    
    if is_synced:
        print(f"\n✅ Perfect Sync!")
        print(f"   All {len(jsonl_ids)} JSONL sessions are present in database")
    else:
        sync_percentage = len(common_sessions) / max(len(jsonl_ids), 1) * 100
        print(f"\n⚠️  Sync Issues Detected")
        print(f"   Sync Rate: {sync_percentage:.1f}%")
        print(f"   Need to add {len(missing_in_db)} sessions to database")
        if orphaned_in_db:
            print(f"   Need to review {len(orphaned_in_db)} orphaned database entries")
    
    return {
        'is_synced': is_synced,
        'jsonl_count': len(jsonl_ids),
        'db_count': len(db_ids),
        'missing_in_db': list(missing_in_db),
        'orphaned_in_db': list(orphaned_in_db),
        'common_count': len(common_sessions),
        'timestamp_issues': timestamp_issues
    }


def show_project_breakdown(jsonl_sessions):
    """Show breakdown by project"""
    
    projects = defaultdict(list)
    for session_id, info in jsonl_sessions.items():
        projects[info['project']].append(session_id)
    
    print(f"\n📁 Project Breakdown:")
    for project, sessions in sorted(projects.items()):
        total_messages = sum(jsonl_sessions[sid]['message_count'] for sid in sessions)
        total_size = sum(jsonl_sessions[sid]['size'] for sid in sessions)
        print(f"   {project}: {len(sessions)} sessions, {total_messages} messages, {total_size/1024:.1f}KB")


def main():
    """Main sync check"""
    
    print("🔍 Simple Sync Parity Check")
    print("=" * 50)
    
    # Step 1: Find JSONL sessions
    print("📊 Scanning JSONL files...")
    jsonl_sessions = find_jsonl_sessions()
    
    if not jsonl_sessions:
        print("❌ No JSONL sessions found. Cannot proceed.")
        return False
    
    # Step 2: Find database sessions
    print("\n🗄️  Scanning database...")
    db_sessions = find_database_sessions()
    
    # Step 3: Compare
    print("\n🔄 Comparing sync state...")
    result = compare_sync_state(jsonl_sessions, db_sessions)
    
    # Step 4: Project breakdown
    show_project_breakdown(jsonl_sessions)
    
    # Summary
    print(f"\n📋 Final Summary:")
    print(f"   Sync Status: {'✅ Perfect' if result['is_synced'] else '⚠️  Issues Found'}")
    print(f"   JSONL Files: {result['jsonl_count']}")
    print(f"   Database Entries: {result['db_count']}")
    
    if not result['is_synced']:
        print(f"\n💡 Next Steps:")
        if result['missing_in_db']:
            print(f"   • {len(result['missing_in_db'])} sessions need to be added to database")
            print(f"   • Run the sync service to import these sessions")
        if result['orphaned_in_db']:
            print(f"   • {len(result['orphaned_in_db'])} orphaned database entries need review")
    
    return result['is_synced']


if __name__ == "__main__":
    try:
        success = main()
        print(f"\n{'🎉 Sync check completed successfully!' if success else '⚙️  Sync issues detected - see details above'}")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n💥 Error during sync check: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)