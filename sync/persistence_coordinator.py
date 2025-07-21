"""
Robust database operations with validation and coordination.

Provides validated database persistence that works seamlessly with the session
state manager and parity validator to ensure data integrity and consistency.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from elia_chat.database.database import get_session
from elia_chat.database.models import MessageDao, ChatDao
from sqlalchemy import select, and_
from .message_parser import ParsedMessage

logger = logging.getLogger(__name__)


class PersistenceCoordinator:
    """
    Coordinates robust database operations with validation.
    
    Features:
    - Validated message persistence with error recovery
    - Chat management with session coordination  
    - Transactional safety with rollback on failure
    - Integration with session state management
    - Automatic cleanup of orphaned records
    """
    
    def __init__(self):
        self.persistence_lock = asyncio.Lock()
        self.chat_cache: Dict[str, ChatDao] = {}
        
        # Persistence statistics
        self.stats = {
            'messages_persisted': 0,
            'chats_created': 0,
            'persistence_errors': 0,
            'last_persistence': None
        }
    
    async def persist_message(
        self, 
        parsed_message: ParsedMessage, 
        chat_dao: Optional[ChatDao],
        db_session: Optional[AsyncSession] = None
    ) -> Optional[MessageDao]:
        """
        Persist a parsed message to the database with full validation.
        
        Args:
            parsed_message: Parsed message ready for database storage
            chat_dao: Associated chat (will be created if None)
            db_session: Optional existing database session
            
        Returns:
            MessageDao if successful, None if failed
        """
        async with self.persistence_lock:
            try:
                # Use provided session or create new one
                if db_session:
                    return await self._persist_message_in_session(
                        db_session, parsed_message, chat_dao
                    )
                else:
                    async with get_session() as session:
                        message_dao = await self._persist_message_in_session(
                            session, parsed_message, chat_dao
                        )
                        if message_dao:
                            await session.commit()
                        return message_dao
                        
            except Exception as e:
                logger.error(f"Persistence error for session {parsed_message.session_id}: {e}")
                self.stats['persistence_errors'] += 1
                return None
    
    async def _persist_message_in_session(
        self,
        db_session: AsyncSession,
        parsed_message: ParsedMessage,
        chat_dao: Optional[ChatDao]
    ) -> Optional[MessageDao]:
        """Internal method to persist message within a database session."""
        
        # Ensure chat exists
        if not chat_dao:
            chat_dao = await self._ensure_chat_exists(db_session, parsed_message)
            if not chat_dao:
                logger.error(f"Failed to ensure chat exists for session {parsed_message.session_id}")
                return None
        
        # Check for duplicates
        existing_message = await self._check_duplicate_message(
            db_session, parsed_message, chat_dao.id
        )
        if existing_message:
            logger.debug(f"Skipping duplicate message for session {parsed_message.session_id}")
            return existing_message
        
        # Create new message record with validation
        message_dao = await self._create_validated_message(
            db_session, parsed_message, chat_dao.id
        )
        
        if message_dao:
            self.stats['messages_persisted'] += 1
            self.stats['last_persistence'] = datetime.now()
            logger.debug(f"Persisted message {message_dao.id} for session {parsed_message.session_id}")
        else:
            logger.error(f"Failed to create message record for session {parsed_message.session_id}")
        
        return message_dao
    
    async def _ensure_chat_exists(
        self, 
        db_session: AsyncSession, 
        parsed_message: ParsedMessage
    ) -> Optional[ChatDao]:
        """Ensure a chat record exists for the session."""
        session_id = parsed_message.session_id
        
        # Check cache first
        if session_id in self.chat_cache:
            return self.chat_cache[session_id]
        
        # Query database for existing chat
        result = await db_session.execute(
            select(ChatDao).where(ChatDao.session_id == session_id)
        )
        chat_dao = result.scalar_one_or_none()
        
        if chat_dao:
            self.chat_cache[session_id] = chat_dao
            return chat_dao
        
        # Create new chat record
        try:
            chat_dao = ChatDao(
                title=self._generate_chat_title(parsed_message),
                session_id=session_id,
                model="claude-code",
                started_at=parsed_message.timestamp
            )
            
            db_session.add(chat_dao)
            await db_session.flush()  # Get the ID
            
            self.chat_cache[session_id] = chat_dao
            self.stats['chats_created'] += 1
            logger.info(f"Created new chat {chat_dao.id} for session {session_id}")
            return chat_dao
            
        except Exception as e:
            logger.error(f"Failed to create chat for session {session_id}: {e}")
            return None
    
    def _generate_chat_title(self, parsed_message: ParsedMessage) -> str:
        """Generate a descriptive title for a new chat."""
        content = parsed_message.content.strip()
        
        # For system messages or empty content, use session ID
        if not content or parsed_message.message_type == "system":
            return f"Claude Code Session ({parsed_message.session_id[:8]})"
        
        # Use first meaningful content as title
        title = content.replace('\n', ' ').strip()
        if len(title) > 100:
            title = title[:97] + "..."
        
        return title or f"Claude Code Session ({parsed_message.session_id[:8]})"
    
    async def _check_duplicate_message(
        self,
        db_session: AsyncSession,
        parsed_message: ParsedMessage,
        chat_id: int
    ) -> Optional[MessageDao]:
        """Check if this message already exists in the database."""
        
        # For system/result messages, check by type and timestamp
        if parsed_message.message_type in ["system", "result"]:
            result = await db_session.execute(
                select(MessageDao).where(
                    and_(
                        MessageDao.chat_id == chat_id,
                        MessageDao.message_type == parsed_message.message_type,
                        MessageDao.timestamp == parsed_message.timestamp
                    )
                )
            )
            return result.scalar_one_or_none()
        
        # For other messages, check by content and type
        result = await db_session.execute(
            select(MessageDao).where(
                and_(
                    MessageDao.chat_id == chat_id,
                    MessageDao.content == parsed_message.content,
                    MessageDao.message_type == parsed_message.message_type
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _create_validated_message(
        self,
        db_session: AsyncSession,
        parsed_message: ParsedMessage,
        chat_id: int
    ) -> Optional[MessageDao]:
        """Create a new message record with validation."""
        try:
            # Validate required fields
            if not parsed_message.content and parsed_message.message_type not in ["system"]:
                logger.warning(f"Message has empty content: {parsed_message.message_type}")
            
            if not parsed_message.session_id:
                logger.error("Message missing session_id")
                return None
            
            # Create message record
            message_dao = MessageDao(
                chat_id=chat_id,
                message_type=parsed_message.message_type,
                content=parsed_message.content or "",
                raw_json=parsed_message.raw_json,
                message_metadata=parsed_message.message_metadata or {},
                timestamp=parsed_message.timestamp,
                is_sidechain=parsed_message.is_sidechain,
                sidechain_metadata=parsed_message.sidechain_metadata or {},
                message_source=parsed_message.message_source,
                role=parsed_message.message_type,  # Map message_type to role for compatibility
                model=parsed_message.message_metadata.get('model', 'claude-code')
            )
            
            # Serialize datetime objects in message_metadata
            try:
                import json
                from datetime import datetime
                
                def serialize_datetime(obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    elif isinstance(obj, dict):
                        return {k: serialize_datetime(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [serialize_datetime(item) for item in obj]
                    return obj
                
                # Serialize all datetime objects
                message_dao.message_metadata = serialize_datetime(message_dao.message_metadata)
                message_dao.sidechain_metadata = serialize_datetime(message_dao.sidechain_metadata)
                
                # Validate final serialization
                json.dumps(message_dao.message_metadata)
                json.dumps(message_dao.sidechain_metadata)
                
            except (TypeError, ValueError) as e:
                logger.warning(f"Message metadata serialization failed, clearing: {e}")
                message_dao.message_metadata = {}
                message_dao.sidechain_metadata = {}
            
            db_session.add(message_dao)
            await db_session.flush()  # Get the ID
            
            return message_dao
            
        except Exception as e:
            logger.error(f"Failed to create validated message record: {e}")
            return None
    
    async def get_chat_for_session(self, session_id: str) -> Optional[ChatDao]:
        """Get the chat record for a session."""
        # Check cache first
        if session_id in self.chat_cache:
            return self.chat_cache[session_id]
        
        try:
            async with get_session() as db_session:
                result = await db_session.execute(
                    select(ChatDao).where(ChatDao.session_id == session_id)
                )
                chat_dao = result.scalar_one_or_none()
                
                if chat_dao:
                    self.chat_cache[session_id] = chat_dao
                
                return chat_dao
                
        except Exception as e:
            logger.error(f"Error getting chat for session {session_id}: {e}")
            return None
    
    async def get_message_count_for_session(self, session_id: str) -> int:
        """Get the current message count for a session."""
        try:
            async with get_session() as db_session:
                # Get chat ID
                result = await db_session.execute(
                    select(ChatDao.id).where(ChatDao.session_id == session_id)
                )
                chat_id = result.scalar_one_or_none()
                
                if not chat_id:
                    return 0
                
                # Count messages
                result = await db_session.execute(
                    select(MessageDao.id).where(MessageDao.chat_id == chat_id)
                )
                return len(result.all())
                
        except Exception as e:
            logger.error(f"Error getting message count for session {session_id}: {e}")
            return 0
    
    async def cleanup_orphaned_messages(self) -> int:
        """Remove messages that reference non-existent chats."""
        try:
            async with get_session() as db_session:
                # Find messages with invalid chat_id references
                result = await db_session.execute("""
                    DELETE FROM message 
                    WHERE chat_id NOT IN (SELECT id FROM chat)
                """)
                
                deleted_count = result.rowcount
                await db_session.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} orphaned messages")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning up orphaned messages: {e}")
            return 0
    
    async def validate_database_integrity(self) -> Dict[str, Any]:
        """
        Perform comprehensive database integrity validation.
        
        Returns:
            Dictionary with validation results and recommendations
        """
        results = {
            'total_chats': 0,
            'total_messages': 0,
            'orphaned_messages': 0,
            'chats_without_messages': 0,
            'empty_session_ids': 0,
            'issues': []
        }
        
        try:
            async with get_session() as db_session:
                # Count totals
                result = await db_session.execute(select(ChatDao.id))
                results['total_chats'] = len(result.all())
                
                result = await db_session.execute(select(MessageDao.id))
                results['total_messages'] = len(result.all())
                
                # Find orphaned messages
                result = await db_session.execute("""
                    SELECT COUNT(*) FROM message 
                    WHERE chat_id NOT IN (SELECT id FROM chat)
                """)
                results['orphaned_messages'] = result.scalar()
                
                # Find chats without messages
                result = await db_session.execute("""
                    SELECT COUNT(*) FROM chat c
                    WHERE NOT EXISTS (SELECT 1 FROM message m WHERE m.chat_id = c.id)
                """)
                results['chats_without_messages'] = result.scalar()
                
                # Find empty session IDs
                result = await db_session.execute(
                    select(ChatDao.id).where(
                        (ChatDao.session_id == None) | (ChatDao.session_id == "")
                    )
                )
                results['empty_session_ids'] = len(result.all())
                
                # Generate recommendations
                if results['orphaned_messages'] > 0:
                    results['issues'].append(f"Found {results['orphaned_messages']} orphaned messages")
                
                if results['chats_without_messages'] > 0:
                    results['issues'].append(f"Found {results['chats_without_messages']} chats without messages")
                
                if results['empty_session_ids'] > 0:
                    results['issues'].append(f"Found {results['empty_session_ids']} chats with empty session IDs")
                
        except Exception as e:
            logger.error(f"Error validating database integrity: {e}")
            results['issues'].append(f"Validation error: {str(e)}")
        
        return results
    
    def get_persistence_stats(self) -> Dict[str, Any]:
        """Get persistence statistics."""
        stats = self.stats.copy()
        if stats['last_persistence']:
            stats['last_persistence'] = stats['last_persistence'].isoformat()
        stats['cached_chats'] = len(self.chat_cache)
        return stats
    
    def clear_cache(self):
        """Clear the chat cache."""
        self.chat_cache.clear()
        logger.debug("Persistence coordinator cache cleared")


# Global instance for use across the application
persistence_coordinator = PersistenceCoordinator()