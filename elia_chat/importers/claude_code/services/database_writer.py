"""Database operations for Claude Code session imports"""

from datetime import datetime
from typing import Dict, Any

from elia_chat.database.database import get_session
from elia_chat.database.models import MessageDao, ChatDao


class DatabaseWriter:
    """Handles database persistence for Claude Code sessions"""
    
    def __init__(self):
        self.message_map: Dict[str, MessageDao] = {}  # uuid -> MessageDao for threading
    
    async def create_chat(self, session_id: str, title: str, first_timestamp: datetime | None = None) -> ChatDao:
        """Create a new chat record in the database"""
        async with get_session() as session:
            chat = ChatDao(
                title=title or f"Claude Code Session ({session_id[:8]})",
                model="claude-sonnet-4",  # Default model
                started_at=first_timestamp or datetime.now(),
            )
            session.add(chat)
            await session.commit()
            return chat
    
    async def create_message(
        self, 
        chat: ChatDao, 
        message_data: Dict[str, Any]
    ) -> MessageDao:
        """Create a message record and handle threading"""
        async with get_session() as session:
            # Find parent message if exists
            parent_id = None
            parent_uuid = message_data.get("parent_uuid")
            if parent_uuid and parent_uuid in self.message_map:
                parent_id = self.message_map[parent_uuid].id
            
            # Update chat model if we find a specific one
            if message_data.get("model") and "claude" in message_data["model"].lower():
                chat.model = message_data["model"]
            
            # Create message
            message = MessageDao(
                chat_id=chat.id,
                role=message_data["role"],
                content=message_data["content"],
                timestamp=message_data["timestamp"],
                model=message_data.get("model"),
                parent_id=parent_id,
                meta=message_data["meta"],
            )
            
            session.add(message)
            await session.commit()
            
            # Store for threading
            if message_data.get("uuid"):
                self.message_map[message_data["uuid"]] = message
            
            return message
    
    async def finalize_session(self) -> None:
        """Perform final database operations"""
        async with get_session() as session:
            await session.commit()
    
    def clear_message_map(self) -> None:
        """Clear the message mapping for a new session"""
        self.message_map.clear()