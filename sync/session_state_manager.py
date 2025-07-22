"""
Central session state management for JSONL-database-UI consistency.

Ensures JSONL files remain the authoritative source of truth while coordinating
database persistence and UI updates. Provides automatic parity validation and
intelligent handling of Claude Code's multi-message streams.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from elia_chat.database.models import MessageDao, ChatDao

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """Complete state for a Claude Code session."""
    session_id: str
    jsonl_path: Path
    chat_dao: Optional[ChatDao] = None
    
    # Message tracking
    jsonl_message_count: int = 0
    database_message_count: int = 0
    last_jsonl_check: datetime = field(default_factory=datetime.now)
    last_database_sync: datetime = field(default_factory=datetime.now)
    
    # State flags
    is_active: bool = False
    has_parity_issues: bool = False
    is_syncing: bool = False
    
    # Event handlers
    ui_update_callbacks: List[Callable] = field(default_factory=list)
    error_callbacks: List[Callable] = field(default_factory=list)


@dataclass 
class StateEvent:
    """Event emitted by session state manager."""
    event_type: str  # 'message_added', 'parity_issue', 'sync_complete', 'ui_update_required'
    session_id: str
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionStateManager:
    """
    Central coordinator ensuring JSONL-database-UI consistency.
    
    Architecture:
    - JSONL files are the authoritative source of truth
    - Database mirrors JSONL state with validation
    - UI updates driven by validated state changes
    - Automatic parity checking and correction
    """
    
    def __init__(self):
        self.active_sessions: Dict[str, SessionState] = {}
        self.event_handlers: Dict[str, List[Callable]] = {
            'message_added': [],
            'parity_issue': [],
            'sync_complete': [],
            'ui_update_required': [],
            'error': []
        }
        
        # Coordination locks
        self.session_locks: Dict[str, asyncio.Lock] = {}
        self.global_lock = asyncio.Lock()
        
        # State validation
        self.validation_enabled = True
        self.auto_correction_enabled = True
        
        logger.info("SessionStateManager initialized")
    
    async def register_session(self, session_id: str, jsonl_path: Path) -> SessionState:
        """
        Register a Claude Code session for state management.
        
        Args:
            session_id: Unique session identifier
            jsonl_path: Path to the session's JSONL file
            
        Returns:
            SessionState object for tracking
        """
        async with self.global_lock:
            if session_id in self.active_sessions:
                logger.debug(f"Session {session_id} already registered")
                return self.active_sessions[session_id]
            
            # Create session state
            session_state = SessionState(
                session_id=session_id,
                jsonl_path=jsonl_path,
                is_active=True
            )
            
            # Create session-specific lock
            self.session_locks[session_id] = asyncio.Lock()
            
            # Initialize state from existing data
            await self._initialize_session_state(session_state)
            
            self.active_sessions[session_id] = session_state
            logger.info(f"Registered session {session_id} (JSONL: {jsonl_path})")
            
            return session_state
    
    async def _initialize_session_state(self, session_state: SessionState) -> None:
        """Initialize session state from existing JSONL and database data."""
        try:
            # Count JSONL messages
            if session_state.jsonl_path.exists():
                with open(session_state.jsonl_path, 'r') as f:
                    session_state.jsonl_message_count = sum(1 for _ in f)
            
            # Find or create corresponding chat in database
            from elia_chat.database.database import get_session
            from sqlalchemy import select
            
            async with get_session() as db_session:
                result = await db_session.execute(
                    select(ChatDao).where(ChatDao.session_id == session_state.session_id)
                )
                session_state.chat_dao = result.scalar_one_or_none()
                
                if session_state.chat_dao:
                    # Count database messages
                    result = await db_session.execute(
                        select(MessageDao.id).where(MessageDao.chat_id == session_state.chat_dao.id)
                    )
                    session_state.database_message_count = len(result.all())
                
            # Check for parity issues
            if session_state.jsonl_message_count != session_state.database_message_count:
                session_state.has_parity_issues = True
                logger.warning(
                    f"Parity issue detected for session {session_state.session_id}: "
                    f"JSONL={session_state.jsonl_message_count}, "
                    f"DB={session_state.database_message_count}"
                )
                
                await self._emit_event(StateEvent(
                    event_type='parity_issue',
                    session_id=session_state.session_id,
                    data={
                        'jsonl_count': session_state.jsonl_message_count,
                        'database_count': session_state.database_message_count,
                        'difference': session_state.jsonl_message_count - session_state.database_message_count
                    }
                ))
            
            logger.debug(
                f"Session {session_state.session_id} initialized: "
                f"JSONL={session_state.jsonl_message_count}, "
                f"DB={session_state.database_message_count}"
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize session state for {session_state.session_id}: {e}")
            await self._emit_event(StateEvent(
                event_type='error',
                session_id=session_state.session_id,
                data={'error': str(e), 'context': 'session_initialization'}
            ))
    
    async def process_new_message(self, session_id: str, raw_json: str) -> Optional[StateEvent]:
        """
        Process a new message from Claude Code stream.
        
        This is the main entry point for new messages, ensuring they are
        properly validated, persisted, and reflected in the UI.
        """
        if session_id not in self.active_sessions:
            logger.error(f"Attempted to process message for unregistered session: {session_id}")
            logger.error(f"Active sessions: {list(self.active_sessions.keys())}")
            return None
        
        session_state = self.active_sessions[session_id]
        
        async with self.session_locks[session_id]:
            try:
                session_state.is_syncing = True
                
                # Step 1: Parse and validate the message
                from .message_parser import MessageParser
                parser = MessageParser()
                parsed_message = parser.parse_claude_message(raw_json, session_id)
                
                if not parsed_message:
                    logger.error(f"Failed to parse message for session {session_id}")
                    return None
                
                # Step 2: Persist to database with validation
                from .persistence_coordinator import persistence_coordinator
                message_dao = await persistence_coordinator.persist_message(
                    parsed_message, session_state.chat_dao
                )
                
                if not message_dao:
                    logger.error(f"Failed to persist message for session {session_id}")
                    return None
                
                # Step 3: Update session state
                session_state.database_message_count += 1
                session_state.last_database_sync = datetime.now()
                
                # Step 4: Emit simple UI update event for Chatbox mounting
                ui_event = StateEvent(
                    event_type='ui_update_required',
                    session_id=session_id,
                    data={
                        'message_dao': message_dao,
                        'action': 'add_message'
                    },
                    metadata={
                        'message_type': parsed_message.message_type,
                        'is_sidechain': parsed_message.is_sidechain,
                        'content_length': len(parsed_message.content)
                    }
                )
                
                await self._emit_event(ui_event)
                
                logger.debug(f"Processed new message for session {session_id}: {message_dao.id}")
                return ui_event
                
            except Exception as e:
                logger.error(f"Error processing message for session {session_id}: {e}")
                await self._emit_event(StateEvent(
                    event_type='error',
                    session_id=session_id,
                    data={'error': str(e), 'context': 'message_processing'}
                ))
                return None
            finally:
                session_state.is_syncing = False
    
    async def validate_session_parity(self, session_id: str) -> bool:
        """
        Validate that JSONL and database are in sync for a session.
        
        Returns:
            True if in sync, False if parity issues detected
        """
        if session_id not in self.active_sessions:
            return False
        
        session_state = self.active_sessions[session_id]
        
        async with self.session_locks[session_id]:
            try:
                # Recount JSONL messages
                if session_state.jsonl_path.exists():
                    with open(session_state.jsonl_path, 'r') as f:
                        current_jsonl_count = sum(1 for _ in f)
                else:
                    current_jsonl_count = 0
                
                # Recount database messages
                if session_state.chat_dao:
                    from elia_chat.database.database import get_session
                    from sqlalchemy import select
                    
                    async with get_session() as db_session:
                        result = await db_session.execute(
                            select(MessageDao.id).where(MessageDao.chat_id == session_state.chat_dao.id)
                        )
                        current_db_count = len(result.all())
                else:
                    current_db_count = 0
                
                # Update session state
                session_state.jsonl_message_count = current_jsonl_count
                session_state.database_message_count = current_db_count
                session_state.last_jsonl_check = datetime.now()
                
                # Check parity
                in_sync = current_jsonl_count == current_db_count
                session_state.has_parity_issues = not in_sync
                
                if not in_sync:
                    logger.warning(
                        f"Parity validation failed for session {session_id}: "
                        f"JSONL={current_jsonl_count}, DB={current_db_count}"
                    )
                    
                    await self._emit_event(StateEvent(
                        event_type='parity_issue',
                        session_id=session_id,
                        data={
                            'jsonl_count': current_jsonl_count,
                            'database_count': current_db_count,
                            'difference': current_jsonl_count - current_db_count
                        }
                    ))
                
                return in_sync
                
            except Exception as e:
                logger.error(f"Error validating parity for session {session_id}: {e}")
                return False
    
    async def correct_parity_issues(self, session_id: str) -> bool:
        """
        Automatically correct parity issues by syncing database to JSONL state.
        
        Returns:
            True if correction successful, False otherwise
        """
        if not self.auto_correction_enabled:
            logger.info(f"Auto-correction disabled, skipping session {session_id}")
            return False
        
        if session_id not in self.active_sessions:
            return False
        
        session_state = self.active_sessions[session_id]
        
        async with self.session_locks[session_id]:
            try:
                logger.info(f"Starting parity correction for session {session_id}")
                
                # Use parity validator for correction
                from .parity_validator import parity_validator
                success = await parity_validator.correct_session_parity(session_state)
                
                if success:
                    # Revalidate after correction
                    await self.validate_session_parity(session_id)
                    
                    await self._emit_event(StateEvent(
                        event_type='sync_complete',
                        session_id=session_id,
                        data={'correction_applied': True}
                    ))
                    
                    logger.info(f"Parity correction completed for session {session_id}")
                
                return success
                
            except Exception as e:
                logger.error(f"Error correcting parity for session {session_id}: {e}")
                return False
    
    def add_event_handler(self, event_type: str, handler: Callable[[StateEvent], None]):
        """Add an event handler for state events."""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].append(handler)
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    def remove_event_handler(self, event_type: str, handler: Callable[[StateEvent], None]):
        """Remove an event handler."""
        if event_type in self.event_handlers and handler in self.event_handlers[event_type]:
            self.event_handlers[event_type].remove(handler)
    
    async def _emit_event(self, event: StateEvent):
        """Emit a state event to all registered handlers."""
        try:
            for handler in self.event_handlers.get(event.event_type, []):
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
        except Exception as e:
            logger.error(f"Error emitting event {event.event_type}: {e}")
    
    async def deregister_session(self, session_id: str):
        """Deregister a session from state management."""
        async with self.global_lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id].is_active = False
                del self.active_sessions[session_id]
                
                if session_id in self.session_locks:
                    del self.session_locks[session_id]
                
                logger.info(f"Deregistered session {session_id}")
    
    def get_session_state(self, session_id: str) -> Optional[SessionState]:
        """Get the current state for a session."""
        return self.active_sessions.get(session_id)
    
    async def get_all_session_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all active sessions."""
        stats = {}
        for session_id, session_state in self.active_sessions.items():
            stats[session_id] = {
                'jsonl_messages': session_state.jsonl_message_count,
                'database_messages': session_state.database_message_count,
                'has_parity_issues': session_state.has_parity_issues,
                'is_active': session_state.is_active,
                'is_syncing': session_state.is_syncing,
                'last_jsonl_check': session_state.last_jsonl_check.isoformat(),
                'last_database_sync': session_state.last_database_sync.isoformat()
            }
        return stats


# Global instance for use across the application
session_state_manager = SessionStateManager()