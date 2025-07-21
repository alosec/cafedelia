"""
Stream coordination for atomic message processing pipeline.

Orchestrates the flow: Claude Code JSON → parsing → truncation → database registration,
ensuring immediate persistence with proper error handling and coordination.
"""

import logging
import asyncio
from typing import Optional, AsyncGenerator, Dict, Any, Callable
from dataclasses import dataclass

from .message_parser import MessageParser, ParsedMessage
from .content_truncator import ContentTruncator, content_truncator
from .database_registrar import DatabaseRegistrar, database_registrar
from .display_grouper import DisplayGrouper, display_grouper, DisplayGroup
from elia_chat.database.models import MessageDao

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """Event emitted by stream coordinator."""
    event_type: str  # 'message_registered', 'display_group_ready', 'error', 'stream_complete'
    data: Any
    session_id: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class StreamCoordinator:
    """Orchestrates atomic message processing pipeline."""
    
    def __init__(self):
        self.message_parser = MessageParser()
        self.content_truncator = content_truncator
        self.database_registrar = database_registrar
        self.display_grouper = display_grouper
        
        # Event handlers
        self.event_handlers: Dict[str, list[Callable]] = {
            'message_registered': [],
            'display_group_ready': [],
            'error': [],
            'stream_complete': []
        }
        
        # Coordination state
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.coordination_lock = asyncio.Lock()
    
    def add_event_handler(self, event_type: str, handler: Callable[[StreamEvent], None]):
        """Add an event handler for stream events."""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].append(handler)
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    def remove_event_handler(self, event_type: str, handler: Callable[[StreamEvent], None]):
        """Remove an event handler."""
        if event_type in self.event_handlers and handler in self.event_handlers[event_type]:
            self.event_handlers[event_type].remove(handler)
    
    async def process_stream_json(self, raw_json_str: str, session_id: str) -> Optional[StreamEvent]:
        """
        Process a single JSON message from Claude Code stream.
        
        Args:
            raw_json_str: Raw JSON string from Claude Code
            session_id: Session ID for coordination
            
        Returns:
            StreamEvent if processing succeeds, None if fails
        """
        async with self.coordination_lock:
            try:
                # Ensure session is tracked
                if session_id not in self.active_sessions:
                    self.active_sessions[session_id] = {
                        'message_count': 0,
                        'last_message_time': None,
                        'display_grouper': DisplayGrouper()
                    }
                
                session_info = self.active_sessions[session_id]
                session_display_grouper = session_info['display_grouper']
                
                # Step 1: Parse the raw JSON with session ID override
                parsed_message = self.message_parser.parse_claude_message(raw_json_str, session_id)
                if not parsed_message:
                    error_event = StreamEvent(
                        event_type='error',
                        data={'error': 'Failed to parse JSON message', 'raw_json': raw_json_str[:200]},
                        session_id=session_id
                    )
                    await self._emit_event(error_event)
                    return error_event
                
                # Step 2: Apply content truncation
                truncated_message = self.content_truncator.truncate_message(parsed_message)
                
                # Step 3: Register in database atomically
                message_dao = await self.database_registrar.register_message(truncated_message)
                if not message_dao:
                    error_event = StreamEvent(
                        event_type='error',
                        data={'error': 'Failed to register message in database', 'parsed_message': str(truncated_message)},
                        session_id=session_id
                    )
                    await self._emit_event(error_event)
                    return error_event
                
                # Update session info
                session_info['message_count'] += 1
                session_info['last_message_time'] = truncated_message.timestamp
                
                # Emit message registered event
                registered_event = StreamEvent(
                    event_type='message_registered',
                    data=message_dao,
                    session_id=session_id,
                    metadata={
                        'original_length': truncated_message.message_metadata.get('original_length'),
                        'truncated': truncated_message.message_metadata.get('truncation_applied', False),
                        'is_sidechain': truncated_message.is_sidechain,
                        'message_source': truncated_message.message_source
                    }
                )
                await self._emit_event(registered_event)
                
                # Step 4: Check for display group formation
                display_group = session_display_grouper.add_message(message_dao)
                if display_group:
                    group_event = StreamEvent(
                        event_type='display_group_ready',
                        data=display_group,
                        session_id=session_id,
                        metadata={
                            'group_message_count': display_group.get_message_count(),
                            'group_content_length': display_group.get_total_length()
                        }
                    )
                    await self._emit_event(group_event)
                    return group_event
                
                return registered_event
                
            except Exception as e:
                logger.error(f"Stream coordination error for session {session_id}: {e}")
                error_event = StreamEvent(
                    event_type='error',
                    data={'error': str(e), 'exception_type': type(e).__name__},
                    session_id=session_id
                )
                await self._emit_event(error_event)
                return error_event
    
    async def complete_stream(self, session_id: str) -> Optional[StreamEvent]:
        """
        Signal stream completion and finalize any pending display groups.
        
        Args:
            session_id: Session ID to complete
            
        Returns:
            StreamEvent for stream completion
        """
        async with self.coordination_lock:
            try:
                if session_id in self.active_sessions:
                    session_info = self.active_sessions[session_id]
                    session_display_grouper = session_info['display_grouper']
                    
                    # Force complete any pending display group
                    final_group = session_display_grouper.force_complete_group()
                    if final_group:
                        group_event = StreamEvent(
                            event_type='display_group_ready',
                            data=final_group,
                            session_id=session_id,
                            metadata={'final_group': True}
                        )
                        await self._emit_event(group_event)
                    
                    # Create completion event
                    completion_event = StreamEvent(
                        event_type='stream_complete',
                        data={
                            'total_messages': session_info['message_count'],
                            'session_duration': None,  # Could calculate from timestamps
                            'final_group_created': final_group is not None
                        },
                        session_id=session_id
                    )
                    
                    # Clean up session
                    del self.active_sessions[session_id]
                    
                    await self._emit_event(completion_event)
                    return completion_event
                
                else:
                    logger.warning(f"Attempted to complete unknown session: {session_id}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error completing stream for session {session_id}: {e}")
                error_event = StreamEvent(
                    event_type='error',
                    data={'error': f"Stream completion failed: {str(e)}"},
                    session_id=session_id
                )
                await self._emit_event(error_event)
                return error_event
    
    async def _emit_event(self, event: StreamEvent):
        """Emit an event to all registered handlers."""
        handlers = self.event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event.event_type}: {e}")
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about an active session."""
        return self.active_sessions.get(session_id)
    
    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs."""
        return list(self.active_sessions.keys())
    
    def get_coordination_stats(self) -> Dict[str, Any]:
        """Get coordination statistics."""
        total_messages = sum(
            session_info['message_count'] 
            for session_info in self.active_sessions.values()
        )
        
        return {
            'active_sessions': len(self.active_sessions),
            'total_active_messages': total_messages,
            'truncation_stats': self.content_truncator.get_truncation_stats(),
            'event_handler_counts': {
                event_type: len(handlers) 
                for event_type, handlers in self.event_handlers.items()
            }
        }
    
    def reset_session(self, session_id: str):
        """Reset a specific session (useful for testing or error recovery)."""
        if session_id in self.active_sessions:
            session_info = self.active_sessions[session_id]
            session_info['display_grouper'].reset()
            session_info['message_count'] = 0
            session_info['last_message_time'] = None
            logger.info(f"Reset coordination state for session {session_id}")
    
    def reset_all(self):
        """Reset all coordination state."""
        self.active_sessions.clear()
        self.display_grouper.reset()
        self.content_truncator.reset_stats()
        self.database_registrar.clear_cache()
        logger.info("Reset all stream coordination state")


# Global instance for use across the application
stream_coordinator = StreamCoordinator()