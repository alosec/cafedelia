"""
JSONL file watcher for Claude Code session discovery.

Monitors ~/.claude/projects/ directory for session file changes and
provides real-time session discovery for the "Browse Mode" of Cafedelia.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional
import time
import hashlib

from .deduplication_service import deduplication_service

logger = logging.getLogger(__name__)


@dataclass
class ClaudeSession:
    """Represents a Claude Code session from JSONL files."""
    session_id: str
    project_path: str
    last_updated: float
    message_count: int
    working_directory: str
    git_branch: Optional[str] = None
    model: Optional[str] = None
    total_cost: float = 0.0
    
    @property
    def project_name(self) -> str:
        """Extract readable project name from encoded path."""
        # Decode the project path (it's URL-encoded)
        import urllib.parse
        return urllib.parse.unquote(self.project_path.replace('-', '/'))


@dataclass
class SessionUpdate:
    """Represents a session update event."""
    session: ClaudeSession
    update_type: str  # 'created', 'updated', 'new_messages'
    new_messages: List[dict]


class JSONLWatcher:
    """Watches Claude Code JSONL files for changes."""
    
    def __init__(self, claude_dir: Optional[Path] = None):
        self.claude_dir = claude_dir or Path.home() / ".claude"
        self.projects_dir = self.claude_dir / "projects"
        self.watched_files: Dict[str, float] = {}  # file_path -> last_modified
        self.session_cache: Dict[str, ClaudeSession] = {}
        
    def discover_sessions(self) -> List[ClaudeSession]:
        """Discover all Claude Code sessions from JSONL files."""
        sessions = []
        
        if not self.projects_dir.exists():
            logger.warning(f"Claude projects directory not found: {self.projects_dir}")
            return sessions
        
        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
                
            # Find JSONL session files
            for jsonl_file in project_dir.glob("*.jsonl"):
                try:
                    session = self._parse_session_file(jsonl_file, project_dir.name)
                    if session:
                        sessions.append(session)
                        self.session_cache[session.session_id] = session
                except Exception as e:
                    logger.error(f"Error parsing session file {jsonl_file}: {e}")
        
        return sessions
    
    def _parse_session_file(self, jsonl_file: Path, project_name: str) -> Optional[ClaudeSession]:
        """Parse a single JSONL session file."""
        if not jsonl_file.exists() or jsonl_file.stat().st_size == 0:
            return None
        
        try:
            messages = []
            session_id = None
            working_directory = ""
            git_branch = None
            model = None
            total_cost = 0.0
            
            with jsonl_file.open('r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        messages.append(data)
                        
                        # Extract session metadata
                        if not session_id:
                            session_id = data.get('sessionId')
                        if not working_directory:
                            working_directory = data.get('cwd', '')
                        if not git_branch:
                            git_branch = data.get('gitBranch')
                        if not model and 'model' in data:
                            model = data.get('model')
                        
                        # Sum up costs if available
                        if 'cost' in data:
                            total_cost += float(data.get('cost', 0))
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON in {jsonl_file}: {e}")
                        continue
            
            if not session_id or not messages:
                return None
            
            return ClaudeSession(
                session_id=session_id,
                project_path=project_name,
                last_updated=jsonl_file.stat().st_mtime,
                message_count=len(messages),
                working_directory=working_directory,
                git_branch=git_branch,
                model=model,
                total_cost=total_cost
            )
            
        except Exception as e:
            logger.error(f"Error reading JSONL file {jsonl_file}: {e}")
            return None
    
    async def watch_for_changes(self) -> AsyncGenerator[SessionUpdate, None]:
        """Watch for changes in Claude Code session files."""
        logger.info(f"Starting JSONL watcher for {self.projects_dir}")
        
        # Initial discovery
        initial_sessions = self.discover_sessions()
        for session in initial_sessions:
            yield SessionUpdate(
                session=session,
                update_type='discovered',
                new_messages=[]
            )
        
        # Watch for changes
        while True:
            try:
                current_sessions = self.discover_sessions()
                
                # Check for new or updated sessions with deduplication
                for session in current_sessions:
                    cached_session = self.session_cache.get(session.session_id)
                    
                    # Use deduplication service to check if we should process this session
                    should_process = await deduplication_service.should_sync_session(
                        session.session_id, session.last_updated
                    )
                    
                    if not should_process:
                        continue
                    
                    if not cached_session:
                        # New session
                        yield SessionUpdate(
                            session=session,
                            update_type='created',
                            new_messages=[]
                        )
                    elif session.last_updated > cached_session.last_updated:
                        # Updated session
                        new_messages = self._get_new_messages(session, cached_session)
                        yield SessionUpdate(
                            session=session,
                            update_type='updated',
                            new_messages=new_messages
                        )
                
                # Update cache
                self.session_cache = {s.session_id: s for s in current_sessions}
                
                # Wait before next check
                await asyncio.sleep(2.0)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"Error in JSONL watcher: {e}")
                await asyncio.sleep(5.0)  # Wait longer on error
    
    def _get_new_messages(self, current: ClaudeSession, cached: ClaudeSession) -> List[dict]:
        """Get new messages by comparing message counts."""
        # This is a simplified approach - could be improved by tracking message timestamps
        if current.message_count > cached.message_count:
            # For now, return empty list - in a full implementation,
            # we'd parse the JSONL file and extract only new messages
            return []
        return []
    
    def get_session_messages(self, session_id: str) -> List[dict]:
        """Get all messages for a specific session."""
        session = self.session_cache.get(session_id)
        if not session:
            return []
        
        # Find the JSONL file for this session
        project_dir = self.projects_dir / session.project_path
        jsonl_file = project_dir / f"{session_id}.jsonl"
        if jsonl_file.exists():
            return self._parse_messages_from_file(jsonl_file)
        
        return []
    
    def _parse_messages_from_file(self, jsonl_file: Path) -> List[dict]:
        """Parse all messages from a JSONL file."""
        messages = []
        
        try:
            with jsonl_file.open('r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        messages.append(data)
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error(f"Error reading messages from {jsonl_file}: {e}")
        
        return messages


# Global watcher instance
watcher = JSONLWatcher()