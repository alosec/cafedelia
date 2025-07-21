"""
Streaming message grouper for live chat UX parity.

Groups streaming Claude Code responses into coherent conversation blocks that match
the sophisticated message grouping used in historical chat viewing.
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .claude_process import ClaudeCodeResponse
from .content_extractor import ContentExtractor

logger = logging.getLogger(__name__)


class MessageGroupState(Enum):
    """State tracking for message group building."""
    WAITING_FOR_ASSISTANT = "waiting_for_assistant"
    COLLECTING_ASSISTANT = "collecting_assistant" 
    WAITING_FOR_TOOLS = "waiting_for_tools"
    COLLECTING_TOOLS = "collecting_tools"
    GROUP_COMPLETE = "group_complete"


@dataclass
class GroupedMessage:
    """A complete message group ready for UI display."""
    content: str
    message_type: str
    metadata: Dict[str, Any]
    is_complete: bool = True


class StreamingMessageGrouper:
    """
    Groups streaming Claude Code responses into coherent conversation blocks.
    
    Achieves UX parity between live chat and historical chat by applying the same
    sophisticated message grouping logic used in JSONL processing.
    """
    
    def __init__(self):
        self.current_group: List[ClaudeCodeResponse] = []
        self.state = MessageGroupState.WAITING_FOR_ASSISTANT
        self.assistant_content_buffer = ""
        self.tool_results_buffer: List[str] = []
        
    def add_response(self, response: ClaudeCodeResponse) -> Optional[GroupedMessage]:
        """
        Add a streaming response and return a complete grouped message if ready.
        
        Returns None if the group is still being built, or a GroupedMessage when
        a complete conversation unit is ready for display.
        """
        logger.debug(f"Adding response: {response.message_type} - {response.content[:50]}...")
        
        if response.message_type == "system":
            # System messages pass through immediately
            return GroupedMessage(
                content=response.content,
                message_type="system", 
                metadata=response.metadata
            )
        
        elif response.message_type == "assistant":
            return self._handle_assistant_response(response)
            
        elif response.message_type == "user":
            return self._handle_user_response(response)
            
        elif response.message_type == "result":
            return self._handle_result_response(response)
        
        return None
    
    def _handle_assistant_response(self, response: ClaudeCodeResponse) -> Optional[GroupedMessage]:
        """Handle assistant message responses with tool call awareness."""
        if self.state == MessageGroupState.WAITING_FOR_ASSISTANT:
            # Start new assistant group
            self.state = MessageGroupState.COLLECTING_ASSISTANT
            self.assistant_content_buffer = response.content
            self.current_group = [response]
            
        elif self.state == MessageGroupState.COLLECTING_ASSISTANT:
            # Continue building assistant content
            self.assistant_content_buffer += response.content
            self.current_group.append(response)
            
        else:
            # Assistant response after tools - complete the previous group and start new one
            completed_group = self._finalize_current_group()
            self._start_new_assistant_group(response)
            return completed_group
        
        return None
    
    def _handle_user_response(self, response: ClaudeCodeResponse) -> Optional[GroupedMessage]:
        """Handle user responses (typically tool results)."""
        if self.state in [MessageGroupState.COLLECTING_ASSISTANT, MessageGroupState.WAITING_FOR_TOOLS]:
            # Tool result following assistant message
            self.state = MessageGroupState.COLLECTING_TOOLS
            self.tool_results_buffer.append(response.content)
            self.current_group.append(response)
            
        else:
            # Standalone user message
            return GroupedMessage(
                content=response.content,
                message_type="user",
                metadata=response.metadata
            )
        
        return None
    
    def _handle_result_response(self, response: ClaudeCodeResponse) -> Optional[GroupedMessage]:
        """Handle result responses (completion signals)."""
        if response.is_complete and self.current_group:
            # Complete the current group
            completed_group = self._finalize_current_group()
            self.state = MessageGroupState.WAITING_FOR_ASSISTANT
            return completed_group
        
        return None
    
    def _start_new_assistant_group(self, response: ClaudeCodeResponse):
        """Start a new assistant message group."""
        self.state = MessageGroupState.COLLECTING_ASSISTANT
        self.assistant_content_buffer = response.content
        self.tool_results_buffer = []
        self.current_group = [response]
    
    def _finalize_current_group(self) -> Optional[GroupedMessage]:
        """Convert the current group into a formatted GroupedMessage."""
        if not self.current_group:
            return None
        
        try:
            # Use ContentExtractor to format the group content
            formatted_content = self._format_group_content()
            
            # Create metadata from the group
            metadata = self._extract_group_metadata()
            
            # Reset state for next group
            self.current_group = []
            self.assistant_content_buffer = ""
            self.tool_results_buffer = []
            self.state = MessageGroupState.WAITING_FOR_ASSISTANT
            
            return GroupedMessage(
                content=formatted_content,
                message_type="assistant",
                metadata=metadata,
                is_complete=True
            )
            
        except Exception as e:
            logger.error(f"Error finalizing message group: {e}")
            return None
    
    def _format_group_content(self) -> str:
        """Format the grouped content using ContentExtractor logic."""
        if not self.current_group:
            return ""
        
        # Build content structure for ContentExtractor using raw message data
        combined_content = []
        
        # Find assistant responses with raw message data for tool calls
        for response in self.current_group:
            if response.message_type == "assistant" and response.raw_message_data:
                # Use ContentExtractor with raw data for rich tool formatting
                formatted = ContentExtractor.extract_message_content({
                    'type': 'assistant',
                    **response.raw_message_data
                })
                if formatted:
                    combined_content.append(formatted)
            elif response.message_type == "user" and response.raw_message_data:
                # Handle tool results
                formatted = ContentExtractor.extract_message_content({
                    'type': 'user', 
                    **response.raw_message_data
                })
                if formatted:
                    combined_content.append(formatted)
            else:
                # Fallback to pre-processed content
                if response.content.strip():
                    combined_content.append(response.content.strip())
        
        return "\n\n".join(combined_content) if combined_content else ""
    
    def _extract_group_metadata(self) -> Dict[str, Any]:
        """Extract metadata from the message group."""
        metadata = {}
        
        if self.current_group:
            # Use metadata from the first response as base
            metadata.update(self.current_group[0].metadata)
            
            # Add group-specific metadata
            metadata["message_count"] = len(self.current_group)
            metadata["has_tool_results"] = len(self.tool_results_buffer) > 0
            metadata["content_length"] = len(self.assistant_content_buffer)
        
        return metadata
    
    def force_complete_group(self) -> Optional[GroupedMessage]:
        """Force completion of current group (useful for cleanup)."""
        if self.current_group:
            return self._finalize_current_group()
        return None
    
    def reset(self):
        """Reset the grouper state."""
        self.current_group = []
        self.state = MessageGroupState.WAITING_FOR_ASSISTANT
        self.assistant_content_buffer = ""
        self.tool_results_buffer = []
        logger.debug("Streaming message grouper reset")


# Global instance for use across the application
streaming_grouper = StreamingMessageGrouper()