#!/usr/bin/env python3
"""
Claude Code to Elia Database Sync Service

Syncs Claude Code sessions from ~/.claude/__store.db into Elia's database
at ~/.local/share/elia/elia.sqlite for unified session history.
"""

import sqlite3
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

@dataclass
class ClaudeSession:
    session_id: str
    project_path: str
    project_name: str
    first_message_time: datetime
    last_message_time: datetime
    message_count: int
    total_cost: float
    summary: Optional[str] = None

class ClaudeEliaSync:
    def __init__(self):
        self.claude_db_path = Path.home() / ".claude" / "__store.db"
        self.elia_db_path = Path.home() / ".local/share/elia/elia.sqlite"
        
    def get_claude_sessions(self) -> List[ClaudeSession]:
        """Extract session metadata from Claude Code database"""
        sessions = []
        
        if not self.claude_db_path.exists():
            print(f"Claude database not found at {self.claude_db_path}")
            return sessions
            
        conn = sqlite3.connect(str(self.claude_db_path))
        cursor = conn.cursor()
        
        # Get session summary with aggregated metadata
        query = """
        SELECT 
            bm.session_id,
            bm.cwd,
            COUNT(*) as message_count,
            MIN(bm.timestamp) as first_timestamp,
            MAX(bm.timestamp) as last_timestamp,
            COALESCE(SUM(am.cost_usd), 0) as total_cost
        FROM base_messages bm
        LEFT JOIN assistant_messages am ON bm.uuid = am.uuid
        GROUP BY bm.session_id, bm.cwd
        ORDER BY MAX(bm.timestamp) DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        for row in rows:
            session_id, cwd, msg_count, first_ts, last_ts, cost = row
            
            # Convert Unix timestamps to datetime
            first_time = datetime.fromtimestamp(first_ts, tz=timezone.utc)
            last_time = datetime.fromtimestamp(last_ts, tz=timezone.utc)
            
            # Extract project name from path
            project_name = Path(cwd).name if cwd else "Unknown"
            
            # Get session summary if available - summaries are keyed by leaf_uuid, not session_id
            summary = None
            try:
                # Get the most recent message uuid for this session to find summary
                cursor.execute("""
                    SELECT bm2.uuid FROM base_messages bm2 
                    WHERE bm2.session_id = ? 
                    ORDER BY bm2.timestamp DESC LIMIT 1
                """, (session_id,))
                latest_msg = cursor.fetchone()
                if latest_msg:
                    cursor.execute("SELECT summary FROM conversation_summaries WHERE leaf_uuid = ?", (latest_msg[0],))
                    summary_row = cursor.fetchone()
                    summary = summary_row[0] if summary_row else None
            except sqlite3.Error:
                pass  # No summaries available
            
            sessions.append(ClaudeSession(
                session_id=session_id,
                project_path=cwd,
                project_name=project_name,
                first_message_time=first_time,
                last_message_time=last_time,
                message_count=msg_count,
                total_cost=cost,
                summary=summary
            ))
        
        conn.close()
        return sessions
    
    def sync_to_elia(self) -> Dict[str, int]:
        """Sync Claude sessions to Elia database"""
        results = {"imported": 0, "updated": 0, "skipped": 0}
        
        if not self.elia_db_path.exists():
            print(f"Elia database not found at {self.elia_db_path}")
            return results
            
        claude_sessions = self.get_claude_sessions()
        
        conn = sqlite3.connect(str(self.elia_db_path))
        cursor = conn.cursor()
        
        # First, extend Elia schema if needed
        self._ensure_elia_schema(cursor)
        
        for session in claude_sessions:
            # Check if session already exists
            cursor.execute(
                "SELECT id FROM chat WHERE model LIKE ? AND title LIKE ?",
                (f"claude-code:{session.session_id}%", f"%{session.project_name}%")
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing session
                chat_id = existing[0]
                cursor.execute("""
                    UPDATE chat SET 
                        title = ?,
                        started_at = ?,
                        archived = FALSE
                    WHERE id = ?
                """, (
                    self._generate_session_title(session),
                    session.first_message_time.isoformat(),
                    chat_id
                ))
                results["updated"] += 1
                
            else:
                # Create new session entry
                cursor.execute("""
                    INSERT INTO chat (model, title, started_at, archived)
                    VALUES (?, ?, ?, FALSE)
                """, (
                    f"claude-code:{session.session_id}",
                    self._generate_session_title(session),
                    session.first_message_time.isoformat()
                ))
                
                chat_id = cursor.lastrowid
                
                # Add summary message if available
                if session.summary:
                    cursor.execute("""
                        INSERT INTO message (chat_id, role, content, timestamp, meta)
                        VALUES (?, 'assistant', ?, ?, ?)
                    """, (
                        chat_id,
                        f"📝 Session Summary: {session.summary}",
                        session.last_message_time.isoformat(),
                        json.dumps({
                            "type": "session_summary",
                            "project_path": session.project_path,
                            "message_count": session.message_count,
                            "total_cost": session.total_cost
                        })
                    ))
                
                results["imported"] += 1
        
        conn.commit()
        conn.close()
        
        return results
    
    def _ensure_elia_schema(self, cursor):
        """Ensure Elia database can handle Claude Code sessions"""
        try:
            # Check if meta column exists in message table
            cursor.execute("PRAGMA table_info(message)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'meta' not in columns:
                cursor.execute("ALTER TABLE message ADD COLUMN meta TEXT DEFAULT '{}'")
                
        except sqlite3.Error as e:
            print(f"Schema extension warning: {e}")
    
    def _generate_session_title(self, session: ClaudeSession) -> str:
        """Generate readable title for Claude Code session"""
        if session.summary:
            # Use first 50 chars of summary
            title = session.summary[:50]
            if len(session.summary) > 50:
                title += "..."
            return f"🔧 {title}"
        else:
            return f"🔧 {session.project_name} ({session.message_count} messages)"

class ClaudeDatabaseWatcher(FileSystemEventHandler):
    """Watch Claude Code database for changes"""
    
    def __init__(self, sync_service: ClaudeEliaSync):
        self.sync_service = sync_service
        self.last_sync = 0
        self.sync_cooldown = 5  # seconds
    
    def on_modified(self, event):
        if event.is_directory:
            return
            
        if event.src_path.endswith("__store.db"):
            current_time = time.time()
            if current_time - self.last_sync > self.sync_cooldown:
                print(f"Claude database changed, syncing...")
                results = self.sync_service.sync_to_elia()
                print(f"Sync results: {results}")
                self.last_sync = current_time

def main():
    """Main sync service entry point"""
    sync_service = ClaudeEliaSync()
    
    # Initial sync
    print("Performing initial sync...")
    results = sync_service.sync_to_elia()
    print(f"Initial sync completed: {results}")
    
    # Setup file watcher
    event_handler = ClaudeDatabaseWatcher(sync_service)
    observer = Observer()
    
    claude_dir = Path.home() / ".claude"
    if claude_dir.exists():
        observer.schedule(event_handler, str(claude_dir), recursive=False)
        observer.start()
        print(f"Watching Claude database at {claude_dir}")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            print("Stopping sync service...")
        
        observer.join()
    else:
        print(f"Claude directory not found at {claude_dir}")

if __name__ == "__main__":
    main()