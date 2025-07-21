#!/usr/bin/env python3
"""Simple test of Claude → Elia sync"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

def test_sync():
    claude_db = Path.home() / ".claude" / "__store.db"
    elia_db = Path.home() / ".local/share/elia/elia.sqlite"
    
    print(f"Claude DB: {claude_db} (exists: {claude_db.exists()})")
    print(f"Elia DB: {elia_db} (exists: {elia_db.exists()})")
    
    if not claude_db.exists():
        print("Claude database not found!")
        return
        
    # Get sessions from Claude
    conn = sqlite3.connect(str(claude_db))
    cursor = conn.cursor()
    
    # Simple query to get sessions
    cursor.execute("""
        SELECT 
            session_id,
            cwd,
            COUNT(*) as msg_count,
            MIN(timestamp) as first_ts,
            MAX(timestamp) as last_ts
        FROM base_messages 
        GROUP BY session_id, cwd
        ORDER BY MAX(timestamp) DESC
        LIMIT 5
    """)
    
    sessions = cursor.fetchall()
    conn.close()
    
    print(f"\nFound {len(sessions)} sessions in Claude DB:")
    for session in sessions:
        session_id, cwd, count, first_ts, last_ts = session
        first_time = datetime.fromtimestamp(first_ts, tz=timezone.utc)
        last_time = datetime.fromtimestamp(last_ts, tz=timezone.utc)
        project_name = Path(cwd).name if cwd else "Unknown"
        
        print(f"  {session_id[:8]}... | {project_name} | {count} msgs | {last_time.strftime('%Y-%m-%d %H:%M')}")
    
    # Test Elia database connection
    if elia_db.exists():
        conn = sqlite3.connect(str(elia_db))
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM chat")
        chat_count = cursor.fetchone()[0]
        print(f"\nElia DB has {chat_count} existing chats")
        
        # Check if we can insert a test entry
        try:
            cursor.execute("""
                INSERT INTO chat (model, title, started_at, archived)
                VALUES ('claude-code:test', '🔧 Test Claude Session', ?, FALSE)
            """, (datetime.now().isoformat(),))
            
            test_id = cursor.lastrowid
            print(f"Successfully inserted test chat with ID {test_id}")
            
            # Clean up test entry
            cursor.execute("DELETE FROM chat WHERE id = ?", (test_id,))
            conn.commit()
            print("Test entry cleaned up")
            
        except Exception as e:
            print(f"Error testing Elia DB: {e}")
        finally:
            conn.close()
    
    print("\nSync test completed!")

if __name__ == "__main__":
    test_sync()