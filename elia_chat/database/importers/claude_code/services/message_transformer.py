"""Message content transformation and normalization for Claude Code sessions"""

from datetime import datetime
from typing import Any, Dict


class MessageTransformer:
    """Handles transformation of Claude Code message data into normalized format"""
    
    @staticmethod
    def extract_text_content(message_content: Any) -> str:
        """Handle both string and structured content formats from Claude Code JSONL"""
        if isinstance(message_content, str):
            return message_content
        
        if isinstance(message_content, list):
            text_parts = []
            for item in message_content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "tool_use":
                        tool_name = item.get("name", "Unknown")
                        text_parts.append(f"🔧 **Used {tool_name}**")
                    elif item.get("type") == "tool_result":
                        # Handle tool results
                        content = item.get("content", "")
                        if isinstance(content, str) and len(content) > 500:
                            content = content[:500] + "... [truncated]"
                        text_parts.append(f"📋 Tool result: {content}")
            return "\n".join(text_parts)
        
        return str(message_content)

    @staticmethod
    def parse_iso_to_datetime(iso_timestamp: str) -> datetime:
        """Convert ISO timestamp to datetime object"""
        return datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))

    @staticmethod
    def extract_message_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize message data from Claude Code JSONL entry"""
        message_data = data.get("message", {})
        role = message_data.get("role", data.get("type", "user"))
        content = MessageTransformer.extract_text_content(message_data.get("content", ""))
        
        # Parse timestamp
        timestamp_str = data.get("timestamp", datetime.now().isoformat())
        timestamp = MessageTransformer.parse_iso_to_datetime(timestamp_str)
        
        # Extract model info for assistant messages
        model = None
        if role == "assistant":
            model = message_data.get("model", "claude-sonnet-4")
        
        # Build metadata
        meta = {
            "uuid": data.get("uuid"),
            "sessionId": data.get("sessionId"),
            "cwd": data.get("cwd"),
            "gitBranch": data.get("gitBranch"),
            "version": data.get("version"),
            "usage": message_data.get("usage", {}),
            "requestId": data.get("requestId"),
        }
        
        return {
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "model": model,
            "parent_uuid": data.get("parentUuid"),
            "uuid": data.get("uuid"),
            "meta": meta,
        }