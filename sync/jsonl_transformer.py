"""
JSONL to Elia database transformer.

Converts Claude Code JSONL data to Elia's SQLite schema for historical browsing.
This provides the "Browse Mode" data for Cafedelia's dual-mode architecture.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from elia_chat.database.models import ChatDao, MessageDao
from elia_chat.database.database import get_session
from elia_chat.models import ChatMessage, get_model
from sync.jsonl_watcher import ClaudeSession

logger = logging.getLogger(__name__)


class JSONLTransformer:
    """Transforms Claude Code JSONL data to Elia database format."""
    
    def __init__(self):
        self.claude_code_model = None
        self._initialize_claude_model()
    
    def _initialize_claude_model(self):
        """Initialize Claude Code model configuration."""
        # Create a model representation for Claude Code sessions
        try:
            self.claude_code_model = get_model("claude-code")
        except:
            # Fallback to a default model configuration
            from elia_chat.config import EliaChatModel
            self.claude_code_model = EliaChatModel(
                id="claude-code",
                name="Claude Code",
                display_name="Claude Code Session",
                provider="Claude Code",
                provider_type="cli"
            )
    
    async def sync_session_to_database(self, session: ClaudeSession, messages: List[dict]) -> Optional[int]:
        """Sync a Claude Code session to Elia database."""
        try:
            async with get_session() as db_session:
                # Check if chat already exists
                existing_chat = await self._find_existing_chat(db_session, session.session_id)
                
                if existing_chat:
                    # Update existing chat
                    chat_id = await self._update_existing_chat(db_session, existing_chat, session, messages)
                else:
                    # Create new chat
                    chat_id = await self._create_new_chat(db_session, session, messages)
                
                await db_session.commit()
                return chat_id
                
        except Exception as e:
            logger.error(f"Error syncing session {session.session_id} to database: {e}")
            return None
    
    async def _find_existing_chat(self, db_session, session_id: str) -> Optional[ChatDao]:
        """Find existing chat by session ID (stored in title or metadata)."""
        from sqlmodel import select
        
        # Look for chats with matching session ID in title
        statement = select(ChatDao).where(ChatDao.title.contains(session_id))
        result = await db_session.exec(statement)
        return result.first()
    
    async def _create_new_chat(self, db_session, session: ClaudeSession, messages: List[dict]) -> int:
        """Create a new chat from Claude Code session."""
        # Generate chat title from first user message or use session metadata
        title = self._generate_chat_title(messages, session)
        
        # Create ChatDao
        chat_dao = ChatDao(
            model=self.claude_code_model.id,
            title=title,
            started_at=datetime.fromtimestamp(session.last_updated)
        )
        
        db_session.add(chat_dao)
        await db_session.flush()  # Get the ID
        
        # Add messages
        await self._add_messages_to_chat(db_session, chat_dao.id, messages)
        
        return chat_dao.id
    
    async def _update_existing_chat(self, db_session, chat_dao: ChatDao, session: ClaudeSession, messages: List[dict]) -> int:
        """Update existing chat with new messages."""
        # Count existing messages
        from sqlmodel import select, func
        statement = select(func.count(MessageDao.id)).where(MessageDao.chat_id == chat_dao.id)
        result = await db_session.exec(statement)
        existing_count = result.one()
        
        # Add only new messages
        if len(messages) > existing_count:
            new_messages = messages[existing_count:]
            await self._add_messages_to_chat(db_session, chat_dao.id, new_messages)
        
        return chat_dao.id
    
    async def _add_messages_to_chat(self, db_session, chat_id: int, messages: List[dict]) -> None:
        """Add messages to a chat."""
        for msg_data in messages:
            try:
                message_dao = self._convert_jsonl_message(msg_data, chat_id)
                if message_dao:
                    db_session.add(message_dao)
            except Exception as e:
                logger.warning(f"Error converting message: {e}")
                continue
    
    def _convert_jsonl_message(self, jsonl_data: dict, chat_id: int) -> Optional[MessageDao]:
        """Convert a JSONL message to MessageDao."""
        try:
            # Extract message content based on type
            message_type = jsonl_data.get('type', 'unknown')
            role = 'assistant' if message_type == 'assistant' else 'user'
            
            # Extract content from various JSONL formats
            content = self._extract_content(jsonl_data)
            if not content and role == 'user':
                # Skip empty user messages
                return None
            
            # Create timestamp
            timestamp_str = jsonl_data.get('timestamp', '')
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except:
                timestamp = datetime.now()
            
            # Extract metadata
            metadata = {
                'session_id': jsonl_data.get('sessionId', ''),
                'working_directory': jsonl_data.get('cwd', ''),
                'git_branch': jsonl_data.get('gitBranch', ''),
                'claude_version': jsonl_data.get('version', ''),
                'cost': jsonl_data.get('cost', 0),
            }
            
            # Handle tool results and other metadata
            if 'toolResult' in jsonl_data:
                metadata['tool_result'] = jsonl_data['toolResult']
            
            return MessageDao(
                chat_id=chat_id,
                role=role,
                content=content or '',
                timestamp=timestamp,
                meta=metadata,
                model=self.claude_code_model.id
            )
            
        except Exception as e:
            logger.error(f"Error converting JSONL message: {e}")
            return None
    
    def _extract_content(self, jsonl_data: dict) -> str:
        """Extract readable content from JSONL message data."""
        # Try various content fields
        if 'message' in jsonl_data:
            msg = jsonl_data['message']
            if isinstance(msg, dict):
                # Standard message format
                if 'content' in msg:
                    content = msg['content']
                    if isinstance(content, str):
                        return content
                    elif isinstance(content, list):
                        # Handle content arrays (text + attachments)
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                text_parts.append(item.get('text', ''))
                        return '\n'.join(text_parts)
            elif isinstance(msg, str):
                return msg
        
        # Try direct content field
        if 'content' in jsonl_data:
            return str(jsonl_data['content'])
        
        # Try summary field (for conversation summaries)
        if 'summary' in jsonl_data:
            return str(jsonl_data['summary'])
        
        # Handle tool results
        if 'toolResult' in jsonl_data:
            tool_result = jsonl_data['toolResult']
            if isinstance(tool_result, dict):
                return f"Tool Result: {tool_result.get('output', str(tool_result))}"
            return f"Tool Result: {tool_result}"
        
        return ''
    
    def _generate_chat_title(self, messages: List[dict], session: ClaudeSession) -> str:
        """Generate a readable title for the chat."""
        # Try to find a conversation summary
        for msg in messages:
            if msg.get('type') == 'summary' or 'summary' in msg:
                summary = msg.get('summary', '')
                if summary and len(summary) < 100:
                    return summary
        
        # Try to use first meaningful user message
        for msg in messages:
            if msg.get('type') == 'user':
                content = self._extract_content(msg)
                if content and len(content.strip()) > 5:
                    # Truncate to reasonable length
                    title = content.strip()[:80]
                    if len(content) > 80:
                        title += "..."
                    return title
        
        # Fallback to project and timestamp
        project_name = session.project_name.split('/')[-1]  # Get last part of path
        return f"{project_name} - {session.session_id[:8]}"
    
    async def sync_all_sessions(self, sessions: List[ClaudeSession]) -> int:
        """Sync all sessions to database and return count of synced sessions."""
        synced_count = 0
        
        for session in sessions:
            try:
                # Get messages for this session
                from sync.jsonl_watcher import watcher
                messages = watcher.get_session_messages(session.session_id)
                
                if messages:
                    chat_id = await self.sync_session_to_database(session, messages)
                    if chat_id:
                        synced_count += 1
                        logger.info(f"Synced session {session.session_id} to chat {chat_id}")
                    
            except Exception as e:
                logger.error(f"Error syncing session {session.session_id}: {e}")
                continue
        
        return synced_count


# Global transformer instance
transformer = JSONLTransformer()