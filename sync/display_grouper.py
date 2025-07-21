"""
UI-only message grouping for coherent conversation display.

Provides visual grouping of messages for the chat interface without affecting
database persistence. Separated from persistence logic for clean architecture.
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from elia_chat.database.models import MessageDao
from .content_extractor import ContentExtractor

logger = logging.getLogger(__name__)


class GroupingState(Enum):
    """State tracking for display grouping."""
    WAITING_FOR_CONTENT = "waiting_for_content"
    COLLECTING_ASSISTANT = "collecting_assistant"
    COLLECTING_TOOLS = "collecting_tools"
    GROUP_READY = "group_ready"


@dataclass
class DisplayGroup:
    """A group of messages ready for UI display."""
    primary_content: str
    message_type: str
    metadata: Dict[str, Any]
    source_messages: List[MessageDao]
    group_id: str
    
    def get_total_length(self) -> int:
        """Get total character length of grouped content."""
        return len(self.primary_content)
    
    def get_message_count(self) -> int:
        """Get number of source messages in this group."""
        return len(self.source_messages)


class DisplayGrouper:
    """UI-only message grouping for coherent conversation display."""
    
    def __init__(self):
        self.current_messages: List[MessageDao] = []
        self.state = GroupingState.WAITING_FOR_CONTENT
        self.group_counter = 0
    
    def add_message(self, message: MessageDao) -> Optional[DisplayGroup]:
        """
        Add a message and return a display group if ready.
        
        Args:
            message: Database message to add to current group
            
        Returns:
            DisplayGroup if a complete group is ready, None otherwise
        """
        logger.debug(f"Adding {message.message_type} message to display grouper")
        
        if message.message_type == "system":
            # System messages are always standalone
            return self._create_standalone_group(message)
        
        elif message.message_type == "assistant":
            return self._handle_assistant_message(message)
        
        elif message.message_type == "user":
            return self._handle_user_message(message)
        
        elif message.message_type == "result":
            return self._handle_result_message(message)
        
        return None
    
    def _handle_assistant_message(self, message: MessageDao) -> Optional[DisplayGroup]:
        """Handle assistant message for grouping."""
        if self.state == GroupingState.WAITING_FOR_CONTENT:
            # Start new assistant group
            self.state = GroupingState.COLLECTING_ASSISTANT
            self.current_messages = [message]
            
        elif self.state == GroupingState.COLLECTING_ASSISTANT:
            # Continue building assistant group
            self.current_messages.append(message)
            
        elif self.state in [GroupingState.COLLECTING_TOOLS, GroupingState.GROUP_READY]:
            # Complete previous group and start new one
            completed_group = self._finalize_current_group()
            self._start_new_assistant_group(message)
            return completed_group
        
        return None
    
    def _handle_user_message(self, message: MessageDao) -> Optional[DisplayGroup]:
        """Handle user message for grouping."""
        # Check if this is a tool result  
        is_tool_result = (
            'tool_name' in (message.message_metadata or {}) or 
            'Tool Result' in message.content or
            message.content.startswith('Tool Result')
        )
        
        if is_tool_result and self.state == GroupingState.COLLECTING_ASSISTANT:
            # Tool result following assistant - add to current group
            self.state = GroupingState.COLLECTING_TOOLS
            self.current_messages.append(message)
            
        elif is_tool_result and self.state == GroupingState.COLLECTING_TOOLS:
            # Continue collecting tool results
            self.current_messages.append(message)
            
        else:
            # Standalone user message or not a tool result
            if self.current_messages:
                # Complete any pending group first
                completed_group = self._finalize_current_group()
                # Create standalone group for this user message
                standalone_group = self._create_standalone_group(message)
                # Return the completed group (standalone will be handled next)
                return completed_group
            else:
                # No pending group, create standalone
                return self._create_standalone_group(message)
        
        return None
    
    def _handle_result_message(self, message: MessageDao) -> Optional[DisplayGroup]:
        """Handle result message (completion signals)."""
        if self.current_messages:
            # Complete the current group
            completed_group = self._finalize_current_group()
            return completed_group
        
        # Standalone result message
        return self._create_standalone_group(message)
    
    def _start_new_assistant_group(self, message: MessageDao):
        """Start a new assistant message group."""
        self.state = GroupingState.COLLECTING_ASSISTANT
        self.current_messages = [message]
    
    def _finalize_current_group(self) -> Optional[DisplayGroup]:
        """Convert current messages into a display group."""
        if not self.current_messages:
            return None
        
        try:
            # Generate unique group ID
            self.group_counter += 1
            group_id = f"group_{self.group_counter}"
            
            # Determine primary content and metadata
            primary_content = self._format_group_content(self.current_messages)
            group_metadata = self._extract_group_metadata(self.current_messages)
            
            # Determine group type (use primary message type)
            primary_message = self.current_messages[0]
            group_type = primary_message.message_type
            
            # Create display group
            display_group = DisplayGroup(
                primary_content=primary_content,
                message_type=group_type,
                metadata=group_metadata,
                source_messages=self.current_messages.copy(),
                group_id=group_id
            )
            
            # Reset state
            self.current_messages = []
            self.state = GroupingState.WAITING_FOR_CONTENT
            
            logger.debug(f"Created display group {group_id} with {len(display_group.source_messages)} messages")
            return display_group
            
        except Exception as e:
            logger.error(f"Error finalizing display group: {e}")
            self.current_messages = []
            self.state = GroupingState.WAITING_FOR_CONTENT
            return None
    
    def _create_standalone_group(self, message: MessageDao) -> DisplayGroup:
        """Create a standalone display group for a single message."""
        self.group_counter += 1
        group_id = f"standalone_{self.group_counter}"
        
        return DisplayGroup(
            primary_content=message.content,
            message_type=message.message_type,
            metadata=message.message_metadata.copy() if message.message_metadata else {},
            source_messages=[message],
            group_id=group_id
        )
    
    def _format_group_content(self, messages: List[MessageDao]) -> str:
        """Format multiple messages into coherent display content."""
        if not messages:
            return ""
        
        if len(messages) == 1:
            return messages[0].content
        
        # Use ContentExtractor for rich formatting
        content_parts = []
        
        for message in messages:
            if message.raw_json:
                # Use raw JSON for rich extraction if available
                try:
                    import json
                    raw_data = json.loads(message.raw_json)
                    
                    # Add type field for ContentExtractor
                    if message.message_type == "assistant":
                        extracted = ContentExtractor.extract_message_content({
                            'type': 'assistant',
                            **raw_data.get('message', {})
                        })
                    elif message.message_type == "user":
                        extracted = ContentExtractor.extract_message_content({
                            'type': 'user',
                            **raw_data.get('message', {}),
                            'toolUseResult': raw_data.get('toolUseResult')
                        })
                    else:
                        extracted = message.content
                    
                    if extracted and extracted.strip():
                        content_parts.append(extracted.strip())
                        
                except Exception as e:
                    logger.debug(f"Failed to extract from raw JSON: {e}")
                    if message.content.strip():
                        content_parts.append(message.content.strip())
            else:
                # Fallback to stored content
                if message.content.strip():
                    content_parts.append(message.content.strip())
        
        return "\n\n".join(content_parts) if content_parts else ""
    
    def _extract_group_metadata(self, messages: List[MessageDao]) -> Dict[str, Any]:
        """Extract metadata from a group of messages."""
        if not messages:
            return {}
        
        # Start with primary message metadata
        primary_message = messages[0]
        group_metadata = primary_message.message_metadata.copy() if primary_message.message_metadata else {}
        
        # Add group-specific metadata
        group_metadata.update({
            'message_count': len(messages),
            'has_tool_results': any(
                'tool_name' in (msg.message_metadata or {}) for msg in messages
            ),
            'sidechain_messages': [
                msg.id for msg in messages if msg.is_sidechain
            ],
            'message_sources': list(set(
                msg.message_source for msg in messages if msg.message_source
            )),
            'total_content_length': sum(len(msg.content) for msg in messages),
            'timestamp_range': {
                'start': min(msg.timestamp for msg in messages if msg.timestamp),
                'end': max(msg.timestamp for msg in messages if msg.timestamp)
            } if messages and any(msg.timestamp for msg in messages) else None
        })
        
        return group_metadata
    
    def force_complete_group(self) -> Optional[DisplayGroup]:
        """Force completion of current group (useful for stream end)."""
        if self.current_messages:
            logger.debug(f"Force completing group with {len(self.current_messages)} messages")
            return self._finalize_current_group()
        return None
    
    def reset(self):
        """Reset the grouper state."""
        self.current_messages = []
        self.state = GroupingState.WAITING_FOR_CONTENT
        logger.debug("Display grouper reset")
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current grouper state for debugging."""
        return {
            'state': self.state.value,
            'current_message_count': len(self.current_messages),
            'group_counter': self.group_counter,
            'current_message_types': [msg.message_type for msg in self.current_messages]
        }


# Global instance for use across the application
display_grouper = DisplayGrouper()