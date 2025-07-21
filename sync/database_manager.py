"""
Database Manager for WTE Pipeline Integration

Provides a unified interface for database operations used by WTE pipelines.
Bridges existing cafedelia database code with new WTE architecture.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from .jsonl_transformer import JSONLTransformer
from .deduplication_service import DeduplicationService
from elia_chat.database.chat_dao import ChatDao
from elia_chat.models import ChatData

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Unified database manager for WTE pipelines"""
    
    def __init__(self):
        self.chat_dao = ChatDao()
        self.jsonl_transformer = JSONLTransformer()
        self.dedup_service = DeduplicationService()
        
    async def register_session(self, 
                             session_id: str, 
                             project_path: str, 
                             jsonl_path: str, 
                             metadata: Dict[str, Any]) -> bool:
        """
        Register a new Claude Code session in the database
        
        This is the core session registration functionality that was failing.
        Ensures session IDs are properly captured and stored.
        """
        try:
            logger.info(f"Registering session {session_id} from {jsonl_path}")
            
            # Check if session already exists
            existing_chat = await self.chat_dao.get_chat_by_session_id(session_id)
            if existing_chat:
                logger.info(f"Session {session_id} already registered")
                return True
            
            # Create ChatData from session metadata
            chat_data = ChatData(
                title=f"{metadata.get('project_name', 'Unknown')}-{metadata.get('conversation_turns', 0)}turns",
                session_id=session_id,
                model_name="claude-code-session",
                created_at=metadata.get('created_at', datetime.now()),
                updated_at=metadata.get('last_activity', datetime.now())
            )
            
            # Insert into database
            chat_id = await self.chat_dao.insert_chat(chat_data)
            
            logger.info(f"Successfully registered session {session_id} with chat_id {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register session {session_id}: {e}")
            return False
    
    async def sync_jsonl_to_database(self, 
                                   session_id: str, 
                                   jsonl_path: str) -> bool:
        """
        Sync JSONL file content to database
        
        Uses existing transformer logic with deduplication protection.
        """
        try:
            logger.info(f"Syncing JSONL {jsonl_path} to database")
            
            # Use deduplication service to prevent race conditions
            async with self.dedup_service.sync_session(session_id, Path(jsonl_path).stat().st_mtime) as should_sync:
                if not should_sync:
                    logger.info(f"Session {session_id} already synced, skipping")
                    return True
                
                # Perform the actual sync using existing transformer
                success = await self.jsonl_transformer.transform_and_store_session(jsonl_path)
                
                if success:
                    logger.info(f"Successfully synced session {session_id}")
                else:
                    logger.error(f"Failed to sync session {session_id}")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to sync JSONL {jsonl_path}: {e}")
            return False
    
    async def get_session_info(self, session_id: str) -> Optional[ChatData]:
        """Get session information from database"""
        try:
            return await self.chat_dao.get_chat_by_session_id(session_id)
        except Exception as e:
            logger.error(f"Failed to get session info for {session_id}: {e}")
            return None
    
    async def list_sessions(self, limit: int = 100) -> List[ChatData]:
        """List recent sessions"""
        try:
            return await self.chat_dao.get_recent_chats(limit)
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    async def update_session_activity(self, session_id: str) -> bool:
        """Update session last activity timestamp"""
        try:
            chat = await self.chat_dao.get_chat_by_session_id(session_id)
            if chat:
                chat.updated_at = datetime.now()
                await self.chat_dao.update_chat(chat)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update session activity for {session_id}: {e}")
            return False
    
    async def cleanup_orphaned_sessions(self) -> int:
        """Clean up sessions that no longer have corresponding JSONL files"""
        try:
            sessions = await self.list_sessions()
            cleaned_count = 0
            
            for session in sessions:
                if session.session_id:
                    # Check if JSONL file still exists
                    # This would need to integrate with JSONLWatcher discovery
                    # For now, just log the check
                    logger.debug(f"Checking JSONL existence for session {session.session_id}")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned sessions: {e}")
            return 0
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for monitoring"""
        try:
            sessions = await self.list_sessions()
            
            stats = {
                'total_sessions': len(sessions),
                'sessions_with_session_id': len([s for s in sessions if s.session_id]),
                'recent_activity': len([s for s in sessions if s.updated_at > datetime.now().replace(hour=0, minute=0, second=0)]),
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}
    
    async def health_check(self) -> bool:
        """Perform database health check"""
        try:
            # Try a simple database operation
            await self.list_sessions(limit=1)
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False