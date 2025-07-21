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
from sync.content_extractor import ContentExtractor
from sync.deduplication_service import deduplication_service
from sync.incremental_sync import incremental_sync_engine

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
    
    async def sync_session_incrementally(self, session: ClaudeSession, jsonl_path: Path) -> int:
        """Use incremental sync engine for efficient updates."""
        try:
            new_message_count = await incremental_sync_engine.sync_new_messages(
                session.session_id, 
                jsonl_path
            )
            return new_message_count
        except Exception as e:
            logger.error(f"Incremental sync failed for {session.session_id}: {e}")
            # Fall back to full sync if incremental fails
            logger.info(f"Falling back to full sync for {session.session_id}")
            incremental_sync_engine.reset_position(session.session_id)
            return await incremental_sync_engine.sync_new_messages(session.session_id, jsonl_path)
    
    async def sync_session_to_database(self, session: ClaudeSession, messages: List[dict]) -> Optional[int]:
        """Sync a Claude Code session to Elia database with proper deduplication."""
        # Use deduplication service for thread-safe sync
        async with deduplication_service.sync_session(session.session_id, session.last_updated) as should_sync:
            if not should_sync:
                logger.debug(f"Skipping sync for session {session.session_id} - deduplication check failed")
                return None
                
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
                    logger.info(f"Successfully synced session {session.session_id} (chat_id: {chat_id})")
                    return chat_id
                    
            except Exception as e:
                logger.error(f"Error syncing session {session.session_id} to database: {e}")
                raise  # Re-raise to trigger deduplication service failure handling
    
    async def _find_existing_chat(self, db_session, session_id: str) -> Optional[ChatDao]:
        """Find existing chat by exact session ID match."""
        from sqlmodel import select
        
        # Use exact session_id field matching for proper deduplication
        statement = select(ChatDao).where(ChatDao.session_id == session_id)
        result = await db_session.exec(statement)
        return result.first()
    
    async def _create_new_chat(self, db_session, session: ClaudeSession, messages: List[dict]) -> int:
        """Create a new chat from Claude Code session."""
        # Generate chat title from first user message or use session metadata
        title = self._generate_chat_title(messages, session)
        
        # Create ChatDao
        chat_dao = ChatDao(
            session_id=session.session_id,
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
        """Add messages to a chat, grouping related tool calls and results."""
        grouped_messages = self._group_related_messages(messages)
        
        for group in grouped_messages:
            try:
                message_dao = self._convert_message_group(group, chat_id)
                if message_dao:
                    db_session.add(message_dao)
            except Exception as e:
                logger.warning(f"Error converting message group: {e}")
                continue
    
    def _convert_jsonl_message(self, jsonl_data: dict, chat_id: int) -> Optional[MessageDao]:
        """Convert a JSONL message to MessageDao."""
        try:
            # Extract message content based on type
            message_type = jsonl_data.get('type', 'unknown')
            
            # Enhanced role assignment logic
            if message_type == 'summary':
                role = 'system'
            elif message_type == 'assistant':
                role = 'assistant'
            elif message_type == 'user':
                role = 'user'
            elif 'toolUseResult' in jsonl_data or 'toolResult' in jsonl_data:
                # Tool results are typically from user context
                role = 'user'
            else:
                # Default to user for unknown types
                role = 'user'
            
            # Detect sidechain messages and metadata
            is_sidechain = jsonl_data.get('isSidechain', False)
            sidechain_metadata = {}
            message_source = "main"
            
            if is_sidechain:
                sidechain_metadata = {
                    'userType': jsonl_data.get('userType'),
                    'parentUuid': jsonl_data.get('parentUuid'),
                    'cwd': jsonl_data.get('cwd'),
                    'gitBranch': jsonl_data.get('gitBranch')
                }
                
                # Determine message source based on content
                message_content = jsonl_data.get('message', {})
                if isinstance(message_content, dict):
                    content_data = message_content.get('content', [])
                    if isinstance(content_data, list):
                        for item in content_data:
                            if isinstance(item, dict) and item.get('type') == 'tool_use':
                                tool_name = item.get('name', '')
                                if tool_name == 'Task':
                                    message_source = "task"
                                elif tool_name == 'TodoWrite':
                                    message_source = "todo"
                                else:
                                    message_source = "tool"
                                break
            
            # Extract content from various JSONL formats
            content = self._extract_content(jsonl_data)
            
            # Enhanced empty message handling
            if not content:
                if role == 'user':
                    # Skip completely empty user messages
                    return None
                elif role == 'assistant':
                    # For assistant messages, check if this might be a tool-only message
                    if 'message' in jsonl_data:
                        msg = jsonl_data['message']
                        if isinstance(msg, dict) and 'content' in msg:
                            if isinstance(msg['content'], list):
                                # Check if it's all tool_use with no text
                                has_tool_use = any(
                                    item.get('type') == 'tool_use' 
                                    for item in msg['content'] 
                                    if isinstance(item, dict)
                                )
                                if has_tool_use:
                                    content = "[Assistant used tools]"
                                else:
                                    return None
                            else:
                                return None
                        else:
                            return None
                    else:
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
                model=self.claude_code_model.id,
                is_sidechain=is_sidechain,
                sidechain_metadata=sidechain_metadata,
                message_source=message_source
            )
            
        except Exception as e:
            logger.error(f"Error converting JSONL message: {e}")
            return None
    
    def _extract_content(self, jsonl_data: dict) -> str:
        """Extract readable content from JSONL message data."""
        content_parts = []
        
        # Handle message content arrays properly
        if 'message' in jsonl_data:
            msg = jsonl_data['message']
            if isinstance(msg, dict) and 'content' in msg:
                content = msg['content']
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    # Handle structured content arrays
                    for item in content:
                        if isinstance(item, dict):
                            item_type = item.get('type', '')
                            if item_type == 'text':
                                text = item.get('text', '')
                                if text:
                                    content_parts.append(text)
                            elif item_type == 'tool_use':
                                # Include tool use information
                                tool_name = item.get('name', 'unknown')
                                tool_id = item.get('id', '')[:8] + '...' if item.get('id') else ''
                                content_parts.append(f"[Used tool: {tool_name} ({tool_id})]")
                            elif item_type == 'tool_result':
                                # Include tool results
                                result_content = item.get('content', '')
                                if isinstance(result_content, str) and result_content:
                                    # Truncate very long results
                                    if len(result_content) > 500:
                                        result_content = result_content[:500] + "..."
                                    content_parts.append(f"[Tool result: {result_content}]")
                                elif isinstance(result_content, dict):
                                    content_parts.append(f"[Tool result: {str(result_content)[:200]}...]")
            elif isinstance(msg, str):
                return msg
        
        # Try direct content field
        if 'content' in jsonl_data and not content_parts:
            return str(jsonl_data['content'])
        
        # Try summary field (for conversation summaries)
        if 'summary' in jsonl_data and not content_parts:
            return str(jsonl_data['summary'])
        
        # Handle toolUseResult field (correct field name)
        if 'toolUseResult' in jsonl_data:
            tool_result = jsonl_data['toolUseResult']
            if isinstance(tool_result, dict):
                result = tool_result.get('result', '')
                if result:
                    # Truncate very long results
                    if len(str(result)) > 500:
                        result = str(result)[:500] + "..."
                    content_parts.append(f"[Tool execution result: {result}]")
                elif 'url' in tool_result:
                    content_parts.append(f"[Tool executed on: {tool_result['url']}]")
            else:
                content_parts.append(f"[Tool result: {str(tool_result)[:200]}...]")
        
        # Handle legacy toolResult field for backward compatibility
        if 'toolResult' in jsonl_data and not content_parts:
            tool_result = jsonl_data['toolResult']
            if isinstance(tool_result, dict):
                result = tool_result.get('output', str(tool_result))
                content_parts.append(f"[Legacy tool result: {str(result)[:200]}...]")
            else:
                content_parts.append(f"[Legacy tool result: {str(tool_result)[:200]}...]")
        
        return '\n'.join(content_parts) if content_parts else ''
    
    def _group_related_messages(self, messages: List[dict]) -> List[List[dict]]:
        """Group related messages (assistant + tool results) for coherent conversation flow."""
        groups = []
        current_group = []
        
        for msg in messages:
            msg_type = msg.get('type', '')
            
            # Start new group for user messages (except tool results)
            if msg_type == 'user' and 'toolUseResult' not in msg and current_group:
                if current_group:
                    groups.append(current_group)
                current_group = [msg]
            
            # Start new group for assistant messages
            elif msg_type == 'assistant':
                if current_group:
                    groups.append(current_group)
                current_group = [msg]
            
            # Add tool results to current group (they follow assistant tool use)
            elif msg_type == 'user' and 'toolUseResult' in msg and current_group:
                current_group.append(msg)
            
            # Handle other message types
            else:
                if not current_group:
                    current_group = [msg]
                else:
                    current_group.append(msg)
        
        # Add final group
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _convert_message_group(self, group: List[dict], chat_id: int) -> Optional[MessageDao]:
        """Convert a group of related messages into a single MessageDao."""
        if not group:
            return None
        
        primary_msg = group[0]
        msg_type = primary_msg.get('type', '')
        
        # Determine role from primary message
        if msg_type == 'summary':
            role = 'system'
        elif msg_type == 'assistant':
            role = 'assistant'
        elif msg_type == 'user':
            role = 'user'
        else:
            role = 'user'
        
        # Build content from all messages in group
        content_parts = []
        
        for msg in group:
            if msg.get('type') == 'assistant':
                content_parts.extend(self._extract_assistant_content(msg))
            elif msg.get('type') == 'user' and 'toolUseResult' in msg:
                content_parts.extend(self._extract_tool_result_content(msg))
            elif msg.get('type') == 'user':
                user_content = self._extract_content(msg)
                if user_content:
                    content_parts.append(user_content)
            elif msg.get('type') == 'summary':
                summary_content = msg.get('summary', '')
                if summary_content:
                    content_parts.append(summary_content)
        
        if not content_parts:
            return None
        
        # Use timestamp from primary message
        timestamp_str = primary_msg.get('timestamp', '')
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            timestamp = datetime.now()
        
        # Extract metadata from primary message
        metadata = {
            'session_id': primary_msg.get('sessionId', ''),
            'working_directory': primary_msg.get('cwd', ''),
            'git_branch': primary_msg.get('gitBranch', ''),
            'claude_version': primary_msg.get('version', ''),
            'message_count': len(group),
            'uuid': primary_msg.get('uuid', ''),
            'parent_uuid': primary_msg.get('parentUuid', ''),
        }
        
        return MessageDao(
            chat_id=chat_id,
            role=role,
            content='\n\n'.join(content_parts),
            timestamp=timestamp,
            meta=metadata,
            model=self.claude_code_model.id
        )
    
    def _extract_assistant_content(self, msg: dict) -> List[str]:
        """Extract content from assistant message, including reasoning and tool calls."""
        # Use shared content extractor for consistency
        content_text = ContentExtractor.extract_message_content({'type': 'assistant', **msg})
        return [content_text] if content_text else []
    
    def _extract_tool_result_content(self, msg: dict) -> List[str]:
        """Extract and format tool result content."""
        # Use shared content extractor for consistency
        results = ContentExtractor.extract_tool_result_content(msg)
        return results
    
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