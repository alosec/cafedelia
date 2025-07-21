"""
Atomic database operations for immediate Claude Code JSON storage.

Handles immediate persistence of parsed messages with deduplication,
proper error handling, and transactional safety for stream coordination.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from elia_chat.database.database import get_session
from elia_chat.database.models import MessageDao, ChatDao
from elia_chat.models import ChatMessage
from .message_parser import ParsedMessage

logger = logging.getLogger(__name__)


class DatabaseRegistrar:
    """Atomic database operations for immediate message persistence."""
    
    def __init__(self):
        self._registration_lock = asyncio.Lock()
        self._chat_cache: Dict[str, ChatDao] = {}
    
    async def register_message(self, parsed_message: ParsedMessage) -> Optional[MessageDao]:
        """
        Atomically register a parsed message in the database.
        
        Args:
            parsed_message: Parsed message ready for database storage
            
        Returns:
            MessageDao if successfully registered, None if failed
        """
        async with self._registration_lock:
            try:
                async with get_session() as session:
                    # Ensure chat exists for this session
                    chat_dao = await self._ensure_chat_exists(session, parsed_message)
                    if not chat_dao:
                        logger.error(f"Failed to ensure chat exists for session {parsed_message.session_id}")
                        return None
                    
                    # Check for duplicate messages
                    existing_message = await self._check_duplicate(session, parsed_message, chat_dao.id)
                    if existing_message:
                        logger.debug(f"Skipping duplicate message for session {parsed_message.session_id}")
                        return existing_message
                    
                    # Create new message record
                    message_dao = await self._create_message_record(session, parsed_message, chat_dao.id)
                    if message_dao:
                        await session.commit()
                        logger.debug(f"Registered message {message_dao.id} for session {parsed_message.session_id}")
                    else:
                        await session.rollback()
                        logger.error(f"Failed to create message record for session {parsed_message.session_id}")
                    
                    return message_dao
                    
            except Exception as e:
                logger.error(f"Database registration failed for session {parsed_message.session_id}: {e}")
                return None
    
    async def _ensure_chat_exists(self, session: AsyncSession, parsed_message: ParsedMessage) -> Optional[ChatDao]:
        """Ensure a chat record exists for the session, creating if necessary."""
        session_id = parsed_message.session_id
        
        # Check cache first
        if session_id in self._chat_cache:
            return self._chat_cache[session_id]
        
        # Query database for existing chat
        result = await session.execute(
            select(ChatDao).where(ChatDao.session_id == session_id)
        )
        chat_dao = result.scalar_one_or_none()
        
        if chat_dao:
            self._chat_cache[session_id] = chat_dao
            return chat_dao
        
        # Create new chat record
        try:
            chat_dao = ChatDao(
                title=self._generate_chat_title(parsed_message),
                session_id=session_id,
                model="claude-code",  # Default for Claude Code sessions
                started_at=parsed_message.timestamp
            )
            
            session.add(chat_dao)
            await session.flush()  # Get the ID
            
            self._chat_cache[session_id] = chat_dao
            logger.info(f"Created new chat {chat_dao.id} for session {session_id}")
            return chat_dao
            
        except Exception as e:
            logger.error(f"Failed to create chat for session {session_id}: {e}")
            return None
    
    def _generate_chat_title(self, parsed_message: ParsedMessage) -> str:
        """Generate a title for a new chat based on the first message."""
        # Use first meaningful content as title
        content = parsed_message.content.strip()
        if not content or parsed_message.message_type == "system":
            return f"Claude Code Session ({parsed_message.session_id[:8]})"
        
        # Truncate content for title
        title = content.replace('\n', ' ').strip()
        if len(title) > 100:
            title = title[:97] + "..."
        
        return title or f"Claude Code Session ({parsed_message.session_id[:8]})"
    
    async def _check_duplicate(self, session: AsyncSession, parsed_message: ParsedMessage, chat_id: int) -> Optional[MessageDao]:
        """Check if this message already exists in the database."""
        # For system/result messages, check by type and timestamp
        if parsed_message.message_type in ["system", "result"]:
            result = await session.execute(
                select(MessageDao).where(
                    and_(
                        MessageDao.chat_id == chat_id,
                        MessageDao.message_type == parsed_message.message_type,
                        MessageDao.timestamp == parsed_message.timestamp
                    )
                )
            )
            return result.scalar_one_or_none()
        
        # For other messages, check by content hash (sequence check disabled for SQLite compatibility)
        # Note: JSON queries with message_metadata['sequence'] don't work reliably with SQLite TEXT storage
        
        # Check by content similarity as fallback
        content_hash = hash(parsed_message.content)
        result = await session.execute(
            select(MessageDao).where(
                and_(
                    MessageDao.chat_id == chat_id,
                    MessageDao.content == parsed_message.content,
                    MessageDao.message_type == parsed_message.message_type
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _create_message_record(self, session: AsyncSession, parsed_message: ParsedMessage, chat_id: int) -> Optional[MessageDao]:
        """Create a new message database record."""
        try:
            # Convert ParsedMessage to database format
            message_dao = MessageDao(
                chat_id=chat_id,
                message_type=parsed_message.message_type,
                content=parsed_message.content,
                raw_json=parsed_message.raw_json,
                message_metadata=parsed_message.message_metadata,
                timestamp=parsed_message.timestamp,
                is_sidechain=parsed_message.is_sidechain,
                sidechain_metadata=parsed_message.sidechain_metadata,
                message_source=parsed_message.message_source,
                role=parsed_message.message_type,  # Map message_type to role for compatibility
                model=parsed_message.message_metadata.get('model', 'claude-code')
            )
            
            session.add(message_dao)
            await session.flush()  # Get the ID
            
            # Update chat's last message timestamp
            await self._update_chat_timestamp(session, chat_id, parsed_message.timestamp)
            
            return message_dao
            
        except Exception as e:
            logger.error(f"Failed to create message record: {e}")
            return None
    
    async def _update_chat_timestamp(self, session: AsyncSession, chat_id: int, timestamp: datetime) -> None:
        """Update the chat's timestamp (no-op since ChatDao doesn't have last_message_at field)."""
        # Note: ChatDao doesn't have a last_message_at field, so this is currently a no-op
        # The started_at field is set during creation and doesn't need updating
        pass
    
    async def get_message_count(self, session_id: str) -> int:
        """Get the current message count for a session."""
        try:
            async with get_session() as session:
                # Get chat ID
                result = await session.execute(
                    select(ChatDao.id).where(ChatDao.session_id == session_id)
                )
                chat_id = result.scalar_one_or_none()
                if not chat_id:
                    return 0
                
                # Count messages
                result = await session.execute(
                    select(MessageDao.id).where(MessageDao.chat_id == chat_id)
                )
                return len(result.all())
                
        except Exception as e:
            logger.error(f"Failed to get message count for session {session_id}: {e}")
            return 0
    
    async def get_latest_message(self, session_id: str) -> Optional[MessageDao]:
        """Get the latest message for a session."""
        try:
            async with get_session() as session:
                # Get chat ID
                result = await session.execute(
                    select(ChatDao.id).where(ChatDao.session_id == session_id)
                )
                chat_id = result.scalar_one_or_none()
                if not chat_id:
                    return None
                
                # Get latest message
                result = await session.execute(
                    select(MessageDao)
                    .where(MessageDao.chat_id == chat_id)
                    .order_by(MessageDao.timestamp.desc())
                    .limit(1)
                )
                return result.scalar_one_or_none()
                
        except Exception as e:
            logger.error(f"Failed to get latest message for session {session_id}: {e}")
            return None
    
    def clear_cache(self) -> None:
        """Clear the chat cache (useful for testing or memory management)."""
        self._chat_cache.clear()
        logger.debug("Database registrar cache cleared")


# Global instance for use across the application
database_registrar = DatabaseRegistrar()