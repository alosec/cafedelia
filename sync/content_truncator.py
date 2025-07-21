"""
Intelligent content truncation for database storage.

Manages content size limits based on message type and tool verbosity,
ensuring database storage remains efficient while preserving essential information.
"""

import logging
from typing import Dict, Any, Tuple
from .message_parser import ParsedMessage

logger = logging.getLogger(__name__)


class ContentTruncator:
    """Intelligent content truncation based on message type and tool characteristics."""
    
    # Content limits for different message types
    DEFAULT_CONTENT_LIMIT = 2000
    SYSTEM_MESSAGE_LIMIT = 500
    TOOL_RESULT_LIMIT = 1000
    ERROR_MESSAGE_LIMIT = 3000  # Errors can be longer for debugging
    
    # Tool-specific limits
    VERBOSE_TOOLS = {
        'LS', 'Grep', 'Glob', 'find', 'tree', 'cat', 'head', 'tail', 
        'Read', 'Bash', 'git', 'npm', 'pip', 'docker'
    }
    VERBOSE_TOOL_LIMIT = 500
    
    # Sidechain message limits
    TASK_AGENT_LIMIT = 1500
    TODO_SYSTEM_LIMIT = 800
    
    def __init__(self):
        self.truncation_stats = {
            'total_processed': 0,
            'total_truncated': 0,
            'bytes_saved': 0
        }
    
    def truncate_message(self, parsed_message: ParsedMessage) -> ParsedMessage:
        """
        Apply intelligent truncation to a parsed message.
        
        Args:
            parsed_message: Message to truncate
            
        Returns:
            ParsedMessage with truncated content and updated metadata
        """
        self.truncation_stats['total_processed'] += 1
        
        original_content = parsed_message.content
        original_length = len(original_content)
        
        # Determine appropriate content limit
        content_limit = self._get_content_limit(parsed_message)
        
        # Apply truncation if needed
        if original_length <= content_limit:
            # No truncation needed
            return parsed_message
        
        # Perform truncation
        truncated_content = self._apply_truncation(original_content, content_limit, parsed_message)
        
        # Update message
        parsed_message.content = truncated_content
        
        # Update metadata
        parsed_message.message_metadata.update({
            'original_length': original_length,
            'truncated_length': len(truncated_content),
            'truncation_applied': True,
            'truncation_reason': self._get_truncation_reason(parsed_message)
        })
        
        # Update stats
        self.truncation_stats['total_truncated'] += 1
        self.truncation_stats['bytes_saved'] += original_length - len(truncated_content)
        
        logger.debug(f"Truncated {parsed_message.message_type} message from {original_length} to {len(truncated_content)} chars")
        
        return parsed_message
    
    def _get_content_limit(self, parsed_message: ParsedMessage) -> int:
        """Determine the appropriate content limit for a message."""
        message_type = parsed_message.message_type
        
        # System messages are typically short
        if message_type == "system":
            return self.SYSTEM_MESSAGE_LIMIT
        
        # Error messages need more space for debugging
        if parsed_message.message_metadata.get('is_error') or 'error' in parsed_message.content.lower():
            return self.ERROR_MESSAGE_LIMIT
        
        # Sidechain messages have specific limits
        if parsed_message.is_sidechain:
            if parsed_message.message_source == "task":
                return self.TASK_AGENT_LIMIT
            elif parsed_message.message_source == "todo":
                return self.TODO_SYSTEM_LIMIT
            else:
                return self.DEFAULT_CONTENT_LIMIT // 2  # Conservative for other sidechain
        
        # Tool results need special handling
        if message_type == "user" and self._is_tool_result(parsed_message):
            tool_name = parsed_message.message_metadata.get('tool_name', '')
            if tool_name in self.VERBOSE_TOOLS:
                return self.VERBOSE_TOOL_LIMIT
            else:
                return self.TOOL_RESULT_LIMIT
        
        # Default limit for assistant and other messages
        return self.DEFAULT_CONTENT_LIMIT
    
    def _is_tool_result(self, parsed_message: ParsedMessage) -> bool:
        """Check if this is a tool result message."""
        return (
            parsed_message.message_type == "user" and 
            ('tool_name' in parsed_message.message_metadata or 'Tool Result' in parsed_message.content)
        )
    
    def _apply_truncation(self, content: str, limit: int, parsed_message: ParsedMessage) -> str:
        """Apply intelligent truncation based on content type."""
        if len(content) <= limit:
            return content
        
        # For tool results, try to preserve structure
        if self._is_tool_result(parsed_message):
            return self._truncate_tool_result(content, limit, parsed_message)
        
        # For structured content (JSON, code, etc.), preserve beginning and end
        if self._is_structured_content(content):
            return self._truncate_structured_content(content, limit)
        
        # For regular text, truncate with ellipsis
        return self._truncate_text_content(content, limit)
    
    def _truncate_tool_result(self, content: str, limit: int, parsed_message: ParsedMessage) -> str:
        """Truncate tool result content intelligently."""
        tool_name = parsed_message.message_metadata.get('tool_name', '')
        
        # For verbose tools, provide summary instead of truncation
        if tool_name in self.VERBOSE_TOOLS:
            lines = content.split('\n')
            char_count = len(content)
            
            # Create summary
            summary = f"[{tool_name} output: {len(lines)} lines, {char_count} chars]"
            
            # Show first few lines and indicate truncation
            remaining_space = limit - len(summary) - 20  # Space for ellipsis
            if remaining_space > 50:
                preview_lines = []
                current_length = 0
                for line in lines:
                    if current_length + len(line) + 1 <= remaining_space:
                        preview_lines.append(line)
                        current_length += len(line) + 1
                    else:
                        break
                
                if preview_lines:
                    preview = '\n'.join(preview_lines)
                    return f"{summary}\n{preview}\n[... output truncated ...]"
            
            return summary
        
        # For other tools, truncate with context preservation
        return self._truncate_text_content(content, limit)
    
    def _is_structured_content(self, content: str) -> bool:
        """Check if content appears to be structured (JSON, code, etc.)."""
        stripped = content.strip()
        return (
            stripped.startswith(('{', '[', '<')) or  # JSON, XML
            stripped.startswith(('```', '~~~')) or  # Code blocks
            '\n    ' in content or  # Indented code
            content.count('\n') > 10  # Multi-line structured content
        )
    
    def _truncate_structured_content(self, content: str, limit: int) -> str:
        """Truncate structured content preserving beginning and end."""
        if len(content) <= limit:
            return content
        
        # Reserve space for truncation indicator
        truncation_marker = "\n[... content truncated ...]\n"
        available_space = limit - len(truncation_marker)
        
        if available_space < 100:
            # Not enough space for meaningful truncation
            return content[:limit-3] + "..."
        
        # Show beginning and end
        beginning_space = available_space * 2 // 3
        ending_space = available_space - beginning_space
        
        beginning = content[:beginning_space].rstrip()
        ending = content[-ending_space:].lstrip()
        
        return f"{beginning}{truncation_marker}{ending}"
    
    def _truncate_text_content(self, content: str, limit: int) -> str:
        """Truncate regular text content with ellipsis."""
        if len(content) <= limit:
            return content
        
        # Try to truncate at word boundary
        truncated = content[:limit-3]
        last_space = truncated.rfind(' ')
        
        if last_space > limit * 0.8:  # If we found a reasonable word boundary
            return content[:last_space] + "..."
        else:
            return content[:limit-3] + "..."
    
    def _get_truncation_reason(self, parsed_message: ParsedMessage) -> str:
        """Get a reason string for why truncation was applied."""
        message_type = parsed_message.message_type
        
        if message_type == "system":
            return "system_message_limit"
        elif parsed_message.is_sidechain:
            return f"sidechain_{parsed_message.message_source}_limit"
        elif self._is_tool_result(parsed_message):
            tool_name = parsed_message.message_metadata.get('tool_name', 'unknown')
            if tool_name in self.VERBOSE_TOOLS:
                return f"verbose_tool_{tool_name}_limit"
            else:
                return "tool_result_limit"
        elif 'error' in parsed_message.content.lower():
            return "error_message_limit"
        else:
            return "default_content_limit"
    
    def get_truncation_stats(self) -> Dict[str, Any]:
        """Get truncation statistics."""
        stats = self.truncation_stats.copy()
        if stats['total_processed'] > 0:
            stats['truncation_rate'] = stats['total_truncated'] / stats['total_processed']
            stats['avg_bytes_saved'] = stats['bytes_saved'] / max(stats['total_truncated'], 1)
        else:
            stats['truncation_rate'] = 0.0
            stats['avg_bytes_saved'] = 0.0
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset truncation statistics."""
        self.truncation_stats = {
            'total_processed': 0,
            'total_truncated': 0,
            'bytes_saved': 0
        }


# Global instance for use across the application
content_truncator = ContentTruncator()