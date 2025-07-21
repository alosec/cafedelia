#!/usr/bin/env python3
"""
Quick Sync Repair

Simple tool to repair sync issues by directly importing JSONL sessions.
Uses minimal dependencies and direct database operations.
"""

import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from simple_sync_check import find_jsonl_sessions, find_database_sessions, compare_sync_state


def extract_first_message_from_jsonl(jsonl_path):
    """Extract the first user message from JSONL file for title generation"""
    
    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Look for user messages
                    if data.get('type') == 'user' and data.get('message', {}).get('content'):
                        content = data['message']['content']
                        
                        # Handle structured content (list of objects with text)
                        if isinstance(content, list):
                            # Extract text from structured content objects
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item:
                                    text_parts.append(item['text'])
                                elif isinstance(item, str):
                                    text_parts.append(item)
                            
                            if text_parts:
                                content = ' '.join(text_parts)
                            else:
                                # If no text found in structured content, continue to next line
                                continue
                        
                        # Handle simple string content
                        elif isinstance(content, str):
                            pass  # content is already a string
                        else:
                            # Skip non-string, non-list content
                            continue
                        
                        # Truncate to reasonable title length
                        if len(content) > 80:
                            return content[:80] + "..."
                        return content
                        
                except json.JSONDecodeError:
                    continue
        
        # Fallback title
        return f"Session from {jsonl_path.parent.name}"
        
    except Exception as e:
        print(f"   Warning: Could not extract title from {jsonl_path}: {e}")
        return f"Session {jsonl_path.stem[:8]}"


def import_session_to_database(session_id, jsonl_info):
    """Import a single JSONL session directly to the database"""
    
    db_path = Path.home() / ".local" / "share" / "cafedelia" / "cafedelia.sqlite"
    
    try:
        # Extract title from JSONL
        jsonl_path = Path(jsonl_info['path'])
        title = extract_first_message_from_jsonl(jsonl_path)
        
        # Connect to database
        conn = sqlite3.connect(str(db_path))
        
        # Insert chat record
        cursor = conn.execute("""
            INSERT INTO chat (model, title, started_at, archived, session_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "claude-code-session",  # model
            title,                  # title
            datetime.now().isoformat(),  # started_at
            False,                  # archived
            session_id             # session_id
        ))
        
        conn.commit()
        conn.close()
        
        print(f"      ✅ Imported: {title[:50]}...")
        return True
        
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            print(f"      ⚠️  Session {session_id} already exists, skipping")
            return True
        else:
            print(f"      ❌ Integrity error for {session_id}: {e}")
            return False
    except Exception as e:
        print(f"      💥 Error importing {session_id}: {e}")
        return False


def repair_missing_sessions(missing_session_ids, jsonl_sessions):
    """Repair missing sessions by direct database import"""
    
    print(f"🔧 Starting repair of {len(missing_session_ids)} missing sessions...")
    
    success_count = 0
    error_count = 0
    
    for i, session_id in enumerate(missing_session_ids, 1):
        print(f"   [{i}/{len(missing_session_ids)}] {session_id[:8]}...")
        
        jsonl_info = jsonl_sessions[session_id]
        
        if import_session_to_database(session_id, jsonl_info):
            success_count += 1
        else:
            error_count += 1
        
        # Progress update every 20 sessions
        if i % 20 == 0:
            print(f"   Progress: {i}/{len(missing_session_ids)} ({success_count} success, {error_count} errors)")
    
    print(f"\n📊 Import Summary:")
    print(f"   Total Processed: {len(missing_session_ids)}")
    print(f"   Successful: {success_count}")
    print(f"   Errors: {error_count}")
    print(f"   Success Rate: {success_count/len(missing_session_ids)*100:.1f}%")
    
    return success_count, error_count


def verify_repair():
    """Verify that repair was successful"""
    
    print(f"\n🔍 Verifying repair...")
    
    # Re-run sync check
    jsonl_sessions = find_jsonl_sessions()
    db_sessions = find_database_sessions()
    result = compare_sync_state(jsonl_sessions, db_sessions)
    
    if result['is_synced']:
        print(f"✅ Repair verification passed! All sessions now synchronized.")
    else:
        print(f"⚠️  Repair status:")
        print(f"   Sync Rate: {result['common_count']/result['jsonl_count']*100:.1f}%")
        print(f"   Missing in DB: {len(result['missing_in_db'])}")
        print(f"   Orphaned in DB: {len(result['orphaned_in_db'])}")
    
    return result['is_synced']


def main():
    """Main repair function"""
    
    print("🔧 Quick Cafedelia Sync Repair")
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
    
    # Step 2: Show repair plan
    missing_count = len(result['missing_in_db'])
    current_sync_rate = result['common_count'] / result['jsonl_count'] * 100
    
    print(f"\n🔧 Current State:")
    print(f"   Sync Rate: {current_sync_rate:.1f}%")
    print(f"   JSONL Sessions: {result['jsonl_count']}")
    print(f"   Database Sessions: {result['db_count']}")
    print(f"   Missing in DB: {missing_count}")
    
    if missing_count == 0:
        print("✅ All sessions are already synchronized!")
        return True
    
    # Step 3: Ask for confirmation (unless auto mode)
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        proceed = True
    else:
        response = input(f"\n🤔 Import {missing_count} missing sessions? [Y/n]: ").strip().lower()
        proceed = response in ('', 'y', 'yes')
    
    if not proceed:
        print("❌ Repair cancelled by user.")
        return False
    
    # Step 4: Perform repair
    success_count, error_count = repair_missing_sessions(
        result['missing_in_db'], jsonl_sessions
    )
    
    # Step 5: Verify repair
    repair_successful = verify_repair()
    
    if repair_successful:
        print(f"\n🎉 Sync repair completed successfully!")
        print(f"   Database now contains all {len(jsonl_sessions)} JSONL sessions")
    else:
        improvement = success_count / missing_count * 100 if missing_count > 0 else 0
        print(f"\n📈 Sync repair improved database:")
        print(f"   Imported: {success_count}/{missing_count} sessions ({improvement:.1f}%)")
        if error_count > 0:
            print(f"   ⚠️  {error_count} sessions failed to import")
    
    return error_count == 0


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n🛑 Repair cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error during repair: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)