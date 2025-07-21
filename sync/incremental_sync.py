"""
Incremental sync engine that tracks file positions to sync only new messages.

This replaces the current full-file parsing approach with efficient incremental
updates, dramatically improving performance for active sessions.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from elia_chat.database.async_db import async_session
from elia_chat.database.models import Chat, Message
from sync.content_extractor import ContentExtractor

logger = logging.getLogger(__name__)


class IncrementalSyncEngine:
    """Tracks file positions and syncs only new messages."""
    
    def __init__(self):
        self.sync_positions: Dict[str, int] = {}  # session_id -> file_position
        self.sync_metadata_file = Path.home() / ".local/share/cafedelia/sync_positions.json"
        self._load_sync_positions()
    
    def _load_sync_positions(self) -> None:
        """Load sync positions from persistent storage."""
        try:
            if self.sync_metadata_file.exists():
                with open(self.sync_metadata_file, 'r') as f:
                    self.sync_positions = json.load(f)
                logger.info(f"Loaded sync positions for {len(self.sync_positions)} sessions")
        except Exception as e:
            logger.error(f"Failed to load sync positions: {e}")
            self.sync_positions = {}
    
    def _save_sync_positions(self) -> None:
        """Persist sync positions to disk."""
        try:
            self.sync_metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.sync_metadata_file, 'w') as f:
                json.dump(self.sync_positions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sync positions: {e}")
    
    async def sync_new_messages(self, session_id: str, jsonl_path: Path) -> int:
        """
        Sync only new messages from JSONL file.
        
        Returns:
            Number of new messages synced
        """
        if not jsonl_path.exists():
            logger.warning(f"JSONL file not found: {jsonl_path}")
            return 0
        
        # Get last sync position
        last_position = self.sync_positions.get(session_id, 0)
        current_size = jsonl_path.stat().st_size
        
        # Check if file has new content
        if current_size <= last_position:
            logger.debug(f"No new content for session {session_id}")
            return 0
        
        logger.info(f"Syncing session {session_id}: {current_size - last_position} new bytes")
        
        new_messages = []
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                # Seek to last position
                f.seek(last_position)
                
                # Read new lines
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            message_data = json.loads(line)
                            new_messages.append(message_data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON in {jsonl_path}: {e}")
                            continue
                
                # Update position
                new_position = f.tell()
                self.sync_positions[session_id] = new_position
                self._save_sync_positions()
        
        except Exception as e:
            logger.error(f"Error reading JSONL file: {e}")
            return 0
        
        # Process new messages if any
        if new_messages:
            await self._process_messages(session_id, new_messages)
            logger.info(f"Synced {len(new_messages)} new messages for session {session_id}")
        
        return len(new_messages)
    
    async def _process_messages(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """Process and store new messages in database."""
        async with async_session() as session:
            # Get or create chat
            chat = await self._get_or_create_chat(session, session_id, messages)
            
            # Get existing message count
            existing_count = await session.execute(
                f"SELECT COUNT(*) FROM message WHERE chat_id = {chat.id}"
            )
            message_offset = existing_count.scalar() or 0
            
            # Process each message
            for idx, msg_data in enumerate(messages):
                try:
                    # Extract content using our aggressive content minimizer
                    content = ContentExtractor.extract_message_content(msg_data)
                    
                    if not content:
                        continue
                    
                    # Determine message type
                    msg_type = msg_data.get('type', 'unknown')
                    role = 'assistant' if msg_type == 'assistant' else 'user'
                    
                    # Create message
                    message = Message(
                        chat_id=chat.id,
                        content=content,
                        role=role,
                        created_at=datetime.utcnow(),
                        idx=message_offset + idx
                    )
                    
                    session.add(message)
                    
                except Exception as e:
                    logger.error(f"Failed to process message: {e}")
                    continue
            
            # Update chat metadata
            chat.updated_at = datetime.utcnow()
            await session.commit()
    
    async def _get_or_create_chat(self, session, session_id: str, messages: List[Dict[str, Any]]) -> Chat:
        """Get existing chat or create new one."""
        # Try to find existing chat by session_id
        result = await session.execute(
            f"SELECT * FROM chat WHERE session_id = '{session_id}' LIMIT 1"
        )
        chat = result.scalar_one_or_none()
        
        if not chat:
            # Extract title from first user message
            title = "Untitled Session"
            for msg in messages:
                if msg.get('type') == 'user':
                    content = msg.get('content', '')
                    if isinstance(content, str) and content:
                        title = content[:100]
                        break
                    elif isinstance(content, list):
                        for item in content:
                            if item.get('type') == 'text':
                                text = item.get('text', '').strip()
                                if text:
                                    title = text[:100]
                                    break
            
            # Create new chat
            chat = Chat(
                title=title,
                model="claude-code",
                session_id=session_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(chat)
            await session.flush()
        
        return chat
    
    def reset_position(self, session_id: str) -> None:
        """Reset sync position for a session (useful for full resync)."""
        if session_id in self.sync_positions:
            del self.sync_positions[session_id]
            self._save_sync_positions()
            logger.info(f"Reset sync position for session {session_id}")
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get sync statistics."""
        return {
            "tracked_sessions": len(self.sync_positions),
            "total_bytes_synced": sum(self.sync_positions.values()),
            "positions": self.sync_positions
        }


# Global instance
incremental_sync_engine = IncrementalSyncEngine()