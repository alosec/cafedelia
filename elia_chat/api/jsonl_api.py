"""
JSONL API for on-demand full content retrieval.

This API allows the UI to fetch complete, untruncated content from JSONL files
when users want to expand tool results or see full message content.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from sync.jsonl_watcher import watcher

logger = logging.getLogger(__name__)


class JSONLAPI:
    """API for accessing full content from JSONL files."""
    
    def __init__(self):
        self.claude_dir = Path.home() / ".claude"
        self.projects_dir = self.claude_dir / "projects"
        self._cache = {}  # Simple in-memory cache
    
    async def get_full_message(self, session_id: str, message_index: int) -> Optional[Dict[str, Any]]:
        """
        Get full message content from JSONL file.
        
        Args:
            session_id: The session ID
            message_index: The message index in the JSONL file
            
        Returns:
            Full message data or None if not found
        """
        jsonl_path = watcher.get_session_file_path(session_id)
        if not jsonl_path:
            logger.warning(f"JSONL file not found for session: {session_id}")
            return None
        
        try:
            # Read specific message by index
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for idx, line in enumerate(f):
                    if idx == message_index:
                        return json.loads(line.strip())
            
            logger.warning(f"Message index {message_index} not found in session {session_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error reading message from JSONL: {e}")
            return None
    
    async def get_tool_result(self, session_id: str, tool_id: str) -> Optional[str]:
        """
        Get full tool result content by tool ID.
        
        Args:
            session_id: The session ID
            tool_id: The tool use ID (e.g., 'toolu_01...')
            
        Returns:
            Full tool result content or None if not found
        """
        cache_key = f"{session_id}:{tool_id}"
        
        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        jsonl_path = watcher.get_session_file_path(session_id)
        if not jsonl_path:
            return None
        
        try:
            # Search for tool result in JSONL
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line.strip())
                    
                    # Check if this is a tool result for our tool_id
                    if 'toolUseResult' in data:
                        result = data['toolUseResult']
                        if result.get('toolUseId', '').startswith(tool_id[:8]):
                            full_result = result.get('result', '')
                            # Cache for future requests
                            self._cache[cache_key] = full_result
                            return full_result
                    
                    # Also check streaming format
                    if data.get('type') == 'user' and 'content' in data:
                        content = data['content']
                        if isinstance(content, list):
                            for item in content:
                                if item.get('type') == 'tool_result' and item.get('tool_use_id', '').startswith(tool_id[:8]):
                                    full_result = item.get('content', '')
                                    self._cache[cache_key] = full_result
                                    return full_result
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching for tool result: {e}")
            return None
    
    async def get_session_messages(self, session_id: str, start_idx: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get a range of messages from a session.
        
        Args:
            session_id: The session ID
            start_idx: Starting message index
            limit: Maximum number of messages to return
            
        Returns:
            List of message data
        """
        jsonl_path = watcher.get_session_file_path(session_id)
        if not jsonl_path:
            return []
        
        messages = []
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for idx, line in enumerate(f):
                    if idx < start_idx:
                        continue
                    
                    if len(messages) >= limit:
                        break
                    
                    try:
                        data = json.loads(line.strip())
                        messages.append(data)
                    except json.JSONDecodeError:
                        continue
            
            return messages
            
        except Exception as e:
            logger.error(f"Error reading session messages: {e}")
            return []
    
    async def search_in_session(self, session_id: str, query: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """
        Search for messages containing specific text in a session.
        
        Args:
            session_id: The session ID
            query: Search query
            case_sensitive: Whether search is case sensitive
            
        Returns:
            List of matching messages with their indices
        """
        jsonl_path = watcher.get_session_file_path(session_id)
        if not jsonl_path:
            return []
        
        if not case_sensitive:
            query = query.lower()
        
        matches = []
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for idx, line in enumerate(f):
                    try:
                        data = json.loads(line.strip())
                        # Convert to string for searching
                        content_str = json.dumps(data)
                        
                        if not case_sensitive:
                            content_str = content_str.lower()
                        
                        if query in content_str:
                            matches.append({
                                "index": idx,
                                "data": data,
                                "preview": content_str[:200] + "..." if len(content_str) > 200 else content_str
                            })
                    except json.JSONDecodeError:
                        continue
            
            return matches
            
        except Exception as e:
            logger.error(f"Error searching session: {e}")
            return []
    
    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()
        logger.info("JSONL API cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "entries": len(self._cache),
            "size_estimate": sum(len(str(v)) for v in self._cache.values())
        }


# Global instance
jsonl_api = JSONLAPI()