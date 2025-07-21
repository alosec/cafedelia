"""
Message expander for fetching complete tool results from JSONL.

This module provides the interface between the UI and JSONL API for
expanding truncated content in the chat interface.
"""

import logging
from typing import Optional, Dict, Any

from .jsonl_api import jsonl_api
from .content_cache import content_cache

logger = logging.getLogger(__name__)


class MessageExpander:
    """Handles expansion of truncated messages and tool results."""
    
    async def expand_tool_result(self, session_id: str, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        Expand a truncated tool result to show full content.
        
        Args:
            session_id: The session ID
            tool_id: The tool use ID
            
        Returns:
            Dict with full content and metadata, or None if not found
        """
        # Check cache first
        cache_key = f"tool:{session_id}:{tool_id}"
        cached = content_cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for tool result: {tool_id}")
            return cached
        
        # Fetch from JSONL
        full_content = await jsonl_api.get_tool_result(session_id, tool_id)
        
        if full_content is None:
            logger.warning(f"Tool result not found: {tool_id}")
            return None
        
        # Prepare response with metadata
        response = {
            "tool_id": tool_id,
            "full_content": full_content,
            "line_count": len(full_content.split('\n')),
            "char_count": len(full_content),
            "truncated": False
        }
        
        # Cache the result
        content_cache.put(cache_key, response)
        
        return response
    
    async def expand_message(self, session_id: str, message_index: int) -> Optional[Dict[str, Any]]:
        """
        Expand a truncated message to show full content.
        
        Args:
            session_id: The session ID
            message_index: The message index in JSONL
            
        Returns:
            Full message data or None if not found
        """
        # Check cache
        cache_key = f"msg:{session_id}:{message_index}"
        cached = content_cache.get(cache_key)
        if cached:
            return cached
        
        # Fetch from JSONL
        full_message = await jsonl_api.get_full_message(session_id, message_index)
        
        if full_message:
            # Cache it
            content_cache.put(cache_key, full_message)
        
        return full_message
    
    async def get_expansion_preview(self, session_id: str, tool_id: str, preview_lines: int = 10) -> Optional[str]:
        """
        Get a preview of expanded content without fetching everything.
        
        Args:
            session_id: The session ID
            tool_id: The tool use ID
            preview_lines: Number of lines to include in preview
            
        Returns:
            Preview text or None
        """
        full_data = await self.expand_tool_result(session_id, tool_id)
        
        if not full_data:
            return None
        
        lines = full_data['full_content'].split('\n')
        
        if len(lines) <= preview_lines:
            return full_data['full_content']
        
        preview = '\n'.join(lines[:preview_lines])
        remaining = len(lines) - preview_lines
        
        return f"{preview}\n\n... {remaining} more lines ..."
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get expander cache statistics."""
        return content_cache.stats()


# Global instance
message_expander = MessageExpander()