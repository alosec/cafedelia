"""
Cafedelia WTE Pipelines

Concrete pipeline implementations for session management and JSONL sync.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, AsyncGenerator, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from .core import WTEBase
from ..jsonl_watcher import JSONLWatcher
from ..database_manager import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class SessionEvent:
    """Event representing a Claude Code session change"""
    session_id: str
    project_path: str
    jsonl_path: Path
    event_type: str  # 'created', 'updated', 'modified'
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class SessionRegistration:
    """Action to register a new session"""
    session_id: str
    project_path: str
    jsonl_path: Path
    metadata: Dict[str, Any]
    

@dataclass
class SyncAction:
    """Action to sync JSONL data to database"""
    session_id: str
    jsonl_path: Path
    last_modified: datetime


class SessionRegistrationPipeline(WTEBase[SessionEvent, SessionRegistration]):
    """Pipeline for registering new Claude Code sessions"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.watcher = JSONLWatcher()
        self.registered_sessions = set()
    
    async def watch(self) -> AsyncGenerator[SessionEvent, None]:
        """Watch for new Claude Code session creation"""
        logger.info("Starting session registration watcher")
        
        async for session in self.watcher.discover_sessions():
            # Only emit events for new sessions
            if session.session_id not in self.registered_sessions:
                yield SessionEvent(
                    session_id=session.session_id,
                    project_path=session.project_path,
                    jsonl_path=Path(session.jsonl_file_path),
                    event_type='created',
                    timestamp=datetime.now(),
                    metadata={
                        'project_name': session.project_name,
                        'conversation_turns': session.conversation_turns,
                        'total_cost': session.total_cost_usd,
                        'created_at': session.created_at,
                        'last_activity': session.last_activity
                    }
                )
                
                self.registered_sessions.add(session.session_id)
    
    def transform(self, event: SessionEvent) -> Optional[SessionRegistration]:
        """Transform session event into registration action"""
        if event.event_type == 'created':
            return SessionRegistration(
                session_id=event.session_id,
                project_path=event.project_path,
                jsonl_path=event.jsonl_path,
                metadata=event.metadata
            )
        return None
    
    async def execute(self, action: SessionRegistration) -> None:
        """Register session in database"""
        try:
            logger.info(f"Registering session: {action.session_id}")
            
            # This would integrate with the database manager
            await self.db_manager.register_session(
                session_id=action.session_id,
                project_path=action.project_path,
                jsonl_path=str(action.jsonl_path),
                metadata=action.metadata
            )
            
            logger.info(f"Successfully registered session: {action.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to register session {action.session_id}: {e}")
            raise


class JSONLSyncPipeline(WTEBase[SessionEvent, SyncAction]):
    """Pipeline for syncing JSONL files to database"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.watcher = JSONLWatcher()
        self.last_sync_times = {}
    
    async def watch(self) -> AsyncGenerator[SessionEvent, None]:
        """Watch for JSONL file changes"""
        logger.info("Starting JSONL sync watcher")
        
        # Initial discovery
        async for session in self.watcher.discover_sessions():
            yield SessionEvent(
                session_id=session.session_id,
                project_path=session.project_path,
                jsonl_path=Path(session.jsonl_file_path),
                event_type='modified',
                timestamp=session.last_activity,
                metadata={'file_size': Path(session.jsonl_file_path).stat().st_size}
            )
        
        # Continuous monitoring (simplified - in real impl would use file watching)
        while True:
            await asyncio.sleep(5)  # Poll every 5 seconds
            
            async for session in self.watcher.discover_sessions():
                jsonl_path = Path(session.jsonl_file_path)
                current_mtime = datetime.fromtimestamp(jsonl_path.stat().st_mtime)
                last_sync = self.last_sync_times.get(session.session_id)
                
                if last_sync is None or current_mtime > last_sync:
                    yield SessionEvent(
                        session_id=session.session_id,
                        project_path=session.project_path,
                        jsonl_path=jsonl_path,
                        event_type='modified',
                        timestamp=current_mtime,
                        metadata={'file_size': jsonl_path.stat().st_size}
                    )
    
    def transform(self, event: SessionEvent) -> Optional[SyncAction]:
        """Transform file change into sync action"""
        if event.event_type == 'modified':
            return SyncAction(
                session_id=event.session_id,
                jsonl_path=event.jsonl_path,
                last_modified=event.timestamp
            )
        return None
    
    async def execute(self, action: SyncAction) -> None:
        """Sync JSONL data to database"""
        try:
            logger.info(f"Syncing session: {action.session_id}")
            
            # This would integrate with existing sync logic
            await self.db_manager.sync_jsonl_to_database(
                session_id=action.session_id,
                jsonl_path=str(action.jsonl_path)
            )
            
            self.last_sync_times[action.session_id] = action.last_modified
            logger.info(f"Successfully synced session: {action.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to sync session {action.session_id}: {e}")
            raise


class LiveChatPipeline(WTEBase[Dict[str, Any], Dict[str, Any]]):
    """Pipeline for handling live Claude Code chat integration"""
    
    def __init__(self):
        self.active_sessions = set()
    
    async def watch(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Watch for live chat events (placeholder)"""
        # This would integrate with claude_process.py streaming
        logger.info("Starting live chat watcher")
        
        # Placeholder - would connect to actual Claude Code CLI streams
        while True:
            await asyncio.sleep(1)
            # yield chat_event when available
    
    def transform(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform chat event"""
        return event  # Pass through for now
    
    async def execute(self, action: Dict[str, Any]) -> None:
        """Execute chat action"""
        # Would update UI, save to JSONL, etc.
        pass